"""Calibrated in-silico ACMG/AMP evidence tiers from REVEL (Pejaver 2022).

EXPANSION_STRATEGY.md §7 / roadmap #11. Pejaver et al. 2022 (*AJHG*; PMID
36413997) recalibrated common pathogenicity predictors against a Bayesian
ACMG/AMP framework, replacing the never-empirically-calibrated original
"≥2 tools agree" PP3/BP4 rule (Richards 2015). This module applies the
**REVEL-only** thresholds — REVEL, VEST4 and CADD are correlated meta-predictors,
so stacking them would double-count PP3 (§12.8). The output is an additive,
DRAFT evidence tag attached to existing findings' ``detail_json``; it **never**
mutates ``evidence_level`` or ``clinvar_significance``.

REVEL → ACMG evidence strength (exact Pejaver 2022 thresholds):

    PP3_Strong       REVEL ≥ 0.932
    PP3_Moderate     0.773 ≤ REVEL < 0.932
    PP3_Supporting   0.644 ≤ REVEL < 0.773
    (indeterminate)  0.290 < REVEL < 0.644      → no tier
    BP4_Supporting   0.183 < REVEL ≤ 0.290
    BP4_Moderate     0.016 < REVEL ≤ 0.183
    BP4_Strong       0.003 < REVEL ≤ 0.016
    BP4_VeryStrong   REVEL ≤ 0.003

PP3/BP4 are missense-applicable criteria, so a tier is returned only for missense
variants; everything else (and a missing REVEL) yields ``None``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.disclaimers import INSILICO_ACMG_EVIDENCE_ONLY

# The SO consequence token that marks a missense change (PP3/BP4 apply to missense).
_MISSENSE_TOKEN = "missense_variant"
_CONSEQUENCE_SPLIT = re.compile(r"[&,;+\s]+")

_DRAFT_NOTE = INSILICO_ACMG_EVIDENCE_ONLY


@dataclass(frozen=True)
class InsilicoTier:
    """A calibrated REVEL → ACMG/AMP evidence assignment (DRAFT)."""

    criterion: str  # "PP3" (pathogenic-supporting) | "BP4" (benign-supporting)
    strength: str  # "Supporting" | "Moderate" | "Strong" | "Very Strong"
    tier: str  # e.g. "PP3_Strong"
    revel: float

    def to_detail(self) -> dict:
        """The additive, non-mutating ``detail_json['insilico']`` block."""
        return {
            "predictor": "REVEL",
            "revel": self.revel,
            "criterion": self.criterion,
            "strength": self.strength,
            "tier": self.tier,
            "is_draft": True,
            "note": _DRAFT_NOTE,
        }


def is_missense_consequence(consequence: str | None) -> bool:
    """True if a VEP consequence string contains the ``missense_variant`` SO term."""
    if not consequence:
        return False
    return _MISSENSE_TOKEN in _CONSEQUENCE_SPLIT.split(consequence.strip().lower())


def revel_to_acmg_tier(revel: float | None, *, is_missense: bool) -> InsilicoTier | None:
    """Map a REVEL score to a calibrated Pejaver-2022 ACMG/AMP evidence tier.

    Returns ``None`` for a missing REVEL, a non-missense variant, or a score in
    the indeterminate band ``(0.290, 0.644)`` where no evidence is assigned.
    """
    if revel is None or not is_missense:
        return None

    if revel >= 0.932:
        return InsilicoTier("PP3", "Strong", "PP3_Strong", revel)
    if revel >= 0.773:
        return InsilicoTier("PP3", "Moderate", "PP3_Moderate", revel)
    if revel >= 0.644:
        return InsilicoTier("PP3", "Supporting", "PP3_Supporting", revel)
    if revel > 0.290:
        return None  # indeterminate gap (0.290, 0.644)
    if revel > 0.183:
        return InsilicoTier("BP4", "Supporting", "BP4_Supporting", revel)
    if revel > 0.016:
        return InsilicoTier("BP4", "Moderate", "BP4_Moderate", revel)
    if revel > 0.003:
        return InsilicoTier("BP4", "Strong", "BP4_Strong", revel)
    return InsilicoTier("BP4", "Very Strong", "BP4_VeryStrong", revel)


def insilico_block(revel: float | None, consequence: str | None) -> dict | None:
    """Convenience: the ``detail_json['insilico']`` block for a finding, or None."""
    tier = revel_to_acmg_tier(revel, is_missense=is_missense_consequence(consequence))
    return tier.to_detail() if tier is not None else None
