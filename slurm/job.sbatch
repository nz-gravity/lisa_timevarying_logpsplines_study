#!/usr/bin/env bash
#SBATCH --job-name=lisa-psd
#SBATCH --account=oz200
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --mem=32G
#SBATCH --time=24:00:00
set -euo pipefail
module load gcc/13.3.0 python/3.12.3
cd "${SLURM_SUBMIT_DIR:?Submit from the case-study checkout}"
export JAX_ENABLE_X64=true
export MPLBACKEND=Agg
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export XLA_FLAGS="--xla_cpu_multi_thread_eigen=false"
# The environment is installed on the login node before submission.
.venv/bin/python -m lisa_psd_analysis "$@"

if [[ "${1:-}" == fit ]]; then
    .venv/bin/python -m lisa_psd_analysis verify "$3" > "$3/verification.json"
fi
