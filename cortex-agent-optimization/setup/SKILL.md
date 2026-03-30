---
name: cortex-agent-optimization-setup
description: "Scaffold an optimization project for a Cortex Agent."
parent_skill: cortex-agent-optimization
---

## Step 1: Discover Agent and Workspace

**Check for existing project:** If `<WORKSPACE_ROOT>/<AGENT_DIR>/agent/` directory already exists, warn the user that a project has been scaffolded. Ask whether to re-scaffold (overwrite) or skip to a specific step.

Collect parameters from the user:
- Agent fully-qualified name (`<DATABASE>.<SCHEMA>.<AGENT_NAME>`)
- Snowflake connection name (`<CONNECTION>`)
- CLI tool for SQL execution (`<CLI_TOOL>`, default: `snow`)
- Execution mode (`<EXECUTION_MODE>`: `supervised` or `autonomous`, default: `supervised`)
- **Workspace directory (`<WORKSPACE_ROOT>`, required)** — prompt: "Where should I create the optimization project?" No default to CWD.

**Validate workspace:** Ensure `<WORKSPACE_ROOT>` is NOT inside the skill directory.

**Detect workspace mode:**
- If `<WORKSPACE_ROOT>/scripts/build_agent_spec.py` exists → multi-agent workspace detected
  - Ask for agent subdirectory name (`<AGENT_DIR>`, default: lowercase `<AGENT_NAME>`)
  - Set `<WORKSPACE_TYPE>` = `"multi"`
- Otherwise → single-agent project
  - Set `<AGENT_DIR>` = `.`
  - Set `<WORKSPACE_TYPE>` = `"single"`

Run `DESCRIBE AGENT <AGENT_FQN>` to confirm the agent exists and retrieve its current spec. Extract current instructions and tool configuration from the spec output.

**Detect existing datasets:** Run `SHOW DATASETS IN SCHEMA <DATABASE>.<SCHEMA>`. If datasets matching `<AGENT_NAME>` exist (e.g., `<AGENT_NAME>_dev_ds_v2`), reuse their names. Otherwise default to:
- `<DEV_DATASET_NAME>`: `<AGENT_NAME>_dev_ds_v1`
- `<TEST_DATASET_NAME>`: `<AGENT_NAME>_test_ds_v1`

**⚠️ STOP**: Present extracted agent details (instructions summary, tools list, model config) and workspace setup to the user for confirmation.

## Step 2: Create Source-of-Truth Directory

Create `<WORKSPACE_ROOT>/<AGENT_DIR>/agent/` directory with markdown files extracted from the current spec:
- `orchestration_instructions.md` — from `spec.instructions.orchestration`
- `response_instructions.md` — from `spec.instructions.response`
- `tool_descriptions.md` — from `spec.tools[].tool_spec.description` (one `## Tool: <name>` section per tool)
- `spec_base.json` — everything except instructions and tool descriptions (models, budget, tool types, tool_resources)

Snapshot the baseline: copy all `agent/*.md` and `agent/spec_base.json` to `<WORKSPACE_ROOT>/<AGENT_DIR>/snapshots/baseline/`.

## Step 3: Create Build Script

**If multi-agent workspace and `<WORKSPACE_ROOT>/scripts/build_agent_spec.py` exists, skip creation** (reuse shared script).

Otherwise, create `<WORKSPACE_ROOT>/scripts/build_agent_spec.py` that:
- For single-agent: Reads `<WORKSPACE_ROOT>/agent/*.md` files and `<WORKSPACE_ROOT>/agent/spec_base.json`
- For multi-agent: Reads agent-specific paths from `metadata.yaml`
- Strips HTML comments and top-level headings from markdown
- Parses `tool_descriptions.md` into per-tool description strings (split on `## Tool: <name>`)
- Assembles the full spec JSON
- Generates `ALTER AGENT <AGENT_FQN> MODIFY LIVE VERSION SET SPECIFICATION = $$...$$;`
- Writes to `<WORKSPACE_ROOT>/<AGENT_DIR>/deploy.sql`
- Supports `--dry-run` (stdout) and `--json` (spec only) flags

The agent FQN should be configurable (constant at top of script or via `--agent` argument for multi-agent).

**Validation:** Refer to `references/agent-template/` for example template files, or `test-fixture-example/` for a complete working validation setup with build script.

## Step 4: Create Eval Data

Guide the user to create an evaluation table. Ask if they already have one or need to create it.

**Detect existing split values (REQUIRED FIRST STEP if table has data):**

If the eval table already exists and has data, run:
```sql
SELECT DISTINCT SPLIT 
FROM <EVAL_TABLE> 
WHERE SPLIT IS NOT NULL 
ORDER BY SPLIT;
```

Interpret results:

- **Exactly 2 distinct values returned:**
  Ask user: "Found split values '<VALUE1>' and '<VALUE2>'. Which is DEV and which is TEST?"
  Set `<DEV_SPLIT_VALUE>` and `<TEST_SPLIT_VALUE>` based on response.

- **0 or 1 values returned:** Splits not assigned yet.
  Ask user to choose split value convention:
  - Option A (default): `'TRAIN'` (DEV) / `'VALIDATION'` (TEST)
  - Option B: `'DEV'` (DEV) / `'TEST'` (TEST)
  - Option C: Custom values (user specifies)
  Set `<DEV_SPLIT_VALUE>` and `<TEST_SPLIT_VALUE>` accordingly.
  Proceed to split assignment (load `eval-data/SKILL.md` Create Split workflow).

- **3+ values returned:** ERROR
  Show: "Found invalid SPLIT values: [list values]. Eval table must have exactly 2 split values. Please fix and re-run."
  STOP - user must clean data.

