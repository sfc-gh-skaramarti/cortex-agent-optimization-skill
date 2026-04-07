# Test Fixture — Build Script Validation

This directory contains a minimal example for testing the build script workflow.

## Directory Structure

```
test-fixture-example/
├── agent/ -> ../cortex-agent-optimization/references/agent-template/  (symlink)
│   ├── orchestration_instructions.md   # Minimal routing example
│   ├── response_instructions.md        # Minimal format example
│   ├── tool_descriptions.md            # 3 tool descriptions
│   └── spec_base.json                  # Basic config
├── scripts/
│   └── build_agent_spec.py             # Reference implementation
├── metadata.yaml                        # Example values
└── README.md                            # This file
```

**Note:** The `agent/` directory is a symlink to the canonical templates in `cortex-agent-optimization/references/agent-template/`. This maintains a single source of truth while allowing the build script to work without modification.

## Testing the Build Script

### 1. Validate script syntax

```bash
cd test-fixture-example
python scripts/build_agent_spec.py --dry-run --json
```

**Expected**: Valid JSON output to stdout

### 2. Check JSON structure

```bash
python scripts/build_agent_spec.py --dry-run --json | jq .
```

**Expected**: 
- `instructions.orchestration` populated from orchestration_instructions.md
- `instructions.response` populated from response_instructions.md
- Each tool has `tool_spec.description` from tool_descriptions.md
- Base spec properties (models, budget, tools) preserved

### 3. Check SQL generation

```bash
python scripts/build_agent_spec.py --dry-run
```

**Expected**: Valid SQL with `ALTER AGENT ... SET SPECIFICATION = $$...$$;`

### 4. Test metadata parsing

The script reads `metadata.yaml` to construct the agent FQN. With the example metadata:
- Database: `TEST_DB`
- Schema: `PUBLIC`
- Name: `TEST_AGENT`
- Expected FQN: `TEST_DB.PUBLIC.TEST_AGENT`

## Validation Checklist

Run through this checklist to verify the build script works correctly:

- [ ] **Syntax valid**: `python scripts/build_agent_spec.py --dry-run` runs without errors
- [ ] **JSON valid**: Output from `--json` flag is valid JSON (test with `jq .`)
- [ ] **HTML comments removed**: Check `instructions.orchestration` has no `<!-- -->` comments
- [ ] **Top-level headings stripped**: Check `instructions` have no `# Title` lines
- [ ] **Tool descriptions mapped**: Each tool in `spec.tools` has `tool_spec.description`
- [ ] **Base spec preserved**: `models`, `orchestration.budget`, `tools` array intact
- [ ] **SQL syntax valid**: ALTER AGENT statement has proper `$$` delimiters
- [ ] **Metadata parsed**: Agent FQN in SQL matches metadata.yaml values

## Expected Output Sample

When running `--dry-run`, you should see:

```sql
ALTER AGENT TEST_DB.PUBLIC.TEST_AGENT
MODIFY LIVE VERSION
SET SPECIFICATION = $$
{
  "models": {
    "orchestration": "auto"
  },
  "orchestration": {
    "budget": {
      "seconds": 300,
      "tokens": 200000
    }
  },
  "instructions": {
    "orchestration": "Route queries based on intent:\n- Investigation requests...",
    "response": "Be direct and concise.\n\nFormat:\n- Use bullet points..."
  },
  "tools": [
    {
      "type": "builtin",
      "tool_name": "search_tool",
      "tool_spec": {
        "description": "Search internal documentation and knowledge base..."
      }
    },
    ...
  ]
}
$$;
```

## Common Issues

### Issue: `FileNotFoundError: agent/orchestration_instructions.md`
**Fix**: Run script from `test-fixture-example` directory or use `--agent` flag

### Issue: `ImportError: No module named 'yaml'`
**Fix**: Install PyYAML: `pip install pyyaml`
The script will fall back to placeholder FQN if PyYAML is not available

### Issue: Tool descriptions not appearing
**Fix**: Check `tool_descriptions.md` uses exact pattern: `## Tool: <tool_name>`

### Issue: HTML comments still present
**Fix**: Check regex in `strip_markdown_metadata()` function

## Using This Example

This directory serves as:
1. **Validation template**: Test that your build script follows the correct patterns
2. **Reference implementation**: Copy `build_agent_spec.py` as a starting point
3. **Documentation**: README explains expected behavior and common issues

When creating your actual optimization project, copy the build script and adapt:
- Update agent FQN logic for your naming convention
- Add any custom preprocessing for your markdown format
- Modify tool parsing if you use different patterns
