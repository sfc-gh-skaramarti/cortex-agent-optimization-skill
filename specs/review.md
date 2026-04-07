---
section: "4.4"
title: "review/SKILL.md — Accept/Reject Decision"
parent_spec: "../cortex-agent-eval-optimizer-spec.md"
---

# Accept/Reject Decision Contract

**Frontmatter:**

```yaml
---
name: cortex-agent-eval-optimizer-review
description: "Review iteration results and make accept/reject decision."
parent_skill: cortex-agent-eval-optimizer
---
```

**Workflow (5 steps):**

## Step 1: Compute Per-Run Means
- Read `optimization_log.md` to identify the previous accepted iteration name (or `baseline`)
- Query per-run means separately for current iter and previous accepted iter — one query per run (`<ITER_NAME>_dev_r1` through `<ITER_NAME>_dev_r<RUNS_PER_SPLIT>`), do NOT union together
- Repeat for TEST split and for previous accepted iteration's runs
- Produce a paired difference table: run | metric | iter_mean | prev_mean | diff
- Also compute aggregate mean ± stddev across all `<RUNS_PER_SPLIT>` runs for display

## Step 2: Apply Acceptance Criteria
- For each metric, compute the paired t-statistic from the `<RUNS_PER_SPLIT>` per-run TEST differences:
  ```
  d_i = iter_test_r_i_mean - prev_test_r_i_mean
  t = mean(d) / (stddev(d) / sqrt(RUNS_PER_SPLIT))
  ```
- Compare t against the one-sided critical value (α=0.10): df=2→−1.886, df=3→−1.638, df=4→−1.533, df=5→−1.476, df=7→−1.415, df=9→−1.383
- **ACCEPT** if t ≥ critical value for all metrics
- **REJECT** if t < critical value for any metric

## Step 3: Present Recommendation

**⚠️ STOP (supervised mode):** Present the accept/reject recommendation with full data. In autonomous mode: proceed with the recommendation automatically.
- DEV scores (mean ± stddev) + delta vs previous
- TEST scores (mean ± stddev) + delta vs previous
- Per-run paired differences and t-statistics for each TEST metric
- Recommendation: ACCEPT or REJECT with t-statistic and critical value

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
