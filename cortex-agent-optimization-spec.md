# Cortex Agent Optimization Skill — Specification

## 1. Overview

| Field | Value |
|-------|-------|
| **Skill name** | `cortex-agent-optimization` |
| **Purpose** | Iterative optimization of Snowflake Cortex Agents using dev/test eval splits. Guides users through editing agent instructions, building/deploying, running evaluations, analyzing failures, and making data-driven accept/reject decisions. |
| **Trigger phrases** | optimize agent, agent eval, improve agent, agent iteration, run eval, optimization loop, agent instructions, eval split, run optimization, next iteration, analyze agent failures, accept reject iteration |

---

## 2. Skill Directory Structure

```
cortex-agent-optimization/
├── SKILL.md                              # Entry point: intent detection + routing
├── setup/
│   └── SKILL.md                          # Sub-skill: scaffold optimization project
├── optimize/
│   └── SKILL.md                          # Sub-skill: run a single optimization iteration
├── review/
│   └── SKILL.md                          # Sub-skill: review results, accept/reject
├── eval-data/
│   └── SKILL.md                          # Sub-skill: create, validate, re-balance eval splits
└── references/
    ├── project-structure.md              # Expected project layout conventions
    ├── eval-setup.md                     # Dev/test split methodology + eval config format
    └── optimization-patterns.md          # Distilled learnings: what works, what doesn't
```

No scripts or `pyproject.toml` needed — the skill is pure markdown guidance. The user's own project contains the build script and SQL.

---

## 3. Intent Routing

The top-level `SKILL.md` detects intent and routes to the appropriate sub-skill.

| Intent | Trigger patterns | Route to |
|--------|-----------------|----------|
| **SETUP** | "set up optimization", "scaffold", "initialize optimization", "set up eval" | `setup/SKILL.md` |
| **OPTIMIZE** | "run iteration", "optimize", "improve agent", "next iteration", "run eval", "analyze failures" | `optimize/SKILL.md` |
| **REVIEW** | "review results", "accept or reject", "compare iterations", "check test scores", "finalize iteration" | `review/SKILL.md` |
| **EVAL DATA** | "create eval split", "validate split", "check eval balance", "split quality", "re-balance eval", "eval dataset" | `eval-data/SKILL.md` |

If intent is ambiguous, ask the user which mode they want.

---

## 4. File Contracts

### 4.1 `SKILL.md` — Entry Point

**Frontmatter:**

```yaml
---
name: cortex-agent-optimization
description: >
  Iterative optimization of Snowflake Cortex Agents using dev/test eval splits.
  Covers project setup, instruction editing, build/deploy, eval execution,
  failure analysis, and accept/reject decisions.
  Use when: optimizing agent instructions, running agent evals, improving agent
  accuracy, setting up eval splits, analyzing agent failures.
  Triggers: optimize agent, agent eval, improve agent, agent iteration,
  run eval, optimization loop, agent instructions, eval split.
---
```

**Body sections:**

1. **When to Use** — One paragraph: this skill applies when a user has (or wants to create) a Cortex Agent with markdown-based instructions and wants to iteratively improve it using evaluations with a dev/test split.

2. **Prerequisites** — Bullet list:
   - A deployed Snowflake Cortex Agent (or intent to create one)
   - `snow` CLI installed and a named connection configured
   - Python 3.11+ (for the build script)

3. **Setup** — Load `references/project-structure.md` for context on expected layout.

4. **Intent Detection Table** — The routing table from Section 3 above, with "Load `<sub-skill>` and follow its workflow" directives.

5. **Execution Mode** — Detect or ask whether to run in **supervised** mode (all `⚠️ STOP` gates active, user approves each decision) or **autonomous** mode (stops skipped, Cortex Code runs the full optimization loop until a termination condition is met). Default to supervised if unclear. In autonomous mode, apply stricter acceptance criteria (statistical significance required) and enforce automated termination (3 consecutive rejections = stop and report).

6. **Ctx Rules to Set** — The skill should set these rules on first use:
   - Only analyze DEV failures to make instruction changes; never examine TEST results before deploying
   - Never drop eval datasets; only drop stale version locks
   - Always read optimization log before starting an iteration
   - In autonomous mode, stop after 3 consecutive rejected iterations and report remaining failures as known limitations

**Target length:** ~70-90 lines.

---

### 4.2 `setup/SKILL.md` — Project Scaffolding

**Frontmatter:**

