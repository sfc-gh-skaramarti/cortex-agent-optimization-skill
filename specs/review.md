---
section: "4.4"
title: "review/SKILL.md — Accept/Reject Decision"
parent_spec: "../cortex-agent-optimization-spec.md"
---

# Accept/Reject Decision Contract

**Frontmatter:**

```yaml
---
name: cortex-agent-optimization-review
description: "Review iteration results and make accept/reject decision."
parent_skill: cortex-agent-optimization
---
```

**Workflow (5 steps):**

## Step 1: Compute Scores
- Query DEV and TEST results for the current iteration across all 3 runs per split:
  ```sql
  SELECT METRIC_NAME,
         ROUND(AVG(EVAL_AGG_SCORE) * 100, 1) AS MEAN_SCORE_PCT,
         ROUND(STDDEV(EVAL_AGG_SCORE) * 100, 1) AS STDDEV_PCT,
         COUNT(*) AS N
  FROM (
    SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
      '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_<split>_r1'
    ))
    UNION ALL
    SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
      '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_<split>_r2'
    ))
    UNION ALL
    SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
      '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_<split>_r3'
    ))
  )
  WHERE METRIC_NAME IS NOT NULL
  GROUP BY METRIC_NAME
  ORDER BY METRIC_NAME;
  ```
- Run this query for both `<split>` = `dev` and `<split>` = `test`
- Compute combined scores (UNION ALL of all 6 run results: 3 DEV + 3 TEST)

## Step 2: Apply Acceptance Criteria
- Compute TEST mean improvement (delta) vs the last accepted iteration's TEST mean
- Compare to previous accepted iteration's TEST mean and stddev
- Rules:
  - **ACCEPT** if: TEST mean improves AND the improvement exceeds 1 stddev of the current iteration's TEST scores (signal > noise)
  - **ACCEPT (marginal)** if: TEST mean improves but within 1 stddev — accept only if DEV improvement is strong and consistent across all 3 runs (all 3 DEV runs individually improved)
  - **REJECT** if: TEST mean regresses by any amount — this is an overfitting signal

## Step 3: Present Recommendation

**⚠️ STOP (supervised mode):** Present the accept/reject recommendation with full data. In autonomous mode: proceed with the recommendation automatically.
- DEV scores (mean ± stddev) + delta vs previous
- TEST scores (mean ± stddev) + delta vs previous
- Combined scores + delta vs previous
- TEST mean comparison with significance assessment (the deciding metric)
- Recommendation: ACCEPT, ACCEPT (marginal), or REJECT with reasoning

Wait for user confirmation (supervised mode only).

## Step 4: Finalize Decision
- **If ACCEPT:**
  - Update `optimization_log.md` — mark iteration as accepted, record final scores
  - Note this as the new "last accepted iteration" for future comparisons
  - Snapshot current `agent/*.md` files to `<WORKSPACE_ROOT>/<AGENT_DIR>/snapshots/<ITER_NAME>/`
  - Reset the consecutive-rejection counter to 0
- **If REJECT:**
  - Update `optimization_log.md` — mark iteration as rejected with reason
  - Increment the consecutive-rejection counter (tracked in `optimization_log.md` metadata)
  - If counter reaches 3: **stop the optimization loop entirely**. Report remaining failures, summarize what was tried across all rejected iterations, and recommend whether architectural changes are needed
  - Restore `agent/*.md` files from the last accepted snapshot in `<WORKSPACE_ROOT>/<AGENT_DIR>/snapshots/` (the most recent accepted `<ITER_NAME>/` directory, or `baseline/` if no iterations have been accepted)
  - Rebuild and redeploy with reverted instructions

## Step 5: Cumulative Summary
- Update the summary section of the optimization log:

```markdown
## Summary: Baseline → Iter N

| Metric | Baseline Combined | Current Combined | Delta |
|--------|------------------|-----------------|-------|
| [metric_1] | X% | Y% | +/-Z |
| [metric_2] | X% | Y% | +/-Z |
```

- Add key learnings from this iteration to the log

**Target length:** ~120-150 lines.
