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

**Example workflow for 3-run sequence:**

```
1. Start run 1 with run_name '<ITER_NAME>_dev_r1'
2. Poll with query above until COMPLETED_METRICS > 0
3. Start run 2 with run_name '<ITER_NAME>_dev_r2'
4. Poll until complete
5. Start run 3 with run_name '<ITER_NAME>_dev_r3'
6. Poll until complete
7. Proceed to aggregation
```

**Troubleshooting:**

If an eval appears stuck (polling returns 0 for 10+ minutes):
1. Check Snowflake query history for the `EXECUTE_AI_EVALUATION` call
2. Look for errors in the query output
3. If the query succeeded but scoring didn't start, the dataset version lock may be stale
4. See `eval-setup.md` for lock troubleshooting steps
