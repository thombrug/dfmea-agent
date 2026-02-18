#!/usr/bin/env python3
"""
DFMEA Agent — CLI entrypoint.

Usage:
  python src/main.py                      # Run built-in example (automotive brake system)
  python src/main.py --example            # Same as above
  python src/main.py input.json           # Run with custom input JSON file
  python src/main.py --output-dir ./out   # Write outputs to a specific directory
  python src/main.py --json-only          # Print JSON output only, no HTML report

The agent expects ANTHROPIC_API_KEY to be set in the environment.

Input JSON format:
{
  "system_name": "My System",
  "system_description": "What the system does...",
  "components": [
    {"name": "Component A", "function": "What it does"},
    {"name": "Component B", "function": "What it does"}
  ],
  "scope": "design"   // optional, default: "design"
}

Output:
  - JSON printed to stdout (FMEAOutput schema)
  - HTML report saved to <output_dir>/fmea_report.html
  - JSON output saved to <output_dir>/fmea_output.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Allow running from the examples/dfmea-agent/ root as well as src/
sys.path.insert(0, str(Path(__file__).parent))

from agent import run_dfmea_agent
from fmea_schema import ComponentInput, FMEAInput
from ui.renderer import render_html_report


# ── Built-in example: Automotive Brake System ─────────────────────────────────
EXAMPLE_INPUT = FMEAInput(
    system_name="Automotive Disc Brake System",
    system_description=(
        "A hydraulic disc brake system used in a passenger vehicle to decelerate "
        "and stop the vehicle safely. The system operates under temperatures ranging "
        "from -40°C to +300°C (rotor surface) and must meet ISO 26262 ASIL-B requirements."
    ),
    components=[
        ComponentInput(
            name="Brake Caliper",
            function="Apply clamping force to the brake disc to generate braking torque",
        ),
        ComponentInput(
            name="Brake Disc (Rotor)",
            function="Convert kinetic energy to heat through friction with brake pads",
        ),
        ComponentInput(
            name="Brake Pads",
            function="Provide controlled friction surface against the rotor to slow rotation",
        ),
        ComponentInput(
            name="Hydraulic Master Cylinder",
            function="Convert driver pedal force into hydraulic pressure throughout the brake circuit",
        ),
        ComponentInput(
            name="ABS Control Unit",
            function="Modulate brake pressure to prevent wheel lock-up during emergency braking",
        ),
    ],
    scope="design",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Design FMEA Agent — IEC 60812:2018 / INCOSE methodology",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="Path to input JSON file (omit to use built-in automotive brake example)",
    )
    parser.add_argument(
        "--example",
        action="store_true",
        help="Run the built-in automotive brake system example",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to write output files (default: current directory)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print JSON to stdout only; do not write HTML report",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save any output files; only print to stdout",
    )

    args = parser.parse_args()

    # ── Check API key ──────────────────────────────────────────────────────────
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: ANTHROPIC_API_KEY environment variable is not set.\n"
            "  export ANTHROPIC_API_KEY=your-api-key",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Load input ─────────────────────────────────────────────────────────────
    if args.input_file and not args.example:
        input_path = Path(args.input_file)
        if not input_path.exists():
            print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        with open(input_path) as f:
            raw = json.load(f)
        fmea_input = FMEAInput(**raw)
        print(f"[DFMEA Agent] Loaded input from {input_path}", file=sys.stderr)
    else:
        fmea_input = EXAMPLE_INPUT
        print("[DFMEA Agent] Using built-in example: Automotive Disc Brake System", file=sys.stderr)

    # ── Run FMEA agent ─────────────────────────────────────────────────────────
    result = run_dfmea_agent(fmea_input)

    # ── Render HTML report ─────────────────────────────────────────────────────
    if not args.json_only:
        result.html_report = render_html_report(result)
        print("[DFMEA Agent] HTML report rendered.", file=sys.stderr)

    # ── Output JSON to stdout ──────────────────────────────────────────────────
    output_dict = result.model_dump()
    if args.json_only or args.no_save:
        # Exclude potentially huge html_report from stdout when json-only
        output_dict.pop("html_report", None)

    print(json.dumps(output_dict, indent=2))

    # ── Save output files ──────────────────────────────────────────────────────
    if not args.no_save:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON
        json_path = output_dir / "fmea_output.json"
        save_dict = result.model_dump()
        save_dict.pop("html_report", None)  # Keep JSON file clean
        with open(json_path, "w") as f:
            json.dump(save_dict, f, indent=2)
        print(f"[DFMEA Agent] JSON saved: {json_path}", file=sys.stderr)

        # Save HTML
        if result.html_report:
            html_path = output_dir / "fmea_report.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(result.html_report)
            print(f"[DFMEA Agent] HTML report saved: {html_path}", file=sys.stderr)

    # ── Print summary ──────────────────────────────────────────────────────────
    s = result.summary
    print("\n" + "=" * 60, file=sys.stderr)
    print(f"  DFMEA COMPLETE: {result.system_name}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  Total entries : {s.total_entries}", file=sys.stderr)
    print(f"  Critical (≥400): {s.critical_count}", file=sys.stderr)
    print(f"  High (200–399) : {s.high_count}", file=sys.stderr)
    print(f"  Medium (100–199): {s.medium_count}", file=sys.stderr)
    print(f"  Low (<100)     : {s.low_count}", file=sys.stderr)
    print(f"  Max RPN        : {s.max_rpn}", file=sys.stderr)
    print(f"  Avg RPN        : {s.avg_rpn}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    main()
