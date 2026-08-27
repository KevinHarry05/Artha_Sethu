"""
Minimal FastAPI intake layer (tech stack per project reference §6.1).

GET  /          serves the single-page form (location, budget, category,
                 plus the eligibility fields the pre-screening gate needs).
POST /assess     runs the full pipeline (0 -> gate -> 2a -> 1 -> 2b) and
                 returns the Report Object as JSON — Module 1 (feasibility)
                 and Module 2 (financial structuring + repayment/viability)
                 output in full, exactly as the pipeline produced it.

Run locally:
    pip install -r requirements.txt
    python3 -m db.init_db
    python3 -m db.ingest_raw_data /path/to/MAKEATHON_Internal
    uvicorn api.main:app --reload
    # open http://127.0.0.1:8000
"""

import os
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from api.auth_routes import router as auth_router
from pipeline import run_pipeline

app = FastAPI(title="ARTHA SETU")

# CORS -- FronteEnd (Next.js) runs on a different origin (localhost:3000)
# than this API (localhost:8000); the browser silently discards a
# cross-origin response without these headers even when the request
# succeeded server-side. Override with FRONTEND_ORIGINS (comma-separated)
# if FronteEnd runs somewhere else, e.g. FRONTEND_ORIGINS=http://localhost:3001
_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("FRONTEND_ORIGINS", _default_origins).split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)  # POST /auth/signup, POST /auth/login

TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"


def decimal_safe(obj):
    """Recursively converts Decimal -> float so FastAPI's default JSON
    encoder can serialize the report object (Decimal is used everywhere
    upstream per R4 — this is the one place it's allowed to lossily become
    a float, purely for wire transport to the browser)."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: decimal_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decimal_safe(v) for v in obj]
    return obj


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


@app.post("/assess")
def assess(
    location: str = Form(...),
    budget: float = Form(...),
    category: str = Form(...),
    community: str = Form("SC"),
    annual_income: float = Form(120000),
    is_defaulter: bool = Form(False),
    moratorium_mode: str = Form("SERVICED"),
):
    if budget <= 0:
        return JSONResponse(status_code=400, content={"error": "Budget/margin must be greater than zero."})
    if category not in ("Dairy", "Retail", "Textiles"):
        return JSONResponse(status_code=400, content={"error": f"Unknown category '{category}'."})

    try:
        report = run_pipeline(
            location_query=location, business_category=category, margin_available=Decimal(str(budget)),
            community=community, annual_family_income_inr=Decimal(str(annual_income)),
            is_defaulter=is_defaulter, moratorium_mode=moratorium_mode,
        )
    except Exception as e:  # pipeline exceptions surface as a clean 400, not a stack trace
        return JSONResponse(status_code=400, content={"error": f"{type(e).__name__}: {e}"})

    trace = [
        {"step": t.step, "inputs": decimal_safe(t.inputs), "formula": t.formula,
         "output": decimal_safe(t.output), "sources": t.sources}
        for t in report.trace
    ]

    return {
        "report_id": report.report_id,
        "generated_at": report.generated_at,
        "data_snapshot_version": report.data_snapshot_version,
        "location": decimal_safe(report.location),
        "eligibility": report.eligibility,
        "financial_structuring": decimal_safe(report.financial_structuring),   # Module 2 (part 1)
        "feasibility": decimal_safe(report.feasibility),                        # Module 1
        "repayment_viability": decimal_safe(report.repayment_viability),        # Module 2 (part 2)
        "dashboard": decimal_safe(report.dashboard),                             # composite overview
        "trace": trace,
    }
