---
name: cortex-agent-eval-optimizer-iterate
description: "Run a single optimization iteration: analyze DEV failures, edit instructions, build/deploy, eval."
parent_skill: cortex-agent-eval-optimizer
---

## Step 1: Read Context

Load project context:
- Read `metadata.yaml` to get all parameters (`<DATABASE>`, `<SCHEMA>`, `<AGENT_NAME>`, `<CONNECTION>`, `<CLI_TOOL>`, `<STAGE_PATH>`, `<DEV_DATASET_NAME>`, `<TEST_DATASET_NAME>`, `<DEV_SPLIT_VALUE>`, `<TEST_SPLIT_VALUE>`, `<EXECUTION_MODE>`, `<WORKSPACE_ROOT>`, `<AGENT_DIR>`, `<RUNS_PER_SPLIT>`).
- Read `optimization_log.md` — understand current scores, previous iterations, what's been tried, and the consecutive-rejection counter.
- Read `DEPLOYMENT_INSTRUCTIONS.md` (if it exists) for project-specific workflow details.
- Ask the user for the iteration name (`<ITER_NAME>`, e.g., `iter7`) or auto-increment from the last iteration in the log.

**If resuming an interrupted iteration:**

1. Use checkpoint detection from `references/resume-iteration.md` to identify completed runs
2. **Validate spec consistency:** If both pre and post runs exist, check that they reflect different agent states:
   ```sql
   -- Compare mean scores between pre and post across all runs
   SELECT 
     ROUND(AVG(CASE WHEN RUN_NAME LIKE '%_dev_r%' THEN MEAN_LC END), 3) AS pre_mean,
     ROUND(AVG(CASE WHEN RUN_NAME LIKE '%_dev_post_r%' THEN MEAN_LC END), 3) AS post_mean,
     ABS(pre_mean - post_mean) AS delta
   FROM (
     -- UNION ALL of per-run means for dev_r1..rN and dev_post_r1..rN
     SELECT '<ITER_NAME>_dev_r1' AS RUN_NAME, AVG(EVAL_AGG_SCORE) AS MEAN_LC
     FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(..., '<ITER_NAME>_dev_r1'))
     WHERE METRIC_NAME = 'logical_consistency' GROUP BY 1
     UNION ALL
     -- Repeat for r2..rN and dev_post_r1..rN
   );
   ```
3. **If delta < 0.05 AND both are far from baseline:** Pre and post likely used the same (bad) spec
   - Action: Discard both, restart iteration with corrected spec using new run names (e.g., `<ITER_NAME>v2_dev_r1`)
4. **Otherwise:** Resume from the identified checkpoint per `references/resume-iteration.md`

## Step 2: Run DEV Eval (if not already run this iteration)

### Pre-flight: Ground Truth Completeness

**MANDATORY before firing any eval runs.** Run the GT completeness check from `eval-data/SKILL.md` Workflow E against the DEV view:

```sql
SELECT 
    COUNT(*) AS TOTAL_QUESTIONS,
    COUNT_IF(GROUND_TRUTH IS NULL 
             OR TRY_PARSE_JSON(GROUND_TRUTH):ground_truth_output::STRING IS NULL
             OR LEN(TRIM(TRY_PARSE_JSON(GROUND_TRUTH):ground_truth_output::STRING)) = 0) AS MISSING_GT
FROM <DATABASE>.<SCHEMA>.AGENT_EVAL_DEV;
```

- If `MISSING_GT = 0`: proceed to fire eval runs.
- If `MISSING_GT > 0`: **HARD STOP**. List the questions with `eval-data/SKILL.md` Workflow E Step 2 query. Do NOT fire eval runs — missing GT scores 0 and silently corrupts all metrics.

### Fire DEV Eval Runs

Fire all `<RUNS_PER_SPLIT>` DEV runs simultaneously — each uses its own slot config:
```sql
-- Fire all simultaneously (do not wait between calls)
CALL EXECUTE_AI_EVALUATION(
  'START',
  OBJECT_CONSTRUCT('run_name', '<ITER_NAME>_dev_r1'),
  '<STAGE_PATH>/eval_config_dev_r1.yaml'
);
-- Repeat immediately for r2 through r<RUNS_PER_SPLIT>, using eval_config_dev_r2.yaml etc.
```

### Run Naming Convention

