"""
Loads the raw input CSVs (01_locations.csv, 02_population_data.csv) into
Postgres. Per docs/DATA_DECISIONS.md, only these two are treated as real
input data at this stage — 07-13 are the generator's own precomputed
outputs and are not ingested here.

Usage: python3 -m db.ingest_raw_data /path/to/MAKEATHON_Internal
"""

import csv
import sys
from pathlib import Path

from db.connection import get_connection


def ingest_locations(conn, data_dir: Path) -> int:
    path = data_dir / "01_locations.csv"
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    cur = conn.cursor()
    cur.execute("TRUNCATE villages CASCADE;")
    for r in rows:
        cur.execute(
            """
            INSERT INTO villages
                (location_id, lgd_code, village, block, district, region, state,
                 latitude, longitude, urban_rural_flag, data_source, data_vintage_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                r["location_id"], r["lgd_code"], r["village"], r["block"], r["district"],
                r["region"], r["state"], float(r["latitude"]), float(r["longitude"]),
                r["urban_rural_flag"], r["data_source"], r["data_vintage_date"],
            ),
        )
    conn.commit()
    cur.close()
    return len(rows)


def ingest_population(conn, data_dir: Path) -> int:
    path = data_dir / "02_population_data.csv"
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    cur = conn.cursor()
    cur.execute("TRUNCATE population;")
    for r in rows:
        cur.execute(
            """
            INSERT INTO population
                (location_id, population_2011, households_2011, catchment_population_default,
                 sc_st_percent, below_poverty_line_percent, data_source, data_vintage_date, confidence_flag)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                r["location_id"], int(r["population_2011"]), int(r["households_2011"]),
                int(r["catchment_population_default"]), float(r["sc_st_percent"]),
                float(r["below_poverty_line_percent"]), r["data_source"],
                r["data_vintage_date"], r["confidence_flag"],
            ),
        )
    conn.commit()
    cur.close()
    return len(rows)


def ingest_activity_templates(conn, data_dir: Path) -> int:
    path = data_dir / "04_business_cost_profiles.csv"
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    cur = conn.cursor()
    cur.execute("TRUNCATE activity_templates RESTART IDENTITY;")
    for r in rows:
        cur.execute(
            """
            INSERT INTO activity_templates
                (business_category, cost_component, cost_component_type, unit_cost_inr,
                 unit_description, quantity_default, total_cost_inr, scale_category,
                 data_source, data_vintage_date, confidence_level)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                r["business_category"], r["cost_component"], r["cost_component_type"],
                float(r["unit_cost_inr"]), r["unit_description"], float(r["quantity_default"]),
                float(r["total_cost_inr"]), r["scale_category"], r["data_source"],
                r["data_vintage_date"], r["confidence_level"],
            ),
        )
    conn.commit()
    cur.close()
    return len(rows)


def ingest_competitors(conn, data_dir: Path) -> int:
    """Reads competitor_count / nearest_competitor_km from
    08_module1_feasibility_assessment.csv — these two fields are generated
    before the feasibility-score formula runs (see docs/DATA_DECISIONS.md
    addendum), so they're treated as raw input, not derived output. No
    other column from that file is read here."""
    path = data_dir / "08_module1_feasibility_assessment.csv"
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    cur = conn.cursor()
    cur.execute("TRUNCATE competitors;")
    for r in rows:
        cur.execute(
            """
            INSERT INTO competitors (location_id, business_category, competitor_count,
                                      nearest_competitor_km, data_source)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (location_id, business_category) DO NOTHING
            """,
            (
                r["location_id"], r["business_category"], int(r["competitor_count"]),
                float(r["nearest_competitor_km"]),
                "synthetic_illustrative_demo (pre-formula field, treated as raw input)",
            ),
        )
    conn.commit()
    cur.close()
    return len(rows)


def ingest_market_prices(conn, data_dir: Path) -> int:
    path = data_dir / "05_market_prices.csv"
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    cur = conn.cursor()
    cur.execute("TRUNCATE market_prices;")
    for r in rows:
        cur.execute(
            """
            INSERT INTO market_prices (market_id, product, district, region, price_modal_inr,
                                        price_min_inr, price_max_inr, price_unit, price_date,
                                        price_source, data_vintage_days_ago)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                r["market_id"], r["product"], r["district"], r["region"], float(r["price_modal_inr"]),
                float(r["price_min_inr"]), float(r["price_max_inr"]), r["price_unit"], r["price_date"],
                r["price_source"], int(r["data_vintage_days_ago"]),
            ),
        )
    conn.commit()
    cur.close()
    return len(rows)


def ingest_seasonality(conn, data_dir: Path) -> int:
    path = data_dir / "06_seasonality_profile.csv"
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    cur = conn.cursor()
    cur.execute("TRUNCATE seasonality;")
    for r in rows:
        cur.execute(
            """
            INSERT INTO seasonality (business_category, month, demand_index, price_index,
                                      revenue_factor, season_label, data_source)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                r["business_category"], int(r["month"]), float(r["demand_index"]),
                float(r["price_index"]), float(r["revenue_factor"]), r["season_label"],
                r["data_source"],
            ),
        )
    conn.commit()
    cur.close()
    return len(rows)


def main(data_dir: str) -> None:
    data_path = Path(data_dir)
    with get_connection() as conn:
        n_loc = ingest_locations(conn, data_path)
        n_pop = ingest_population(conn, data_path)
        n_act = ingest_activity_templates(conn, data_path)
        n_comp = ingest_competitors(conn, data_path)
        n_price = ingest_market_prices(conn, data_path)
        n_season = ingest_seasonality(conn, data_path)
    print(
        f"Ingested {n_loc} locations, {n_pop} population rows, {n_act} activity template rows, "
        f"{n_comp} competitor rows, {n_price} market price rows, {n_season} seasonality rows."
    )


if __name__ == "__main__":
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/MAKEATHON_Internal"
    main(data_dir)
