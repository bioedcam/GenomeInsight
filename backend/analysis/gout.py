"""Gout / serum-urate risk module (ABCG2 Q141K + SLC2A9) — §9 / roadmap #43.

Thin adapter over the shared declarative risk-genotype caller, injecting the
sample's inferred ancestry so the engine selects the ancestry-appropriate odds
band (ABCG2 Q141K gout effects are larger in East Asian ancestry). These are
common urate-transporter risk alleles, not ClinVar P/LP, so findings carry
clinvar_significance=NULL. Gout is multifactorial — this is a risk modifier, not
a diagnosis, and the module makes no dietary/purine recommendations.
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa

from backend.analysis.ancestry import get_inferred_ancestry, get_top_ancestry_fraction
from backend.analysis.risk_genotype import (
    RiskAssessment,
    RiskPanel,
    classify,
    compute_dosages,
    load_risk_panel,
    read_genotypes,
    store_risk_findings,
)

_PANEL_PATH = Path(__file__).resolve().parent.parent / "data" / "panels" / "gout_panel.json"

MODULE = "gout"


def load_gout_panel(panel_path: Path | None = None) -> RiskPanel:
    """Load the curated gout/urate risk panel."""
    return load_risk_panel(panel_path or _PANEL_PATH)


def assess_gout(panel: RiskPanel, sample_engine: sa.Engine) -> RiskAssessment:
    """Read ABCG2/SLC2A9 genotypes and classify with ancestry-appropriate ORs."""
    readouts = read_genotypes(panel, sample_engine)
    dosages = compute_dosages(panel, readouts)
    inferred_ancestry = get_inferred_ancestry(sample_engine)
    ancestry_fraction = get_top_ancestry_fraction(sample_engine)
    return classify(
        panel,
        dosages,
        readouts,
        inferred_ancestry=inferred_ancestry,
        ancestry_fraction=ancestry_fraction,
    )


def store_gout_findings(assessment: RiskAssessment, sample_engine: sa.Engine) -> int:
    """Persist gout findings to the sample DB (idempotent)."""
    return store_risk_findings(assessment, sample_engine)