```yaml
---
name: cortex-agent-optimization-setup
description: "Scaffold an optimization project for a Cortex Agent."
parent_skill: cortex-agent-optimization
---
```

**Workflow (7 steps):**

#### Step 1: Discover Agent
- Ask user for: agent fully-qualified name (`<DATABASE>.<SCHEMA>.<AGENT_NAME>`), Snowflake connection name
- Run `DESCRIBE AGENT <AGENT_FQN>` to confirm it exists and retrieve current spec
- Extract current instructions and tool configuration

**⚠️ STOP**: Confirm agent details with user.

#### Step 2: Create Source-of-Truth Directory
- Create `agent/` directory with markdown files extracted from the current spec:
  - `orchestration_instructions.md` — from `spec.instructions.orchestration`
  - `response_instructions.md` — from `spec.instructions.response`
  - `tool_descriptions.md` — from `spec.tools[].tool_spec.description` (one `## Tool: <name>` section per tool)
  - `spec_base.json` — everything except instructions and tool descriptions (models, budget, tool types, tool_resources)
- Snapshot the baseline: copy all `agent/*.md` and `agent/spec_base.json` to `<OUTPUT_DIR>/snapshots/baseline/`

#### Step 3: Create Build Script
- Create `scripts/build_agent_spec.py` that:
  - Reads `agent/*.md` files and `agent/spec_base.json`
  - Strips HTML comments and top-level headings from markdown
  - Parses `tool_descriptions.md` into per-tool description strings
  - Assembles the full spec JSON
  - Generates `ALTER AGENT <AGENT_FQN> MODIFY LIVE VERSION SET SPECIFICATION = $$...$$;`
  - Writes to `<OUTPUT_DIR>/deploy.sql`
  - Supports `--dry-run` (stdout) and `--json` (spec only) flags
- The agent FQN should be configurable (constant at top of script or via argument)

#### Step 4: Create Eval Data
- Guide user to create an evaluation table with columns:
  - `TEST_ID` (NUMBER) — unique question identifier
  - `TEST_CATEGORY` (VARCHAR) — question category for analysis
  - `INPUT_QUERY` (VARCHAR) — the question to ask the agent
  - `GROUND_TRUTH` (OBJECT) — containing:
    - `ground_truth_invocations`: array of `{tool_name, tool_sequence, description}` (optional)
    - `ground_truth_output`: expected answer text
  - `SPLIT` (VARCHAR) — `'TRAIN'` for DEV, `'VALIDATION'` for TEST
- Guide split assignment: ~45% DEV, ~55% TEST, stratified across categories
- For automated stratified split assignment and validation, load `eval-data/SKILL.md`
- Create views: `AGENT_EVAL_DEV` (WHERE SPLIT = 'TRAIN'), `AGENT_EVAL_TEST` (WHERE SPLIT = 'VALIDATION')

**⚠️ STOP**: Review eval questions and split with user.

#### Step 5: Create Eval Configs
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

#### Step 6: Create Metadata and Log
- Create `<OUTPUT_DIR>/metadata.yaml`:
  ```yaml
  database: <DATABASE>
  schema: <SCHEMA>
  name: <AGENT_NAME>
  ```
- Initialize `<OUTPUT_DIR>/optimization_log.md` with a `# Optimization Log` heading, a `## Baseline` section, and iteration table template:
  ```markdown
  | Metric | DEV Mean (N=X) | DEV StdDev | TEST Mean (N=Y) | TEST StdDev | Combined Mean |
  ```

#### Step 7: Run Baseline Eval
- Build and deploy current instructions (to confirm the pipeline works)
- Run DEV eval 3 times (`baseline_dev_r1`, `baseline_dev_r2`, `baseline_dev_r3`) — runs must be sequential due to dataset version locks
- Run TEST eval 3 times (`baseline_test_r1`, `baseline_test_r2`, `baseline_test_r3`)
- Compute mean and stddev per metric across the 3 runs for each split
- Record baseline mean scores and stddev in `optimization_log.md`

**⚠️ STOP**: Present baseline scores (mean ± stddev), confirm pipeline works end-to-end.

**Target length:** ~160-190 lines.

---

### 4.3 `optimize/SKILL.md` — Run an Optimization Iteration

**Frontmatter:**

```yaml
---
name: cortex-agent-optimization-iterate
description: "Run a single optimization iteration: analyze DEV failures, edit instructions, build/deploy, eval."
parent_skill: cortex-agent-optimization
---
```

**Workflow (9 steps):**

