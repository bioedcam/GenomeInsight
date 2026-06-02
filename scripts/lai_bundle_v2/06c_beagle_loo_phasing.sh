#!/usr/bin/env bash
# Phase 6c — leave-one-out Beagle phasing for each trio child, PARALLELIZED.
#
# Every (child, chromosome) Beagle run is independent (child- and chrom-specific
# output files), so they fan out concurrently via `xargs -P BEAGLE_PARALLEL`, each
# Beagle capped to BEAGLE_NTHREADS threads (BEAGLE_PARALLEL * BEAGLE_NTHREADS must
# fit the job's cpu allocation; both auto-scale from SLURM_CPUS_PER_TASK in env.sh).
# The per-(child,chrom) work lives in 06c_beagle_one.sh, which is idempotent (skips
# pairs already phased), so a resubmit reuses prior progress.
#
# Plan §6.4 phase 6c — logic unchanged from v1.1; only the scheduling is parallel.

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PHASE_NAME=06c_beagle_loo
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

require bcftools
require java
require_file "$BEAGLE_JAR"
require_file "$VALIDATION_DIR/trio_pedigree.tsv"
require_file "$SCRIPT_DIR/06c_beagle_one.sh"

cd "$VALIDATION_DIR"

# Per-child family exclusion files (child + both parents). Build them ONCE here,
# before the parallel fan-out, so concurrent workers never race to create them.
awk -F'\t' 'NR>1 {f="trio_family_"$1".txt"; print $1 > f; print $2 >> f; print $3 >> f}' \
  trio_pedigree.tsv

# Build the (child, chrom) job list.
joblist="$(mktemp)"
trap 'rm -f "$joblist"' EXIT
while IFS=$'\t' read -r child father mother pop; do
  [ "$child" = "child" ] && continue
  [ -z "$child" ] && continue
  for chr in $CHROMS; do
    printf '%s\t%s\n' "$child" "$chr" >> "$joblist"
  done
done < "$VALIDATION_DIR/trio_pedigree.tsv"

n_jobs=$(wc -l < "$joblist")
phase_log "phase 6c: $n_jobs (child,chrom) beagle jobs — ${BEAGLE_PARALLEL} parallel x ${BEAGLE_NTHREADS} threads"

# Fan out. xargs runs one worker per line (-L1), BEAGLE_PARALLEL at a time (-P),
# and exits non-zero if ANY worker fails — so set -e fails the phase loudly rather
# than silently shipping a bundle with missing beagle phasings.
xargs -P "$BEAGLE_PARALLEL" -L1 -a "$joblist" bash "$SCRIPT_DIR/06c_beagle_one.sh"

phase_log "phase 6c complete"
