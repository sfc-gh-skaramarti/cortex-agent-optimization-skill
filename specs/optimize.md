---
section: "4.3"
title: "optimize/SKILL.md — Run an Optimization Iteration"
parent_spec: "../cortex-agent-eval-optimizer-spec.md"
---

# Run an Optimization Iteration Contract

**Frontmatter:**

```yaml
---
name: cortex-agent-eval-optimizer-iterate
description: "Run a single optimization iteration: analyze DEV failures, edit instructions, build/deploy, eval."
parent_skill: cortex-agent-eval-optimizer
---
```

**Workflow (9 steps):**

## Step 1: Read Context
- Load `<WORKSPACE_ROOT>/<AGENT_DIR>/optimization_log.md` — understand current scores, previous iterations, what's been tried
- Load `<WORKSPACE_ROOT>/<AGENT_DIR>/DEPLOYMENT_INSTRUCTIONS.md` (if it exists) for project-specific workflow details
- Ask user for iteration name (e.g., `iter7`) or auto-increment from log

**If resuming an interrupted iteration:**
1. Use checkpoint detection from `references/resume-iteration.md` to identify completed runs
2. Validate spec consistency: if both pre-edit and post-edit runs exist, check the mean score delta between them. If delta < 0.05 AND both are far from baseline, pre and post likely used the same (bad) spec — discard both and restart with versioned run names (e.g., `<ITER_NAME>v2_dev_r1`)
3. Otherwise: resume from the identified checkpoint per `references/resume-iteration.md`

## Step 2: Run DEV Eval (if not already run)
Fire all `<RUNS_PER_SPLIT>` DEV runs simultaneously — each uses its own slot config (`eval_config_dev_r1.yaml` through `eval_config_dev_r<RUNS_PER_SPLIT>.yaml`). Poll all runs in parallel using the parallel polling pattern from `references/eval-polling.md` until every slot reports completion. On lock errors, clear only the affected slot's lock (append `_r<N>` to the dataset name); other slots are unaffected.

**Run Naming Convention:**
- Pre-edit: `<ITER_NAME>_dev_r1` through `<ITER_NAME>_dev_r<RUNS_PER_SPLIT>`
- Post-edit: `<ITER_NAME>_dev_post_r1` through `<ITER_NAME>_dev_post_r<RUNS_PER_SPLIT>`
- TEST: `<ITER_NAME>_test_r1` through `<ITER_NAME>_test_r<RUNS_PER_SPLIT>`

**On deployment failures, instruction revisions, or spec errors:** increment a version suffix (`<ITER_NAME>v2_dev_post_r1..rN`, `v3_...`). Document in `optimization_log.md` which version was accepted. **Never reuse run names** — the eval framework blocks overwrites.

## Step 3: Analyze DEV Failures
- Build a UNION ALL query with one SELECT block per run (`<ITER_NAME>_dev_r1` through `<ITER_NAME>_dev_r<RUNS_PER_SPLIT>`) to aggregate results:
  ```sql
  SELECT METRIC_NAME,
         ROUND(AVG(EVAL_AGG_SCORE) * 100, 1) AS MEAN_SCORE_PCT,
         ROUND(STDDEV(EVAL_AGG_SCORE) * 100, 1) AS STDDEV_PCT,
         COUNT(*) AS N
  FROM (
    SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
      '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_dev_r1'
    ))
    UNION ALL
    SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
      '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_dev_r2'
    ))
    -- ... add one UNION ALL block per run through r<RUNS_PER_SPLIT>
  )
  WHERE METRIC_NAME IS NOT NULL
  GROUP BY METRIC_NAME;
  ```
- Filter to questions where **mean** `EVAL_AGG_SCORE` across all `<RUNS_PER_SPLIT>` runs is `< 1.0`
- Questions that fail in all `<RUNS_PER_SPLIT>` runs are high-confidence failures; questions that fail in only 1 run are noise candidates — note this distinction in the analysis
- **CRITICAL: Only analyze DEV failures. Do NOT examine TEST results at this stage.**