#### Step 1: Read Context
- Load `<OUTPUT_DIR>/optimization_log.md` — understand current scores, previous iterations, what's been tried
- Load `<OUTPUT_DIR>/DEPLOYMENT_INSTRUCTIONS.md` (if it exists) for project-specific workflow details
- Ask user for iteration name (e.g., `iter7`) or auto-increment from log

#### Step 2: Run DEV Eval (if not already run)
Run DEV eval 3 times sequentially (dataset version lock prevents parallel runs):
```sql
-- Run 1
CALL EXECUTE_AI_EVALUATION(
  'START',
  OBJECT_CONSTRUCT('run_name', '<ITER_NAME>_dev_r1'),
  '@<STAGE_PATH>/eval_config_dev.yaml'
);
-- Wait for completion, then run 2 and 3 with _r2, _r3 suffixes
```
Each run must complete (including scoring) before the next starts. Wait for the dataset version lock to clear between runs.

- If error "Dataset version already exists": wait 2-3 minutes and retry. If persists 5+ min with no eval running, clear stale lock:
  ```sql
  ALTER DATASET <DATABASE>.<SCHEMA>.<DEV_DATASET_NAME>
  DROP VERSION 'SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE';
  ```
- **NEVER drop the dataset itself** — only the version lock.

#### Step 3: Analyze DEV Failures
- Query results from all 3 DEV runs:
  ```sql
  SELECT METRIC_NAME,
         ROUND(AVG(EVAL_AGG_SCORE) * 100, 1) AS MEAN_SCORE_PCT,
         ROUND(STDDEV(EVAL_AGG_SCORE) * 100, 1) AS STDDEV_PCT,
         COUNT(*) AS N
  FROM (
    SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
      '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_dev_r1'
    ))
    UNION ALL
    SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
      '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_dev_r2'
    ))
    UNION ALL
    SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
      '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<ITER_NAME>_dev_r3'
    ))
  )
  WHERE METRIC_NAME IS NOT NULL
  GROUP BY METRIC_NAME;
  ```
- Filter to questions where **mean** `EVAL_AGG_SCORE` across the 3 runs is `< 1.0`
- Questions that fail in all 3 runs are high-confidence failures; questions that fail in only 1 of 3 are noise candidates — note this distinction in the analysis
- **CRITICAL: Only analyze DEV failures. Do NOT examine TEST results at this stage.**

#### Step 4: Classify Failures
Classify each failure using this ordered decision tree. Evaluate conditions top-to-bottom; the first match is the classification.

1. **Compare actual tool sequence to `ground_truth_invocations`.** If the first tool called differs from ground truth → **Routing error.** Fix: add keyword triggers or negative routing rules to `orchestration_instructions.md`.

2. **Check if any tool call returned an error/exception.** If yes → **Tool error.** Fix: add retry logic to `orchestration_instructions.md` ("retry up to 2x on transient errors before reporting failure").

3. **Compare answer structure to ground truth output.** If the facts are correct but the format/structure doesn't match → **Formatting error.** Fix: add explicit format templates to `response_instructions.md`.

4. **Compare answer content to ground truth output.** If facts are wrong, missing, or incomplete despite correct tool calls → **Content error.** Fix: add domain-specific rules or corrected examples to `response_instructions.md`.

5. **Re-read the current instructions that should govern this behavior.** If the instructions can reasonably be interpreted to produce the agent's (wrong) behavior → **Instruction ambiguity.** Fix: rewrite the ambiguous rule with a concrete example showing expected behavior.

6. **Check the optimization log for this failure pattern.** If the same failure has persisted across 2+ prior iterations despite targeted fixes → **Model behavior limit.** Fix: consider architectural changes (tool guardrails, workflow restructuring) or document as a known limitation.

For questions that failed in only 1 of 3 runs: classify as **Intermittent** — these are noise and should generally not drive instruction changes unless a clear pattern emerges across multiple questions.

**⚠️ STOP (supervised mode):** Present failure analysis to user. Propose specific instruction changes. In autonomous mode: proceed if all failures have a single unambiguous classification; stop and ask if any failure has multiple plausible classifications or if the proposed change is large (touching 3+ files).

