---
section: "4.2"
title: "setup/SKILL.md — Project Scaffolding"
parent_spec: "../cortex-agent-optimization-spec.md"
---

# Setup Workflow Contract

**Frontmatter:**

```yaml
---
name: cortex-agent-optimization-setup
description: "Scaffold an optimization project for a Cortex Agent."
parent_skill: cortex-agent-optimization
---
```

**Workflow (7 steps):**

## Step 1: Discover Agent and Workspace
- Ask user for:
  - Agent fully-qualified name (`<DATABASE>.<SCHEMA>.<AGENT_NAME>`)
  - Snowflake connection name
  - **Workspace directory** (required, no CWD default) — prompt: "Where should I create the optimization project?"
- Validate workspace is NOT inside the skill directory
- Detect workspace mode:
  - If `<WORKSPACE_ROOT>/scripts/build_agent_spec.py` exists → multi-agent workspace
  - Otherwise → single-agent project
- If multi-agent detected, ask for agent subdirectory name (default: lowercase agent name)
- Run `DESCRIBE AGENT <AGENT_FQN>` to confirm it exists and retrieve current spec
- Extract current instructions and tool configuration

**⚠️ STOP**: Confirm agent details and workspace setup with user.

## Step 2: Create Source-of-Truth Directory
- Create `<WORKSPACE_ROOT>/<AGENT_DIR>/agent/` directory with markdown files extracted from the current spec:
  - `orchestration_instructions.md` — from `spec.instructions.orchestration`
  - `response_instructions.md` — from `spec.instructions.response`
  - `tool_descriptions.md` — from `spec.tools[].tool_spec.description` (one `## Tool: <name>` section per tool)
  - `spec_base.json` — everything except instructions and tool descriptions (models, budget, tool types, tool_resources)
- Snapshot the baseline: copy all `agent/*.md` and `agent/spec_base.json` to `<WORKSPACE_ROOT>/<AGENT_DIR>/snapshots/baseline/`

## Step 3: Create Build Script
- If multi-agent workspace and `<WORKSPACE_ROOT>/scripts/build_agent_spec.py` exists, skip creation (reuse shared script)
- Otherwise, create `<WORKSPACE_ROOT>/scripts/build_agent_spec.py` that:
  - Reads `<WORKSPACE_ROOT>/<AGENT_DIR>/agent/*.md` files and `agent/spec_base.json`
  - Strips HTML comments and top-level headings from markdown
  - Parses `tool_descriptions.md` into per-tool description strings
  - Assembles the full spec JSON
  - Generates `ALTER AGENT <AGENT_FQN> MODIFY LIVE VERSION SET SPECIFICATION = $$...$$;`
  - Writes to `<WORKSPACE_ROOT>/<AGENT_DIR>/deploy.sql`
  - Supports `--dry-run` (stdout) and `--json` (spec only) flags
  - For multi-agent: reads agent config from metadata.yaml to determine paths
- The agent FQN should be configurable (constant at top of script or via argument)

## Step 4: Create Eval Data
- Detect existing split values in eval table if data present:
  - If 2 distinct values found: ask user which is DEV and which is TEST
  - If 0-1 values: ask user to choose convention (TRAIN/VALIDATION, DEV/TEST, or custom)
  - If 3+ values: error - invalid structure, user must fix
  - Store chosen values as `<DEV_SPLIT_VALUE>` and `<TEST_SPLIT_VALUE>`
- Guide user to create an evaluation table with columns:
  - `TEST_ID` (NUMBER) — unique question identifier
  - `TEST_CATEGORY` (VARCHAR) — question category for analysis
  - `INPUT_QUERY` (VARCHAR) — the question to ask the agent
  - `GROUND_TRUTH` (OBJECT) — containing:
    - `ground_truth_invocations`: array of `{tool_name, tool_sequence, description}` (optional)
    - `ground_truth_output`: expected answer text
  - `SPLIT` (VARCHAR) — DEV split value or TEST split value
- Guide split assignment: ~45% DEV, ~55% TEST, stratified across categories
- For automated stratified split assignment and validation, load `eval-data/SKILL.md`
- Create views filtering on detected/chosen split values

**⚠️ STOP**: Review eval questions and split with user.

## Step 5: Create Eval Configs
- Generate two YAML files and upload to a Snowflake stage:

**`eval_config_dev.yaml`:**
```yaml
dataset:
  dataset_type: "cortex agent"
  table_name: "<DATABASE>.<SCHEMA>.AGENT_EVAL_DEV"
  dataset_name: "<AGENT_NAME>_dev_ds_v1"
  column_mapping:
    query_text: "INPUT_QUERY"
    ground_truth: "GROUND_TRUTH"

evaluation:
  agent_params:
    agent_name: "<AGENT_FQN>"
    agent_type: "CORTEX AGENT"
  run_params:
    label: "evaluation"
    description: "Evaluation of <AGENT_NAME> — DEV split"
  source_metadata:
    type: "dataset"
    dataset_name: "<AGENT_NAME>_dev_ds_v1"

metrics:
  - "answer_correctness"
  - "logical_consistency"
```

**`eval_config_test.yaml`:** Same structure, pointing at the TEST view and dataset name.

- Upload both to `@<DATABASE>.<SCHEMA>.<EVAL_STAGE>/`

## Step 6: Create Metadata and Log
- Create `<WORKSPACE_ROOT>/<AGENT_DIR>/metadata.yaml`:
  ```yaml
  database: <DATABASE>
  schema: <SCHEMA>
  name: <AGENT_NAME>
  workspace_root: <WORKSPACE_ROOT>
  workspace_type: "single" | "multi"
  agent_dir: <AGENT_DIR> | "."
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
- Initialize `<WORKSPACE_ROOT>/<AGENT_DIR>/optimization_log.md` with a `# Optimization Log` heading, a `## Baseline` section, and iteration table template:
  ```markdown
  | Metric | DEV Mean (N=X) | DEV StdDev | TEST Mean (N=Y) | TEST StdDev | Combined Mean |
  ```

## Step 7: Run Baseline Eval
- Build and deploy current instructions (to confirm the pipeline works)
- Run DEV eval 3 times (`baseline_dev_r1`, `baseline_dev_r2`, `baseline_dev_r3`) — runs must be sequential due to dataset version locks
- Run TEST eval 3 times (`baseline_test_r1`, `baseline_test_r2`, `baseline_test_r3`)
- Compute mean and stddev per metric across the 3 runs for each split
- Record baseline mean scores and stddev in `optimization_log.md`

**⚠️ STOP**: Present baseline scores (mean ± stddev), confirm pipeline works end-to-end.

**Target length:** ~160-190 lines.
