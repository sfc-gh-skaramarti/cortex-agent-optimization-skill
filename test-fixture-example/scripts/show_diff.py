#!/usr/bin/env python3
"""
Show visual diff between two agent instruction snapshots.

Usage:
  python scripts/show_diff.py --from snapshots/iter6/ --to agent/
  python scripts/show_diff.py --from snapshots/baseline/ --to agent/
"""
import argparse
import difflib
from pathlib import Path

def colorize_diff(line: str) -> str:
    """Add terminal colors to diff lines."""
    if line.startswith('+'):
        return f"\033[32m{line}\033[0m"  # Green
    elif line.startswith('-'):
        return f"\033[31m{line}\033[0m"  # Red
    elif line.startswith('@'):
        return f"\033[36m{line}\033[0m"  # Cyan
    return line

def show_file_diff(file1: Path, file2: Path) -> bool:
    """Show unified diff for a single file. Returns True if differences found."""
    try:
        content1 = file1.read_text().splitlines(keepends=True)
        content2 = file2.read_text().splitlines(keepends=True)
    except FileNotFoundError as e:
        print(f"  Error: {e}")
        return False
    
    diff = difflib.unified_diff(
        content1, content2,
        fromfile=str(file1), tofile=str(file2),
        lineterm=''
    )
    
    has_changes = False
    for line in diff:
        has_changes = True
        print(colorize_diff(line))
    
    return has_changes

def main():
    parser = argparse.ArgumentParser(description="Show agent instruction diffs")
    parser.add_argument("--from", dest="from_dir", required=True,
                       help="Source directory (e.g., snapshots/iter6/)")
    parser.add_argument("--to", dest="to_dir", required=True,
                       help="Target directory (e.g., agent/)")
    
    args = parser.parse_args()
    
    from_path = Path(args.from_dir)
    to_path = Path(args.to_dir)
    
    if not from_path.exists():
        print(f"Error: Source directory not found: {from_path}")
        return 1
    
    if not to_path.exists():
        print(f"Error: Target directory not found: {to_path}")
        return 1
    
    # Compare markdown files
    md_files = ["orchestration_instructions.md", "response_instructions.md", 
                "tool_descriptions.md"]
    
    any_changes = False
    for md_file in md_files:
        file1 = from_path / md_file
        file2 = to_path / md_file
        
        if file1.exists() and file2.exists():
            print(f"\n{'='*60}")
            print(f"Comparing: {md_file}")
            print('='*60)
            has_changes = show_file_diff(file1, file2)
            if not has_changes:
                print("  (no changes)")
            else:
                any_changes = True
        elif not file1.exists():
            print(f"\nSkipping {md_file}: not found in source directory")
        elif not file2.exists():
            print(f"\nSkipping {md_file}: not found in target directory")
    
    if not any_changes:
        print("\n✓ No changes detected between directories")
    
    return 0

if __name__ == "__main__":
    exit(main())