#### Step 5: Edit Instructions
- Before making changes, verify a snapshot of the current `agent/*.md` state exists (either `baseline/` or the last accepted iteration in `<OUTPUT_DIR>/snapshots/`). If not, create one now.
- Modify the relevant `agent/*.md` files based on failure analysis
- Follow optimization patterns (load `references/optimization-patterns.md`):
  - **Prefer examples over verbose procedural rules**
  - **Fix buggy examples** — agents faithfully reproduce them
  - **Small, targeted changes** — one pattern per iteration
  - **Add "WRONG" examples** — showing what NOT to do is effective
  - **Don't over-strengthen rules** that failed 2+ iterations — diminishing returns

**⚠️ STOP (supervised mode):** Get approval on instruction changes before building. In autonomous mode: proceed.

#### Step 6: Build and Deploy
```bash
python scripts/build_agent_spec.py
<CLI_TOOL> sql --connection <CONNECTION> --filename <OUTPUT_DIR>/deploy.sql
```
- Verify deployment: `DESCRIBE AGENT <AGENT_FQN>;`

#### Step 7: Re-run DEV Eval
- Run DEV eval 3 times (`<ITER_NAME>_dev_r1` through `_r3`), sequentially
- Compare mean scores to previous iteration's mean scores
- If mean regression exceeds 1 stddev: return to Step 5 and adjust

#### Step 8: Run TEST Eval (only if DEV is satisfactory)
Run TEST eval 3 times sequentially (`<ITER_NAME>_test_r1` through `_r3`):
```sql
-- Run 1
CALL EXECUTE_AI_EVALUATION(
  'START',
  OBJECT_CONSTRUCT('run_name', '<ITER_NAME>_test_r1'),
  '@<STAGE_PATH>/eval_config_test.yaml'
);
-- Wait for completion, then run 2 and 3 with _r2, _r3 suffixes
```

#### Step 9: Log Results
- Append iteration to `optimization_log.md` with this template:

```markdown
## Iteration N

**Run names:** `<ITER_NAME>_dev_r[1-3]`, `<ITER_NAME>_test_r[1-3]`

**Changes made:**
1. [Change description]

**Files changed:** `agent/[file1].md`, `agent/[file2].md`

| Metric | DEV Mean ± StdDev | TEST Mean ± StdDev | Combined Mean |
|--------|-------------------|--------------------|--------------| 
| [metric_1] | X% ± Y% | X% ± Y% | Z% |
| [metric_2] | X% ± Y% | X% ± Y% | Z% |

**Comparison to [previous accepted iteration]:**
[Delta table with significance note]

**Decision:** [ACCEPT/REJECT with reasoning]
```

- Hand off to `review/SKILL.md` for the accept/reject decision.

**Target length:** ~200-230 lines.

---

### 4.4 `review/SKILL.md` — Accept/Reject Decision

**Frontmatter:**

```yaml
---
name: cortex-agent-optimization-review
description: "Review iteration results and make accept/reject decision."
parent_skill: cortex-agent-optimization
---
```

**Workflow (5 steps):**

#### Step 1: Compute Scores
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

#### Step 2: Apply Acceptance Criteria
- Compute TEST mean improvement (delta) vs the last accepted iteration's TEST mean
- Compare to previous accepted iteration's TEST mean and stddev
- Rules:
  - **ACCEPT** if: TEST mean improves AND the improvement exceeds 1 stddev of the current iteration's TEST scores (signal > noise)
  - **ACCEPT (marginal)** if: TEST mean improves but within 1 stddev — accept only if DEV improvement is strong and consistent across all 3 runs (all 3 DEV runs individually improved)
  - **REJECT** if: TEST mean regresses by any amount — this is an overfitting signal

#### Step 3: Present Recommendation

**⚠️ STOP (supervised mode):** Present the accept/reject recommendation with full data. In autonomous mode: proceed with the recommendation automatically.
- DEV scores (mean ± stddev) + delta vs previous
- TEST scores (mean ± stddev) + delta vs previous
- Combined scores + delta vs previous
- TEST mean comparison with significance assessment (the deciding metric)
- Recommendation: ACCEPT, ACCEPT (marginal), or REJECT with reasoning

Wait for user confirmation (supervised mode only).

#### Step 4: Finalize Decision
- **If ACCEPT:**
  - Update `optimization_log.md` — mark iteration as accepted, record final scores
  - Note this as the new "last accepted iteration" for future comparisons
  - Snapshot current `agent/*.md` files to `<OUTPUT_DIR>/snapshots/<ITER_NAME>/`
  - Reset the consecutive-rejection counter to 0
