# Data source decisions — logged 27 Aug 2026

The `MAKEATHON_Internal` folder ships a full synthetic dataset (13 CSVs,
~7,600 rows) plus `generate_synthetic_dataset_scaled.py`, the deterministic
generator that produced them. This is separate from — and generated before —
the engines this repo builds. Two decisions, confirmed with the team:

## 1. Scheme parameters: real NSFDC, not the dataset's "SUVIDHA"

`07_scheme_rules.csv` defines a fictional single-tier "NSFDC SUVIDHA" scheme
(10% margin, 8% flat interest, 5yr tenure, 3mo moratorium, ₹9L loan cap,
project cost band ₹25k–₹10L) invented for the generator. It does not match
the real, nsfdc.nic.in-verified two-tier scheme already in
`config/scheme_config.yaml` (Micro Credit Finance ≤₹1.4L @ 6.5%, Term Loan
≤₹50L @ 8%, caps ₹1.25L/₹45L).

**Decision:** the Financial Structuring engine (module 2a) implements the
real NSFDC scheme from `config/scheme_config.yaml`. It will not numerically
reproduce columns in `07_scheme_rules.csv`, `12_module2_financial_assessment.csv`,
or `13_repayment_schedule.csv` (those used SUVIDHA) when driven with real
parameters — this is expected and correct.

## 2. Formulas: reproduce the generator's shapes exactly, re-parameterize with real scheme

Files 08–13 are precomputed outputs of the generator, not raw source data.
Per team decision, our engines reproduce the generator's formulas exactly
(same shape, same inputs) — verified below — but driven by
`config/scheme_config.yaml` instead of `07_scheme_rules.csv`. This gives us
a validation path: run the engine with the SUVIDHA preset against the raw
inputs and diff against 08-13 to prove the engine logic is correct, then
switch to the real NSFDC preset for the actual pitch/demo.

Formulas extracted from `generate_synthetic_dataset_scaled.py` (all
`Decimal`-based, quantized to 2dp with `ROUND_HALF_UP`):

**Feasibility (module 1):**
```
demand_gap_pct   = 100 * (1 - competitor_count / (competitor_count + 5))
feasibility_score = 0.35 + (demand_gap_pct/100)*0.45 - (risk_severity*0.02) + (nearest_km*0.01)
                     clamped to [0, 1]
opportunity_class:   >=0.75 high | >=0.55 medium | >=0.35 low | else saturated
feasibility_category: >=0.70 highly_feasible | >=0.50 feasible | >=0.35 marginal | else not_feasible
effective_daily_units = base_daily_units * (0.7 + (gap/100)*0.3)
monthly_revenue        = effective_daily_units * 30 * price_modal
```

**Financial structuring / borrow-right (module 2a):**
```
entitled_max_project_cost = margin / 0.10
recommended_project_cost  = MIN(entitled_max_project_cost, operational_project_cost)
loan_amount                = MAX(0, recommended_project_cost - margin)
margin_safety_flag         = within_ceiling  if entitled_max >= operational_cost
                              else margin_insufficient_for_full_scale
```
Note: our real-scheme engine replaces the fixed 10% with config's per-tier
`loan_share_pct`/cap-clamp logic (project reference §2.5 item 3 — caps
override the percentage), which SUVIDHA's flat 10%/no-clamp does not need.

**Quarterly installment (standard amortizing, declining balance):**
```
r = (annual_rate_pct / 100) / 4
installment = P * r * (1+r)^n / ((1+r)^n - 1)      # n = tenure_years * 4
```

**Repayment schedule:** moratorium quarters = moratorium_months // 3 (min 1),
interest-only during moratorium, `seasonality_factor` applied to installment
post-moratorium only, standard declining-balance amortization otherwise.

**Viability:**
```
dsr_peak   = monthly_equivalent_installment / minimum_monthly_revenue (worst season month)
viability  = clamp(1 - dsr_peak, 0, 1)
status:  viable (dsr_peak<0.35 & within_ceiling) | marginal (dsr_peak<0.50) | at_risk (else)
```

## Files treated as raw input data (used as-is by our engines)
`01_locations.csv`, `02_population_data.csv`, `04_business_cost_profiles.csv`,
`05_market_prices.csv`, `06_seasonality_profile.csv`.

## Files treated as generator output / validation oracle only
`03_applicants.csv` (demo applicant scenarios — reusable as engine test
fixtures), `07_scheme_rules.csv`, `08`–`13` (regenerate via our engine with
a SUVIDHA-preset config and diff against these for correctness; not
authoritative for the real-scheme demo).
