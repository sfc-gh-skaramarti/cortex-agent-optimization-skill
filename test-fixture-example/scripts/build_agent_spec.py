#!/usr/bin/env python3
"""
Build Cortex Agent specification from markdown instructions and base spec.

Usage:
  python build_agent_spec.py [--dry-run] [--json] [--agent AGENT_DIR]
"""
import argparse
import json
import re
import sys
from pathlib import Path

def strip_markdown_metadata(content: str) -> str:
    """Remove HTML comments and top-level headings."""
    # Remove HTML comments
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    # Remove top-level heading (# Title)
    content = re.sub(r'^#\s+.*$', '', content, flags=re.MULTILINE)
    return content.strip()

def parse_tool_descriptions(content: str) -> dict:
    """Parse tool_descriptions.md into dict of tool_name -> description."""
    tools = {}
    # Split on ## Tool: <name> pattern
    sections = re.split(r'^## Tool:\s+(\w+)', content, flags=re.MULTILINE)
    
    # Sections come in pairs: [preamble, tool1_name, tool1_desc, tool2_name, tool2_desc, ...]
    for i in range(1, len(sections), 2):
        tool_name = sections[i].strip()
        description = sections[i + 1].strip()
        tools[tool_name] = strip_markdown_metadata(description)
    
    return tools

def build_spec(agent_dir: Path) -> dict:
    """Build agent spec from agent directory."""
    agent_path = agent_dir / "agent"
    
    # Read base spec
    with open(agent_path / "spec_base.json") as f:
        spec = json.load(f)
    
    # Read instructions
    orch_content = (agent_path / "orchestration_instructions.md").read_text()
    resp_content = (agent_path / "response_instructions.md").read_text()
    
    spec["instructions"] = {
        "orchestration": strip_markdown_metadata(orch_content),
        "response": strip_markdown_metadata(resp_content)
    }
    
    # Read tool descriptions
    tool_desc_content = (agent_path / "tool_descriptions.md").read_text()
    tool_descriptions = parse_tool_descriptions(tool_desc_content)
    
    # Add descriptions to tools
    for tool in spec.get("tools", []):
        tool_name = tool.get("tool_spec", {}).get("name")
        if tool_name and tool_name in tool_descriptions:
            if "tool_spec" not in tool:
                tool["tool_spec"] = {}
            tool["tool_spec"]["description"] = tool_descriptions[tool_name]
    
    return spec

def generate_deploy_sql(spec: dict, agent_fqn: str) -> str:
    """Generate ALTER AGENT SQL."""
    spec_json = json.dumps(spec, indent=2)
    return f"""ALTER AGENT {agent_fqn}
MODIFY LIVE VERSION
SET SPECIFICATION = $$
{spec_json}
$$;
"""

def main():
    parser = argparse.ArgumentParser(description="Build Cortex Agent spec")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Print to stdout instead of writing file")
    parser.add_argument("--json", action="store_true",
                       help="Output spec JSON only (no SQL wrapper)")
    parser.add_argument("--agent", default=".",
                       help="Agent directory (for multi-agent workspace)")
    
    args = parser.parse_args()
    
    # Determine paths
    workspace_root = Path(__file__).parent.parent
    agent_dir = workspace_root / args.agent
    
    # Read metadata for agent FQN
    metadata_path = agent_dir / "metadata.yaml"
    if metadata_path.exists():
        try:
            import yaml
            with open(metadata_path) as f:
                metadata = yaml.safe_load(f)
            agent_fqn = f"{metadata['database']}.{metadata['schema']}.{metadata['name']}"
        except ImportError:
            print("Warning: PyYAML not installed. Using placeholder agent FQN.", file=sys.stderr)
            agent_fqn = "DATABASE.SCHEMA.AGENT_NAME"
        except KeyError as e:
            print(f"Warning: Missing key in metadata.yaml: {e}. Using placeholder.", file=sys.stderr)
            agent_fqn = "DATABASE.SCHEMA.AGENT_NAME"
    else:
        agent_fqn = "DATABASE.SCHEMA.AGENT_NAME"  # Placeholder for testing
    
    # Build spec
    try:
        spec = build_spec(agent_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(f"Make sure the agent directory exists with agent/*.md files", file=sys.stderr)
        sys.exit(1)
    
    # Output
    if args.json:
        output = json.dumps(spec, indent=2)
    else:
        output = generate_deploy_sql(spec, agent_fqn)
    
    if args.dry_run:
        print(output)
    else:
        output_path = agent_dir / "deploy.sql"
        output_path.write_text(output)
        print(f"✓ Generated {output_path}")

if __name__ == "__main__":
    main()
