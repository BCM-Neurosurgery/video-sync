#!/usr/bin/env bash
#SBATCH --job-name=video-sync
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=08:00:00
#SBATCH --output=slurm-%j.out

# Run from your checkout after: uv sync --locked --inexact
# Direct execution:
#   uv run --no-sync stitch-videos --config /path/to/patient.yaml
# Slurm on Wrangell:
#   sbatch --partition=chipmunk scripts/sync.sbatch /path/to/patient.yaml
# Override resources with sbatch options, e.g. --mem=16G --time=24:00:00.
# The checkout, environment and data must be accessible on the compute node.
# Use a separate output_dir in the config for each concurrent run.

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: sbatch [options] scripts/sync.sbatch CONFIG.yaml" >&2
    exit 2
fi

export PYTHONUNBUFFERED=1
export MPLBACKEND=Agg
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"

exec uv run --no-sync stitch-videos --config "$1"