**Primary runs:**
- Pre-edit: `<ITER_NAME>_dev_r1` through `<ITER_NAME>_dev_r<RUNS_PER_SPLIT>`
- Post-edit: `<ITER_NAME>_dev_post_r1` through `<ITER_NAME>_dev_post_r<RUNS_PER_SPLIT>`
- TEST: `<ITER_NAME>_test_r1` through `<ITER_NAME>_test_r<RUNS_PER_SPLIT>`

**If you need to re-run after deployment failures, instruction revisions, or spec errors:**
- Increment a version suffix: `<ITER_NAME>v2_dev_post_r1` through `r<RUNS_PER_SPLIT>`
- If another retry needed: `<ITER_NAME>v3_dev_post_r1`, etc.
- Document in optimization_log.md which version was accepted
- **Never reuse run names** — Snowflake eval framework blocks overwrites

**Example:** If iter2_dev_post runs fail due to a bad spec:
- First retry: iter2v2_dev_post_r1 through r4
- If that also fails: iter2v3_dev_post_r1 through r4

Then poll all runs in parallel using the parallel polling pattern from `references/eval-polling.md` until every slot reports `COMPLETED_METRICS > 0`.

**If "Dataset version already exists" error occurs:**

**Decision tree:**
1. **Check eval status:** `CALL EXECUTE_AI_EVALUATION('STATUS', OBJECT_CONSTRUCT('run_name', '<RUN_NAME>'), '<CONFIG_PATH>');`
2. **If STATUS = 'RUNNING':**
   - Wait 2-3 minutes, retry the slot
   - Repeat check until status changes or 5 minutes elapsed
3. **If STATUS = 'FAILED' or no status after 5+ minutes:**
   - Lock is stale, clear it for the specific failing slot:
     ```sql
     ALTER DATASET <DATABASE>.<SCHEMA>.<DEV_DATASET_NAME>_r<N>
     DROP VERSION 'SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE';
     ```
   - Retry the slot immediately
4. **Other slots are unaffected** — only the failing slot needs clearing
5. **NEVER drop the dataset itself** — this destroys historical results. Only drop stale version locks.

## Step 3: Analyze DEV Failures

Query aggregate results across all `<RUNS_PER_SPLIT>` DEV runs. Build a UNION ALL query with one SELECT block per run (`<ITER_NAME>_dev_r1` through `<ITER_NAME>_dev_r<RUNS_PER_SPLIT>`):

**Important — exclude two categories of non-representative rows before aggregating:**
- `METRIC_CALLS LIKE '%Missing ground truth%'` — AC cannot be scored on invocations-only rows (no `ground_truth_output`); these always return 0 and are dataset gaps, not agent failures.
- `METRIC_CALLS LIKE '%LLM error%' OR LIKE '%Evaluation failed%'` — the LLM judge hit an error (e.g. token limit on long traces); these always return 0 and are infrastructure failures, not agent failures.

The Snowflake UI excludes these rows automatically. Your queries must do the same or scores will appear far lower than the UI shows.

```sql
SELECT METRIC_NAME,
       ROUND(AVG(EVAL_AGG_SCORE) * 100, 1) AS MEAN_SCORE_PCT,
       ROUND(STDDEV(EVAL_AGG_SCORE) * 100, 1) AS STDDEV_PCT,
       COUNT(*) AS N
FROM (
  SELECT METRIC_NAME, EVAL_AGG_SCORE, METRIC_CALLS FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
    '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_dev_r1'
  ))
  UNION ALL
  SELECT METRIC_NAME, EVAL_AGG_SCORE, METRIC_CALLS FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
    '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_dev_r2'
  ))
  -- ... add one UNION ALL block per run through r<RUNS_PER_SPLIT>
)
WHERE METRIC_NAME IS NOT NULL
  AND METRIC_CALLS::VARCHAR NOT LIKE '%Missing ground truth%'
  AND METRIC_CALLS::VARCHAR NOT LIKE '%LLM error%'
  AND METRIC_CALLS::VARCHAR NOT LIKE '%Evaluation failed%'
GROUP BY METRIC_NAME;
```

For per-question failure analysis, query individual question scores across all `<RUNS_PER_SPLIT>` runs. Apply the same artifact exclusion filter (`METRIC_CALLS` filters above). Filter to questions where **mean** `EVAL_AGG_SCORE` across the scoreable runs is `< 1.0`.