- **If REJECT:**
  - Update `optimization_log.md` — mark iteration as rejected with reason
  - Increment the consecutive-rejection counter (tracked in `optimization_log.md` metadata)
  - If counter reaches 3: **stop the optimization loop entirely**. Report remaining failures, summarize what was tried across all rejected iterations, and recommend whether architectural changes are needed
  - Restore `agent/*.md` files from the last accepted snapshot in `<OUTPUT_DIR>/snapshots/` (the most recent accepted `<ITER_NAME>/` directory, or `baseline/` if no iterations have been accepted)
  - Rebuild and redeploy with reverted instructions

#### Step 5: Cumulative Summary
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

---

### 4.5 `eval-data/SKILL.md` — Eval Dataset Splits

**Frontmatter:**

```yaml
---
name: cortex-agent-optimization-eval-data
description: "Create, validate, and re-balance dev/test eval splits for a Cortex Agent."
parent_skill: cortex-agent-optimization
---
```

This sub-skill has three workflows. Detect which the user wants, or default to Validate if an eval table already exists with a SPLIT column.

#### Workflow A: Create Split

**Step 1:** Read the eval table (`<EVAL_TABLE>`), count questions per `TEST_CATEGORY`.

**Step 2:** For each category independently, randomly assign ~45% of questions to `TRAIN` (DEV) and ~55% to `VALIDATION` (TEST). Target DEV count per category: `ROUND(N * 0.45)`.

**Step 3:** Validate minimum coverage — if any category has fewer than 3 questions in either split after assignment, flag it:
> ⚠️ Category `<CAT>` has only N questions — too small for reliable stratification. Recommend: add more questions or merge with a related category.

**Step 4:** Generate `UPDATE` SQL to set the `SPLIT` column for each `TEST_ID`. Present the proposed split with a per-category distribution table for approval.

**⚠️ STOP**: Present proposed split. Wait for approval before executing.

#### Workflow B: Validate Split

**Step 1:** Query category distribution per split — compute `DEV_COUNT`, `TEST_COUNT`, and `DEV_RATIO` per `TEST_CATEGORY`.

**Step 2:** Run quality checks:
- **Category proportionality:** Each category's DEV ratio is within ±10% of the target 45/55 (i.e., between 0.35 and 0.55). Status: PASS/WARN.
- **Minimum coverage:** Every category has ≥3 questions in each split. Status: PASS/FAIL.
- **Overall balance:** Total TRAIN/VALIDATION ratio is within ±5% of the target 45/55. Status: PASS/WARN.

**Step 3:** Present results with PASS/WARN/FAIL per check. If all PASS, confirm split is healthy. If any WARN/FAIL, recommend running Workflow C to re-balance.

#### Workflow C: Re-balance

**Step 1:** Run Workflow B validation to identify WARN/FAIL categories.

**Step 2:** For each flagged category, propose specific `TEST_ID` moves between splits to bring the ratio within bounds. Minimize total moves — prefer moving from the over-represented split in that category.

**Step 3:** Generate `UPDATE` SQL for the proposed moves. Present a before/after distribution table for approval.

**⚠️ STOP**: Present proposed moves. Wait for approval before executing.

**Target length:** ~80-100 lines.

---

### 4.6 `references/project-structure.md`

Documents the expected file layout for a project using this optimization workflow:

```
<project_root>/
├── agent/                                  # Source of truth for agent behavior
│   ├── orchestration_instructions.md       # Decision logic, routing, workflows
│   ├── response_instructions.md            # Output format, tone, structure rules
│   ├── tool_descriptions.md                # Per-tool descriptions (## Tool: <name>)
│   └── spec_base.json                      # Static config: models, budget, tool types, tool_resources
│
├── scripts/
│   └── build_agent_spec.py                 # Assembles agent/*.md + spec_base.json → deploy.sql
│
├── <output_dir>/                           # Named after the agent (e.g., MY_DB_PUBLIC_MY_AGENT/)
│   ├── deploy.sql                          # Generated — do not edit by hand
│   ├── optimization_log.md                 # Iteration history with scores and decisions
│   ├── metadata.yaml                       # Agent database/schema/name
│   ├── eval_config_dev.yaml                # DEV split eval configuration
│   ├── eval_config_test.yaml               # TEST split eval configuration
│   ├── DEPLOYMENT_INSTRUCTIONS.md          # (Optional) project-specific workflow notes
│   └── snapshots/                          # Versioned copies of agent/*.md per iteration
│       └── baseline/                       # Original instructions before any optimization
│
└── sql/
    └── eval_data.sql                       # Eval questions seed + DEV/TEST views
```

