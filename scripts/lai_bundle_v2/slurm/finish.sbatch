#!/bin/bash
# LAI v2 rebuild — final phases after the gnomix array: 06 (validation:
# trios -> phasing switch error + LAI accuracy) and 07 (assemble bundle +
# checksums + metadata). Depends on the phase-05 array via afterok.
#
#SBATCH --job-name=lai_finish
#SBATCH --partition=gpu
# 64 cpus so phase 6c fans out 16 concurrent Beagle runs x 4 threads each
# (env.sh derives BEAGLE_PARALLEL = SLURM_CPUS_PER_TASK / BEAGLE_NTHREADS); the
# other finish phases (06b/06d/06e single-thread, 07) just under-use the request.
#SBATCH --cpus-per-task=64
#SBATCH --mem=128G
#SBATCH --time=24:00:00
#SBATCH --output=lai_finish_%j.out

set -euo pipefail

# shellcheck source=/dev/null
source "${CONDA_SH:-$HOME/miniconda3/etc/profile.d/conda.sh}"
conda activate "${CONDA_ENV:-lai_bundle}"

SCRIPTS_DIR="${LAI_SCRIPTS_DIR:-$SLURM_SUBMIT_DIR}"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] finish: phases 06 07 (WORKDIR=$WORKDIR)"
bash "$SCRIPTS_DIR/run_rebuild.sh" 06 07
