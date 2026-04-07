---
section: "4.2.1"
title: "Workspace Mode Detection"
parent_spec: "../cortex-agent-eval-optimizer-spec.md"
---

# Workspace Mode Detection

**On setup (Step 1):**

1. Ask user: "Where should I create the optimization project?" (no default to CWD)
2. Validate the path is NOT inside the skill directory
3. Check if `<WORKSPACE_ROOT>/scripts/build_agent_spec.py` exists:
   - **Exists** → Multi-agent workspace detected. Ask for agent subdirectory name (default: lowercase `<AGENT_NAME>`)
   - **Doesn't exist** → Single-agent project. Use flat structure (no subdirectory, `<AGENT_DIR>` = `.`)

**Single-agent structure:**
```
my_project/
├── agent/
├── scripts/
├── deploy.sql
├── metadata.yaml
└── snapshots/
```

**Multi-agent workspace:**
```
workspace/
├── scripts/              # Shared
├── agent1/              # First agent
│   ├── agent/
│   ├── deploy.sql
│   └── ...
└── agent2/              # Second agent
```

**metadata.yaml stores:**
```yaml
workspace_type: "single" | "multi"
agent_dir: "agent1" | "."   # "." for single-agent
```

**Build script behavior:**
- Single-agent: Hard-coded paths to `agent/`, `deploy.sql`
- Multi-agent: Reads `metadata.yaml` to determine agent-specific paths