**Conventions:**
- `agent/*.md` files are the source of truth; `deploy.sql` is always generated
- Never edit `deploy.sql` by hand
- Use `ALTER AGENT ... MODIFY LIVE VERSION`, never `CREATE OR REPLACE`
- The output directory name convention is `<DATABASE>_<SCHEMA>_<AGENT_NAME>/` (underscores replacing dots)
- Before every edit to `agent/*.md`, a snapshot of the current state must exist in `<OUTPUT_DIR>/snapshots/`
- On accept: snapshot `agent/*.md` to `<OUTPUT_DIR>/snapshots/<ITER_NAME>/`
- On reject: restore `agent/*.md` from the last accepted snapshot (or `baseline/` if no iterations accepted)

**Target length:** ~40-50 lines.

---

### 4.7 `references/eval-setup.md`

Documents the dev/test evaluation methodology:

**Split Strategy:**
- DEV (~45%): rapid feedback loop, run every iteration
- TEST (~55%): held-out generalization check, run only after DEV is satisfactory
- Stratify across question categories (ensure each category has representation in both splits)
- SPLIT column values: `'TRAIN'` = DEV, `'VALIDATION'` = TEST

**Critical Rule:** Never examine TEST failure details to guide instruction changes. TEST is the held-out set. Looking at TEST failures before finalizing changes = training on the test set = overfitting. Only use TEST for the aggregate accept/reject decision.

**Eval Table Schema:**
```sql
CREATE TABLE IF NOT EXISTS <EVAL_TABLE> (
    TEST_ID       NUMBER(38,0),
    TEST_CATEGORY VARCHAR,
    INPUT_QUERY   VARCHAR,
    GROUND_TRUTH  OBJECT,
    SPLIT         VARCHAR DEFAULT 'VALIDATION'
);
```

**Ground Truth Format:**
```sql
OBJECT_CONSTRUCT(
  'ground_truth_invocations', PARSE_JSON('[
    {"tool_name": "<TOOL>", "tool_sequence": 1, "description": "..."}
  ]'),
  'ground_truth_output', '<expected answer text>'
)
```
- `ground_truth_invocations` is optional but improves `logical_consistency` scoring
- `ground_truth_output` is required

**Eval Config YAML Template:**
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

**Available Metrics:**
- `answer_correctness` — factual accuracy of the agent's response vs ground truth
- `logical_consistency` — whether the agent's reasoning and tool usage is logically sound

**Dataset Version Lock Troubleshooting:**
If `EXECUTE_AI_EVALUATION` fails with "Dataset version SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE already exists":
1. Wait 2-3 minutes — a previous eval's scoring phase may still be running
2. If still failing after 5+ min, check for running evals in the UI or via query history
3. If no eval is running, the lock is stale — clear it:
   ```sql
   ALTER DATASET <DATABASE>.<SCHEMA>.<DATASET_NAME>
   DROP VERSION 'SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE';
   ```
4. **NEVER drop the dataset itself** — this destroys all historical eval results

**Multiple Runs per Evaluation:**

Each eval (DEV or TEST) runs 3 times per iteration to capture model response variance.

- **Why:** The same question can receive a correct answer on one run and an incorrect answer on another due to non-deterministic generation. A single run gives a point estimate with unknown variance.
- **Run naming:** `<ITER_NAME>_<split>_r1`, `<ITER_NAME>_<split>_r2`, `<ITER_NAME>_<split>_r3`
- **Execution:** Runs must be sequential — the dataset version lock prevents parallel execution. Wait for each run to complete (including scoring phase) before starting the next.
- **Aggregation:** Compute `AVG` and `STDDEV` of per-question `EVAL_AGG_SCORE` across all 3 runs (UNION ALL of the 3 result sets, then GROUP BY METRIC_NAME).
- **Failure analysis:** A question that fails in all 3 runs is a high-confidence failure. A question that fails in 1 of 3 runs is likely noise and should generally not drive instruction changes.
- **Lock implications:** 3 sequential runs means 3x the chance of hitting a stale version lock. Follow the troubleshooting guide above for each occurrence.

**Target length:** ~100-120 lines.

---

### 4.8 `references/optimization-patterns.md`

Distilled learnings from real optimization work (6 iterations on a production agent). These patterns should guide instruction editing decisions:

### High-Impact Patterns

