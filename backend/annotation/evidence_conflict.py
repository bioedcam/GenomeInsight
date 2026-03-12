"""Evidence conflict detection — amber flag logic.

Fires when ClinVar classifies a variant as VUS/B/LB **and** ≥3 in-silico
tools predict deleterious **and** CADD PHRED > 20.

No flag when ClinVar is P/LP or absent.  No flag when fewer than 3 tools
agree on deleterious.  This implements PRD §5, Sprint 2.1, P2-07.

In-silico tool thresholds (standard community cutoffs):
    - SIFT:      pred == 'D' or score < 0.05
    - PolyPhen-2: pred == 'D' (probably_damaging)
    - CADD PHRED: > 20
    - REVEL:     > 0.5
    - MetaSVM:   > 0

Usage::

    from backend.annotation.evidence_conflict import detect_evidence_conflict

    flag = detect_evidence_conflict(variant_row)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ClinVar significances that trigger conflict detection.
# P/LP and absent ClinVar → no flag.
_CONFLICT_ELIGIBLE_SIGNIFICANCES = frozenset(
    {
        "Uncertain significance",
        "Benign",
        "Likely benign",
        # Handle alternate spellings from ClinVar VCF
        "Uncertain_significance",
        "Likely_benign",
        "VUS",
    }
)

# ClinVar significances where conflict is never flagged (authoritative).
_AUTHORITATIVE_SIGNIFICANCES = frozenset(
    {
        "Pathogenic",
        "Likely pathogenic",
        "Likely_pathogenic",
        "Pathogenic/Likely pathogenic",
        "Pathogenic/Likely_pathogenic",
    }
)

# CADD PHRED threshold for the CADD-specific gate
_CADD_THRESHOLD = 20.0

# Minimum number of in-silico tools predicting deleterious
_MIN_DELETERIOUS_TOOLS = 3


@dataclass(frozen=True, slots=True)
class EvidenceConflictResult:
    """Result of evidence conflict detection for a single variant."""

    flag: bool
    deleterious_count: int
    total_tools_assessed: int
    cadd_phred: float | None
    clinvar_significance: str | None


def _is_sift_deleterious(pred: str | None, score: float | None) -> bool | None:
    """SIFT: 'D' prediction or score < 0.05.  Returns None if no data."""
    if pred is not None:
        return pred.upper() == "D"
    if score is not None:
        return score < 0.05
    return None


def _is_polyphen_deleterious(pred: str | None, score: float | None) -> bool | None:
    """PolyPhen-2: 'D' (probably_damaging).  Returns None if no data."""
    if pred is not None:
        return pred.upper() == "D"
    if score is not None:
        return score > 0.909  # standard probably_damaging threshold
    return None


def _is_cadd_deleterious(phred: float | None) -> bool | None:
    """CADD PHRED > 20.  Returns None if no data."""
    if phred is None:
        return None
    return phred > _CADD_THRESHOLD


def _is_revel_deleterious(score: float | None) -> bool | None:
    """REVEL > 0.5.  Returns None if no data."""
    if score is None:
        return None
    return score > 0.5


def _is_metasvm_deleterious(score: float | None) -> bool | None:
    """MetaSVM > 0.  Returns None if no data."""
    if score is None:
        return None
    return score > 0


def count_deleterious_tools(variant: dict[str, Any] | Any) -> tuple[int, int]:
    """Count how many of the 5 in-silico tools predict deleterious.

    Args:
        variant: A dict or row-like object with in-silico score fields.

    Returns:
        (deleterious_count, total_assessed) — tools with data that voted.
    """

    # Support both dict-style and attribute-style access
    def _get(key: str) -> Any:
        if isinstance(variant, dict):
            return variant.get(key)
        return getattr(variant, key, None)

    assessments: list[bool | None] = [
        _is_sift_deleterious(_get("sift_pred"), _get("sift_score")),
        _is_polyphen_deleterious(_get("polyphen2_hsvar_pred"), _get("polyphen2_hsvar_score")),
        _is_cadd_deleterious(_get("cadd_phred")),
        _is_revel_deleterious(_get("revel")),
        _is_metasvm_deleterious(_get("metasvm")),
    ]

    assessed = [a for a in assessments if a is not None]
    deleterious = sum(1 for a in assessed if a)
    return deleterious, len(assessed)


def detect_evidence_conflict(variant: dict[str, Any] | Any) -> EvidenceConflictResult:
    """Detect evidence conflict for a single variant.

    The amber flag fires when ALL three conditions are met:
        1. ClinVar significance is VUS, B, or LB
        2. ≥3 in-silico tools predict deleterious
        3. CADD PHRED > 20

    Args:
        variant: A dict or row-like object with annotation fields.

    Returns:
        :class:`EvidenceConflictResult` with the flag and supporting data.
    """

    def _get(key: str) -> Any:
        if isinstance(variant, dict):
            return variant.get(key)
        return getattr(variant, key, None)

    clinvar_sig = _get("clinvar_significance")
    cadd_phred = _get("cadd_phred")

    # Condition 1: ClinVar must be present and VUS/B/LB
    if clinvar_sig is None:
        return EvidenceConflictResult(
            flag=False,
            deleterious_count=0,
            total_tools_assessed=0,
            cadd_phred=cadd_phred,
            clinvar_significance=clinvar_sig,
        )

    # Normalise: strip whitespace for safety
    clinvar_sig_stripped = clinvar_sig.strip()

    # P/LP → never flag
    if clinvar_sig_stripped in _AUTHORITATIVE_SIGNIFICANCES:
        return EvidenceConflictResult(
            flag=False,
            deleterious_count=0,
            total_tools_assessed=0,
            cadd_phred=cadd_phred,
            clinvar_significance=clinvar_sig,
        )

    # Must be one of the conflict-eligible significances
    if clinvar_sig_stripped not in _CONFLICT_ELIGIBLE_SIGNIFICANCES:
        return EvidenceConflictResult(
            flag=False,
            deleterious_count=0,
            total_tools_assessed=0,
            cadd_phred=cadd_phred,
            clinvar_significance=clinvar_sig,
        )

    # Condition 2 & 3: count deleterious tools and check CADD
    del_count, total_assessed = count_deleterious_tools(variant)

    flag = (
        del_count >= _MIN_DELETERIOUS_TOOLS
        and cadd_phred is not None
        and cadd_phred > _CADD_THRESHOLD
    )

    return EvidenceConflictResult(
        flag=flag,
        deleterious_count=del_count,
        total_tools_assessed=total_assessed,
        cadd_phred=cadd_phred,
        clinvar_significance=clinvar_sig,
    )


def apply_evidence_conflicts(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply evidence conflict detection to a list of merged variant dicts.

    Mutates each dict in place, setting ``evidence_conflict`` to True/False.

    Args:
        variants: List of annotation dicts (as produced by _merge_annotations).

    Returns:
        The same list, with ``evidence_conflict`` set on each dict.
    """
    for v in variants:
        result = detect_evidence_conflict(v)
        v["evidence_conflict"] = result.flag
    return variants
