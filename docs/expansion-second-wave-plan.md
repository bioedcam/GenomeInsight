# Expansion — Second-Wave Implementation Plan

> **Status:** Planning. Grounded on `main` @ `12e77ea` (2026-06-09).
> **Source roadmap:** `EXPANSION_STRATEGY.md` (kept untracked at repo root by design — a 56-proposal,
> citation-verified roadmap; §11 is the numbered proposal table this plan references as `#N`).
> **First wave (DONE & merged):** `#4` PRS strand harmonization, `#11` Pejaver PP3/BP4 in-silico tiers,
> `#12` gnomAD gene-constraint, `#23` HFE, `#24` thrombophilia, `#25` alpha-1, `#26` AMD, `#27` APOL1,
> `#43` gout (PRs #319/#322/#323/#330/#331/#333/#334/#336/#337).
> This plan covers the **47 remaining proposals**, broken into PRs and sequenced by dependency and leverage.

---

## 0. How to read this plan

- **One PR per feature**, branched off the latest `main`, squash-merged on green CI (the repo's convention).
- PRs are grouped into **Waves A–F**. Within a wave, most PRs are independent and can run in parallel;
  across waves, later waves depend on earlier infrastructure (see §3 dependency graph).
- Every PR carries the firm **§12 scientific guardrails** (restated in §7). Honesty-guardrail tests are
  part of Definition of Done, not optional.
- New analysis modules follow the **established module pattern** (§4) and must register their `sample_id`
  routes in the §7.5 stale-sample **drift guard** (`tests/backend/test_stale_sample_dependency.py`).
- **Tiered tests:** targeted per PR; full local sweep for any Alembic/schema change; CI runs the full
  matrix (and `ruff check` + `ruff format --check` repo-wide — format every touched file).
- Effort key: **S** ≤ ~1 day, **M** ~2–4 days, **L** ~1–2 weeks (external runtime / large data).

---

## 1. Coordinate with the parallel validation / Phase-F effort (do NOT duplicate)

A separate **annotation-validation / Phase-F** campaign is **actively merging into `main`**
(`docs/annotation-validation-strategy.md`, `docs/phase-f-remaining-plan.md`). It **owns the
annotation-layer evidence pipeline**. The following are **already live** and must be **built on, not
re-implemented**, by any second-wave PR:

| Phase-F | Capability (merged) | Touches roadmap |
|---|---|---|
| F1–F8 | Carriage-aware engine: `zygosity`/`ref`/`alt` populated; cancer/cardio/carrier/rare-variant findings gate on `zygosity ∈ {het,hom_alt}` | substrate for everything |
| F9 | High-confidence dashboard gate (no-call/indel barred from top-5) | — |
| F10/F11 | Multi-allelic ClinVar alt-picker + dbNSFP ALT-aware in-silico lookup (per-carried-ALT) | `#31`, `#39` |
| F12 | `is_novel` = absent from **any** AF source (not just gnomAD) | `#14` |
| F15 | `gnomad_af_popmax` column + popmax-based rarity (ancestry-aware) | `#14` |
| F19 | In-silico ensemble → **PRELIMINARY (evidence 2)**, not MODERATE ★★ | `#13`, `#31`, §12.8 |
| F20 | 0-star ClinVar P/LP → low-confidence sub-tier | `#14` |
| F22–F25 | Gene→disease/inheritance hygiene; backup/report/source-tag prefixes | — |

**Open Phase-F items (theirs, not ours):** F30 (`database_versions.genome_build`), F34/F35 (build guards),
G1 (re-annotation trigger). **`#8` and `#9` below depend on F30** — coordinate timing.

**Boundary rule:** second-wave PRs may **read** `evidence_level`, `gnomad_af_popmax`, `zygosity`, the
in-silico ensemble verdict, etc., and add **adjacent, additive** layers (a reliability badge, a
provenance block, a new module). They must **not** change how evidence tiers / rarity / carriage are
computed — open an issue against the Phase-F plan instead.

---

## 2. Reusable infrastructure already in `main` (grounded inventory)

| Area | Reusable asset | Used by |
|---|---|---|
| Risk-genotype modules | `backend/analysis/risk_genotype.py` (declarative caller: indel/`total_risk_dosage`/`recessive`/`modifier`/`odds_ratio_by_ancestry`/`partial_disclosure`, ancestry gate, loader guards) | all new directly-typed modules |
| Module route plumbing | `backend/api/routes/risk_common.py::make_risk_router` (~30-line routes) | every new module |
| Strand/allele | `backend/analysis/allele_match.py` (`match_effect_allele_dosage`, `risk_dosage`, palindrome drop) | PRS + risk modules |
| PRS engine | `backend/analysis/prs.py` (`compute_prs`, bootstrap CI, percentile/Z, `check_ancestry_mismatch`, no-call/ambiguous/flip **disclosure counters**, `store_prs_findings`) | all PGS work |
| Ancestry | `backend/analysis/ancestry.py` (5k-AIM PCA bundle, 8 PCs, 7 pops; NNLS+kNN admixture + bootstrap CI; `get_inferred_ancestry`, `get_top_ancestry_fraction`, `get_ancestry_matched_af_column`) | `#5` calibration, ancestry gates |
| Sex inference | `backend/services/sex_inference.py` (validated XX/XY/manual_review/unknown) | `#48` aneuploidy screen |
| PGx | `backend/analysis/pharmacogenomics.py` (8 CPIC genes, `PrescribingAlert`, `STRUCTURAL_VARIANT_GENES` CYP2D6 flag, `Insufficient` confidence handling) + `cpic_*` tables (incl. DPYD `*2A/*13/c.2846A>T` already in `cpic_alleles.csv`) | `#15/16/20/21/22/34/35` |
| Imputation tooling | **Beagle JAR already vendored** for LAI phasing in `backend/analysis/lai_runner.py::_phase_chromosome`; `gnomix_inference.py` LAI; `bundles/` + `manifest.json` distribution; gnomAD AF in `reference.db` | `#1/#2/#3` reuse phasing path |
| HLA proxy | `backend/data/panels/hla_proxy_lookup*` + `hla_proxy_lookup` table (single tag-SNP per allele, per-ancestry r²) used by the Allergy module | superseded by `#17` HIBAG; keep as fallback |
| Provenance hooks | `findings.detail_json`/`pmid_citations`; `database_versions`; `annotation_state` + `reannotation_prompts`; `annotation_coverage` bitmask; `qc_metrics` schema (**exists, unpopulated**) | `#8`, `#9` |
| Module-add pattern | panel JSON → adapter → `make_risk_router` → `run_all._get_modules` → `main.py` include → drift-guard entry → tests (see HFE/AMD/APOL1/gout) | `#29/41/48/49/50/56` |

---

## 3. Dependency graph (what unlocks what)

```
Wave A  (cross-cutting + greenfield directly-typed; NO imputation/HLA/R needed)  ── ship first, parallel
   │
   ├─ #8 provenance ── needs Phase-F F30 (genome_build)         (coordinate)
   ├─ #9 expanded QC ── builds on Phase-F carriage + qc_metrics  (coordinate)
   ├─ #10 responsible-return, #30 trait-architecture (doc/UI; no algo)
   ├─ #55 MT-RNR1, #41 Parkinson's, #29 ROH, #49 kinship, #48 sex-aneuploidy, #50 mtDNA/LHON
   └─ #14 array-confidence guardrail ──► gates #13
         #31 AlphaMissense (independent; additive to F11/F19 ensemble)

Wave B  PGS Catalog at scale
   #6 ingest PGS Catalog ──► #46 provenance UI, #45 APOE exclusion, #33 PRS-CSx select,
                              #28 T2D/obesity, #52 osteoporosis, #56 FH LDL-C overlay, #44 abs-risk
   #5 PC-continuous calibration (independent of #6; both feed credible percentiles)

Wave C  Imputation foundation (the big unlock; L effort, external runtime)
   #1 NYGC 1000G panel ──► #2 Beagle impute+DR2 ──► #3 MAF/r² firewall
                              ├─► #7 PRS coverage gating  (also needs #6)
                              ├─► #47 reachability labels
                              ├─► #32 imputed AF/GWAS uplift
                              └─► #53 advanced engines (IMPUTE5/GLIMPSE)

Wave D  HLA / HIBAG (needs R subprocess; mostly post-imputation framing)
   #17 HIBAG engine ──► #18 drug-hypersensitivity, #19 celiac/narcolepsy NPV,
                        #36 autoimmune, #37 viewer, #42 celiac/RA card, #54 DEEP*HLA (low)

Wave E  Pharmacogenomics expansion
   #15 PharmVar adoption ──► #16 DPWG/PharmGKB/FDA, #22 G6PD/BCHE, #35 NUDT15
   #20 med-safety report (needs #21), #21 CYP2D6 CNV guardrails, #34 DPYD (data mostly present)

Wave F  Deeper variant interpretation (coordinate tightly with validation effort)
   #14 (Wave A) ──► #13 InterVar DRAFT-ACMG engine
   #38 SpliceAI (user-built; needs Phase-F build-schema), #39 GTEx eQTL (needs coordinate infra)
```

---

## 4. The new-module pattern (for every directly-typed module PR)

1. `backend/data/panels/<module>_panel.json` — loci + genotype_models (reuse `risk_genotype.py` fields).
2. `backend/analysis/<module>.py` — thin adapter (`load_*`/`assess_*`/`store_*`), inject sex/ancestry as needed.
3. `backend/api/routes/<module>.py` — `make_risk_router(...)` (~30 lines).
4. `backend/disclaimers.py` — `<MODULE>_DISCLAIMER_TITLE/TEXT` (Yeliztli naming).
5. `backend/analysis/run_all.py` — add to `_get_modules()` + a `_run_<module>` runner.
6. `backend/main.py` — import + `include_router` (alphabetical).
7. `tests/backend/test_stale_sample_dependency.py` — add the module to `_FULLY_GATED_MODULES`.
8. `tests/backend/test_<module>.py` + `test_<module>_api.py` — synthetic-genotype validation (+ `registry.dispose_all()` in API fixtures). **Verify every locus's risk allele against dbSNP plus-strand before committing** (first-wave caught an inverted Pi*S allele this way).

---

## 5. PR breakdown

### Wave A — Cross-cutting rigor + greenfield directly-typed (ship first; no imputation/HLA/R)

| PR | Roadmap | Goal | Key/new files | Effort | Depends on | Guardrails / notes |
|----|---------|------|---------------|--------|------------|--------------------|
| **SW-A1** | `#10` | Calibrated responsible-return layer: PRS percentile = research-only + mandatory source-population label + bootstrap CI always paired; ClinVar P/LP non-dismissible confirm-in-CLIA gate (mirror APOE gate). | `disclaimers.py`, `store_prs_findings` detail, a shared `return_framing.py`; frontend gate card | S | — | §12.3/§12.10; UI → ui-inspector/WCAG gate |
| **SW-A2** | `#30` | Polygenic trait-architecture education card per PRS (h²_twin>h²_SNP>h²_PRS; Ding-2023 portability r=−0.95; "calibration ≠ accuracy"). | PRS `detail_json` `architecture` block; frontend card | S | — | §12.4; doc/UI only, no algo change |
| **SW-A3** | `#9` | Expanded QC + reference-bias disclosure: populate `qc_metrics` (call-rate ~98% line, X-het sex-check concordant/discordant/indeterminate, het-outlier ~3 SD); surface PRS no-call count per finding (engine already counts it). | `qc_metrics` populate, `services/sex_inference.py` reuse, QC panel in SystemHealth | M | Phase-F carriage (merged) | §12.5 (no aneuploidy claims); concordance-only sex check |
| **SW-A4** | `#8` | Per-finding provenance + version pinning + change-diff: provenance JSON per finding (ClinVar/gnomAD/dbNSFP/CPIC release + variation IDs + `annotation_coverage` + pipeline commit); extend VUS-reclassification banner into a general "finding changed" diff on the Huey scheduler. | `findings` provenance column (**Alembic**), `database_versions` read, update scheduler | M | **Phase-F F30** (`genome_build`) | **Schema change → full sweep**; coordinate F30 timing |
| **SW-A5** | `#55` | MT-RNR1 aminoglycoside-ototoxicity panel (m.1555A>G / m.1494C>T / m.1095T>C): "avoid aminoglycosides", maternal-inheritance, homoplasmic. **Verify 23andMe mtDNA probe coverage of these positions first.** | new module (pattern §4) + CPIC link | S | — | §12.6 negative≠clear; probe-coverage gate → indeterminate |
| **SW-A6** | `#41` | Parkinson's module: LRRK2 G2019S (rs34637584, directly typed, ~25–42.5% penetrance) behind an **APOE-style ethical gate**; GBA1 **suppressed/flagged** (GBAP1 pseudogene — unreliable, never imputed). | new module (pattern §4) + gate | M | — | §12.6; ethical gate (no preventive tx); GBA call-quality gate |
| **SW-A7** | `#29` | Runs-of-Homozygosity / FROH / autozygosity: reimplement ~100-line sliding-window (PLINK `--homozyg` equivalent, MIT-clean); re-validate params for ~600–700k markers. | new `backend/analysis/roh.py` + route + tests | M | — | FROH = genomic estimate, **not** an inbreeding diagnosis about parents |
| **SW-A8** | `#49` | Within-account KING-robust kinship (phi bands; PO vs sib via IBS0); duplicate/sample-swap QC. **Strictly within one user's own samples, never cross-user.** | new `backend/analysis/kinship.py` + route | M | — | report SNP count used; cross-vendor overlap caveat |
| **SW-A9** | `#48` | Sex-chromosome aneuploidy **screen** (XXY/XYY/XXX via non-PAR X-het + Y call-rate). Turner 45,X unreliable (no intensity) → confirmation-only language; never overwrite `biological_sex`. | extend `services/sex_inference.py` + opt-in gate | M | — | §12.5; APOE-style opt-in (psychosocial weight) |
| **SW-A10** | `#50` | Array-typed mtDNA/Y LHON panel (m.11778G>A / m.14484T>C / m.3460G>A) with hard heteroplasmy disclaimer. **Verify array probe coverage.** | new module (pattern §4) | S | — | §12.5; binary calls — negative ≠ rule-out, positive ≠ penetrance |
| **SW-A11** | `#14` | **Array-confidence + ClinGen gene-disease-validity guardrail** on every P/LP: reliability flag (Weedon 2021 PPV by AF band; reads Phase-F `gnomad_af_popmax`/`is_novel`) + ClinGen 6-tier validity context ("no curation" = "not yet evaluated"). | new `backend/analysis/array_confidence.py`; ClinGen download (public) | M | reads Phase-F F12/F15/F20 | **Foundational — gates SW-F1**; additive only (no evidence-tier change) |
| **SW-A12** | `#31` | AlphaMissense proteome-wide missense class (CC-BY-4.0 Zenodo predictions, GRCh37). Surfaced as an **additive** complement to REVEL — **not** a third independent vote (do not double-count with PM2/AF). | new loader (mirror `gnomad_constraint.py`) + detail block | M | reads F11 ensemble | §12.8 no double-counting; class thresholds 0.34/0.564 |

> Wave A is ~12 PRs, mostly **S/M, directly-typed, no external runtime** — the highest leverage-per-effort
> tranche and the natural next batch. SW-A4 is the only schema change; SW-A1/A2/A11 are additive disclosure/UI.

### Wave B — PGS Catalog at scale

| PR | Roadmap | Goal | Effort | Depends on |
|----|---------|------|--------|------------|
| **SW-B1** | `#6` | Ingest PGS Catalog **GRCh37-harmonized** scoring files into local SQLite (replace the 4 hand-curated cancer JSONs); per-score license honoring (CC-BY vs non-commercial in header — mirror dbNSFP-vs-gnomAD discipline); store PGS ID/PMID/source-ancestry/sample-size/PRS-CSx flag; reject build-mismatched scores at load. | M | — |
| **SW-B2** | `#5` | Ancestry-continuous PRS calibration: precompute per-weight-set PC1–PC8 → adjusted mean/variance at bundle-build; apply in `compute_prs_percentile`. **Corrects calibration, not predictive accuracy — say so** (mandatory, quantitative mismatch warning, non-dismissible). | L | reuses PCA bundle |
| **SW-B3** | `#46`, `#45` | Per-PGS provenance/evidence-tier UI (PGS ID/PMID/ancestry/coverage) + APOE/monogenic region exclusion from disease PRS (deconflict AD-PRS; no re-reported monogenic hits). | S | SW-B1 |
| **SW-B4** | `#33` | Prefer multi-ancestry / PRS-CSx-derived scores; select per inferred ancestry (scoring-rule enum). | S | SW-B1 |
| **SW-B5** | `#28` | T2D & obesity PRS (PGS Catalog) + anchor SNPs (TCF7L2/FTO/MC4R framed as near-noise singly); report % coverage; fire ancestry-mismatch warning. | L | SW-B1, SW-B2, (SW-C* coverage) |
| **SW-B6** | `#56` | Dedicated FH view over the existing cardiovascular panel: add APOB R3527Q (rs5742904) founder variant + an LDL-C polygenic score to distinguish monogenic vs polygenic hypercholesterolemia; frame vs Simon Broome / Dutch Lipid criteria. | M | SW-B1 (LDL-C score) |
| **SW-B7** | `#52` | Osteoporosis eBMD PRS (PGS Catalog) — one small input, **not** a FRAX/DXA substitute. | M | SW-B1 |
| **SW-B8** | `#44` | Opt-in guard-railed absolute-risk overlay for the few externally-validated traits only (breast via BOADICEA/CanRisk); SEER/CI5 incidence; **Alembic** incidence band; never default, always CI + ancestry-validity. | L | SW-B1; **schema change** |

### Wave C — Imputation foundation (the big unlock)

| PR | Roadmap | Goal | Effort | Depends on |
|----|---------|------|--------|------------|
| **SW-C1** | `#1` | Ship NYGC 30× 1000 Genomes panel as the local imputation reference (bref3, CC0, chunked bundle ~GB) via the existing `manifest.json`/`bundles/` mechanism; license + build verification. | L | — |
| **SW-C2** | `#2` | Local Beagle 5.x phase+impute pipeline with **per-variant DR2/r² persisted** (reuse the vendored Beagle JAR already used in `lai_runner.py`; run as isolated subprocess; chunked to bound RAM; **measure single-sample laptop runtime, don't assume**). | L | SW-C1 |
| **SW-C3** | `#3` | Hard **MAF/r² firewall**: tag every variant typed-vs-imputed (extend `annotation_coverage`); imputed rare (MAF<1%) **quarantined** from ClinVar P/LP/carrier/monogenic — never a finding; version-pin the panel + re-annotate. | S | SW-C2 |
| **SW-C4** | `#47` | Imputation-feasibility gating labels (per-target reachability/reliability from panel + gnomAD MAF). | M | SW-C1/2/3 |
| **SW-C5** | `#7` | Honest PRS coverage gating: per-score genotyped-fraction + imputed-r² tier; surface coverage % + r²-mean. | M | SW-C2/3, SW-B1 |
| **SW-C6** | `#32` | Imputation-aware AF + GWAS-Catalog/ClinVar common-variant uplift. | M | SW-C2/3 |
| **SW-C7** | `#53` | Advanced engines (GLIMPSE/IMPUTE5 — **verify redistribution licenses**) + honest per-sample "imputation reach" report. | M | SW-C1 |

### Wave D — HLA / HIBAG

| PR | Roadmap | Goal | Effort | Depends on |
|----|---------|------|--------|------------|
| **SW-D1** | `#17` | Core HIBAG engine (R subprocess, GPL-isolated; bundled multi-ethnic classifiers — **verify redistribution, else user-download**); ancestry/locus-gated posteriors; African/admixed hard-capped to 2-field. Supersedes the single-tag HLA proxy (keep proxy as fallback). | L | — (independent of imputation) |
| **SW-D2** | `#18` | HLA drug-hypersensitivity PGx layer (B*57:01, B*15:02, A*31:01, B*58:01, B*13:01) — **imputed, confirm-with-clinical-HLA banner**, posterior-gated. | M | SW-D1 |
| **SW-D3** | `#19` | Celiac (DQ2.5/DQ8) + narcolepsy (DQB1*06:02) **high-NPV rule-OUT** reports. | M | SW-D1 |
| **SW-D4** | `#36`, `#42` | Autoimmune susceptibility (B*27, DRB1 shared epitope, C*06:02, T1D DR-DQ) + consolidated celiac/RA card; strictest posterior gate on DRB1. | M | SW-D1 |
| **SW-D5** | `#37` | Raw imputed-HLA viewer/export (NPV framing; **never** a transplant/donor match; antigen-level only for low-confidence/non-EUR). | S | SW-D1 |
| **SW-D6** | `#54` | DEEP*HLA upgrade path (rare/amino-acid resolution) — **low priority**, licensing hard; defer unless needed. | L | SW-D1 |

### Wave E — Pharmacogenomics expansion

| PR | Roadmap | Goal | Effort | Depends on |
|----|---------|------|--------|------------|
| **SW-E1** | `#15` | Adopt **PharmVar** as canonical versioned star-allele defs; expand panel (+CYP2B6, CYP4F2, NUDT15, NAT2, VKORC1, UGT1A1); explicit **indeterminate** flags for unassayed defining variants. | L | — |
| **SW-E2** | `#16` | Layer **DPWG + PharmGKB LOE (1A–4) + FDA PGx table** over CPIC (PharmGKB CC-BY-SA — honor share-alike). | M | SW-E1 |
| **SW-E3** | `#21` | Honest CYP2D6 structural-variant/CNV guardrails: activity-score **band** + "duplication/deletion not assessed" (extend existing `STRUCTURAL_VARIANT_GENES` flag). | M | — |
| **SW-E4** | `#20` | Consolidated drug-centric **medication-safety report** (CPIC-standard phenotype terms + reference-bias disclosure + per-gene coverage/confidence). | M | SW-E3 |
| **SW-E5** | `#34` | DPYD fluoropyrimidine panel (4 actionable variants — **data already in `cpic_alleles.csv`**; wire the guideline + absent-allele caveat). | S | — |
| **SW-E6** | `#35`, `#22` | G6PD (X-linked dosage; het females may be deficient) + NUDT15 (rs116855232, EAS/Hispanic) + BCHE additions. | M | SW-E1 |

> §12.1/§12.6 throughout: a "Normal Metabolizer"/negative result never rules out untyped/CNV alleles
> (CYP2D6 reference-bias); do **not** extrapolate PREPARE's 30% ADR reduction to array-derived results.

### Wave F — Deeper variant interpretation (coordinate with validation effort)

| PR | Roadmap | Goal | Effort | Depends on |
|----|---------|------|--------|------------|
| **SW-F1** | `#13` | InterVar-style **DRAFT** ACMG/AMP engine (the 18 computable criteria; PVS1 via Abou-Tayoun SVI tree; Tavtigian point combination). **DRAFT / non-clinical**, gated by SW-A11 array-confidence; never auto-upgrades a P. PM3 unknown from unphased array. Reimplement (InterVar is academic-license). | L | SW-A11; reads Phase-F evidence/ensemble |
| **SW-F2** | `#38` | SpliceAI precomputed delta-scores (0.2/0.5/0.8; ClinGen SVI framework) — **CC-BY-NC → user-built local DB only, never redistribute**; applies only to the few typed SNPs in splice windows. | L | Phase-F build-schema (F30/F35) |
| **SW-F3** | `#39` | GTEx v8 eQTL/sQTL regulatory layer for typed non-coding SNPs (open-access; **GRCh38 → handle coords**; eQTL = association, not mechanism; do **not** inflate ACMG). | M | coordinate infra |

---

## 6. Recommended sequencing

1. **Wave A first** (≈12 PRs, S/M, directly-typed, parallelizable, no external runtime) — best
   leverage-per-effort and it hardens validity across all existing modules. Land SW-A11 (array-confidence)
   early since it gates Wave F.
2. **Wave B** (PGS Catalog) in parallel with late Wave A — SW-B1 unlocks five downstream PRs.
3. **Wave C** (imputation) is the single biggest unlock but L-effort with external runtime — start once
   Wave A/B reviewers free up; it then enables `#7/#28/#32/#47` credibility.
4. **Waves D/E/F** after their prerequisites (HLA needs R; PGx independent; deep-interp needs SW-A11 +
   Phase-F build-schema).

---

## 7. Firm guardrails carried into every PR (EXPANSION_STRATEGY §12)

1. **No imputed monogenic/pathogenic calls** — MAF/r² firewall (SW-C3) non-negotiable; imputed rare P/LP never user-facing.
2. **No MTHFR / "detox" pseudoscience** — methylation content stays categorical/educational, never prescriptive.
3. **No absolute lifetime risk** except the few externally-validated pathways (SW-B8), opt-in + CI + ancestry-validity; percentile+CI is the default.
4. **No PRS ancestry overstatement** — PC-continuous calibration fixes the percentile, **not** predictive accuracy; mandatory quantitative mismatch warning; APOL1 stays African-ancestry-only.
5. **No array CNV/structural claims** — no LRR/BAF → no PennCNV/Turner-45,X/CYP2D6-CNV/mosaicism; state limits plainly.
6. **No "negative = clear"** — every negative monogenic/carrier/PGx result says "does not exclude untyped/rare variants"; G6PD/DPYD/AATD/MCAD/HFE framed partial by design.
7. **No imputed HLA as confirmed genotype** — posterior-gated, ancestry-capped, "confirm with clinical HLA typing" banner; value is high NPV.
8. **No double-counting** — APOE excluded from AD-PRS; disease PRS don't re-report monogenic hits; REVEL/VEST4/CADD and AlphaMissense-vs-PM2 not stacked as independent evidence.
9. **No license violations** — gnomAD/1000G CC0 bundled; AlphaMissense CC-BY-4.0 + GTEx redistribute w/ attribution; dbNSFP/SpliceAI(CC-BY-NC)/HRC/TOPMed user-built-only; PGS Catalog & PharmGKB(CC-BY-SA) per-file; copyleft tools (Beagle/HIBAG/PLINK-equivalents) isolated subprocess or reimplemented.
10. **No clinical-decision framing** — research/educational decision-support only; actionable findings route to genetic counseling + CLIA confirmation (mirror the APOE gate).

---

## 8. Out of scope here

- Anything the **validation/Phase-F** effort owns (§1) — evidence-tier/in-silico/carriage/rarity logic.
- The **Yeliztli rebrand** residual manual phases (worktree/folder rename, live config migration) — separate, owner-gated.
- Net-new proposals beyond `EXPANSION_STRATEGY.md` §11.