## Step 4: Classify Failures
Classify each failure using this ordered decision tree. Evaluate conditions top-to-bottom; the first match is the classification.

1. **Routing check (if ground_truth_invocations provided):**
   - If ground_truth_invocations is NULL: skip to Step 2
   - If provided: compare actual tool sequence to ground truth
     - If first tool differs: **Routing error** — Fix: add keyword triggers or negative routing rules to `orchestration_instructions.md`
     - If match: proceed to Step 2

2. **Check if any tool call returned an error/exception.** If yes → **Tool error.** Fix: add retry logic to `orchestration_instructions.md` ("retry up to 2x on transient errors before reporting failure").

3. **Compare answer structure to ground truth output.** If the facts are correct but the format/structure doesn't match → **Formatting error.** Fix: add explicit format templates to `response_instructions.md`.

4. **Compare answer content to ground truth output.** If facts are wrong, missing, or incomplete despite correct tool calls → **Content error.** Fix: add domain-specific rules or corrected examples to `response_instructions.md`.

5. **Re-read the current instructions that should govern this behavior.** If the instructions can reasonably be interpreted to produce the agent's (wrong) behavior → **Instruction ambiguity.** Fix: rewrite the ambiguous rule with a concrete example showing expected behavior.

6. **Check for conflicting instructions across agent files.** If the agent behavior suggests it is following one instruction that contradicts another (e.g., claiming tools are unavailable when tools are configured, asking for clarification when instructions say to proceed with defaults) → **Instruction conflict.** Fix: read all instruction files (`orchestration_instructions.md`, `response_instructions.md`, `tool_descriptions.md`), identify the conflicting pattern, remove or rephrase to align with intended behavior.

7. **Check the optimization log for this failure pattern.** If the same failure has persisted across 2+ prior iterations despite targeted fixes → **Model behavior limit.** Fix: consider architectural changes (tool guardrails, workflow restructuring) or document as a known limitation.

For questions that failed in only 1 of `<RUNS_PER_SPLIT>` runs: classify as **Intermittent** — these are noise and should generally not drive instruction changes unless a clear pattern emerges across multiple questions.

**⚠️ STOP (supervised mode):** Present failure analysis to user. Propose specific instruction changes. In autonomous mode: proceed if all failures have a single unambiguous classification; stop and ask if any failure has multiple plausible classifications or if the proposed change is large (touching 3+ files).

## Step 5: Edit Instructions

**Before making any changes, complete this pre-edit protocol:**
1. List all files in `<WORKSPACE_ROOT>/<AGENT_DIR>/agent/*.md`
2. Read each file completely (`orchestration_instructions.md`, `response_instructions.md`, `tool_descriptions.md`, and any others)
3. Search for phrases that might conflict with the proposed change (e.g., if adding "tools are available", grep for "don't have access" or "not available")
4. Verify a snapshot of the current state exists in `snapshots/` (either `baseline/` or the last accepted iteration). If not, create one now.

Only after completing steps 1–4, proceed with modifications.

- Modify the relevant `agent/*.md` files based on failure analysis
- Follow optimization patterns (load `references/optimization-patterns.md`):
  - **Prefer examples over verbose procedural rules**
  - **Fix buggy examples** — agents faithfully reproduce them
  - **Small, targeted changes** — one pattern per iteration
  - **Add "WRONG" examples** — showing what NOT to do is effective
  - **Don't over-strengthen rules** that failed 2+ iterations — diminishing returns

**⚠️ STOP (supervised mode):** Present the proposed instruction changes (diff) and get approval before building. In autonomous mode: proceed.

If `show_diff.py` exists in `scripts/`, use it to show a readable diff: `python scripts/show_diff.py --from snapshots/<last_iteration>/ --to agent/`

- **Log progress:** Append an IN PROGRESS entry to `optimization_log.md` recording status `Instructions edited, awaiting build/deploy`, files changed, and timestamp

