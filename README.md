# ARTHA SETU

AI Business Advisory Assistant with Smart Scheme Calculator — SIH 2026, PS SIH26091.
Team PIXIL.

**Governing principle: Code computes. The LLM only speaks.**
Every number is produced by deterministic Python. The LLM only narrates finished
numbers into human language and is structurally barred from emitting raw digits.

## Architecture (build order: 0 → gate → 2a → 1 → 2b → report)

```
USER INPUT (location, margin capital, business category, eligibility info)
        │
        ▼
[0] LOCATION RESOLVER        village → LGD/Census codes, block, district, coordinates
        │
        ▼
[PRE-SCREENING GATE]         community · income ceiling · non-defaulter status
        │
        ▼
[2a] FINANCIAL STRUCTURING   two-way solver → project cost, loan, scheme, margin
        │  (budget tier passed down)
        ▼
[1] FEASIBILITY ENGINE       catchment · competitors · demand · pricing · risk · SWOT
        │  (expected revenue passed down)
        ▼
[2b] REPAYMENT & VIABILITY   quarterly amortisation · surplus · coverage · scenario verdict
        │
        ▼
REPORT OBJECT { values, intervals, sources, vintages, trace }
        │
        ├──► Narration layer (slot-filled, digit-rejecting) ──► multilingual text
        └──► Dashboard / printable PDF
```

## Repo layout

```
config/                  scheme_config.yaml — NSFDC parameters, DO NOT hardcode in modules
modules/
  location_resolver/     [0] village → LGD/Census codes
  financial_structuring/ [2a] two-way solver, scheme router, project cost builder
  feasibility_engine/    [1] catchment, competitors, demand, pricing, risk, SWOT
  repayment_viability/   [2b] amortisation, surplus, coverage, interval verdict
  narration/             slot-filling templates + LLM narration wrapper
schema/                  Evidence, ReportObject data contracts shared by all modules
data/
  raw/                   untouched source downloads (SHRUG, Census, HCES, ...)
  processed/             cleaned/joined tables the engines actually query
tests/                   pytest — unit tests + property tests (R9)
docs/                    reference material, decisions, ADRs
```

## Build stages (tracked — proceed one at a time)

1. Project scaffold (this commit) — folders, config stub, data contracts, no logic
2. Location Resolver + Pre-Screening Gate
3. Module 2a — Financial Structuring
4. Module 1 — Feasibility Engine (stub data providers first)
5. Module 2b — Repayment & Viability
6. Report Object assembly + Narration layer + dashboard/PDF stub

See `docs/artha_setu_reference.md` for the full project reference (problem statement,
scheme ground truth, data sources, engineering rules), and `docs/DATA_DECISIONS.md`
for how the bundled synthetic dataset is used.

## Database setup (PostgreSQL — the project's backend)

```
pip install -r requirements.txt
python3 -m db.init_db                              # creates schema (pg_trgm, pgcrypto, tables)
python3 -m db.ingest_raw_data /path/to/MAKEATHON_Internal   # loads 01_locations.csv, 02_population_data.csv
pytest tests/ -q
```

Connection string comes from `DATABASE_URL`; defaults to
`postgresql://postgres:artha_setu_dev@localhost:5432/artha_setu` for local dev
(see `db/connection.py`). `villages` and `population` are ingested now (build
stage 2); `catchment_cache`, `establishments`, `consumption`, `prices`,
`activity_templates`, `scheme_config` land as later stages need them.

## Running the frontend

```
uvicorn api.main:app --reload
```
Then open http://127.0.0.1:8000 — a single-page form (location, budget,
category, plus eligibility fields) that calls `POST /assess`, which runs the
full pipeline and returns Module 1 (Feasibility) and Module 2 (Financial
Structuring + Repayment/Viability) output in full, along with the
calculation trace. Location accepts anything in India, not just the curated
Tamil Nadu dataset — see modules/location_resolver/synth.py.
