# Eval Completion Polling

Use this query to check if an eval run has completed (including scoring phase):

```sql
SELECT 
  COUNT(*) AS COMPLETED_METRICS,
  ARRAY_AGG(DISTINCT METRIC_NAME) AS METRICS_FOUND
FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
  '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<RUN_NAME>'
))
WHERE METRIC_NAME IS NOT NULL;
```

**Interpretation:**
- `COMPLETED_METRICS = 0`: Eval not started or scoring not complete yet
- `COMPLETED_METRICS > 0`: Scoring is done, next run can start
- `METRICS_FOUND` should match configured metrics (e.g., `['answer_correctness', 'logical_consistency']`)

**Polling Pattern:**

After starting a run, poll every 30-60 seconds until `COMPLETED_METRICS > 0`.

**Expected timing:**
- Small eval (<20 questions): 2-3 min per run
- Medium eval (20-50 questions): 3-5 min per run  
- Large eval (50+ questions): 5-10 min per run

**Example workflow for `<RUNS_PER_SPLIT>`-run sequence:**

```
1. Fire all <RUNS_PER_SPLIT> runs simultaneously, each with its own slot config
2. Poll with the parallel polling pattern below until all slots complete
3. Proceed to aggregation
```

**Parallel Polling Pattern:**

Use a single UNION ALL query to check all N runs at once:

```sql
-- Repeat one SELECT block per run through r<RUNS_PER_SPLIT>
SELECT '<ITER_NAME>_dev_r1' AS RUN_NAME, COUNT(*) AS COMPLETED_METRICS
FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
  '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_dev_r1'
)) WHERE METRIC_NAME IS NOT NULL
UNION ALL
SELECT '<ITER_NAME>_dev_r2', COUNT(*)
FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
  '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_dev_r2'
)) WHERE METRIC_NAME IS NOT NULL;
-- ... add one block per run through r<RUNS_PER_SPLIT>
```

**Interpretation:** All runs are complete when every row in the result has `COMPLETED_METRICS > 0`. Any row with `COMPLETED_METRICS = 0` means that slot is still scoring — keep polling. Poll every 30-60 seconds.

## Polling Implementation Strategy

**Recommended: Inline SQL polling**
- Use `snowflake_sql_execute` in a loop with 2-minute waits between polls
- Pros: Session managed automatically, cross-platform compatible
- Cons: Blocks other work during polling period (use for <50 questions)
- **When to use:** Default choice for all eval polling

**Not recommended: Background bash script**
- Pros: Non-blocking, allows parallel work
- Cons: Session token expiry issues, harder to debug, platform-dependent
- **When to use:** Only if you need to work on other tasks during a long eval (50+ questions)

**Example inline polling loop:**
```sql
-- Poll every 2 minutes until all runs complete
-- Pseudo-code (implement in actual tool):
LOOP:
  SELECT run_name, COUNT(*) as completed
  FROM (/* UNION ALL of all runs */)
  WHERE METRIC_NAME IS NOT NULL;
  
  IF all runs have completed > 0:
    BREAK
  ELSE:
    WAIT 120 seconds
    CONTINUE
END LOOP
```

**Session token management:**
- Inline SQL: Tokens auto-refreshed by snowflake_sql_execute tool
- Background bash: Tokens expire after ~10 minutes, causing "invalid session" errors

**Troubleshooting:**

If an eval appears stuck (polling returns 0 for 10+ minutes):
1. Check Snowflake query history for the `EXECUTE_AI_EVALUATION` call
2. Look for errors in the query output
3. If the query succeeded but scoring didn't start, the dataset version lock may be stale
4. See `eval-setup.md` for lock troubleshooting steps
