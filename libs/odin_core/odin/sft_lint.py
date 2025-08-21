#!/usr/bin/env python3
"""
ODIN SFT Linter CLI

Usage:
    python -m odin.sft_lint <map_file_or_directory>
    
Examples:
    python -m odin.sft_lint configs/sft_maps/invoice_to_payment.json
    python -m odin.sft_lint configs/sft_maps/
"""
import argparse
import sys
import json
from pathlib import Path
from typing import List, Dict, Any

from odin.sft_advanced import lint_sft_map_file, SftMapLintResult


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Lint and validate ODIN SFT maps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s configs/sft_maps/invoice_to_payment.json
  %(prog)s configs/sft_maps/ --recursive
  %(prog)s configs/sft_maps/ --fail-on-warnings
        """
    )
    
    parser.add_argument(
        "path",
        help="Path to SFT map file or directory"
    )
    
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively lint all .json files in directory"
    )
    
    parser.add_argument(
        "-f", "--fail-on-warnings",
        action="store_true",
        help="Exit with error code if warnings are found"
    )
    
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Only show errors and warnings, not success messages"
    )
    
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Output results in JSON format"
    )
    
    parser.add_argument(
        "--ignore-warnings",
        nargs="+",
        default=[],
        help="Ignore specific warning patterns"
    )
    
    args = parser.parse_args()
    
    # Determine paths to lint
    target_path = Path(args.path)
    
    if not target_path.exists():
        print(f"Error: Path does not exist: {target_path}", file=sys.stderr)
        sys.exit(1)
    
    if target_path.is_file():
        map_files = [target_path]
    elif target_path.is_dir():
        if args.recursive:
            map_files = list(target_path.rglob("*.json"))
        else:
            map_files = list(target_path.glob("*.json"))
    else:
        print(f"Error: Invalid path: {target_path}", file=sys.stderr)
        sys.exit(1)
    
    if not map_files:
        print(f"No .json files found in {target_path}")
        sys.exit(0)
    
    # Lint all files
    results = {}
    total_errors = 0
    total_warnings = 0
    
    for map_file in sorted(map_files):
        if not args.quiet:
            print(f"Linting {map_file}...")
        
        result = lint_sft_map_file(str(map_file))
        results[str(map_file)] = result
        
        # Filter ignored warnings
        if args.ignore_warnings:
            filtered_warnings = []
            for warning in result.warnings:
                if not any(pattern in warning for pattern in args.ignore_warnings):
                    filtered_warnings.append(warning)
            result.warnings = filtered_warnings
        
        total_errors += len(result.errors)
        total_warnings += len(result.warnings)
        
        # Print results for this file
        if args.json_output:
            continue  # Print all at once at the end
        
        if result.valid and not result.warnings:
            if not args.quiet:
                print(f"  ✅ Valid")
        elif result.valid and result.warnings:
            print(f"  ⚠️  Valid with warnings:")
            for warning in result.warnings:
                print(f"    - {warning}")
        else:
            print(f"  ❌ Invalid:")
            for error in result.errors:
                print(f"    - ERROR: {error}")
            for warning in result.warnings:
                print(f"    - WARNING: {warning}")
        
        if result.suggestions and not args.quiet:
            print(f"  💡 Suggestions:")
            for suggestion in result.suggestions:
                print(f"    - {suggestion}")
    
    # Output JSON if requested
    if args.json_output:
        json_results = {}
        for path, result in results.items():
            json_results[path] = {
                "valid": result.valid,
                "errors": result.errors,
                "warnings": result.warnings,
                "suggestions": result.suggestions
            }
        
        print(json.dumps(json_results, indent=2))
    
    # Summary
    if not args.json_output and not args.quiet:
        print(f"\nSummary:")
        print(f"  Files linted: {len(map_files)}")
        print(f"  Valid files: {sum(1 for r in results.values() if r.valid)}")
        print(f"  Invalid files: {sum(1 for r in results.values() if not r.valid)}")
        print(f"  Total errors: {total_errors}")
        print(f"  Total warnings: {total_warnings}")
    
    # Exit code logic
    if total_errors > 0:
        sys.exit(1)  # Hard failure on errors
    elif args.fail_on_warnings and total_warnings > 0:
        sys.exit(1)  # Optional failure on warnings
    else:
        sys.exit(0)  # Success


if __name__ == "__main__":
    main()