1. **Tool retry logic has the highest single-iteration impact.**
   Adding "retry up to 2x on transient errors before reporting failure" to orchestration instructions fixed complete failures caused by intermittent tool errors. Measured: +9.3% answer_correctness in one iteration.

2. **Buggy examples in instructions are poisonous.**
   If an example in the instructions contains an inconsistency (e.g., listing 3 items but the formula only uses 2), the agent will faithfully reproduce that inconsistency. Audit all examples for internal consistency.

3. **Fix the examples, not just the rules.**
   Adding a rule saying "be consistent" is less effective than fixing the example that demonstrates inconsistency. Agents learn more from examples than from abstract rules.

### Anti-Patterns (What Doesn't Work)

4. **Verbose procedural instructions backfire.**
   Adding multi-step verification checklists (e.g., "4-step PRE-FLIGHT CHECK before every tool call") degrades performance. Measured: -7.5% answer_correctness, -9.3% logical_consistency. Simpler, example-driven rules outperform procedural checklists.

5. **Tool description changes have minimal routing influence.**
   Adding warnings like "DO NOT use this tool for X" to tool descriptions had zero impact on DEV scores and hurt TEST performance. Tool descriptions appear to have less influence on tool selection than orchestration instructions.

6. **Tool order changes in the spec cause unpredictable regressions.**
   Reordering tools in the `tools` array caused the worst TEST regression across all iterations (-8.0%). Tool order is not a reliable lever for influencing behavior.

7. **Progressive strengthening of the same rule has diminishing returns.**
   If the same failure persists after 2-3 iterations of strengthening the same rule (adding more emphasis, more examples, more "NEVER" directives), it likely indicates a model behavior limit, not an instruction clarity issue. Consider architectural changes instead (tool-level guardrails, tool configuration, or workflow redesign).

### Methodology Patterns

8. **Small, targeted changes per iteration.**
   Change one pattern at a time when possible. This makes it clear which change caused improvement or regression. Bundling many changes makes attribution impossible.

9. **"WRONG" examples are effective.**
   Showing the agent what NOT to do (with explicit "WRONG" labels) is an effective complement to positive examples. Format: show the wrong approach, label it "WRONG", then show the correct approach.

10. **Domain-specific consistency rules need nuance.**
    Strict rules based on surface-level patterns (e.g., "counter count must match formula expression count") can be too aggressive. Documentation-based rules ("list all counters the documentation identifies as required") are more robust because they account for domain nuance (e.g., filtering counters not in the math expression).

11. **Revert aggressively on TEST regression.**
    Any TEST average regression is an overfitting signal. Don't try to "fix" a rejected iteration by making more changes on top — revert to the last accepted state and try a different approach.

12. **Know when to stop.**
    After 2-3 consecutive rejected iterations targeting the same failures, the agent has likely reached a local optimum for instruction-level changes. Document the remaining failures as known limitations and consider whether they require architectural changes (different tools, guardrails, or workflow restructuring).

13. **Single eval runs are noisy — use 3 runs per split.**
    LLM-based eval metrics have inherent variance from non-deterministic model responses. A +2% improvement on a single run can easily be noise. Running 3 evals and comparing means reduces the probability of accepting noise as signal or rejecting real improvements. The cost is 3x eval time per iteration, which is justified for production agents where a wrong accept/reject decision wastes an entire iteration.

14. **Classify failures with a decision tree, not intuition.**
    Follow a fixed diagnostic order: routing → tool error → formatting → content → ambiguity → model limit. This prevents the optimizer from jumping to instruction rewrites when the real problem is a tool error, or adding formatting rules when the issue is routing. Consistent classification also makes the optimization log more useful — you can track which *categories* of failure are decreasing across iterations.

**Target length:** ~100-120 lines.

---

## 5. Parameterization Scheme

Every user-specific value must be parameterized. The skill should never contain hardcoded project references.

