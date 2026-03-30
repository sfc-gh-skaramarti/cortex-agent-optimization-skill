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

## 4. File Contracts (Modular Specifications)

Section 4 has been modularized into separate specification files in the `specs/` directory for better maintainability. Each file is a complete contract for its corresponding SKILL.md implementation.

| Section | File | Description |
|---------|------|-------------|
| 4.1 | [specs/entry-point.md](specs/entry-point.md) | Entry point skill contract (SKILL.md) |
| 4.2 | [specs/setup.md](specs/setup.md) | Project scaffolding workflow (setup/SKILL.md) |
| 4.2.1 | [specs/setup-detection.md](specs/setup-detection.md) | Workspace mode detection algorithm |
| 4.3 | [specs/optimize.md](specs/optimize.md) | Optimization iteration workflow (optimize/SKILL.md) |
| 4.4 | [specs/review.md](specs/review.md) | Accept/reject decision workflow (review/SKILL.md) |
| 4.5 | [specs/eval-data.md](specs/eval-data.md) | Eval dataset split management (eval-data/SKILL.md) |
| 4.6 | [specs/project-structure.md](specs/project-structure.md) | Expected file layouts (references/project-structure.md) |
| 4.7 | [specs/eval-setup.md](specs/eval-setup.md) | Dev/test evaluation methodology (references/eval-setup.md) |
| 4.8 | [specs/optimization-patterns.md](specs/optimization-patterns.md) | Distilled optimization learnings (references/optimization-patterns.md) |

Each modular spec file includes:
- Section number and title in frontmatter
- Parent spec reference for traceability
- Complete contract content from the original spec
- Target length guidelines where applicable

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
| `<WORKSPACE_ROOT>` | Workspace/project root directory | `~/my_agent_project/` | Base for all local files |
| `<AGENT_DIR>` | Agent subdirectory name | `investigation_agent` or `.` | Agent-specific folder (`.` for single-agent) |
| `<DEV_DATASET_NAME>` | DEV eval dataset name | `MY_AGENT_dev_ds_v1` | Eval config, lock troubleshooting |
| `<TEST_DATASET_NAME>` | TEST eval dataset name | `MY_AGENT_test_ds_v1` | Eval config, lock troubleshooting |
| `<ITER_NAME>` | Current iteration name | `iter3` | Run names, log entries |
| `<METRICS>` | List of eval metrics | `answer_correctness, logical_consistency` | Eval configs, score queries |
| `<EVAL_TABLE>` | Eval data table name | `AGENT_EVALUATION_DATA` | Seed SQL, views |
| `<CLI_TOOL>` | CLI tool for SQL execution | `snow` | Deploy command |
| `<EXECUTION_MODE>` | supervised or autonomous | `supervised` | Top-level SKILL.md, sub-skill STOP points |

**Collection:** Parameters should be collected in Step 1 of setup sub-skill, with workspace path prompted (no CWD default). The setup sub-skill detects single vs multi-agent mode and stores workspace_type and agent_dir in `metadata.yaml`. The optimize and review sub-skills read them from `metadata.yaml`.

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