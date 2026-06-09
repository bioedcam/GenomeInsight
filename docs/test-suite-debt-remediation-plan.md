# Test-Suite Audit Debt — Remediation Plan

**Created:** 2026-06-09
**Source:** an internal 2026-06-08 multi-agent test-suite audit (working notes, not committed to the repo). Its findings are reproduced inline below, so this plan is self-contained.
**Purpose:** track the remaining test-quality debt after the first remediation wave, with concrete, PR-sized actions.

---

## 1. Background

The audit's headline finding: the test suite encoded the **genotype-agnostic bug's happy path, not its guard** — almost no test seeded a `hom_ref` (non-carrier) Pathogenic variant and asserted it is suppressed, and several value-producing functions were covered only by `assert x is not None` / `status_code == 200`. It surfaced **12 code-verified masking flaws**, **~53 medium/low weaknesses**, CI-tiering issues, and validation-worktree blockers.

### Already remediated (for context — not part of this plan)

| Area | PRs |
|---|---|
| Live-engine carriage gate + zygosity column + M1–M9 validation suite | #315, #316, #320 |
| CI 3-tier model (path filters, Linux-only PR matrices, `ci-required` aggregator, nightly cross-OS backstop, slow-marks) | #325 |
| Value-blind unit tests #7–#12 (query-translator `literal_binds`, ancestry/LAI per-population asserts, e2e re-annotation counts, frontend zygosity labels) | #326 |
| P3 named items: `test_security_audit` CORS/regex, `test_backup_api` path-traversal | #326 |
| Carriage negative-controls + interactive `/search`, `/run`, panel-search gating (#2/#4) | #326, #339 |
| Nutrigenomics MTHFR C677T strand fix (#6) + shared strand-aware lookup across all 8 panel-scoring modules | #340, #344, #347 |
| `test_update_manager` ineffective-patch → real `CHECK_FNS` dispatch | #341 |

### What remains (this plan)

- **A.** De-mask the one remaining "hand-overwrite the column under test" end-to-end test (audit finding #5 / guardrail §1.5.4).
- **B.** Operationalize the test-quality guardrails from the audit's §1.5 (anti-`assert-is-not-None` convention; relaxed perf-assert cleanup; the hom_ref negative-control convention as a repo norm).
- **C.** The medium/low masked-assertion sweep (the ~49 items not yet touched).
- **D.** Owner-only repo settings (branch protection + merge queue).

> Every file/test reference below should be **re-verified against current code** before editing — line numbers drift and some tests have been renamed.

---

## 2. Prioritized remaining work

### P1 — De-mask the hand-overwritten end-to-end test (audit #5)

**Problem.** `tests/backend/test_sample_merge_full_pipeline.py::test_carrier_finding_source_attribution_emitted` hand-writes the column it claims to validate (`UPDATE annotated_variants SET zygosity='het' WHERE rsid='rs113993960'`) before calling `extract_carrier_variants`. The real path: CFTR F508del is an **indel** (ref `ATCT`, alt `A`), and `classify_zygosity(genotype='AT', ref='ATCT', alt='A')` returns `None` (it only scores single-base ref/alt), so the carrier finding is actually *suppressed*. The overwrite masks a real indel-carriage gap.

**Action (choose one, in priority order):**
1. **De-mask the test** — drive it with a genuinely scoreable carrier (a SNV carrier whose zygosity the production path computes), so no manual `UPDATE` is needed. Keep the existing `xfail(strict)` indel-carriage test (`test_f508del_indel_carriage_resolved`) as the tracking marker for the real gap.
2. **(Larger, optional) Support indel carriage** — extend `classify_zygosity` (and any allele-set logic) to score simple indels, then remove the overwrite *and* flip the `xfail`. Scope this only if indel carrier-status is a product requirement.

**DoD:** the end-to-end test no longer mutates `zygosity`; it fails if the production carriage path regresses. ~1 PR.

---

### P1 — Test-quality guardrails (audit §1.5) — make them repo norms, not one-offs

1. **Anti-`assert x is not None` / `status_code == 200`-only convention.**
   - Add a short "test assertion standards" section to `CONTRIBUTING`/test docs: value-producing functions must assert the *value*; status-only assertions are insufficient for behavior.
   - Consider a lightweight CI check (e.g. a `ruff` custom-message lint, a `grep`-based guard in a `pytest` meta-test, or a path-scoped review rule in `.coderabbit.yaml`) that flags new `assert .* is not None$` / `status_code == 200`-only test bodies. Start advisory, not blocking.
   - **DoD:** documented convention + (optional) advisory check. ~1 PR.

2. **Relaxed perf / timing asserts.**
   - `tests/backend/test_benchmark.py::test_annotation_600k_timing` asserts `< 1800s/2700s` while the PRD (Product Requirements Document) target is `<120s/<300s`. Either tighten to the real target or move to the nightly/benchmark tier — and **inline the target values (`120s/300s`) in a comment directly adjacent to the assertion** (the module comment references "the PRD target" but the assert site shows only the relaxed limits), so a future relaxation sees the 10× gap at the point of edit.
   - Sweep for sibling relaxed timing asserts (e.g. `test_performance_optimization` timing tests — already `slow`-marked; confirm their thresholds are meaningful).
   - **DoD:** no perf assert sits next to a target it's 10× looser than. ~1 PR.

3. **hom_ref negative-control convention.**
   - The shared `tests/backend/_carriage_fixtures.py` (`hom_ref_pathogenic_row` / `het_pathogenic_row`) exists. Extend the convention: **every analysis module that emits clinical findings** gets at least one test seeding a `hom_ref` Pathogenic variant and asserting it is absent from findings.
   - Audit current coverage and fill gaps (cancer, cardiovascular, the new disease modules: thrombophilia, alpha-1, AMD, APOL1, gout, HFE).
   - **DoD:** each clinical-finding module has a hom_ref negative control. 1–2 PRs (batch by module family).

---

### P2 — Targeted masked-assertion fixes (highest-signal medium items)

Each is a real masked defect; fix the assertion (and the SUT if the assertion then fails).

| Item | Test | Fix |
|---|---|---|
| Carriage not surfaced | `test_variant_detail_api` (seeds `zygosity='hom_ref'`, never asserts the endpoint reflects carriage) | Assert the endpoint surfaces/suppresses by carriage. |
| One-sided zygosity filter | `test_rare_variants_api::test_search_zygosity_filter` | Also assert the `hom_alt` row is **excluded** (not just that returned rows are `het`). |
| VCF body unverified | `test_export::test_vcf_export` | Assert REF/ALT/GT on data lines (catches dropped variants, swapped REF↔ALT, mis-encoded GT). |
| Aggregation could drop modules | `test_cross_module_integration::test_unified_findings_aggregates_all_modules` | Assert each expected module contributes, not just `len(findings) > 0`. |
| APOE genotype too loose | `test_cross_module_integration::test_apoe_genotype_determination` | Assert the exact diplotype (e.g. `ε3/ε3`), not `'3' in str(genotype)`. |
| PGx phenotype unchecked | `test_pharmacogenomics::test_no_data_defaults_to_normal` | Assert the phenotype call, not only `diplotype=='*1/*1'`. |
| PRS RUO/cap derived from SUT | `test_traits_api::test_prs_evidence_cap` / `test_prs_research_use_only` | Assert against an independent expected value. |
| LAI label/remap not value-asserted | `test_lai::test_painting_structure` / `test_remap_indices` | Assert per-segment labels / remap values (same mislabel class as the fixed #9). |

**DoD:** each test asserts the behavior it claims to. Batch into ~2–3 PRs by subsystem (variant/export, cross-module, traits/pgx/lai). 

---

### P2 — Frontend chart/mocks that discard the data under test

| Item | Test | Fix |
|---|---|---|
| Plotly mock collapses traces | `density-chart.test.tsx`, `qc-charts.test.tsx` | Mock should expose per-trace data so bin counts / het-hom-nocall values can be asserted (not just `data.length`). |
| System dark mode untested | `dark-mode.test.tsx` | Mock `matchMedia`/`prefers-color-scheme` and assert the resolved `.dark` class in System mode. |
| Promised coverage absent | `overlays.test.tsx` | Add the upload/apply/delete cases the docstring promises. |
| Findings/variant zygosity not asserted | `findings-explorer.test.tsx`, `variant-table.test.tsx` | Assert the rendered genotype/zygosity (both `het` and `hom_alt`). |

**DoD:** chart mocks preserve the data under test; promised cases exist. ~1–2 frontend PRs.

---

### P3 — Low-severity cleanups

- `test_auth::test_authenticated_request` asserts `!= 401` (a 500 would pass) → assert the expected success status.
- `test_skin_api::test_run_idempotent` asserts equal counts → also assert no duplicate rows.
- `test_watches::test_list_multiple` orders via real `time.sleep(0.01)` → use injected/monotonic timestamps to de-flake.
- `test_scripts_lai_runner_removed` skips on `git grep` exit 128 → fail (don't skip) on the error path.
- `test_variant_card::test_generate_pdf_endpoint_with_mock` fully mocks `generate_variant_card_pdf` → exercise the real generator (or add one integration test that does).

**DoD:** each low item asserts real behavior / de-flaked. 1 catch-all PR.

---

### Owner — repo settings (not code; requires `bioedcam`)

1. **Branch protection on `main`:** require status checks **`ci-required`** + **`lint`** (the `ci-required` aggregator is already wired in `ci.yml`; skipped jobs are treated as pass, so it is safe as the sole required check alongside `lint`).
2. **Merge queue:** enable it with the **Tier-2** matrix (macOS `test-backend-cross-os` / `smoke-install-cross-os`, `docker-build`, 3-browser `test-e2e`) as required merge-queue checks — this closes the pre-merge macOS/Docker/E2E blind spot (those legs only run on `push`/`merge_group` today).

**DoD:** `main` is protected by `ci-required` + `lint`; merge queue active with Tier-2 gates.

---

## 3. Suggested sequencing & PR grouping

One PR per logical change (repo convention), each rebased on current `main`, reviewed locally with the CodeRabbit CLI (`coderabbit review`) before push.

1. **De-mask #5** (P1) — small; unblocks the last "fixture stubs the SUT" case.
2. **Perf-assert cleanup** (P1 guardrails item 2) — small, isolated to `test_benchmark`.
3. **hom_ref negative-control coverage** (P1 guardrails item 3) — one PR, batched by module family (cancer/cardio, then the new disease modules).
4. **Backend masked-assertion fixes** (P2) — split into ~2–3 PRs by subsystem.
5. **Frontend chart/mocks** (P2) — ~1–2 frontend PRs.
6. **Low-severity catch-all** (P3) — a single cleanup PR.
7. **Anti-`assert-is-not-None` convention** (P1 guardrails item 1) — docs plus an optional advisory check.
8. **Branch protection + merge queue** — owner-only config, no PR.

Rough order of effort: P1 items are small and high-signal; the P2 sweep is the bulk; P3 is a single catch-all; the owner items are config, not code.

---

## 4. Definition of done (overall)

- No "end-to-end" test mutates the column it validates.
- Every clinical-finding module has a `hom_ref` negative control.
- No value-producing function is covered by `assert x is not None` / `status_code == 200` alone.
- No perf assert sits next to a target it is an order of magnitude looser than.
- Frontend chart tests assert the data, not the trace count.
- `main` is protected by the `ci-required` + `lint` required checks, with the merge queue gating Tier-2 (macOS/Docker/E2E).
