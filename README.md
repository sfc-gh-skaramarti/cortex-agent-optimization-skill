# Cortex Agent Optimization Skill

A Cortex Code skill that guides iterative optimization of Snowflake Cortex Agents using dev/test evaluation splits.

## How It Works

The skill implements an LLM-as-optimizer loop: Cortex Code reads evaluation failures, edits agent instructions, deploys, and re-evaluates — repeating until scores converge or a termination condition is met.

Key properties:

- **Dev/Test Split**: ~45% DEV / ~55% TEST, stratified per category. DEV failures guide changes; TEST validates generalization.
- **Multiple Runs**: 3 runs per evaluation capture model response variance. Decisions use mean ± stddev.
- **Statistical Acceptance**: ACCEPT if TEST mean improves > 1 stddev. REJECT on any regression.
- **Failure Classification**: Ordered decision tree (routing → tool error → formatting → content → instruction ambiguity → model limit).
- **Snapshot Versioning**: File-based snapshots of agent instructions at each accepted iteration, with rollback on rejection.
- **Execution Modes**: Supervised (all stop gates active) or autonomous (stricter criteria, automated termination after 3 consecutive rejections).

## Skill Structure

```
cortex-agent-optimization/
├── SKILL.md                          # Entry point and routing
├── setup/SKILL.md                    # Agent discovery, source-of-truth, baseline eval
├── optimize/SKILL.md                 # DEV eval → failure analysis → edit → re-eval loop
├── review/SKILL.md                   # Cross-run scoring, accept/reject, snapshots
├── eval-data/SKILL.md                # Create, validate, re-balance dev/test splits
└── references/
    ├── project-structure.md          # Output directory layout
    ├── eval-setup.md                 # Eval config YAML and dataset setup
    └── optimization-patterns.md      # Failure classification tree, edit patterns
```

## Getting Started

1. Copy `test-fixture.template.md` to `test-fixture.md`
2. Fill in the parameter values for your agent and eval dataset
3. Run the profiling queries to verify your eval data
4. Complete the prerequisites checklist
5. Invoke the skill in Cortex Code

## Specification

The full design specification is in `cortex-agent-optimization-spec.md`. All skill files reference the spec section they implement.
