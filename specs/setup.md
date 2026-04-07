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
  - **Execution mode** (`<EXECUTION_MODE>`: `supervised` or `autonomous`, default: `supervised`)
  - **`<RUNS_PER_SPLIT>`** — number of eval runs per split per iteration. After detecting eval dataset size (Step 4), recommend based on question count: <20 → 6, 20–50 → 4, 50–100 → 3 (default), >100 → 3. Present recommendation; user may override.
- Load `<WORKSPACE_ROOT>/<AGENT_DIR>/DEPLOYMENT_INSTRUCTIONS.md` if it exists, for project-specific workflow details
- Validate workspace is NOT inside the skill directory
- Detect workspace mode:
  - If `<WORKSPACE_ROOT>/scripts/build_agent_spec.py` exists → multi-agent workspace
  - Otherwise → single-agent project
- If multi-agent detected, ask for agent subdirectory name (default: lowercase agent name)
- Run `cortex agents describe <AGENT_FQN>` (CLI, not SQL) to retrieve current spec; fall back to `snow sql` if unavailable
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
- Generate `<RUNS_PER_SPLIT>` YAML files per split (`eval_config_dev_r1.yaml` through `eval_config_dev_r<RUNS_PER_SPLIT>.yaml`, and same for TEST), each differing only in `dataset_name` (e.g., `<DEV_DATASET_NAME>_r1` through `_r<RUNS_PER_SPLIT>`)
- Show full template for `_r1`; note "repeat for `_r2` through `_r<RUNS_PER_SPLIT>`" for remaining files
- Upload all `2 × <RUNS_PER_SPLIT>` configs to the stage

- Use the template from `references/eval-setup.md` for `eval_config_dev_r1.yaml`, with `dataset_name: <DEV_DATASET_NAME>_r1` and `table_name` pointing at the DEV view; `eval_config_test_r1.yaml` mirrors it for the TEST view

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
  runs_per_split: <RUNS_PER_SPLIT>
  ```
- Initialize `<WORKSPACE_ROOT>/<AGENT_DIR>/optimization_log.md` with a `# Optimization Log` heading, a `## Baseline` section, and iteration table template:
  ```markdown
  | Metric | DEV Mean (N=X) | DEV StdDev | TEST Mean (N=Y) | TEST StdDev | Combined Mean |
  ```

## Step 7: Run Baseline Eval
- Build and deploy current instructions (to confirm the pipeline works)
- Fire all `<RUNS_PER_SPLIT>` DEV baseline runs simultaneously, each using its slot config (`eval_config_dev_r1.yaml` through `eval_config_dev_r<RUNS_PER_SPLIT>.yaml`); poll all in parallel until every slot reports completion
- Fire all `<RUNS_PER_SPLIT>` TEST baseline runs simultaneously using the TEST slot configs; poll all in parallel until all complete
- Compute mean and stddev per metric across all `<RUNS_PER_SPLIT>` runs for each split
- Record baseline mean scores and stddev in `optimization_log.md`

**⚠️ STOP**: Present baseline scores (mean ± stddev), confirm pipeline works end-to-end.

**Target length:** ~160-190 lines.