**If creating new:** Generate SQL for the eval table (see `references/eval-setup.md` for schema). Guide the user to populate it with evaluation questions. Each row needs:
- `TEST_ID` — unique identifier
- `TEST_CATEGORY` — category for stratified analysis
- `INPUT_QUERY` — the question to ask the agent
- `GROUND_TRUTH` — `OBJECT_CONSTRUCT('ground_truth_invocations', PARSE_JSON('[...]'), 'ground_truth_output', '...')`
- `SPLIT` — `<DEV_SPLIT_VALUE>` (DEV) or `<TEST_SPLIT_VALUE>` (TEST)

**For advanced dataset creation options:**
- Production data extraction and annotation → See bundled `dataset-curation` skill (Option B)
- Agent Events Explorer (Streamlit UI) → See bundled `dataset-curation` skill, launches interactive browser for event annotation
- Format conversion from existing tables → See bundled `dataset-curation` skill (Option C)

Note: Bundled skill creates OBJECT-type GROUND_TRUTH columns; this skill uses OBJECT columns for ground truth. Ensure format compatibility.

For split assignment (~45% DEV, ~55% TEST, stratified by category), load `eval-data/SKILL.md` and run its Create Split workflow.

Create views for each split:
```sql
CREATE OR REPLACE VIEW <DATABASE>.<SCHEMA>.AGENT_EVAL_DEV AS
SELECT * FROM <EVAL_TABLE> WHERE SPLIT = '<DEV_SPLIT_VALUE>';

CREATE OR REPLACE VIEW <DATABASE>.<SCHEMA>.AGENT_EVAL_TEST AS
SELECT * FROM <EVAL_TABLE> WHERE SPLIT = '<TEST_SPLIT_VALUE>';
```

**⚠️ STOP**: Review eval questions and split distribution with the user.

## Step 5: Create Eval Configs

Generate two YAML eval config files using the template in `references/eval-setup.md`:
- **`eval_config_dev.yaml`**: Points at `<DATABASE>.<SCHEMA>.AGENT_EVAL_DEV`, dataset name `<DEV_DATASET_NAME>`.
- **`eval_config_test.yaml`**: Points at `<DATABASE>.<SCHEMA>.AGENT_EVAL_TEST`, dataset name `<TEST_DATASET_NAME>`.

Write both to `<WORKSPACE_ROOT>/<AGENT_DIR>/` locally. Ask the user for the stage path (`<STAGE_PATH>`), then upload:
```sql
PUT 'file://<WORKSPACE_ROOT>/<AGENT_DIR>/eval_config_dev.yaml' <STAGE_PATH>/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
PUT 'file://<WORKSPACE_ROOT>/<AGENT_DIR>/eval_config_test.yaml' <STAGE_PATH>/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
```

## Step 6: Create Metadata and Log

Create `<WORKSPACE_ROOT>/<AGENT_DIR>/metadata.yaml`:
```yaml
database: <DATABASE>
schema: <SCHEMA>
name: <AGENT_NAME>
workspace_root: <WORKSPACE_ROOT>
workspace_type: <WORKSPACE_TYPE>
agent_dir: <AGENT_DIR>
connection: <CONNECTION>
cli_tool: <CLI_TOOL>
stage_path: <STAGE_PATH>
dev_dataset_name: <DEV_DATASET_NAME>
test_dataset_name: <TEST_DATASET_NAME>
eval_table: <EVAL_TABLE>
dev_split_value: <DEV_SPLIT_VALUE>
test_split_value: <TEST_SPLIT_VALUE>
execution_mode: <EXECUTION_MODE>
```

Initialize `<WORKSPACE_ROOT>/<AGENT_DIR>/optimization_log.md`:
```markdown
# Optimization Log

**Agent:** <AGENT_FQN>
**Consecutive rejections:** 0

## Baseline

| Metric | DEV Mean (N=X) | DEV StdDev | TEST Mean (N=Y) | TEST StdDev | Combined Mean |
|--------|----------------|------------|-----------------|-------------|---------------|
```

## Step 7: Run Baseline Eval

Build and deploy current instructions to confirm the pipeline works:
```bash
python <WORKSPACE_ROOT>/scripts/build_agent_spec.py
<CLI_TOOL> sql --connection <CONNECTION> --filename <WORKSPACE_ROOT>/<AGENT_DIR>/deploy.sql
```

Run DEV eval 3 times sequentially (`baseline_dev_r1`, `baseline_dev_r2`, `baseline_dev_r3`):
```sql
CALL EXECUTE_AI_EVALUATION(
  'START',
  OBJECT_CONSTRUCT('run_name', 'baseline_dev_r1'),
  '<STAGE_PATH>/eval_config_dev.yaml'
);
-- Wait for completion, then run r2, then r3
```

Each run must complete (including scoring) before the next starts. 

**Polling tip:** See `references/eval-polling.md` for a status check query to monitor completion instead of estimating wait times.

If "Dataset version already exists" error occurs, wait 2-3 minutes and retry. If persists 5+ min with no eval running, clear the stale lock per `references/eval-setup.md`.

Run TEST eval 3 times sequentially (`baseline_test_r1`, `baseline_test_r2`, `baseline_test_r3`).

Compute mean and stddev per metric across the 3 runs for each split using the aggregation query pattern from `optimize/SKILL.md` Step 3 (UNION ALL of 3 runs, GROUP BY METRIC_NAME, AVG + STDDEV of EVAL_AGG_SCORE). Run for both DEV and TEST. Record baseline scores in `optimization_log.md`.

**⚠️ STOP**: Present baseline scores (mean ± stddev for each split), confirm pipeline works end-to-end. The optimization project is now ready. Continue to `optimize/SKILL.md` for the first iteration.