| Parameter | Description | Example | Where used |
|-----------|-------------|---------|------------|
| `<AGENT_FQN>` | Fully qualified agent name | `MY_DB.PUBLIC.MY_AGENT` | Eval configs, deploy SQL, DESCRIBE |
| `<DATABASE>` | Agent database | `MY_DB` | Eval queries, metadata |
| `<SCHEMA>` | Agent schema | `PUBLIC` | Eval queries, metadata |
| `<AGENT_NAME>` | Agent name (no qualifiers) | `MY_AGENT` | Dataset names, log entries |
| `<CONNECTION>` | Snowflake CLI connection name | `my_conn` | `snow sql --connection` |
| `<STAGE_PATH>` | Stage path for eval configs | `@MY_DB.PUBLIC.EVAL_STAGE` | `EXECUTE_AI_EVALUATION` |
| `<OUTPUT_DIR>` | Directory for generated files | `MY_DB_PUBLIC_MY_AGENT/` | deploy.sql, log, configs |
| `<DEV_DATASET_NAME>` | DEV eval dataset name | `MY_AGENT_dev_ds_v1` | Eval config, lock troubleshooting |
| `<TEST_DATASET_NAME>` | TEST eval dataset name | `MY_AGENT_test_ds_v1` | Eval config, lock troubleshooting |
| `<ITER_NAME>` | Current iteration name | `iter3` | Run names, log entries |
| `<METRICS>` | List of eval metrics | `answer_correctness, logical_consistency` | Eval configs, score queries |
| `<EVAL_TABLE>` | Eval data table name | `AGENT_EVALUATION_DATA` | Seed SQL, views |
| `<CLI_TOOL>` | CLI tool for SQL execution | `snow` | Deploy command |
| `<EXECUTION_MODE>` | supervised or autonomous | `supervised` | Top-level SKILL.md, sub-skill STOP points |

**Collection:** Parameters should be collected in Step 1 of each sub-skill and stored as ctx memories or passed through the workflow. The setup sub-skill collects all parameters once; the optimize and review sub-skills read them from `metadata.yaml`.

---

## 6. Optimization Patterns (Summary for Frontmatter/Description)

The full patterns are in `references/optimization-patterns.md` (Section 4.8 above). The key principles to embed in the skill's decision-making:

1. **DO**: Add tool retry logic, fix buggy examples, use "WRONG" examples, make small targeted changes
2. **DON'T**: Add verbose checklists, modify tool descriptions for routing, change tool order, keep strengthening the same failing rule
3. **ALWAYS**: Revert on TEST regression, log every iteration, separate DEV analysis from TEST evaluation
4. **STOP WHEN**: 2-3 consecutive rejections on the same failures → local optimum reached

---

## 7. Acceptance Criteria for the Built Skill

Use this checklist to verify the skill is correctly built:

### Structure
- [ ] All 8 files exist in the directory tree (SKILL.md + 4 sub-skills + 3 references)
- [ ] Every file in the directory tree has a corresponding implementation
- [ ] Frontmatter on all SKILL.md files has `name` and `description`
- [ ] Sub-skills have `parent_skill: cortex-agent-optimization`

### Content
- [ ] Top-level SKILL.md is under 100 lines
- [ ] Each sub-skill is under 250 lines
- [ ] Total SKILL.md content (excluding references) is under 600 lines
- [ ] All workflow steps have clear numbered actions
- [ ] All mandatory stopping points are marked with `⚠️ STOP` (with mode annotation where applicable)
- [ ] Multi-run methodology (3 runs) is documented in eval steps and references
- [ ] Statistical acceptance criteria (mean + stddev) replace single-run comparisons
- [ ] Decision tree for failure classification is present in optimize sub-skill
- [ ] Autonomous mode termination condition (3 consecutive rejections) is documented
- [ ] Split validation checks (proportionality, minimum coverage, overall balance) are documented in eval-data sub-skill

### Parameterization
- [ ] No hardcoded database, schema, agent, or connection names anywhere
- [ ] All 13 parameters from the scheme are used with `<ANGLE_BRACKET>` notation
- [ ] Parameters are collected at the start of each sub-skill workflow

### Routing
- [ ] All 4 intent routes are reachable from the top-level SKILL.md
- [ ] Every sub-skill workflow terminates (success, user decision, or return to caller)
- [ ] No dead-end paths or unreachable sections
- [ ] Transition language uses active directives ("Load", "Continue to", "Run")

### Patterns
- [ ] `references/optimization-patterns.md` contains all 14 patterns from this spec
- [ ] `references/eval-setup.md` contains the dataset version lock troubleshooting guide
- [ ] The "never examine TEST before deploying" rule is prominently stated in at least 2 places

### Operational Safety
- [ ] "Never drop eval datasets" warning is present
- [ ] Dataset version lock troubleshooting includes the exact SQL (with single quotes around version name)
- [ ] Revert instructions are included in the reject path of `review/SKILL.md`
- [ ] The skill sets ctx rules for critical operational guardrails
- [ ] Snapshot-based versioning is documented: baseline snapshot on setup, pre-edit verification, accept snapshots, reject restores from snapshot