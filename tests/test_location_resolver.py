"""Stage 2 tests: Location Resolver + Pre-Screening Gate against real Postgres data."""

import pytest

from modules.location_resolver import (
    LocationAmbiguous,
    LocationNotFound,
    LocationNotRecognized,
    get_population,
    resolve_location,
)
from modules.pre_screening_gate import check_eligibility


def test_resolve_exact_village_name():
    loc = resolve_location("Chengalpattu Town (HQ)")
    assert loc["location_id"] == "loc_CGP_01"
    assert loc["district"] == "Chengalpattu"
    assert loc["lgd_code"] == "TN-CGP-001"


def test_resolve_by_location_id():
    loc = resolve_location("loc_CGP_01")
    assert loc["village"] == "Chengalpattu Town (HQ)"


def test_resolve_unrecognized_place_raises_with_suggestions():
    # Updated per product decision: a place that matches nothing in the
    # curated dataset AND nothing in the locality/city/state gazetteer no
    # longer gets a fabricated coordinate (that used to silently place
    # "Ohio" or a typo inside India and feed a real-looking catchment
    # calculation). It now raises LocationNotRecognized, carrying
    # best-effort "did you mean" suggestions instead.
    with pytest.raises(LocationNotRecognized) as exc_info:
        resolve_location("Nonexistent Place Xyz123")
    assert isinstance(exc_info.value.suggestions, list)


def test_resolve_real_place_outside_india_raises_not_fabricates():
    # The concrete case that motivated the change: a real place that just
    # isn't in India shouldn't get a real-looking Indian coordinate.
    with pytest.raises(LocationNotRecognized):
        resolve_location("Ohio")


def test_resolve_only_raises_on_empty_query():
    with pytest.raises(LocationNotFound):
        resolve_location("")


def test_resolve_locality_koramangala_maps_to_bengaluru():
    loc = resolve_location("Koramangala")
    assert loc["district"] == "Bengaluru Urban"
    assert loc["state"] == "Karnataka"
    assert loc["urban_rural_flag"] == "urban"


def test_resolve_city_bengaluru_alt_spelling():
    loc1 = resolve_location("Bengaluru")
    loc2 = resolve_location("bangalore")
    assert loc1["district"] == loc2["district"] == "Bengaluru Urban"


def test_resolve_bare_state_name_falls_back_to_capital():
    loc = resolve_location("Rajasthan")
    assert loc["state"] == "Rajasthan"
    assert loc["district"] == "Jaipur"


def test_resolve_auto_location_is_idempotent():
    loc1 = resolve_location("Koramangala")
    loc2 = resolve_location("Koramangala")
    assert loc1["location_id"] == loc2["location_id"]


def test_auto_resolved_location_has_working_population_and_competitors():
    from modules.feasibility_engine import get_competitors

    loc = resolve_location("Whitefield")
    pop = get_population(loc["location_id"])
    assert pop["population_2011"] > 0
    comp = get_competitors(loc["location_id"], "Dairy")
    assert comp.value >= 0


def test_resolve_fuzzy_typo():
    # one-character typo should still resolve via trigram similarity
    loc = resolve_location("Chengalpattu Twon (HQ)")
    assert loc["location_id"] == "loc_CGP_01"


def test_get_population():
    pop = get_population("loc_CGP_01")
    assert pop["population_2011"] == 65423
    assert pop["catchment_population_default"] == 66499


def test_eligibility_passes_for_sc_within_income():
    result = check_eligibility(community="SC", annual_family_income_inr=250000, is_defaulter=False)
    assert result.passed
    assert result.reasons == []


def test_eligibility_fails_over_income_ceiling():
    result = check_eligibility(community="SC", annual_family_income_inr=350000, is_defaulter=False)
    assert not result.passed
    assert any("income" in r.lower() for r in result.reasons)


def test_eligibility_fails_for_defaulter():
    result = check_eligibility(community="SC", annual_family_income_inr=100000, is_defaulter=True)
    assert not result.passed
    assert any("default" in r.lower() for r in result.reasons)


def test_eligibility_fails_for_wrong_community():
    result = check_eligibility(community="OBC", annual_family_income_inr=100000, is_defaulter=False)
    assert not result.passed
