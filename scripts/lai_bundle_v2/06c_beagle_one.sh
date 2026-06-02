#!/usr/bin/env bash
# Phase 6c worker — leave-one-out Beagle phasing for ONE (child, chromosome).
#
# Invoked in parallel by 06c_beagle_loo_phasing.sh via `xargs -P` (one process per
# (child, chrom)). Every output path is child- AND chrom-specific, so concurrent
# workers never write the same file. Idempotent: skips if the beagle output exists
# (so a resubmit reuses already-phased pairs). Each Beagle run is capped to
# BEAGLE_NTHREADS threads so BEAGLE_PARALLEL workers fit the job's cpu allocation.
#
# Usage: bash 06c_beagle_one.sh <child> <chr>

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PHASE_NAME=06c_beagle_one
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

child="${1:?usage: 06c_beagle_one.sh <child> <chr>}"
chr="${2:?usage: 06c_beagle_one.sh <child> <chr>}"

cd "$VALIDATION_DIR"

beagle_out="child_beagle_phased_${child}_chr${chr}.vcf.gz"
# Skip only a COMPLETE prior output: a non-empty BGZF that passes an EOF-integrity
# check (bgzip -t). A bare `-s` test would accept a half-written .vcf.gz left by a
# killed/scancel'd worker and ship corrupt phasing to 06d. If bgzip is unavailable
# the test fails and we regenerate (the safe default). Drop any partial first so
# Beagle re-creates it cleanly.
if [ -s "$beagle_out" ] && bgzip -t "$beagle_out" 2>/dev/null; then
  phase_log "chr${chr} ${child}: beagle present + intact, skipping"
  exit 0
fi
rm -f "$beagle_out"

panel_in="$PANEL_DIR/ref_panel_chr${chr}.vcf.gz"
require_file "$panel_in"
exclude_file="trio_family_${child}.txt"
require_file "$exclude_file"

# Extract the child as an unphased single sample (| -> /).
bcftools view -s "$child" "$panel_in" \
  | sed 's/|/\//g' \
  | bcftools view -Oz -o "child_unphased_${child}_chr${chr}.vcf.gz"
bcftools index -t "child_unphased_${child}_chr${chr}.vcf.gz"

# Reference panel without the child's family (child + both parents).
ref_loo="ref_without_family_${child}_chr${chr}.vcf.gz"
# Reuse only a COMPLETE ref panel: non-empty + indexed (the .tbi is written last by
# `bcftools index -t`, so its presence proves the view finished) + BGZF-intact. A
# killed worker can leave a truncated ref_loo; rebuild from scratch in that case.
if [ -s "$ref_loo" ] && [ -s "${ref_loo}.tbi" ] && bgzip -t "$ref_loo" 2>/dev/null; then
  :
else
  rm -f "$ref_loo" "${ref_loo}.tbi"
  bcftools view -S "^${exclude_file}" "$panel_in" -Oz -o "$ref_loo"
  bcftools index -t "$ref_loo"
fi

# Beagle wants the chr_in_chrom_field plink map whose chrom field matches the
# panel's chr-prefixed contigs (plink.chrchrN.GRCh38.map) — the same file the
# runtime loads (backend/analysis/lai_runner.py).
genetic_map="$RAW_DIR/genetic_maps_grch38/chr_in_chrom_field/plink.chrchr${chr}.GRCh38.map"
require_file "$genetic_map"

phase_log "Beagle: ${child} chr${chr} (nthreads=${BEAGLE_NTHREADS})"
java -Xmx"$BEAGLE_XMX" -jar "$BEAGLE_JAR" \
  gt="child_unphased_${child}_chr${chr}.vcf.gz" \
  ref="$ref_loo" \
  map="$genetic_map" \
  out="child_beagle_phased_${child}_chr${chr}" \
  impute=false \
  nthreads="$BEAGLE_NTHREADS" \
  2>&1 | tee "$LOG_DIR/beagle_${child}_chr${chr}.log"
