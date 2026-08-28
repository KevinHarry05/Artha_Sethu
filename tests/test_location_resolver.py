"""Stage 2 tests: Location Resolver + Pre-Screening Gate against real Postgres data."""

import pytest

from modules.location_resolver import (
    LocationNotFound,
    LocationNotRecognized,
    get_population,
    resolve_location,
)
from modules.pre_screening_gate import check_eligibility


def test_resolve_exact_pincode():
    # loc_CGP_01 was assigned pincode 600001 (01_locations.csv, row 1 --
    # pincodes assigned sequentially starting at 600001).
    loc = resolve_location("600001")
    assert loc["location_id"] == "loc_CGP_01"
    assert loc["district"] == "Chengalpattu"
    assert loc["lgd_code"] == "TN-CGP-001"
    assert loc["pincode"] == "600001"


def test_resolve_by_location_id():
    # Internal/structured callers can still pass the canonical id directly.
    loc = resolve_location("loc_CGP_01")
    assert loc["village"] == "Chengalpattu Town (HQ)"


def test_resolve_unknown_pincode_raises_with_suggestions():
    # A well-formed but uncovered PIN code raises LocationNotRecognized
    # with a sample of PIN codes this tool actually has data for, rather
    # than silently fabricating a location for it.
    with pytest.raises(LocationNotRecognized) as exc_info:
        resolve_location("999999")
    assert isinstance(exc_info.value.suggestions, list)
    assert len(exc_info.value.suggestions) > 0


def test_resolve_malformed_input_raises_not_found():
    # Free-text place names are no longer accepted at all -- PIN code
    # matching replaced that whole flow (see location_resolver/__init__.py
    # module docstring). A non-numeric or wrong-length string raises the
    # same LocationNotRecognized as an unknown PIN code, with a clear
    # "not a valid 6-digit PIN code" message.
    with pytest.raises(LocationNotRecognized) as exc_info:
        resolve_location("Chengalpattu")
    assert "6-digit" in str(exc_info.value)


def test_resolve_only_raises_location_not_found_on_empty_query():
    with pytest.raises(LocationNotFound):
        resolve_location("")


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
