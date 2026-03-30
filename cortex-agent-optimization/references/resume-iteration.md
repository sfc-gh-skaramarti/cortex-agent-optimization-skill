# Resuming Interrupted Iterations

If an optimization iteration is interrupted (network issue, timeout, stale version lock), use this workflow to resume from the last checkpoint.

## Step 1: Identify Iteration State

Check what completed:

```sql
-- Check which DEV runs completed
SELECT '<ITER_NAME>_dev_r1' AS RUN_NAME, COUNT(*) AS COMPLETED
FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
  '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_dev_r1'
)) WHERE METRIC_NAME IS NOT NULL
UNION ALL
SELECT '<ITER_NAME>_dev_r2', COUNT(*)
FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
  '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_dev_r2'
)) WHERE METRIC_NAME IS NOT NULL
UNION ALL
SELECT '<ITER_NAME>_dev_r3', COUNT(*)
FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
  '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_dev_r3'
)) WHERE METRIC_NAME IS NOT NULL;

-- Repeat for TEST runs (_test_r1, _test_r2, _test_r3)
```

**Interpretation:**
- `COMPLETED = 0`: Run not started or failed
- `COMPLETED > 0`: Run completed successfully

## Step 2: Resume from Checkpoint

| Checkpoint | What Completed | Resume Action |
|-----------|----------------|---------------|
| A | No DEV runs | Start from `optimize/SKILL.md` Step 2 |
| B | DEV r1 only | Continue DEV r2 and r3 |
| C | DEV r1, r2 only | Continue DEV r3 |
| D | All 3 DEV runs | Proceed to Step 3 (failure analysis) |
| E | Analysis done, instructions edited | Rebuild and deploy (Step 6) |
| F | Deployed, no re-eval | Run re-eval DEV (Step 7) |
| G | Re-eval DEV done | Run TEST eval (Step 8) |
| H | TEST r1 only | Continue TEST r2 and r3 |
| I | TEST r1, r2 only | Continue TEST r3 |
| J | All 6 runs done | Proceed to `review/SKILL.md` |

## Step 3: Clear Stale Locks if Needed

If resuming after interruption, check for stale version locks:

```sql
-- If next run fails with "version already exists", clear lock:
ALTER DATASET <DATABASE>.<SCHEMA>.<DEV_DATASET_NAME>
DROP VERSION 'SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE';

-- Repeat for TEST dataset if needed
ALTER DATASET <DATABASE>.<SCHEMA>.<TEST_DATASET_NAME>
DROP VERSION 'SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE';
```

**NEVER drop the dataset itself** — only drop stale version locks.

## Step 4: Document Interruption

Add note to `optimization_log.md`:

```markdown
**Note:** Iteration interrupted at [checkpoint] on [timestamp]. Resumed from [checkpoint] on [timestamp].
```

## Common Interruption Scenarios

### Scenario 1: Network timeout during eval run

**Symptoms:** Eval started but query history shows incomplete

**Action:**
1. Use checkpoint detection query to see which runs completed
2. Clear stale version lock if present
3. Resume from next incomplete run

### Scenario 2: Dataset version lock stuck

**Symptoms:** "Dataset version already exists" error persists for 10+ minutes

**Action:**
1. Check Snowflake query history for running EXECUTE_AI_EVALUATION calls
2. If none running, clear the stale lock with ALTER DATASET ... DROP VERSION
3. Continue from the failed run

### Scenario 3: Iteration paused mid-analysis

**Symptoms:** DEV evals complete but no instruction changes made

**Action:**
1. Re-read `optimization_log.md` to see what was analyzed
2. Continue from Step 4 (classify failures)
3. Complete editing and deployment

### Scenario 4: Deployed but TEST not run

**Symptoms:** Agent deployed, DEV re-eval done, but no TEST runs

**Action:**
1. Verify deployment with `DESCRIBE AGENT <AGENT_FQN>`
2. Check DEV re-eval scores show no regression
3. Proceed to Step 8 (run TEST eval)

## Avoiding Interruptions

**Best practices:**
1. Use polling helper (`references/eval-polling.md`) to monitor progress
2. Set longer timeout_ms for eval SQL calls if network is slow
3. Complete full iterations in one session when possible
4. Save work frequently - commit instruction edits before deploying