Distinguish failure confidence:
- **High-confidence failures**: Failed in all `<RUNS_PER_SPLIT>` runs — these drive instruction changes.
- **Noise candidates**: Failed in only 1 of `<RUNS_PER_SPLIT>` runs — generally should not drive changes unless a clear pattern emerges across multiple questions.

**CRITICAL: Only analyze DEV failures. Do NOT examine TEST results at this stage.**

## Step 4: Classify Failures

Classify each high-confidence failure using this ordered decision tree. Evaluate conditions top-to-bottom; the first match is the classification.

1. **Routing Check:**
   
   **If `ground_truth_invocations` is provided (not NULL):**
   - Compare actual tool sequence to ground truth
   - If the first tool called differs from ground truth → **Routing error**
     - Fix: Add keyword triggers or negative routing rules to `orchestration_instructions.md`
   - If tools match → proceed to Step 2
   
   **If `ground_truth_invocations` is NULL:**
   - Ground truth does not specify expected tool sequence
   - Skip routing verification
   - Proceed directly to Step 2

2. **Check if any tool call returned an error/exception.** If yes → **Tool error.** Fix: add retry logic to `orchestration_instructions.md` ("retry up to 2x on transient errors before reporting failure").

3. **Compare answer structure to ground truth output.** If the facts are correct but the format/structure doesn't match → **Formatting error.** Fix: add explicit format templates to `response_instructions.md`.

4. **Compare answer content to ground truth output.** If facts are wrong, missing, or incomplete despite correct tool calls → **Content error.** Fix: add domain-specific rules or corrected examples to `response_instructions.md`.

5. **Re-read the current instructions that should govern this behavior.** If the instructions can reasonably be interpreted to produce the agent's (wrong) behavior → **Instruction ambiguity.** Fix: rewrite the ambiguous rule with a concrete example showing expected behavior.

6. **Check for conflicting instructions across agent files.** If the agent behavior suggests it's following one instruction that contradicts another (e.g., claiming tools are unavailable when tools are configured, or asking for clarification when instructions say to proceed with defaults) → **Instruction conflict.** Fix: Read all instruction files (`orchestration_instructions.md`, `response_instructions.md`, `tool_descriptions.md`), identify the conflicting pattern, remove or rephrase it to align with intended behavior.

7. **Check the optimization log for this failure pattern.** If the same failure has persisted across 2+ prior iterations despite targeted fixes → **Model behavior limit.** Fix: consider architectural changes (tool guardrails, workflow restructuring) or document as a known limitation.

For questions that failed in only 1 of `<RUNS_PER_SPLIT>` runs: classify as **Intermittent** — noise that should not drive instruction changes unless a clear cross-question pattern emerges.

**⚠️ STOP (supervised mode):** Present failure analysis with classifications and proposed instruction changes to the user. In autonomous mode: proceed if all failures have a single unambiguous classification; stop and ask if any failure has multiple plausible classifications or if the proposed change touches 3+ files.

**Optional: Deep-dive debugging**

For complex failures requiring detailed trace analysis, consider using bundled `debug-single-query-for-cortex-agent` skill:
- Provides GET_AI_RECORD_TRACE queries with span-level detail
- Analyzes observability logs for errors and warnings
- Useful when classification is ambiguous or when investigating tool execution issues

Example handoff: "I've identified 3 routing failures. Would you like me to deep-dive into request_id X using the debug skill?"

## Step 5: Edit Instructions

**Before making any changes, read ALL current agent instruction files to understand the complete context:**

1. **List all instruction files:**
   ```bash
   ls -la <WORKSPACE_ROOT>/<AGENT_DIR>/agent/*.md
   ```

2. **Read each file completely:**
   - `orchestration_instructions.md` - tool selection logic, workflows, business rules
   - `response_instructions.md` - response formatting, tone, out-of-scope handling  
   - `tool_descriptions.md` - tool capabilities and when to use each
   - Any other `.md` files in the `agent/` directory

3. **Check for conflicting patterns before editing:**
   - Search for phrases that might conflict with your proposed change
   - Example: If adding "tools are available", search for "don't have access" or "not available"
   - Example: If fixing tool calls, search for examples that claim tools are unavailable
   - Example: If adding default parameters, search for examples that ask for clarification
   - Use grep to find conflicts:
     ```bash
     grep -i "don't have access\|not available\|no access" <WORKSPACE_ROOT>/<AGENT_DIR>/agent/*.md
     ```

