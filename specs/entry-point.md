---
section: "4.1"
title: "SKILL.md — Entry Point"
parent_spec: "../cortex-agent-optimization-spec.md"
---

# Entry Point Skill Contract

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
