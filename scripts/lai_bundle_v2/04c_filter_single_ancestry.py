#!/usr/bin/env python3
"""Select the gnomix training reference panel by curated continental label.

REPLACES the prior ``max_q >= 0.95`` ADMIXTURE single-ancestry filter, which
catastrophically under-selected continentally-intermediate groups.

Why the old filter was wrong
----------------------------
The v1.1-ported logic kept a sample only if its top fastmixture/ADMIXTURE
component was >= 0.95 of its ancestry. But European, Middle-Eastern and
American ancestry is admixed/intermediate at the continental scale and never
forms a single clean ADMIXTURE component at any K. Measured on the v2.0.0
panel (``04_admixture_filtering`` Q-matrices), the fraction of each region
reaching ``max_q >= 0.95`` was:

    region   K7      K12     K20     median max_q (K7)
    AFR      81.7%   51.5%   62.6%   1.000
    EAS      87.6%   38.7%   39.7%   0.994
    OCE      60.0%   53.3%   93.3%   1.000
    CSA      39.9%   28.3%   28.5%   0.890
    EUR       0.4%    0.3%    0.0%   0.767   <- global max max_q = 0.959
    MID       0.0%    0.0%   12.1%   0.806
    AMR      15.5%   14.0%   13.5%   0.466

So the 0.95 cutoff kept only the genetically-distinct groups (AFR/EAS/OCE) and
discarded intermediate ones. In v2.0.0 it left **3 of 770 EUR** samples (and 0
MID, 85 AMR) in training. A gnomix model trained on 3 Europeans cannot learn a
European decision boundary and assigns real Europeans to the nearest
well-trained class — observed: a held-out Iberian (HG01502) classified as 94%
CSA, 0.3% EUR through the production pipeline. Raising K does not help (EUR
gets *worse*: 0.4% -> 0.0%); the problem is structural, not a threshold/K tweak.

The fix
-------
Trust the gnomAD HGDP+1KG curated ``genetic_region`` superpopulation labels
(already QC'd for known admixture) as the reference labels. ADMIXTURE Q is kept
only as an OPTIONAL light outlier floor (``--min-q``, default 0.5 — removes only
~50/50 individuals, not intermediate-but-clean ones) and for the audit log. A
per-region **composition gate** (``--min-per-region``) fails the build if any
target superpopulation is under-represented, so an "EUR=3" panel can never
silently ship again. An optional ``--per-region-cap`` balances class sizes.

Ported from / supersedes lai_bundle_build Phase 4c.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Canonical superpopulations the LAI bundle classifies (gnomAD genetic_region
# values). MID/OCE are tiny in HGDP+1KG; the composition gate floor accounts
# for that. Keep in sync with backend gnomix_inference.CANONICAL_POPULATIONS.
DEFAULT_REGIONS = ("AFR", "AMR", "CSA", "EAS", "EUR", "MID", "OCE")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fam", required=True, type=Path, help="PLINK .fam matching the .Q row order"
    )
    parser.add_argument(
        "--meta",
        required=True,
        type=Path,
        help="gnomAD HGDP+1KG metadata TSV (gnomad_meta_updated.tsv)",
    )
    parser.add_argument(
        "--q-matrix",
        type=Path,
        default=None,
        help="OPTIONAL fastmixture .Q (headerless) for the light "
        "admixture-outlier floor + audit; omit to select on "
        "labels alone",
    )
    parser.add_argument(
        "--min-q",
        type=float,
        default=0.5,
        help="light admixture-outlier floor on top-Q; drops only "
        "grossly-admixed individuals (default 0.5). Requires "
        "--q-matrix; set 0 to disable",
    )
    parser.add_argument(
        "--regions",
        type=str,
        default=" ".join(DEFAULT_REGIONS),
        help="space-separated target superpopulations to include",
    )
    parser.add_argument(
        "--per-region-cap",
        type=int,
        default=0,
        help="if >0, randomly (seeded) downsample each region to at "
        "most this many samples for class balance",
    )
    parser.add_argument(
        "--min-per-region",
        type=int,
        default=20,
        help="BUILD GATE: fail if any selected region has fewer than "
        "this many training samples (default 20). This is what "
        "would have caught the EUR=3 regression",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="seed for --per-region-cap downsampling (reproducible)",
    )
    # Back-compat: the old wrapper passed --threshold (the 0.95 cutoff). Accept it
    # but ignore it with a loud warning so a stale invocation doesn't silently
    # resurrect the broken behaviour.
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="DEPRECATED/IGNORED — the >=0.95 single-ancestry cutoff "
        "that dropped EUR. Use --min-q instead",
    )
    parser.add_argument("--out-sample-map", required=True, type=Path)
    parser.add_argument("--out-single-ancestry", required=True, type=Path)
    parser.add_argument("--out-excluded", required=True, type=Path)
    args = parser.parse_args()

    if args.threshold is not None:
        print(
            f"WARNING: --threshold {args.threshold} is DEPRECATED and IGNORED. "
            "Reference selection is now by curated genetic_region (the 0.95 "
            "ADMIXTURE cutoff dropped 767/770 EUR samples). Use --min-q for the "
            "light outlier floor.",
            file=sys.stderr,
        )

    target_regions = set(args.regions.split())

    fam = pd.read_csv(
        args.fam,
        sep=r"\s+",
        header=None,
        names=["FID", "IID", "PAT", "MAT", "SEX", "PHENO"],
    )

    meta = pd.read_csv(
        args.meta,
        sep="\t",
        usecols=["s", "hgdp_tgp_meta.Population", "hgdp_tgp_meta.Genetic.region"],
    )
    meta.columns = ["sample_id", "population", "genetic_region"]

    merged = fam.merge(meta, left_on="IID", right_on="sample_id", how="left")

    # Optional light admixture-outlier floor (NOT the old 0.95 single-component gate).
    if args.q_matrix is not None and args.min_q > 0:
        Q = np.loadtxt(args.q_matrix)
        if len(merged) != Q.shape[0]:
            raise SystemExit(f"row mismatch: fam/meta={len(merged)} Q={Q.shape[0]}")
        merged["max_q"] = Q.max(axis=1)
        merged["assigned_k"] = Q.argmax(axis=1)
    else:
        merged["max_q"] = np.nan
        merged["assigned_k"] = -1

    has_region = merged["genetic_region"].isin(target_regions)
    passes_floor = (merged["max_q"] >= args.min_q) | merged["max_q"].isna()

    selected = merged[has_region & passes_floor].copy()
    excluded = merged[~(has_region & passes_floor)].copy()

    # Optional per-region cap for class balance (reproducible).
    if args.per_region_cap > 0:
        rng = np.random.default_rng(args.seed)
        capped = []
        for _region, grp in selected.groupby("genetic_region"):
            if len(grp) > args.per_region_cap:
                idx = rng.choice(grp.index.to_numpy(), args.per_region_cap, replace=False)
                capped.append(grp.loc[idx])
            else:
                capped.append(grp)
        selected = pd.concat(capped).sort_index()

    counts = selected["genetic_region"].value_counts().to_dict()
    print(f"Total panel samples: {len(merged)}")
    print(f"Selected (curated genetic_region, min_q>={args.min_q}): {len(selected)}")
    print(f"Excluded: {len(excluded)}")
    print("\nPer-region (selected reference panel):")
    for region in sorted(target_regions):
        print(f"  {region:6} {counts.get(region, 0)}")

    # ── BUILD GATE — fail loud on under-representation ──────────────────────
    available = set(meta["genetic_region"].dropna())
    present = [r for r in target_regions if r in available]
    under = {r: counts.get(r, 0) for r in present if counts.get(r, 0) < args.min_per_region}
    if under:
        raise SystemExit(
            "COMPOSITION GATE FAILED: these target superpopulations have fewer "
            f"than --min-per-region={args.min_per_region} training samples: "
            f"{under}. A balanced LAI reference panel must represent every "
            "continental group (this gate exists because v2.0.0 shipped with "
            "EUR=3 and misclassified all Europeans). Fix the upstream panel "
            "(phase 03/04 inputs) or lower --min-per-region deliberately."
        )

    selected[["IID", "genetic_region"]].to_csv(
        args.out_sample_map,
        sep="\t",
        header=False,
        index=False,
    )
    selected.to_csv(args.out_single_ancestry, sep="\t", index=False)
    excluded[["IID", "population", "genetic_region", "max_q"]].to_csv(
        args.out_excluded,
        sep="\t",
        index=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
