# Test Fixture — Agent Optimization Skill

Fill in the values below to test the `cortex-agent-optimization` skill against your own Snowflake Cortex Agent and eval dataset.

---

## Parameter Values

| Parameter | Value | Description |
|-----------|-------|-------------|
| `<AGENT_FQN>` | | Fully qualified agent name: `DATABASE.SCHEMA.AGENT_NAME` |
| `<DATABASE>` | | Agent database |
| `<SCHEMA>` | | Agent schema |
| `<AGENT_NAME>` | | Agent name (no qualifiers) |
| `<CONNECTION>` | | Snowflake CLI connection name |
| `<STAGE_PATH>` | | Stage path for eval configs: `@DATABASE.SCHEMA.STAGE_NAME` |
| `<OUTPUT_DIR>` | | Directory for generated files (convention: `DATABASE_SCHEMA_AGENTNAME/`) |
| `<DEV_DATASET_NAME>` | | DEV eval dataset name (convention: `AGENTNAME_dev_ds_v1`) |
| `<TEST_DATASET_NAME>` | | TEST eval dataset name (convention: `AGENTNAME_test_ds_v1`) |
| `<EVAL_TABLE>` | | Fully qualified eval table: `DATABASE.SCHEMA.TABLE_NAME` |
| `<CLI_TOOL>` | | CLI tool for SQL execution (e.g., `snow`) |
| `<METRICS>` | | Eval metrics (default: `answer_correctness, logical_consistency`) |
| `<EXECUTION_MODE>` | | `supervised` or `autonomous` |

---

## Prerequisites Checklist

Before testing, verify:

- [ ] Agent is deployed and responds to queries
- [ ] Eval table exists with columns: `TEST_ID`, `TEST_CATEGORY`, `INPUT_QUERY`, `GROUND_TRUTH`, `SPLIT`
- [ ] Ground truth includes `ground_truth_output` (required) and optionally `ground_truth_invocations`
- [ ] A Snowflake stage exists for uploading eval config YAMLs
- [ ] `snow` CLI (or equivalent) is installed with the named connection configured
- [ ] Python 3.11+ is available (for the build script)
- [ ] Refer to `cortex-agent-optimization/references/agent-template/` for template examples and `test-fixture-example/` for a working build script example

---

## Eval Dataset Profile

Run these queries to profile your eval dataset before testing:

**Summary:**
```sql
SELECT COUNT(*) AS TOTAL_QUESTIONS,
       COUNT(DISTINCT TEST_CATEGORY) AS CATEGORIES,
       COUNT_IF(SPLIT = 'TRAIN') AS DEV_COUNT,
       COUNT_IF(SPLIT = 'VALIDATION') AS TEST_COUNT
FROM <EVAL_TABLE>;
```

**Category distribution:**
```sql
SELECT TEST_CATEGORY,
       COUNT(*) AS TOTAL,
       COUNT_IF(SPLIT = 'TRAIN') AS DEV_COUNT,
       COUNT_IF(SPLIT = 'VALIDATION') AS TEST_COUNT,
       ROUND(COUNT_IF(SPLIT = 'TRAIN') / NULLIF(COUNT(*), 0), 2) AS DEV_RATIO
FROM <EVAL_TABLE>
GROUP BY TEST_CATEGORY
ORDER BY TOTAL DESC;
```

**What to look for:**
- Categories with <3 questions will fail the minimum coverage check during split validation
- Categories with <6 questions cannot achieve ≥3 per split per side — consider merging with related categories
- If no splits are assigned yet (all counts are 0), the eval-data sub-skill's Create Split workflow will be the first test path

---

## Testing Each Sub-Skill

### Setup (`setup/SKILL.md`)

| Step | What to verify |
|------|---------------|
| Step 1 (Discover Agent) | `DESCRIBE AGENT` succeeds, spec is extracted |
| Step 2 (Source-of-Truth) | `agent/*.md` files and `spec_base.json` are created; baseline snapshot saved |
| Step 3 (Build Script) | `build_agent_spec.py` generated, `--dry-run` produces valid spec JSON |
| Step 4 (Eval Data) | Table detected, routes to eval-data sub-skill if splits not assigned |
| Step 7 (Baseline) | 3 runs per split complete, baseline scores recorded with mean ± stddev |

### Eval Data (`eval-data/SKILL.md`)

| Workflow | What to verify |
|----------|---------------|
| A (Create Split) | Stratified assignment per category; small categories flagged; UPDATE SQL generated |
| B (Validate) | PASS/WARN/FAIL per category; overall balance checked |
| C (Re-balance) | Specific TEST_ID moves proposed; before/after distribution shown |

### Optimize (`optimize/SKILL.md`)

| Step | What to verify |
|------|---------------|
| Step 2 (DEV Eval) | 3 sequential runs complete; dataset version lock handled between runs |
| Step 3 (Analyze) | Cross-run aggregation with AVG/STDDEV; high-confidence vs noise failures distinguished |
| Step 4 (Classify) | Decision tree applied in order; each failure gets exactly one classification |
| Step 5 (Edit) | Snapshot verified before editing; changes are small and targeted |
| Steps 7-8 (Re-eval) | 3 runs each; mean comparison used for regression check |

### Review (`review/SKILL.md`)

| Step | What to verify |
|------|---------------|
| Step 1 (Scores) | Mean ± stddev computed across 3 runs per split |
| Step 2 (Criteria) | Improvement > 1 stddev = ACCEPT; within stddev = marginal; regression = REJECT |
| Step 4 (Finalize) | Accept: snapshot saved; Reject: files restored from last accepted snapshot |
| Termination | 3 consecutive rejections stops the loop |
