---
name: cortex-agent-optimization-iterate
description: "Run a single optimization iteration: analyze DEV failures, edit instructions, build/deploy, eval."
parent_skill: cortex-agent-optimization
---

## Step 1: Read Context

Load project context:
- Read `metadata.yaml` to get all parameters (`<DATABASE>`, `<SCHEMA>`, `<AGENT_NAME>`, `<CONNECTION>`, `<CLI_TOOL>`, `<STAGE_PATH>`, `<DEV_DATASET_NAME>`, `<TEST_DATASET_NAME>`, `<DEV_SPLIT_VALUE>`, `<TEST_SPLIT_VALUE>`, `<EXECUTION_MODE>`, `<WORKSPACE_ROOT>`, `<AGENT_DIR>`).
- Read `optimization_log.md` — understand current scores, previous iterations, what's been tried, and the consecutive-rejection counter.
- Read `DEPLOYMENT_INSTRUCTIONS.md` (if it exists) for project-specific workflow details.
- Ask the user for the iteration name (`<ITER_NAME>`, e.g., `iter7`) or auto-increment from the last iteration in the log.

**If resuming an interrupted iteration:** See `references/resume-iteration.md` for checkpoint detection queries and resume workflow.

## Step 2: Run DEV Eval (if not already run this iteration)

Run DEV eval 3 times sequentially (dataset version lock prevents parallel runs):
```sql
CALL EXECUTE_AI_EVALUATION(
  'START',
  OBJECT_CONSTRUCT('run_name', '<ITER_NAME>_dev_r1'),
  '<STAGE_PATH>/eval_config_dev.yaml'
);
-- Wait for completion (including scoring), then run r2, then r3
```

Each run must complete before the next starts. 

**Polling tip:** Use the completion check query from `references/eval-polling.md` to monitor progress. Poll every 30-60 seconds instead of waiting blindly.

If "Dataset version already exists" error occurs:
- Wait 2-3 minutes and retry.
- If persists 5+ min with no eval running, clear the stale lock:
  ```sql
  ALTER DATASET <DATABASE>.<SCHEMA>.<DEV_DATASET_NAME>
  DROP VERSION 'SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE';
  ```
- **NEVER drop the dataset itself** — only the version lock.

## Step 3: Analyze DEV Failures

Query aggregate results from all 3 DEV runs:
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

For per-question failure analysis, query individual question scores across the 3 runs. Filter to questions where **mean** `EVAL_AGG_SCORE` across the 3 runs is `< 1.0`.

Distinguish failure confidence:
- **High-confidence failures**: Failed in all 3 runs — these drive instruction changes.
- **Noise candidates**: Failed in only 1 of 3 runs — generally should not drive changes unless a clear pattern emerges across multiple questions.

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

6. **Check the optimization log for this failure pattern.** If the same failure has persisted across 2+ prior iterations despite targeted fixes → **Model behavior limit.** Fix: consider architectural changes (tool guardrails, workflow restructuring) or document as a known limitation.

For questions that failed in only 1 of 3 runs: classify as **Intermittent** — noise that should not drive instruction changes unless a clear cross-question pattern emerges.

**⚠️ STOP (supervised mode):** Present failure analysis with classifications and proposed instruction changes to the user. In autonomous mode: proceed if all failures have a single unambiguous classification; stop and ask if any failure has multiple plausible classifications or if the proposed change touches 3+ files.

**Optional: Deep-dive debugging**

For complex failures requiring detailed trace analysis, consider using bundled `debug-single-query-for-cortex-agent` skill:
- Provides GET_AI_RECORD_TRACE queries with span-level detail
- Analyzes observability logs for errors and warnings
- Useful when classification is ambiguous or when investigating tool execution issues

Example handoff: "I've identified 3 routing failures. Would you like me to deep-dive into request_id X using the debug skill?"

## Step 5: Edit Instructions

Before making changes, verify a snapshot of the current `agent/*.md` state exists in `snapshots/` (either `baseline/` or the last accepted iteration). If not, create one now.

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

## Step 6: Build and Deploy

```bash
python <WORKSPACE_ROOT>/scripts/build_agent_spec.py
<CLI_TOOL> sql --connection <CONNECTION> --filename <WORKSPACE_ROOT>/<AGENT_DIR>/deploy.sql
```

Verify deployment:
```sql
DESCRIBE AGENT <AGENT_FQN>;
```

## Step 7: Re-run DEV Eval

Run DEV eval 3 times sequentially (`<ITER_NAME>_dev_r1` through `_r3`). Use the same run names — if Step 2 already ran them before edits, use new suffixed names (e.g., `<ITER_NAME>_dev_post_r1`).

**Polling tip:** Use the completion check query from `references/eval-polling.md` to monitor progress between runs.

Compare mean scores to the previous iteration's mean scores:
- If mean regression exceeds 1 stddev on any metric: the edit likely degraded performance. Return to Step 5 and adjust.
- If mean improvement or within noise: proceed to TEST.

## Step 8: Run TEST Eval (only if DEV is satisfactory)

Run TEST eval 3 times sequentially (`<ITER_NAME>_test_r1` through `_r3`):
```sql
CALL EXECUTE_AI_EVALUATION(
  'START',
  OBJECT_CONSTRUCT('run_name', '<ITER_NAME>_test_r1'),
  '<STAGE_PATH>/eval_config_test.yaml'
);
-- Wait for completion, then run r2, then r3
```

**Polling tip:** See `references/eval-polling.md` for a status check query to monitor completion.

Handle dataset version lock errors per the standard troubleshooting guide in `references/eval-setup.md`.

## Step 9: Log Results

Append the iteration to `optimization_log.md` with: run names, changes made, files changed, score table (DEV Mean ± StdDev | TEST Mean ± StdDev | Combined Mean per metric), comparison delta vs previous accepted iteration, and `Decision: PENDING`.

Continue to `review/SKILL.md` for the accept/reject decision.
