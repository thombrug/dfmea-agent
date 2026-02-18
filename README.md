# Design FMEA Agent

A **Science-Backed Agent** that executes Design Failure Mode and Effects Analysis (DFMEA) for engineering systems. Built on IEC 60812:2018 and INCOSE Systems Engineering methodology, grounded in a peer-reviewed publication.

**Scientific basis:** Rajput, M.S. et al. (2020). *A System Engineering Approach Using FMEA and Bayesian Network for Risk Analysis—A Case Study*. Sustainability, 12(1), 77. [doi:10.3390/su12010077](https://doi.org/10.3390/su12010077)

---

## What is DFMEA?

Design Failure Mode and Effects Analysis (DFMEA) is a systematic risk analysis method used in systems engineering to:

1. **Identify** potential ways a component or system can fail (failure modes)
2. **Assess** the severity of each failure's effect on the system and end user (S = 1–10)
3. **Rate** how likely each failure is to occur (O = 1–10)
4. **Rate** how detectable each failure is before reaching the customer (D = 1–10)
5. **Compute** the Risk Priority Number: **RPN = S × O × D** (range: 1–1000)
6. **Prioritize** corrective actions based on RPN thresholds

DFMEA is mandated by INCOSE's V-model, referenced in VDI 2206 (mechatronic systems design methodology), and formalized in IEC 60812:2018.

### Risk Thresholds (AIAG-VDA FMEA, 2019)

| Risk Level | RPN Range | Action Required |
|------------|-----------|-----------------|
| 🔴 Critical | ≥ 400 | Immediate corrective action |
| 🟠 High | 200–399 | High priority action required |
| 🟡 Medium | 100–199 | Action recommended in near term |
| 🟢 Low | < 100 | Monitor and review |

---

## Quick Start

### 1. Install Dependencies

```bash
cd examples/dfmea-agent
pip install -r requirements.txt
```

### 2. Set API Key

```bash
export ANTHROPIC_API_KEY=your-api-key-here
```

### 3. Run the Built-in Example (Automotive Brake System)

```bash
python src/main.py
```

This runs a DFMEA on a 5-component automotive disc brake system and produces:
- `fmea_output.json` — structured JSON output
- `fmea_report.html` — interactive color-coded matrix (open in any browser)

### 4. Run with Custom Input

```bash
python src/main.py my_system.json
```

See [Input Format](#input-format) below.

### 5. Run Tests

```bash
pytest tests/ -v
```

---

## Input Format

```json
{
  "system_name": "Hydraulic Pump System",
  "system_description": "A high-pressure hydraulic pump used in industrial machinery operating at 250 bar, continuous duty cycle, ambient temperature -10°C to +60°C.",
  "components": [
    {
      "name": "Pump Housing",
      "function": "Contain hydraulic fluid and support rotating components"
    },
    {
      "name": "Rotating Group (Pistons)",
      "function": "Convert mechanical rotational input to hydraulic pressure"
    },
    {
      "name": "Valve Plate",
      "function": "Control timing of fluid intake and discharge strokes"
    },
    {
      "name": "Shaft Seal",
      "function": "Prevent hydraulic fluid leakage at the drive shaft interface"
    }
  ],
  "scope": "design"
}
```

**Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `system_name` | string | ✅ | Name of the system being analyzed |
| `system_description` | string | ✅ | Function, environment, and operating conditions |
| `components` | array | ✅ | List of components (min 1) |
| `components[].name` | string | ✅ | Component name |
| `components[].function` | string | ✅ | Intended function of the component |
| `scope` | enum | ❌ | `"design"` (default), `"process"`, or `"system"` |

---

## Output Format

```json
{
  "system_name": "Automotive Disc Brake System",
  "analysis_date": "2026-02-18",
  "doi_reference": "10.3390/su12010077",
  "scope": "design",
  "entries": [
    {
      "id": "DFMEA-001",
      "component": "Brake Caliper",
      "function": "Apply clamping force to the brake disc",
      "failure_mode": "Piston seizure",
      "failure_effect": "Partial or complete loss of braking on affected wheel",
      "failure_cause": "Corrosion due to moisture ingress through deteriorated seal",
      "severity": 9,
      "occurrence": 3,
      "detection": 4,
      "rpn": 108,
      "recommended_action": "Apply corrosion-resistant PTFE piston coating; add IP67-rated dust seal",
      "risk_level": "medium"
    }
  ],
  "summary": {
    "total_entries": 14,
    "critical_count": 1,
    "high_count": 3,
    "medium_count": 7,
    "low_count": 3,
    "max_rpn": 504,
    "avg_rpn": 187.5
  }
}
```

---

## HTML Report

The agent generates a self-contained, interactive HTML report (`fmea_report.html`) featuring:

- **Color-coded rows** by risk level (red/orange/yellow/green)
- **Sortable columns** — click any column header to sort
- **Risk filter buttons** — filter to show only critical, high, medium, or low entries
- **Summary statistics cards** with counts by risk level, max and avg RPN
- **DOI badge** linking to the methodology publication
- **Print-friendly** layout
- **Mobile responsive**
- **No external dependencies** — single portable HTML file

---

## Project Structure

```
dfmea-agent/
├── agent.yaml              # Platform manifest (input/output contract + metadata)
├── README.md               # This file
├── requirements.txt        # Python dependencies
├── src/
│   ├── main.py             # CLI entrypoint
│   ├── agent.py            # Claude claude-opus-4-6 DFMEA reasoning core
│   ├── fmea_schema.py      # Pydantic models + RPN/risk logic
│   ├── prompts.py          # System prompt (IEC 60812:2018 scales embedded)
│   └── ui/
│       ├── fmea_matrix.html  # Jinja2 HTML template
│       └── renderer.py       # HTML report generator
└── tests/
    └── test_fmea.py        # Unit tests (RPN, risk levels, parsing, mocked API)
```

---

## Platform Integration (agent.yaml)

This project is structured as a **Science-Backed Agent** for the platform. The `agent.yaml` file defines:

- **`name`**: `dfmea-agent` — unique slug for the platform
- **`doi`**: `10.3390/su12010077` — peer-reviewed scientific basis
- **`fields`**: `["2.3", "2.11"]` — OECD taxonomy (Mechanical Engineering, Other Engineering)
- **`input`** / **`output`**: JSON Schema contracts validated by the platform
- **`tools`**: `run_dfmea` — exposed as an MCP tool via `/api/agents/[id]/mcp`

### MCP Endpoint

Once registered on the platform, the agent exposes an MCP-compatible endpoint:

```bash
# List available tools
curl -X POST https://your-platform.com/api/agents/[id]/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# Call the DFMEA tool
curl -X POST https://your-platform.com/api/agents/[id]/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 2,
    "params": {
      "name": "run_dfmea",
      "arguments": {
        "system_name": "My System",
        "system_description": "...",
        "components": [{"name": "A", "function": "B"}]
      }
    }
  }'
```

---

## References

| Source | Role |
|--------|------|
| Rajput et al. (2020), *Sustainability* — [doi:10.3390/su12010077](https://doi.org/10.3390/su12010077) | Primary scientific reference (open access) |
| IEC 60812:2018 — *Analysis techniques for system reliability: FMEA* | Rating scales and procedure |
| INCOSE Systems Engineering Handbook, 4th Ed. (2015), §9.4 | V-model FMEA integration |
| VDI 2206:2004 — *Design methodology for mechatronic systems* | RFLP + FMEA workflow |
| AIAG-VDA FMEA Handbook (2019) | Risk threshold classification |
