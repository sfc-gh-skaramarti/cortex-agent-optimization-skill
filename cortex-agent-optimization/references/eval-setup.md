# Eval Setup

## Split Strategy

- **DEV (~45%)**: Rapid feedback loop — run every iteration to analyze failures and guide instruction changes.
- **TEST (~55%)**: Held-out generalization check — run only after DEV is satisfactory. Used solely for the aggregate accept/reject decision.
- Stratify across question categories (ensure each category has representation in both splits).
- SPLIT column values: `<DEV_SPLIT_VALUE>` (default `'TRAIN'`) for DEV, `<TEST_SPLIT_VALUE>` (default `'VALIDATION'`) for TEST. If the table already has splits assigned, detect the existing values and use them (e.g., `'DEV'`/`'TEST'`).

**CRITICAL: Never examine TEST failure details to guide instruction changes.** TEST is the held-out set. Looking at TEST failures before finalizing changes = training on the test set = overfitting. Only use TEST for the aggregate accept/reject decision.

## Eval Table Schema

```sql
CREATE TABLE IF NOT EXISTS <EVAL_TABLE> (
    TEST_ID       NUMBER(38,0),
    TEST_CATEGORY VARCHAR,
    INPUT_QUERY   VARCHAR,
    GROUND_TRUTH  OBJECT,
    SPLIT         VARCHAR DEFAULT <TEST_SPLIT_VALUE>
);
```

## Ground Truth Format

```sql
OBJECT_CONSTRUCT(
  'ground_truth_invocations', PARSE_JSON('[
    {"tool_name": "<TOOL>", "tool_sequence": 1, "description": "..."}
  ]'),
  'ground_truth_output', '<expected answer text>'
)
```

- `ground_truth_invocations` is optional but improves `logical_consistency` scoring.
- `ground_truth_output` is required.

## Eval Config YAML Template

```yaml
dataset:
  dataset_type: "cortex agent"
  table_name: "<DATABASE>.<SCHEMA>.<VIEW_NAME>"
  dataset_name: "<DATASET_NAME>"
  column_mapping:
    query_text: "INPUT_QUERY"
    ground_truth: "GROUND_TRUTH"

evaluation:
  agent_params:
    agent_name: "<AGENT_FQN>"
    agent_type: "CORTEX AGENT"
  run_params:
    label: "evaluation"
    description: "<description>"
  source_metadata:
    type: "dataset"
    dataset_name: "<DATASET_NAME>"

metrics:
  - "answer_correctness"
  - "logical_consistency"
```

## Available Metrics

- `answer_correctness` — factual accuracy of the agent's response vs ground truth.
- `logical_consistency` — whether the agent's reasoning and tool usage is logically sound.

## Multiple Runs per Evaluation

Each eval (DEV or TEST) runs **3 times** per iteration to capture model response variance.

- **Why:** The same question can receive a correct answer on one run and an incorrect answer on another due to non-deterministic generation. A single run gives a point estimate with unknown variance.
- **Run naming:** `<ITER_NAME>_<split>_r1`, `<ITER_NAME>_<split>_r2`, `<ITER_NAME>_<split>_r3`
- **Execution:** Runs must be sequential — the dataset version lock prevents parallel execution. Wait for each run to complete (including scoring phase) before starting the next.
- **Aggregation:** Compute `AVG` and `STDDEV` of per-question `EVAL_AGG_SCORE` across all 3 runs (UNION ALL of the 3 result sets, then GROUP BY METRIC_NAME).
- **Failure analysis:** A question that fails in all 3 runs is a high-confidence failure. A question that fails in 1 of 3 runs is likely noise and should generally not drive instruction changes.
- **Lock implications:** 3 sequential runs means 3x the chance of hitting a stale version lock. Follow the troubleshooting guide below for each occurrence.

## Dataset Version Lock Troubleshooting

If `EXECUTE_AI_EVALUATION` fails with "Dataset version SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE already exists":

1. Wait 2-3 minutes — a previous eval's scoring phase may still be running.
2. If still failing after 5+ min, check for running evals in the UI or via query history.
3. If no eval is running, the lock is stale — clear it:
   ```sql
   ALTER DATASET <DATABASE>.<SCHEMA>.<DATASET_NAME>
   DROP VERSION 'SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE';
   ```
4. **NEVER drop the dataset itself** — this destroys all historical eval results. Only drop the stale version lock.
