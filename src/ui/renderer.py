"""
HTML Report Renderer — converts FMEAOutput into a self-contained HTML file.

Uses Jinja2 templating with the fmea_matrix.html template.
The output is a single, portable HTML file with no external dependencies.
"""

from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from fmea_schema import FMEAOutput

_TEMPLATE_DIR = Path(__file__).parent
_TEMPLATE_NAME = "fmea_matrix.html"


def render_html_report(output: FMEAOutput) -> str:
    """
    Render a self-contained HTML FMEA matrix report.

    Args:
        output: Validated FMEAOutput from the agent.

    Returns:
        Complete HTML string suitable for writing to a .html file.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template(_TEMPLATE_NAME)

    context = {
        "system_name": output.system_name,
        "analysis_date": output.analysis_date,
        "doi_reference": output.doi_reference,
        "scope": output.scope,
        "entries": output.entries,
        # Summary fields flattened for easy template access
        "total_entries": output.summary.total_entries,
        "critical_count": output.summary.critical_count,
        "high_count": output.summary.high_count,
        "medium_count": output.summary.medium_count,
        "low_count": output.summary.low_count,
        "max_rpn": output.summary.max_rpn,
        "avg_rpn": output.summary.avg_rpn,
    }

    return template.render(**context)
