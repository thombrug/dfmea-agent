"""
FMEA Data Models — Pydantic schemas for input, entries, and output.

RPN (Risk Priority Number) = Severity × Occurrence × Detection
Risk level thresholds follow AIAG-VDA FMEA (2019) guidance:
  - low:      RPN < 100
  - medium:   RPN 100–199
  - high:     RPN 200–399
  - critical: RPN ≥ 400
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class ComponentInput(BaseModel):
    """A single component/subsystem to be analyzed."""
    name: str = Field(..., min_length=1, description="Component name")
    function: str = Field(..., min_length=1, description="Intended function of the component")


class FMEAInput(BaseModel):
    """Input contract for the DFMEA agent."""
    system_name: str = Field(..., min_length=1, description="Name of the system being analyzed")
    system_description: str = Field(..., min_length=1, description="System's intended function and context")
    components: list[ComponentInput] = Field(..., min_length=1, description="Components to analyze")
    scope: Literal["design", "process", "system"] = Field(
        default="design",
        description="FMEA scope type",
    )


RiskLevel = Literal["low", "medium", "high", "critical"]


def compute_rpn(severity: int, occurrence: int, detection: int) -> int:
    """RPN = S × O × D per IEC 60812:2018."""
    return severity * occurrence * detection


def classify_risk(rpn: int) -> RiskLevel:
    """Classify RPN into risk level per AIAG-VDA FMEA thresholds."""
    if rpn >= 400:
        return "critical"
    elif rpn >= 200:
        return "high"
    elif rpn >= 100:
        return "medium"
    else:
        return "low"


class FMEAEntry(BaseModel):
    """A single row in the FMEA matrix."""
    id: str = Field(..., description="Unique entry ID, e.g. DFMEA-001")
    component: str = Field(..., description="Component name")
    function: str = Field(..., description="Component intended function")
    failure_mode: str = Field(..., description="How the component could fail")
    failure_effect: str = Field(..., description="Effect of failure on system/user")
    failure_cause: str = Field(..., description="Root cause or mechanism of failure")
    severity: int = Field(..., ge=1, le=10, description="Severity rating 1-10")
    occurrence: int = Field(..., ge=1, le=10, description="Occurrence rating 1-10")
    detection: int = Field(..., ge=1, le=10, description="Detection rating 1-10")
    rpn: int = Field(..., ge=1, le=1000, description="Risk Priority Number = S × O × D")
    recommended_action: str = Field(..., description="Recommended corrective action")
    risk_level: RiskLevel = Field(..., description="Risk classification based on RPN")

    @field_validator("rpn")
    @classmethod
    def rpn_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("RPN must be at least 1")
        return v

    @model_validator(mode="after")
    def validate_rpn_consistency(self) -> "FMEAEntry":
        expected_rpn = self.severity * self.occurrence * self.detection
        if self.rpn != expected_rpn:
            raise ValueError(
                f"RPN {self.rpn} does not match S×O×D = "
                f"{self.severity}×{self.occurrence}×{self.detection} = {expected_rpn}"
            )
        expected_risk = classify_risk(self.rpn)
        if self.risk_level != expected_risk:
            raise ValueError(
                f"risk_level '{self.risk_level}' does not match expected '{expected_risk}' for RPN={self.rpn}"
            )
        return self

    @classmethod
    def create(
        cls,
        id: str,
        component: str,
        function: str,
        failure_mode: str,
        failure_effect: str,
        failure_cause: str,
        severity: int,
        occurrence: int,
        detection: int,
        recommended_action: str,
    ) -> "FMEAEntry":
        """Factory method that auto-computes RPN and risk_level."""
        rpn = compute_rpn(severity, occurrence, detection)
        risk_level = classify_risk(rpn)
        return cls(
            id=id,
            component=component,
            function=function,
            failure_mode=failure_mode,
            failure_effect=failure_effect,
            failure_cause=failure_cause,
            severity=severity,
            occurrence=occurrence,
            detection=detection,
            rpn=rpn,
            recommended_action=recommended_action,
            risk_level=risk_level,
        )


class FMEASummary(BaseModel):
    """Aggregate statistics over all FMEA entries."""
    total_entries: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    max_rpn: int
    avg_rpn: float

    @classmethod
    def from_entries(cls, entries: list[FMEAEntry]) -> "FMEASummary":
        if not entries:
            return cls(
                total_entries=0,
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                max_rpn=0,
                avg_rpn=0.0,
            )
        rpns = [e.rpn for e in entries]
        return cls(
            total_entries=len(entries),
            critical_count=sum(1 for e in entries if e.risk_level == "critical"),
            high_count=sum(1 for e in entries if e.risk_level == "high"),
            medium_count=sum(1 for e in entries if e.risk_level == "medium"),
            low_count=sum(1 for e in entries if e.risk_level == "low"),
            max_rpn=max(rpns),
            avg_rpn=round(sum(rpns) / len(rpns), 2),
        )


class FMEAOutput(BaseModel):
    """Full output contract for the DFMEA agent."""
    system_name: str
    analysis_date: str = Field(..., description="ISO 8601 date, e.g. 2026-02-18")
    doi_reference: str = Field(
        default="10.3390/su12010077",
        description="DOI of methodology source",
    )
    scope: Literal["design", "process", "system"]
    entries: list[FMEAEntry]
    summary: FMEASummary
    html_report: Optional[str] = Field(
        default=None,
        description="Self-contained HTML FMEA matrix report",
    )
