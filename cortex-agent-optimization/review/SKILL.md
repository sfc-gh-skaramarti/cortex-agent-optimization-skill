---
name: cortex-agent-optimization-review
description: "Review iteration results and make accept/reject decision."
parent_skill: cortex-agent-optimization
---

## Step 1: Compute Scores

Read `metadata.yaml` for parameters if not already loaded.

Query DEV and TEST results for the current iteration across all 3 runs per split:
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
GROUP BY METRIC_NAME
ORDER BY METRIC_NAME;
```

Run the same query for the TEST split (`<ITER_NAME>_test_r1` through `_r3`).

Compute combined scores by UNION ALL of all 6 run results (3 DEV + 3 TEST), grouped by METRIC_NAME.

## Step 2: Apply Acceptance Criteria

Compute TEST mean improvement (delta) vs the last accepted iteration's TEST mean (from `optimization_log.md`).

**Acceptance rules:**

- **ACCEPT** if: TEST mean improves AND the improvement exceeds 1 stddev of the current iteration's TEST scores (signal > noise).
- **ACCEPT (marginal)** if: TEST mean improves but within 1 stddev — accept only if DEV improvement is strong and consistent across all 3 runs (all 3 individual DEV runs improved vs the previous iteration's individual runs).
- **REJECT** if: TEST mean regresses by any amount — this is an overfitting signal.

## Step 3: Present Recommendation

**⚠️ STOP (supervised mode):** Present the accept/reject recommendation with full data. In autonomous mode: proceed with the recommendation automatically.

Present:
- DEV scores (mean ± stddev) + delta vs previous accepted iteration
- TEST scores (mean ± stddev) + delta vs previous accepted iteration
- Combined scores + delta vs previous accepted iteration
- TEST mean comparison with significance assessment (the deciding metric)
- Recommendation: **ACCEPT**, **ACCEPT (marginal)**, or **REJECT** with reasoning

Wait for user confirmation (supervised mode only).

## Step 4: Finalize Decision

### If ACCEPT:
1. Update `optimization_log.md` — mark the iteration's Decision as **ACCEPTED**, record final scores.
2. Note this as the new "last accepted iteration" for future comparisons.
3. Snapshot current `agent/*.md` files to `snapshots/<ITER_NAME>/`.
4. Reset the consecutive-rejection counter to 0 in `optimization_log.md`.

### If REJECT:
1. Update `optimization_log.md` — mark the iteration's Decision as **REJECTED** with the reason.
2. Increment the consecutive-rejection counter in `optimization_log.md`.
3. **If counter reaches 3:** Stop the optimization loop entirely. Report:
   - Remaining failures that could not be resolved
   - Summary of what was tried across all rejected iterations
   - Recommendation on whether architectural changes are needed (different tools, guardrails, workflow restructuring)
4. Restore `agent/*.md` files from the last accepted snapshot in `snapshots/` (the most recent accepted `<ITER_NAME>/` directory, or `baseline/` if no iterations have been accepted).
5. Rebuild and redeploy with reverted instructions:
   ```bash
   python <WORKSPACE_ROOT>/scripts/build_agent_spec.py
   <CLI_TOOL> sql --connection <CONNECTION> --filename <WORKSPACE_ROOT>/<AGENT_DIR>/deploy.sql
   ```
6. Verify revert: `DESCRIBE AGENT <AGENT_FQN>;`

## Step 5: Cumulative Summary

Update the summary section of `optimization_log.md`:

```markdown
## Summary: Baseline → <ITER_NAME>

| Metric | Baseline Combined | Current Combined | Delta |
|--------|------------------|-----------------|-------|
| [metric_1] | X% | Y% | +/-Z% |
| [metric_2] | X% | Y% | +/-Z% |

**Key learnings:**
- [What worked or didn't work in this iteration]
```

If accepted, the project is ready for the next iteration. Continue to `optimize/SKILL.md` when ready.

If rejected and consecutive-rejection counter < 3, revert is complete. Continue to `optimize/SKILL.md` with a different approach targeting the same or different failures.

If rejected and consecutive-rejection counter = 3, the optimization loop is terminated. Present the final summary and recommend next steps.
