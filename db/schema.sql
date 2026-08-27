-- ARTHA SETU — PostgreSQL schema
-- Every table carries source + vintage (non-optional — see project reference §6.4).
-- Adapted from the core schema sketch to match the synthetic dataset's actual
-- columns (01_locations.csv, 02_population_data.csv) while keeping LGD as the
-- join key, per the reference doc.

CREATE TABLE IF NOT EXISTS villages (
    location_id            TEXT PRIMARY KEY,          -- dataset's natural key, e.g. loc_CGP_01
    lgd_code                TEXT NOT NULL,
    village                 TEXT NOT NULL,
    block                   TEXT NOT NULL,
    district                TEXT NOT NULL,
    region                   TEXT NOT NULL,
    state                    TEXT NOT NULL,
    latitude                 DOUBLE PRECISION NOT NULL,
    longitude                DOUBLE PRECISION NOT NULL,
    urban_rural_flag         TEXT NOT NULL,             -- urban | peri-urban | rural-agri | ...
    data_source               TEXT NOT NULL,
    data_vintage_date         DATE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_villages_district ON villages (district);
CREATE INDEX IF NOT EXISTS idx_villages_block ON villages (block);
CREATE INDEX IF NOT EXISTS idx_villages_name_trgm ON villages USING gin (village gin_trgm_ops);

CREATE TABLE IF NOT EXISTS population (
    location_id                        TEXT PRIMARY KEY REFERENCES villages(location_id),
    population_2011                     INTEGER NOT NULL,
    households_2011                     INTEGER NOT NULL,
    catchment_population_default        INTEGER NOT NULL,
    sc_st_percent                        NUMERIC(5,2) NOT NULL,
    below_poverty_line_percent           NUMERIC(5,2) NOT NULL,
    data_source                           TEXT NOT NULL,
    data_vintage_date                     DATE NOT NULL,
    confidence_flag                       TEXT NOT NULL
);

-- Catchment cache: materialised 5km/10km buffer aggregates, populated by the
-- Feasibility Engine in build stage 4 (needs pairwise haversine distances
-- over `villages`, computed once, not per request — R1).
CREATE TABLE IF NOT EXISTS catchment_cache (
    location_id            TEXT NOT NULL REFERENCES villages(location_id),
    radius_km               INTEGER NOT NULL CHECK (radius_km IN (5, 10)),
    catchment_population     INTEGER NOT NULL,
    catchment_households      INTEGER NOT NULL,
    village_count             INTEGER NOT NULL,
    computed_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (location_id, radius_km)
);

-- Activity templates (capex/opex/working-capital per business category).
-- Loaded from 04_business_cost_profiles.csv (NABARD-sourced, per project
-- reference §5.2.9 — highest fabrication risk item, content not code).
CREATE TABLE IF NOT EXISTS activity_templates (
    id                      SERIAL PRIMARY KEY,
    business_category        TEXT NOT NULL,
    cost_component             TEXT NOT NULL,
    cost_component_type          TEXT NOT NULL CHECK (cost_component_type IN ('capex', 'opex')),
    unit_cost_inr                  NUMERIC(14,2) NOT NULL,
    unit_description                 TEXT NOT NULL,
    quantity_default                   NUMERIC(10,2) NOT NULL,
    total_cost_inr                       NUMERIC(14,2) NOT NULL,
    scale_category                         TEXT NOT NULL,
    data_source                              TEXT NOT NULL,
    data_vintage_date                          DATE NOT NULL,
    confidence_level                             TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activity_templates_category ON activity_templates (business_category);

-- Competitor counts per (location, category). Sourced from the synthetic
-- dataset's pre-formula fields (competitor_count / nearest_competitor_km in
-- 08_module1_feasibility_assessment.csv are generated *before* the
-- feasibility-score formula runs — see generate_synthetic_dataset_scaled.py
-- build_competitor_analysis_csv/COMPETITOR_LOOKUP — so they're treated as
-- raw input here, analogous to what EC 2013 would supply in production;
-- the feasibility SCORE itself is computed fresh by our own engine, not
-- copied). See docs/DATA_DECISIONS.md addendum.
CREATE TABLE IF NOT EXISTS competitors (
    location_id            TEXT NOT NULL REFERENCES villages(location_id),
    business_category        TEXT NOT NULL,
    competitor_count           INTEGER NOT NULL,
    nearest_competitor_km        NUMERIC(6,2) NOT NULL,
    data_source                    TEXT NOT NULL,
    PRIMARY KEY (location_id, business_category)
);

-- District-level market prices (05_market_prices.csv — Agmarknet-style).
CREATE TABLE IF NOT EXISTS market_prices (
    market_id             TEXT PRIMARY KEY,
    product                  TEXT NOT NULL,
    district                   TEXT NOT NULL,
    region                       TEXT NOT NULL,
    price_modal_inr                NUMERIC(12,2) NOT NULL,
    price_min_inr                    NUMERIC(12,2) NOT NULL,
    price_max_inr                      NUMERIC(12,2) NOT NULL,
    price_unit                           TEXT NOT NULL,
    price_date                             DATE NOT NULL,
    price_source                             TEXT NOT NULL,
    data_vintage_days_ago                      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_market_prices_district_product ON market_prices (district, product);

-- Statewide seasonality calendar (06_seasonality_profile.csv).
CREATE TABLE IF NOT EXISTS seasonality (
    business_category      TEXT NOT NULL,
    month                     INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    demand_index                NUMERIC(5,2) NOT NULL,
    price_index                   NUMERIC(5,2) NOT NULL,
    revenue_factor                  NUMERIC(5,2) NOT NULL,
    season_label                      TEXT NOT NULL,
    data_source                         TEXT NOT NULL,
    PRIMARY KEY (business_category, month)
);

-- Applicant intake — one row per pre-screening/financial-structuring run.
-- Written by the API layer (module 0 + gate), read by 2a/1/2b downstream.
CREATE TABLE IF NOT EXISTS applicant_sessions (
    session_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id               TEXT NOT NULL REFERENCES villages(location_id),
    business_category          TEXT NOT NULL,
    available_margin_capital_inr NUMERIC(14,2) NOT NULL,
    community                    TEXT,
    annual_family_income_inr      NUMERIC(14,2),
    is_defaulter                    BOOLEAN,
    eligibility_passed               BOOLEAN,
    eligibility_reason                 TEXT,
    created_at                          TIMESTAMPTZ NOT NULL DEFAULT now()
);
