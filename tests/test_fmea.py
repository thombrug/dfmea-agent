"""
Unit tests for the DFMEA agent.

Tests cover:
  - Pydantic model validation (FMEAEntry, FMEAInput, FMEAOutput)
  - RPN computation and risk level classification
  - Summary statistics
  - JSON parsing and entry construction
  - Agent response parsing (with mocked Claude API)

Run with:
  pytest tests/
  pytest tests/ -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fmea_schema import (
    ComponentInput,
    FMEAEntry,
    FMEAInput,
    FMEAOutput,
    FMEASummary,
    classify_risk,
    compute_rpn,
)


# ── RPN Computation ───────────────────────────────────────────────────────────

class TestComputeRPN:
    def test_basic_multiplication(self):
        assert compute_rpn(5, 4, 3) == 60

    def test_maximum_rpn(self):
        assert compute_rpn(10, 10, 10) == 1000

    def test_minimum_rpn(self):
        assert compute_rpn(1, 1, 1) == 1

    def test_critical_threshold(self):
        assert compute_rpn(8, 5, 10) == 400  # exactly critical


# ── Risk Level Classification ─────────────────────────────────────────────────

class TestClassifyRisk:
    def test_low_boundary(self):
        assert classify_risk(1) == "low"
        assert classify_risk(99) == "low"

    def test_medium_boundary(self):
        assert classify_risk(100) == "medium"
        assert classify_risk(199) == "medium"

    def test_high_boundary(self):
        assert classify_risk(200) == "high"
        assert classify_risk(399) == "high"

    def test_critical_boundary(self):
        assert classify_risk(400) == "critical"
        assert classify_risk(1000) == "critical"

    def test_typical_values(self):
        assert classify_risk(48) == "low"
        assert classify_risk(150) == "medium"
        assert classify_risk(280) == "high"
        assert classify_risk(560) == "critical"


# ── FMEAEntry Validation ──────────────────────────────────────────────────────

class TestFMEAEntry:
    def _make_entry(self, s=5, o=3, d=4, **kwargs) -> FMEAEntry:
        defaults = dict(
            id="DFMEA-001",
            component="Brake Caliper",
            function="Apply clamping force",
            failure_mode="Piston seizure",
            failure_effect="Reduced braking force",
            failure_cause="Corrosion due to moisture ingress",
            severity=s,
            occurrence=o,
            detection=d,
            rpn=s * o * d,
            recommended_action="Apply corrosion-resistant coating",
            risk_level=classify_risk(s * o * d),
        )
        defaults.update(kwargs)
        return FMEAEntry(**defaults)

    def test_valid_entry_created(self):
        entry = self._make_entry(s=5, o=3, d=4)
        assert entry.rpn == 60
        assert entry.risk_level == "low"

    def test_create_factory_method(self):
        entry = FMEAEntry.create(
            id="DFMEA-001",
            component="Brake Caliper",
            function="Apply clamping force",
            failure_mode="Piston seizure",
            failure_effect="Reduced braking force",
            failure_cause="Corrosion",
            severity=8,
            occurrence=5,
            detection=10,
            recommended_action="Apply coating",
        )
        assert entry.rpn == 400
        assert entry.risk_level == "critical"

    def test_severity_out_of_range_low(self):
        with pytest.raises(Exception):
            self._make_entry(s=0)

    def test_severity_out_of_range_high(self):
        with pytest.raises(Exception):
            self._make_entry(s=11)

    def test_occurrence_out_of_range(self):
        with pytest.raises(Exception):
            self._make_entry(o=0)

    def test_detection_out_of_range(self):
        with pytest.raises(Exception):
            self._make_entry(d=11)

    def test_rpn_inconsistency_raises(self):
        with pytest.raises(Exception):
            FMEAEntry(
                id="DFMEA-001",
                component="X",
                function="Y",
                failure_mode="Z",
                failure_effect="E",
                failure_cause="C",
                severity=5,
                occurrence=3,
                detection=4,
                rpn=99,  # wrong — should be 60
                recommended_action="Fix it",
                risk_level="low",
            )

    def test_risk_level_inconsistency_raises(self):
        with pytest.raises(Exception):
            FMEAEntry(
                id="DFMEA-001",
                component="X",
                function="Y",
                failure_mode="Z",
                failure_effect="E",
                failure_cause="C",
                severity=9,
                occurrence=9,
                detection=9,
                rpn=729,  # correct
                recommended_action="Fix it",
                risk_level="low",  # wrong — should be critical
            )


# ── FMEAInput Validation ──────────────────────────────────────────────────────

class TestFMEAInput:
    def test_valid_input(self):
        inp = FMEAInput(
            system_name="Test System",
            system_description="A test system for demonstration",
            components=[ComponentInput(name="Widget", function="Does widgety things")],
        )
        assert inp.scope == "design"  # default

    def test_scope_validation(self):
        inp = FMEAInput(
            system_name="Test",
            system_description="Test",
            components=[ComponentInput(name="A", function="B")],
            scope="process",
        )
        assert inp.scope == "process"

    def test_invalid_scope(self):
        with pytest.raises(Exception):
            FMEAInput(
                system_name="Test",
                system_description="Test",
                components=[ComponentInput(name="A", function="B")],
                scope="invalid_scope",
            )

    def test_empty_components_raises(self):
        with pytest.raises(Exception):
            FMEAInput(
                system_name="Test",
                system_description="Test",
                components=[],
            )


# ── FMEASummary Statistics ────────────────────────────────────────────────────

class TestFMEASummary:
    def _make_entries(self, rpns: list[tuple[int, int, int]]) -> list[FMEAEntry]:
        entries = []
        for i, (s, o, d) in enumerate(rpns):
            entries.append(FMEAEntry.create(
                id=f"DFMEA-{i+1:03d}",
                component=f"Component {i+1}",
                function="Function",
                failure_mode="Failure",
                failure_effect="Effect",
                failure_cause="Cause",
                severity=s,
                occurrence=o,
                detection=d,
                recommended_action="Action",
            ))
        return entries

    def test_empty_entries(self):
        summary = FMEASummary.from_entries([])
        assert summary.total_entries == 0
        assert summary.max_rpn == 0
        assert summary.avg_rpn == 0.0

    def test_counts_by_risk_level(self):
        # low=48, medium=150, high=280, critical=400
        entries = self._make_entries([(6, 8, 1), (5, 5, 6), (5, 7, 8), (8, 5, 10)])
        summary = FMEASummary.from_entries(entries)
        assert summary.total_entries == 4
        assert summary.low_count == 1      # 48
        assert summary.medium_count == 1   # 150
        assert summary.high_count == 1     # 280
        assert summary.critical_count == 1 # 400

    def test_max_and_avg_rpn(self):
        entries = self._make_entries([(2, 2, 2), (5, 4, 5), (10, 10, 10)])
        summary = FMEASummary.from_entries(entries)
        assert summary.max_rpn == 1000
        # (8 + 100 + 1000) / 3 = 369.33
        assert summary.avg_rpn == round((8 + 100 + 1000) / 3, 2)


# ── Agent Response Parsing ────────────────────────────────────────────────────

class TestAgentResponseParsing:
    """Test the _parse_and_validate_entries function with mock Claude responses."""

    def _get_parser(self):
        from agent import _parse_and_validate_entries
        return _parse_and_validate_entries

    def test_clean_json_array(self):
        parse = self._get_parser()
        raw = json.dumps([
            {
                "component": "Caliper",
                "function": "Apply force",
                "failure_mode": "Seizure",
                "failure_effect": "No braking",
                "failure_cause": "Corrosion",
                "severity": 9,
                "occurrence": 3,
                "detection": 5,
                "recommended_action": "Apply coating",
            }
        ])
        entries = parse(raw)
        assert len(entries) == 1
        assert entries[0].rpn == 9 * 3 * 5
        assert entries[0].id == "DFMEA-001"

    def test_json_with_markdown_fences(self):
        parse = self._get_parser()
        raw = "```json\n" + json.dumps([
            {
                "component": "Disc",
                "function": "Dissipate heat",
                "failure_mode": "Warping",
                "failure_effect": "Vibration",
                "failure_cause": "Thermal stress",
                "severity": 6,
                "occurrence": 4,
                "detection": 3,
                "recommended_action": "Use vented disc",
            }
        ]) + "\n```"
        entries = parse(raw)
        assert len(entries) == 1
        assert entries[0].component == "Disc"

    def test_missing_json_array_raises(self):
        parse = self._get_parser()
        with pytest.raises(ValueError, match="does not contain a JSON array"):
            parse("Here is a text response without any JSON array.")

    def test_multiple_entries(self):
        parse = self._get_parser()
        raw_entries = [
            {
                "component": f"Component {i}",
                "function": "Function",
                "failure_mode": "Mode",
                "failure_effect": "Effect",
                "failure_cause": "Cause",
                "severity": 5,
                "occurrence": 4,
                "detection": 3,
                "recommended_action": "Action",
            }
            for i in range(5)
        ]
        entries = self._get_parser()(json.dumps(raw_entries))
        assert len(entries) == 5
        assert entries[4].id == "DFMEA-005"


# ── Integration: run_dfmea_agent with mocked API ──────────────────────────────

class TestRunDFMEAAgentMocked:
    """Integration test with mocked Anthropic API."""

    MOCK_RESPONSE = json.dumps([
        {
            "component": "Brake Caliper",
            "function": "Apply clamping force to the brake disc",
            "failure_mode": "Piston seizure",
            "failure_effect": "Partial or complete loss of braking on affected wheel",
            "failure_cause": "Corrosion due to moisture ingress through deteriorated seal",
            "severity": 9,
            "occurrence": 3,
            "detection": 4,
            "recommended_action": (
                "Apply corrosion-resistant PTFE piston coating; "
                "add IP67-rated dust seal; include corrosion test per ISO 9227"
            ),
        },
        {
            "component": "Brake Caliper",
            "function": "Apply clamping force to the brake disc",
            "failure_mode": "Brake fluid leak",
            "failure_effect": "Progressive loss of hydraulic pressure and braking force",
            "failure_cause": "Piston seal deterioration due to thermal cycling",
            "severity": 8,
            "occurrence": 4,
            "detection": 3,
            "recommended_action": (
                "Use EPDM seals rated to 200°C; implement fluid level sensor with dashboard warning"
            ),
        },
    ])

    def test_mocked_agent_returns_valid_output(self):
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=self.MOCK_RESPONSE)]

        with patch("agent.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_message
            MockAnthropic.return_value = mock_client

            from agent import run_dfmea_agent

            inp = FMEAInput(
                system_name="Brake System",
                system_description="Hydraulic disc brake",
                components=[ComponentInput(name="Brake Caliper", function="Apply clamping force")],
            )
            result = run_dfmea_agent(inp)

        assert result.system_name == "Brake System"
        assert len(result.entries) == 2
        assert result.entries[0].rpn == 9 * 3 * 4  # 108
        assert result.entries[1].rpn == 8 * 4 * 3  # 96
        assert result.summary.total_entries == 2
        assert result.summary.medium_count == 1  # RPN=108
        assert result.summary.low_count == 1     # RPN=96
        assert result.doi_reference == "10.3390/su12010077"
