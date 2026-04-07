---
name: cortex-agent-optimization
description: >
  Iterative optimization of Snowflake Cortex Agents using dev/test eval splits.
  Covers project setup, instruction editing, build/deploy, eval execution,
  failure analysis, and accept/reject decisions.
  Use when: optimizing agent instructions, running agent evals, improving agent
  accuracy, setting up eval splits, analyzing agent failures.
  Triggers: optimize agent, agent eval, improve agent, agent iteration,
  run eval, optimization loop, agent instructions, eval split,
  run optimization, next iteration, analyze agent failures, accept reject iteration.
---

## When to Use

This skill applies when a user has (or wants to create) a Snowflake Cortex Agent with markdown-based instructions and wants to iteratively improve it using evaluations with a dev/test split. It covers the full optimization lifecycle: project scaffolding, eval dataset management, instruction editing guided by failure analysis, build/deploy, evaluation execution with statistical rigor (configurable runs per split), and data-driven accept/reject decisions.

## Prerequisites

- A deployed Snowflake Cortex Agent (or intent to create one)
- `snow` CLI installed and a named connection configured
- Python 3.11+ (for the build script)

## Related Skills

**Bundled alternatives:** Snowflake provides a bundled `cortex-agent` skill with sub-skills for agent lifecycle management, including `optimize-cortex-agent`. This custom skill differs by providing statistical rigor through dev/test splits and multi-run evaluations. See README.md "Related Bundled Skills" section for detailed comparison.

**Complementary workflows:** This skill can leverage bundled sub-skills for dataset creation (`dataset-curation`), debugging (`debug-single-query-for-cortex-agent`), and ad-hoc testing (`adhoc-testing-for-cortex-agent`). References are provided in the relevant workflow steps.

## Setup

Load `references/project-structure.md` for context on the expected file layout and conventions.

## Intent Detection

Detect the user's intent and route to the appropriate sub-skill:

| Intent | Trigger Patterns | Action |
|--------|-----------------|--------|
| **SETUP** | "set up optimization", "scaffold", "initialize optimization", "set up eval" | Load `setup/SKILL.md` and follow its workflow |
| **OPTIMIZE** | "run iteration", "optimize", "improve agent", "next iteration", "run eval", "analyze failures", "resume iteration" | Load `optimize/SKILL.md` and follow its workflow |
| **REVIEW** | "review results", "accept or reject", "compare iterations", "check test scores", "finalize iteration" | Load `review/SKILL.md` and follow its workflow |
| **EVAL DATA** | "create eval split", "validate split", "check eval balance", "split quality", "re-balance eval", "eval dataset" | Load `eval-data/SKILL.md` and follow its workflow |

If intent is ambiguous, ask the user which mode they want.

## Execution Mode

Detect or ask whether to run in **supervised** or **autonomous** mode:

- **Supervised** (default): All `⚠️ STOP` gates are active. The user approves each decision before proceeding.
- **Autonomous**: STOP gates in Steps 4-5 are conditionally skipped:
  - **Skip if:**
    - All failures have a single unambiguous classification (no competing hypotheses)
    - Proposed change touches ≤2 files
    - Change follows established patterns from `references/optimization-patterns.md`
  - **Present analysis and ask if:**
    - Any failure has multiple plausible classifications
    - Change touches 3+ files or deviates from known patterns
  - **User can interrupt at any time** — autonomous mode is resumable, not uninterruptible
  - **Termination:** 3 consecutive rejected iterations = stop and report remaining failures as known limitations

Default to supervised if the user's preference is unclear.

## Ctx Rules

Run `cortex ctx rule list` and check if each rule below is already present.
Only run `cortex ctx rule add` for rules that are **not** already in the list:

- "Only analyze DEV failures to make instruction changes; never examine TEST results before deploying"
- "Never drop eval datasets; only drop stale version locks"
- "Always read optimization log before starting an iteration"
- "In autonomous mode, stop after 3 consecutive rejected iterations and report remaining failures as known limitations"

## Quick Reference

- **DO**: Add tool retry logic, fix buggy examples, use "WRONG" examples, make small targeted changes
- **DON'T**: Add verbose checklists, modify tool descriptions for routing, change tool order, keep strengthening the same failing rule
- **ALWAYS**: Revert on TEST regression, log every iteration, separate DEV analysis from TEST evaluation
- **STOP WHEN**: 2-3 consecutive rejections on the same failures — local optimum reached

Load `references/optimization-patterns.md` for the full set of distilled patterns.
