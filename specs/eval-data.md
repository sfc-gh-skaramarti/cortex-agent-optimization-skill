---
section: "4.5"
title: "eval-data/SKILL.md — Eval Dataset Splits"
parent_spec: "../cortex-agent-eval-optimizer-spec.md"
---

# Eval Dataset Splits Contract

**Frontmatter:**

```yaml
---
name: cortex-agent-eval-optimizer-eval-data
description: "Create, validate, and re-balance dev/test eval splits for a Cortex Agent."
parent_skill: cortex-agent-eval-optimizer
---
```

This sub-skill has four workflows. Detect which the user wants, or default to Validate if an eval table already exists with a SPLIT column.

**Parameter Detection:**
- Read metadata.yaml for all parameters
- If dev_split_value/test_split_value not set: detect from eval table or default to 'TRAIN'/'VALIDATION'

## Workflow A: Create Split

**Step 1:** Read the eval table (`<EVAL_TABLE>`), count questions per `TEST_CATEGORY`.

**Step 2:** For each category independently, randomly assign ~45% of questions to DEV split value and ~55% to TEST split value. Target DEV count per category: `ROUND(N * 0.45)`.

**Step 3:** Validate minimum coverage — if any category has fewer than 3 questions in either split after assignment, flag it:
> ⚠️ Category `<CAT>` has only N questions — too small for reliable stratification. Recommend: add more questions or merge with a related category.

**Step 4:** Generate `UPDATE` SQL to set the `SPLIT` column for each `TEST_ID`. Present the proposed split with a per-category distribution table for approval.

**⚠️ STOP**: Present proposed split. Wait for approval before executing.

## Workflow B: Validate Split

**Step 1:** Query category distribution per split — compute `DEV_COUNT`, `TEST_COUNT`, and `DEV_RATIO` per `TEST_CATEGORY`.

**Step 2:** Run quality checks:
- **Category proportionality:** Each category's DEV ratio is within ±10% of the target 45/55 (i.e., between 0.35 and 0.55). Status: PASS/WARN.
- **Minimum coverage:** Every category has ≥3 questions in each split. Status: PASS/FAIL.
- **Overall balance:** Total DEV/TEST ratio is within ±5% of the target 45/55. Status: PASS/WARN.

**Step 3:** Present results with PASS/WARN/FAIL per check. If all PASS, confirm split is healthy. If any WARN/FAIL, recommend running Workflow C to re-balance.

## Workflow C: Re-balance

**Step 1:** Run Workflow B validation to identify WARN/FAIL categories.

**Step 2:** For each flagged category, propose specific `TEST_ID` moves between splits to bring the ratio within bounds. Minimize total moves — prefer moving from the over-represented split in that category.

**Step 3:** Generate `UPDATE` SQL for the proposed moves. Present a before/after distribution table for approval.

**⚠️ STOP**: Present proposed moves. Wait for approval before executing.

## Workflow D: Merge Small Categories

Use when Workflow B identifies categories with <6 total questions.

**Step 1:** For each small category, query similar categories using edit distance.

**Step 2:** Present merge candidates to user. Show before/after distribution impact.

**Step 3:** Generate UPDATE SQL to merge categories.

**⚠️ STOP**: Present merge proposal. Wait for approval before executing.

**Step 4:** After execution, re-run Workflow B to confirm checks pass.

**Target length:** ~110-130 lines.
