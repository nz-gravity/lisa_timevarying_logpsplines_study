#!/usr/bin/env bash
# Submit two preparation jobs and six dependent inference jobs.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ $# -lt 2 ]]; then
    echo "Usage: bash slurm/submit.sh DATASET OUTPUT_ROOT [--execute] [--warmup N --samples N]" >&2
    exit 2
fi
archive=$(realpath "$1")
output=$2
shift 2
execute=0
if [[ "${1:-}" == --execute ]]; then execute=1; shift; fi
fit_options=("$@")
if [[ -e "$output" ]]; then
    echo "Choose a fresh output root: $output" >&2
    exit 2
fi
if ((execute)); then mkdir -p "$output/logs"; fi
for mode in continuous gapped; do
    bundle="$output/$mode.h5"
    prepare=(sbatch --parsable --job-name="lisa-prep-$mode" --time=04:00:00
        --output="$output/logs/prepare-$mode-%j.log" slurm/job.sbatch
        prepare "$archive" "$bundle" --profile paper --mode "$mode")
    if ((execute)); then
        prepare_id=$("${prepare[@]}")
        prepare_id=${prepare_id%%;*}
        printf '%s\tprepare\t%s\n' "$prepare_id" "$mode" >> "$output/jobs.tsv"
    else
        printf '%q ' "${prepare[@]}"; printf '\n'
        prepare_id=PREPARE_JOB_ID
    fi
    for model in Hagn Horb Hpara; do
        command=(sbatch --parsable --dependency="afterok:$prepare_id"
            --job-name="lisa-$model-$mode" --output="$output/logs/$model-$mode-%j.log"
            slurm/job.sbatch fit "$bundle" "$output/$mode-$model"
            --profile paper --models "$model" --channels A "${fit_options[@]}")
        if ((execute)); then
            job_id=$("${command[@]}")
            printf '%s\t%s\t%s\n' "${job_id%%;*}" "$model" "$mode" >> "$output/jobs.tsv"
        else
            printf '%q ' "${command[@]}"; printf '\n'
        fi
    done
done
