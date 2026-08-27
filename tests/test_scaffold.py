"""Stage 1 sanity checks: config loads, data contracts hold their invariant."""

from pathlib import Path

import pytest
import yaml

from schema import Evidence

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "scheme_config.yaml"


def test_scheme_config_loads():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    assert "nsfdc" in config
    assert config["nsfdc"]["schemes"]["micro_credit_finance"]["loan_cap"] == 125000
    assert config["nsfdc"]["schemes"]["term_loan"]["loan_cap"] == 4500000


def test_evidence_rejects_value_outside_range():
    with pytest.raises(ValueError):
        Evidence(value=100, low=0, high=50, source="test", vintage="2026", method="test")


def test_evidence_accepts_value_within_range():
    e = Evidence(value=25, low=0, high=50, source="test", vintage="2026", method="test")
    assert e.value == 25
