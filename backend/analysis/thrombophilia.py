"""Inherited thrombophilia risk module — EXPANSION_STRATEGY.md §6 / #24.

A thin adapter over the shared risk-genotype caller. Factor V Leiden (rs6025)
and Prothrombin G20210A (rs1799963) — both minus-strand cross-vendor pitfalls
that the strand-harmonized ``risk_dosage`` resolves. No sex or ancestry input.
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa

from backend.analysis.risk_genotype import (
    RiskAssessment,
    RiskPanel,
    classify,
    compute_dosages,
    load_risk_panel,
    read_genotypes,
    store_risk_findings,
)

_PANEL_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "panels" / "thrombophilia_panel.json"
)

MODULE = "thrombophilia"


def load_thrombophilia_panel(panel_path: Path | None = None) -> RiskPanel:
    """Load the curated thrombophilia risk panel."""
    return load_risk_panel(panel_path or _PANEL_PATH)


def assess_thrombophilia(panel: RiskPanel, sample_engine: sa.Engine) -> RiskAssessment:
    """Read FVL/Prothrombin genotypes and classify."""
    readouts = read_genotypes(panel, sample_engine)
    dosages = compute_dosages(panel, readouts)
    return classify(panel, dosages, readouts)


def store_thrombophilia_findings(assessment: RiskAssessment, sample_engine: sa.Engine) -> int:
    """Persist thrombophilia findings to the sample DB (idempotent)."""
    return store_risk_findings(assessment, sample_engine)
