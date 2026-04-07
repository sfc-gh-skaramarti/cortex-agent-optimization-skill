# Cortex Agent Optimization Skill

A Cortex Code skill that guides iterative optimization of Snowflake Cortex Agents using dev/test evaluation splits.

## How It Works

The skill implements an LLM-as-optimizer loop: Cortex Code reads evaluation failures, edits agent instructions, deploys, and re-evaluates — repeating until scores converge or a termination condition is met.

Key properties:

- **Dev/Test Split**: ~45% DEV / ~55% TEST, stratified per category. DEV failures guide changes; TEST validates generalization.
- **Multiple Runs**: Configurable `runs_per_split` per evaluation captures model response variance. Decisions use a one-sided paired t-test across per-run means.
- **Statistical Acceptance**: ACCEPT if one-sided paired t-test (α=0.10) passes. REJECT on any regression.
- **Failure Classification**: Ordered decision tree (routing → tool error → formatting → content → instruction ambiguity → instruction conflict → model limit).
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
    ├── agent-template/               # Format validation examples
    ├── eval-polling.md               # Eval completion status queries
    ├── eval-setup.md                 # Eval config YAML and dataset setup
    ├── optimization-patterns.md      # Failure classification tree, edit patterns
    ├── project-structure.md          # Output directory layout
    └── resume-iteration.md           # Resume interrupted iterations
```

## Getting Started

1. Copy `test-fixture.template.md` to `test-fixture.md`
2. Fill in the parameter values for your agent and eval dataset
3. Run the profiling queries to verify your eval data
4. Complete the prerequisites checklist
5. Invoke the skill in Cortex Code

## Specification

The full design specification is in `cortex-agent-optimization-spec.md`. All skill files reference the spec section they implement.

## Related Bundled Skills

This skill provides **statistical rigor and reproducibility** for agent optimization through dev/test splits, multi-run evaluations, and quantitative acceptance criteria (one-sided paired t-test, α=0.10).

### Complementary Workflows

**Dataset Creation:**
- For advanced dataset options (production data, Streamlit event explorer), see bundled `dataset-curation` skill
- Particularly useful: Agent Events Explorer for annotating real production queries

**Debugging:**
- For deep trace analysis during failure investigation, see bundled `debug-single-query-for-cortex-agent` skill
- Provides GET_AI_RECORD_TRACE queries and observability log analysis

**Ad-hoc Testing:**
- For interactive question testing between iterations, see bundled `adhoc-testing-for-cortex-agent` skill
- Good for sanity checks before running formal evaluations

### Choosing Between Optimization Approaches

**Use this skill (`cortex-agent-optimization`) when:**
- You need reproducible, quantitative metrics
- You want automated acceptance criteria (statistical thresholds)
- You're optimizing for generalization (dev/test methodology prevents overfitting)
- You prefer data-driven decisions over qualitative assessment

**Use bundled `optimize-cortex-agent` when:**
- You have domain experts available for qualitative review
- You prefer single evaluation set with expert judgment
- You want integrated workspace/versioning with get_agent_config.py scripts
- You need todo tracking and phase-based workflow management

Both are valid approaches serving different team needs.