4. **Verify snapshot exists:**
   - Check that a snapshot of current state exists in `snapshots/` (either `baseline/` or the last accepted iteration)
   - If not, create one now

**Only after completing steps 1-4, proceed with modifications.**

Modify the relevant `agent/*.md` files based on the failure analysis. Follow optimization patterns (load `references/optimization-patterns.md`):
- **Prefer examples over verbose procedural rules**
- **Fix buggy examples** — agents faithfully reproduce them
- **Small, targeted changes** — one pattern per iteration
- **Add "WRONG" examples** — showing what NOT to do is effective
- **Don't over-strengthen rules** that failed 2+ iterations — diminishing returns

**⚠️ STOP (supervised mode):** Present the proposed instruction changes (diff) and get approval before building. In autonomous mode: proceed.

**Viewing changes:**
If `show_diff.py` exists in scripts/:
```bash
python scripts/show_diff.py --from snapshots/<last_iteration>/ --to agent/
```
Otherwise, manually review changed files in `agent/` directory.

**Log progress:** Append to `optimization_log.md`:
```markdown
### <ITER_NAME> — IN PROGRESS
**Status:** Instructions edited, awaiting build/deploy
**Files changed:** [list changed files]
**Timestamp:** [current timestamp]
```

## Step 6: Build and Deploy

```bash
python <WORKSPACE_ROOT>/scripts/build_agent_spec.py
<CLI_TOOL> sql --connection <CONNECTION> --filename <WORKSPACE_ROOT>/<AGENT_DIR>/deploy.sql
```

Verify deployment:
```sql
DESCRIBE AGENT <AGENT_FQN>;
```

**Critical: Verify tool_resources configuration in the deployed spec:**

After deployment, check that all tools have required resources:
- **cortex_analyst_text_to_sql** tools MUST have both `semantic_view` AND `execution_environment` in tool_resources
- **cortex_search** tools MUST have `name` (the search service name) in tool_resources

**Required format for cortex_analyst_text_to_sql tools:**
```json
{
  "tool_resources": {
    "analyze_tool": {
      "semantic_view": "<DATABASE>.<SCHEMA>.<SEMANTIC_VIEW>",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "<WAREHOUSE_NAME>"
      }
    }
  }
}
```

Example verification:
```sql
-- Check deployed spec includes execution_environment for Analyst tools
SELECT agent_spec:tool_resources
FROM (DESCRIBE AGENT <AGENT_FQN>)
WHERE name = '<AGENT_NAME>';
```

**Common configuration errors that cause "Invocation failed":**
- ❌ Missing execution_environment in cortex_analyst tool_resources → Error: "missing an execution environment"
- ❌ Using legacy format `"warehouse": "WH"` instead of nested `"execution_environment": {"type": "warehouse", "warehouse": "WH"}` → Error: "missing an execution environment"
- ❌ Incorrect search service name → Error: "service not found"  
- ❌ Semantic view doesn't exist → Error: "view not found"

If tool_resources are incomplete, update `spec_base.json` and redeploy before running evals.

**Log progress:** Update the `<ITER_NAME>` IN PROGRESS entry in `optimization_log.md`:
```markdown
**Status:** Deployed, awaiting DEV post-eval
**Timestamp:** [current timestamp]
```

## Step 7: Re-run DEV Eval

Fire all `<RUNS_PER_SPLIT>` DEV runs simultaneously using the same slot configs as Step 2, with post-edit run names (e.g., `<ITER_NAME>_dev_post_r1` through `<ITER_NAME>_dev_post_r<RUNS_PER_SPLIT>`). Poll all in parallel until every slot reports completion.

**Before applying t-test, validate that pre-edit and post-edit runs reflect different agent states:**