## Step 6: Build and Deploy
```bash
python scripts/build_agent_spec.py
<CLI_TOOL> sql --connection <CONNECTION> --filename <WORKSPACE_ROOT>/<AGENT_DIR>/deploy.sql
```
- Verify deployment: `DESCRIBE AGENT <AGENT_FQN>;`

**Verify `tool_resources` configuration in deployed spec:**
- `cortex_analyst_text_to_sql` tools MUST have both `semantic_view` AND `execution_environment` in `tool_resources`
- `cortex_search` tools MUST have `name` (the search service name) in `tool_resources`

Common errors that cause "Invocation failed":
- Missing `execution_environment` in analyst `tool_resources`
- Using legacy format `"warehouse": "WH"` instead of nested `"execution_environment": {"type": "warehouse", "warehouse": "WH"}`
- Incorrect search service name or missing semantic view

If `tool_resources` are incomplete, update `spec_base.json` and redeploy before running evals.

- **Log progress:** Update the IN PROGRESS entry in `optimization_log.md` to status `Deployed, awaiting DEV post-eval` with timestamp

## Step 7: Re-run DEV Eval
- Fire all `<RUNS_PER_SPLIT>` DEV runs simultaneously using the same slot configs as Step 2, with post-edit run names (`<ITER_NAME>_dev_post_r1` through `<ITER_NAME>_dev_post_r<RUNS_PER_SPLIT>`); poll all in parallel until every slot reports completion

**Validate pre/post delta before applying t-test:**
Compute the mean score delta between pre-edit runs (`<ITER_NAME>_dev_r1..rN`) and post-edit runs (`<ITER_NAME>_dev_post_r1..rN`). If delta < 0.03, the runs likely reflect the same agent spec — verify last deployment succeeded and the agent spec was actually updated (`DESCRIBE AGENT <AGENT_FQN>`). If not updated, rebuild and redeploy, then re-run post-edit evals with versioned names (`<ITER_NAME>v2_dev_post_r1..rN`).

- Apply paired t-test vs previous accepted iteration's DEV per-run means (same formula as `review/SKILL.md` Step 2)

**On DEV regression (t < critical value):**
1. Keep the same `<ITER_NAME>` — this is still the same iteration, just revised
2. Log the failed attempt in `optimization_log.md` with the t-statistic and verdict
3. Return to Step 3 (re-analyze DEV failures) to revise the approach
4. Use versioned run names for the retry: `<ITER_NAME>v2_dev_post_r1..rN`, then `v3_...` if needed
5. Do NOT proceed to TEST until DEV post-edit passes the regression check

## Step 8: Run TEST Eval (only if DEV is satisfactory)
Fire all `<RUNS_PER_SPLIT>` TEST runs simultaneously using slot configs `eval_config_test_r1.yaml` through `eval_config_test_r<RUNS_PER_SPLIT>.yaml`. Poll all in parallel until every slot reports completion. Handle lock errors per-slot per `references/eval-setup.md`.

## Step 9: Log Results
- Append iteration to `optimization_log.md` with this template:

```markdown
## Iteration N

**Run names:** `<ITER_NAME>_dev_r1` through `<ITER_NAME>_dev_r<RUNS_PER_SPLIT>`, `<ITER_NAME>_test_r1` through `<ITER_NAME>_test_r<RUNS_PER_SPLIT>`

**Changes made:**
1. [Change description]

**Files changed:** `agent/[file1].md`, `agent/[file2].md`

| Metric | DEV Mean ± StdDev | TEST Mean ± StdDev | Combined Mean |
|--------|-------------------|--------------------|--------------| 
| [metric_1] | X% ± Y% | X% ± Y% | Z% |
| [metric_2] | X% ± Y% | X% ± Y% | Z% |

**Comparison to [previous accepted iteration]:**
[Delta table with significance note]

**Decision:** [ACCEPT/REJECT with reasoning]
```

- Hand off to `review/SKILL.md` for the accept/reject decision.

**Target length:** ~200-230 lines.
