---
section: "4.3"
title: "optimize/SKILL.md — Run an Optimization Iteration"
parent_spec: "../cortex-agent-optimization-spec.md"
---

# Run an Optimization Iteration Contract

**Frontmatter:**

```yaml
---
name: cortex-agent-optimization-iterate
description: "Run a single optimization iteration: analyze DEV failures, edit instructions, build/deploy, eval."
parent_skill: cortex-agent-optimization
---
```

**Workflow (9 steps):**

## Step 1: Read Context
- Load `<WORKSPACE_ROOT>/<AGENT_DIR>/optimization_log.md` — understand current scores, previous iterations, what's been tried
- Load `<WORKSPACE_ROOT>/<AGENT_DIR>/DEPLOYMENT_INSTRUCTIONS.md` (if it exists) for project-specific workflow details
- Ask user for iteration name (e.g., `iter7`) or auto-increment from log

## Step 2: Run DEV Eval (if not already run)
Run DEV eval 3 times sequentially (dataset version lock prevents parallel runs):
```sql
-- Run 1
CALL EXECUTE_AI_EVALUATION(
  'START',
  OBJECT_CONSTRUCT('run_name', '<ITER_NAME>_dev_r1'),
  '@<STAGE_PATH>/eval_config_dev.yaml'
);
-- Wait for completion, then run 2 and 3 with _r2, _r3 suffixes
```
Each run must complete (including scoring) before the next starts. Wait for the dataset version lock to clear between runs.

- If error "Dataset version already exists": wait 2-3 minutes and retry. If persists 5+ min with no eval running, clear stale lock:
  ```sql
  ALTER DATASET <DATABASE>.<SCHEMA>.<DEV_DATASET_NAME>
  DROP VERSION 'SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE';
  ```
- **NEVER drop the dataset itself** — only the version lock.

## Step 3: Analyze DEV Failures
- Query results from all 3 DEV runs:
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
    UNION ALL
    SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
      '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_dev_r3'
    ))
  )
  WHERE METRIC_NAME IS NOT NULL
  GROUP BY METRIC_NAME;
  ```
- Filter to questions where **mean** `EVAL_AGG_SCORE` across the 3 runs is `< 1.0`
- Questions that fail in all 3 runs are high-confidence failures; questions that fail in only 1 of 3 are noise candidates — note this distinction in the analysis
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

6. **Check the optimization log for this failure pattern.** If the same failure has persisted across 2+ prior iterations despite targeted fixes → **Model behavior limit.** Fix: consider architectural changes (tool guardrails, workflow restructuring) or document as a known limitation.

For questions that failed in only 1 of 3 runs: classify as **Intermittent** — these are noise and should generally not drive instruction changes unless a clear pattern emerges across multiple questions.

**⚠️ STOP (supervised mode):** Present failure analysis to user. Propose specific instruction changes. In autonomous mode: proceed if all failures have a single unambiguous classification; stop and ask if any failure has multiple plausible classifications or if the proposed change is large (touching 3+ files).

## Step 5: Edit Instructions
- Before making changes, verify a snapshot of the current `agent/*.md` state exists (either `baseline/` or the last accepted iteration in `<WORKSPACE_ROOT>/<AGENT_DIR>/snapshots/`). If not, create one now.
- Modify the relevant `agent/*.md` files based on failure analysis
- Follow optimization patterns (load `references/optimization-patterns.md`):
  - **Prefer examples over verbose procedural rules**
  - **Fix buggy examples** — agents faithfully reproduce them
  - **Small, targeted changes** — one pattern per iteration
  - **Add "WRONG" examples** — showing what NOT to do is effective
  - **Don't over-strengthen rules** that failed 2+ iterations — diminishing returns

**⚠️ STOP (supervised mode):** Get approval on instruction changes before building. In autonomous mode: proceed.

## Step 6: Build and Deploy
```bash
python scripts/build_agent_spec.py
<CLI_TOOL> sql --connection <CONNECTION> --filename <WORKSPACE_ROOT>/<AGENT_DIR>/deploy.sql
```
- Verify deployment: `DESCRIBE AGENT <AGENT_FQN>;`

## Step 7: Re-run DEV Eval
- Run DEV eval 3 times (`<ITER_NAME>_dev_r1` through `_r3`), sequentially
- Compare mean scores to previous iteration's mean scores
- If mean regression exceeds 1 stddev: return to Step 5 and adjust

## Step 8: Run TEST Eval (only if DEV is satisfactory)
Run TEST eval 3 times sequentially (`<ITER_NAME>_test_r1` through `_r3`):
```sql
-- Run 1
CALL EXECUTE_AI_EVALUATION(
  'START',
  OBJECT_CONSTRUCT('run_name', '<ITER_NAME>_test_r1'),
  '@<STAGE_PATH>/eval_config_test.yaml'
);
-- Wait for completion, then run 2 and 3 with _r2, _r3 suffixes
```

## Step 9: Log Results
- Append iteration to `optimization_log.md` with this template:

```markdown
## Iteration N

**Run names:** `<ITER_NAME>_dev_r[1-3]`, `<ITER_NAME>_test_r[1-3]`

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
