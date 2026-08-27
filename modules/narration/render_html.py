"""
Minimal dashboard / printable annexure stub (§4.7).

Renders a ReportObject as a single self-contained HTML page — the
versioned annexure the beneficiary carries to their SCA (report ID, data
snapshot version, timestamp, every figure with its source, full trace).
PDF export (WeasyPrint, per the tech stack in the reference doc) reuses
this same HTML and is deferred to a later stage — this function is written
so that step is a one-line `weasyprint.HTML(string=html).write_pdf(...)`
wrap, not a rewrite.
"""

from decimal import Decimal
from html import escape

from modules.narration import render as render_text


def _inr(value) -> str:
    return f"&#8377;{Decimal(str(value)):,.2f}"


def render_html(report_object) -> str:
    r = report_object
    text_narration = escape(render_text(r))

    trace_rows = "".join(
        f"<tr><td>{escape(step.step)}</td><td>{escape(str(step.inputs))}</td>"
        f"<td>{escape(step.formula)}</td><td>{escape(str(step.output))}</td>"
        f"<td>{escape(', '.join(step.sources))}</td></tr>"
        for step in r.trace
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ARTHA SETU Report {escape(r.report_id)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; line-height: 1.5; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; }}
  .meta {{ color: #555; font-size: 0.85rem; margin-bottom: 1.5rem; }}
  pre {{ white-space: pre-wrap; background: #f7f7f7; padding: 1rem; border-radius: 6px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.8rem; margin-top: 1rem; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; vertical-align: top; }}
  th {{ background: #f0f0f0; }}
</style>
</head>
<body>
  <h1>ARTHA SETU — Feasibility &amp; Financial Structuring Report</h1>
  <div class="meta">
    Report ID: {escape(r.report_id)} &middot;
    Data snapshot: {escape(r.data_snapshot_version)} &middot;
    Generated: {escape(r.generated_at)}
  </div>
  <pre>{text_narration}</pre>
  <h2>Calculation trace</h2>
  <table>
    <thead><tr><th>Step</th><th>Inputs</th><th>Formula</th><th>Output</th><th>Sources</th></tr></thead>
    <tbody>{trace_rows}</tbody>
  </table>
</body>
</html>"""