```sql
-- Compute mean LC scores for pre and post across all runs
SELECT 
  ROUND(AVG(CASE WHEN RUN_NAME LIKE '%_dev_r%' THEN MEAN_SCORE END), 3) AS pre_mean,
  ROUND(AVG(CASE WHEN RUN_NAME LIKE '%_dev_post_r%' THEN MEAN_SCORE END), 3) AS post_mean,
  ROUND(ABS(pre_mean - post_mean), 3) AS delta
FROM (
  -- UNION ALL of per-run means for dev_r1..rN and dev_post_r1..rN
  SELECT '<ITER_NAME>_dev_r1' AS RUN_NAME, AVG(EVAL_AGG_SCORE) AS MEAN_SCORE
  FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(..., '<ITER_NAME>_dev_r1'))
  WHERE METRIC_NAME = 'logical_consistency'
    AND METRIC_CALLS::VARCHAR NOT LIKE '%Missing ground truth%'
    AND METRIC_CALLS::VARCHAR NOT LIKE '%LLM error%'
    AND METRIC_CALLS::VARCHAR NOT LIKE '%Evaluation failed%'
  GROUP BY 1
  UNION ALL
  -- Repeat for all runs (apply same METRIC_CALLS filters in each block)
)
HAVING ABS(pre_mean - post_mean) >= 0.03;  -- Expect at least 3% change
```

**If delta < 0.03:** Pre and post likely used the same agent spec (deployment may have failed or been skipped):
1. Verify last deployment succeeded: check deploy.sql output
2. Verify agent spec was updated: `DESCRIBE AGENT <AGENT_FQN>`
3. If spec wasn't updated, rebuild and redeploy, then re-run post-edit evals with versioned names (`<ITER_NAME>v2_dev_post_r1..rN`)

Apply the paired t-test to check for regression vs the previous accepted iteration's DEV means (same formula as `review/SKILL.md` Step 2, using DEV per-run means).

**On DEV post-edit regression (t < critical value):**

1. **Keep the same `<ITER_NAME>`** — this is still the same iteration, just revised
2. **Log the failed attempt** in optimization_log.md:
   ```markdown
   ### Iteration <ITER_NAME> (attempt 1) - REGRESSION
   
   **Changes:** [describe what was changed]
   **DEV post-edit result:** t-stat = [value], below critical value [value]
   **Verdict:** Regression detected, reverting to re-analyze
   ```
3. **Return to Step 3** (analyze DEV failures) to revise the approach
4. **Use versioned run names** for the retry:
   - New post-edit runs: `<ITER_NAME>v2_dev_post_r1` through `r<RUNS_PER_SPLIT>`
   - If regression happens again: `<ITER_NAME>v3_dev_post_r1`, etc.
5. **Do NOT proceed to TEST** until DEV post-edit passes the regression check

Otherwise proceed to TEST.

## Step 8: Run TEST Eval (only if DEV is satisfactory)

### Pre-flight: TEST Ground Truth Completeness

Run the same GT completeness check against the TEST view before firing TEST runs:

```sql
SELECT 
    COUNT(*) AS TOTAL_QUESTIONS,
    COUNT_IF(GROUND_TRUTH IS NULL 
             OR TRY_PARSE_JSON(GROUND_TRUTH):ground_truth_output::STRING IS NULL
             OR LEN(TRIM(TRY_PARSE_JSON(GROUND_TRUTH):ground_truth_output::STRING)) = 0) AS MISSING_GT
FROM <DATABASE>.<SCHEMA>.AGENT_EVAL_TEST;
```

If `MISSING_GT > 0`: **HARD STOP** — same as Step 2 pre-flight.

### Fire TEST Eval Runs

Fire all `<RUNS_PER_SPLIT>` TEST runs simultaneously — each uses its own slot config:
```sql
-- Fire all simultaneously (do not wait between calls)
CALL EXECUTE_AI_EVALUATION(
  'START',
  OBJECT_CONSTRUCT('run_name', '<ITER_NAME>_test_r1'),
  '<STAGE_PATH>/eval_config_test_r1.yaml'
);
-- Repeat immediately for r2 through r<RUNS_PER_SPLIT>, using eval_config_test_r2.yaml etc.
```

Poll all runs in parallel using the parallel polling pattern from `references/eval-polling.md` until every slot reports completion.

Handle dataset version lock errors per-slot per `references/eval-setup.md` lock troubleshooting.

## Step 9: Log Results

Append the iteration to `optimization_log.md` with: run names, changes made, files changed, score table (DEV Mean ± StdDev | TEST Mean ± StdDev | Combined Mean per metric), comparison delta vs previous accepted iteration, and `Decision: PENDING`.

Continue to `review/SKILL.md` for the accept/reject decision.
