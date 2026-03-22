# pipelines/resolver/tier1_deterministic.py
# Tier 1: Normalize → hash → exact-match deduplication. Target: >60% catch rate at $0 cost.

import hashlib
import re

# Whole-word legal suffix list — stripped from company names before hashing.
_LEGAL_SUFFIXES_RE = re.compile(
    r"\b(inc|llc|corp|ltd|limited|plc|co|incorporated|holdings|group"
    r"|technologies|systems|solutions)\b",
    re.IGNORECASE,
)


def normalize(name: str) -> str:
    """Lowercase, strip punctuation, remove legal suffixes, collapse whitespace."""
    name = name.lower().strip()
    # Remove periods and commas
    name = name.replace(".", "").replace(",", "")
    # Remove legal suffixes (whole-word match only)
    name = _LEGAL_SUFFIXES_RE.sub("", name)
    # Collapse multiple spaces from suffix removal and strip edges
    name = re.sub(r"\s+", " ", name).strip()
    return name


def deterministic_hash(normalized_name: str) -> str:
    """Return the first 16 hex chars of SHA256(normalized_name). Stable across runs."""
    return hashlib.sha256(normalized_name.encode()).hexdigest()[:16]


def resolve(name: str) -> dict:
    """Run Tier-1 resolution and return a structured result dict."""
    normalized = normalize(name)
    return {
        "original": name,
        "normalized": normalized,
        "hash": deterministic_hash(normalized),
        "tier": 1,
    }
