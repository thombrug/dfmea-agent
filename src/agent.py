"""
DFMEA Agent Core — uses the Anthropic Python SDK to execute the FMEA analysis.

The agent sends the system description and components to Claude claude-haiku-4-5,
which returns a structured JSON array of FMEA entries validated against the
Pydantic schema defined in fmea_schema.py.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date

import anthropic

from fmea_schema import (
    FMEAEntry,
    FMEAInput,
    FMEAOutput,
    FMEASummary,
)
from prompts import SYSTEM_PROMPT


def run_dfmea_agent(input_data: FMEAInput) -> FMEAOutput:
    """
    Execute a Design FMEA using Claude claude-haiku-4-5.

    Args:
        input_data: Validated FMEAInput with system info and components.

    Returns:
        FMEAOutput with complete FMEA entries, summary, and (optionally) HTML report.

    Raises:
        ValueError: If Claude returns unparseable or invalid JSON.
        anthropic.APIError: On API communication failures.
    """
    client = anthropic.Anthropic()

    components_json = json.dumps(
        [c.model_dump() for c in input_data.components],
        indent=2,
    )

    user_message = f"""Perform a complete Design FMEA for the following engineering system.

**System Name**: {input_data.system_name}
**FMEA Scope**: {input_data.scope}
**System Description**: {input_data.system_description}

**Components to Analyze**:
{components_json}

Apply the IEC 60812:2018 rating scales from your instructions. Return ONLY the JSON array of FMEA entries, one object per failure mode."""

    print(f"[DFMEA Agent] Calling Claude claude-haiku-4-5 for {len(input_data.components)} component(s)...", file=sys.stderr)

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=8096,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_message},
        ],
    )

    raw_content = message.content[0].text.strip()
    print(f"[DFMEA Agent] Received response ({len(raw_content)} chars). Parsing...", file=sys.stderr)

    entries = _parse_and_validate_entries(raw_content)

    print(f"[DFMEA Agent] Validated {len(entries)} FMEA entries.", file=sys.stderr)

    summary = FMEASummary.from_entries(entries)

    return FMEAOutput(
        system_name=input_data.system_name,
        analysis_date=date.today().isoformat(),
        doi_reference="10.3390/su12010077",
        scope=input_data.scope,
        entries=entries,
        summary=summary,
    )


def _parse_and_validate_entries(raw: str) -> list[FMEAEntry]:
    """
    Extract JSON array from Claude response and validate each entry.

    Claude is instructed to return only the JSON array, but may occasionally
    include markdown fences. This function handles both cases robustly.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    # Find JSON array boundaries
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(
            f"Claude response does not contain a JSON array.\n"
            f"Response (first 500 chars): {raw[:500]}"
        )

    json_str = cleaned[start : end + 1]

    try:
        raw_entries: list[dict] = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from Claude response: {e}\nJSON: {json_str[:500]}") from e

    if not isinstance(raw_entries, list):
        raise ValueError(f"Expected a JSON array, got {type(raw_entries).__name__}")

    entries: list[FMEAEntry] = []
    errors: list[str] = []

    for i, raw_entry in enumerate(raw_entries):
        try:
            entry = FMEAEntry.create(
                id=f"DFMEA-{i + 1:03d}",
                component=raw_entry["component"],
                function=raw_entry["function"],
                failure_mode=raw_entry["failure_mode"],
                failure_effect=raw_entry["failure_effect"],
                failure_cause=raw_entry["failure_cause"],
                severity=int(raw_entry["severity"]),
                occurrence=int(raw_entry["occurrence"]),
                detection=int(raw_entry["detection"]),
                recommended_action=raw_entry["recommended_action"],
            )
            entries.append(entry)
        except (KeyError, ValueError, TypeError) as e:
            errors.append(f"Entry {i + 1}: {e}")

    if errors:
        print(f"[DFMEA Agent] WARNING: {len(errors)} entries had validation errors:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)

    if not entries:
        raise ValueError(
            f"No valid FMEA entries could be extracted. "
            f"Encountered {len(errors)} validation errors."
        )

    return entries
