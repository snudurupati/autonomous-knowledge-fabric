# tests/test_tier1.py
# Unit tests for the Tier-1 deterministic entity resolver.

import pytest

from pipelines.resolver.tier1_deterministic import (
    deterministic_hash,
    normalize,
    resolve,
)


# ---------------------------------------------------------------------------
# normalize() correctness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("Apple Inc.",          "apple"),
    ("APPLE INCORPORATED",  "apple"),
    ("Apple, Inc.",         "apple"),
    ("iSpecimen Inc.",      "ispecimen"),
    ("ispecimen",           "ispecimen"),
    ("Applied Digital Corp.", "applied digital"),
    ("Applied Digital",       "applied digital"),
])
def test_normalize(raw, expected):
    assert normalize(raw) == expected


# ---------------------------------------------------------------------------
# Hash stability — identical inputs must produce identical hashes
# ---------------------------------------------------------------------------

def test_apple_variants_same_hash():
    variants = [
        "Apple Inc.",
        "APPLE INCORPORATED",
        "Apple, Inc.",
        "iSpecimen Inc.",
        "ispecimen",
    ]
    # First three are all "apple"; last two are all "ispecimen"
    apple_hashes = {deterministic_hash(normalize(v)) for v in variants[:3]}
    assert len(apple_hashes) == 1, f"Apple variants produced different hashes: {apple_hashes}"

    ispecimen_hashes = {deterministic_hash(normalize(v)) for v in variants[3:]}
    assert len(ispecimen_hashes) == 1, f"iSpecimen variants produced different hashes: {ispecimen_hashes}"


def test_applied_digital_variants_same_hash():
    h1 = deterministic_hash(normalize("Applied Digital Corp."))
    h2 = deterministic_hash(normalize("Applied Digital"))
    assert h1 == h2, f"Hash mismatch: {h1!r} != {h2!r}"


# ---------------------------------------------------------------------------
# resolve() structure
# ---------------------------------------------------------------------------

def test_resolve_structure():
    result = resolve("Apple Inc.")
    assert result["original"] == "Apple Inc."
    assert result["normalized"] == "apple"
    assert len(result["hash"]) == 16
    assert result["tier"] == 1


def test_resolve_hash_is_hex():
    result = resolve("iSpecimen Inc.")
    int(result["hash"], 16)  # raises ValueError if not valid hex


# ---------------------------------------------------------------------------
# All five test cases produce expected normalized forms and hashes
# ---------------------------------------------------------------------------

def test_all_five_cases():
    cases = [
        ("Apple Inc.",          "apple"),
        ("APPLE INCORPORATED",  "apple"),
        ("Apple, Inc.",         "apple"),
        ("iSpecimen Inc.",      "ispecimen"),
        ("ispecimen",           "ispecimen"),
    ]
    for raw, expected_norm in cases:
        r = resolve(raw)
        assert r["normalized"] == expected_norm, f"{raw!r} → {r['normalized']!r}, want {expected_norm!r}"

    # All three Apple variants share one hash
    apple_hash = resolve("Apple Inc.")["hash"]
    assert resolve("APPLE INCORPORATED")["hash"] == apple_hash
    assert resolve("Apple, Inc.")["hash"] == apple_hash

    # Both iSpecimen variants share one hash
    ispecimen_hash = resolve("iSpecimen Inc.")["hash"]
    assert resolve("ispecimen")["hash"] == ispecimen_hash
