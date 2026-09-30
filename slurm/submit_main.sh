#!/usr/bin/env bash
# Submit full-length A-channel surface fits and joint A/E/T parametric fits.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if (( $# < 2 )); then
    echo "Usage: bash slurm/submit_main.sh BUNDLE_ROOT OUTPUT_ROOT [--execute] [--time HH:MM:SS]" >&2
    exit 2
fi
bundles=${1%/}
output=${2%/}
shift 2
execute=0
walltime=24:00:00
while (( $# )); do
    case "$1" in
        --execute) execute=1; shift ;;
        --time)
            if (( $# < 2 )); then echo '--time requires HH:MM:SS' >&2; exit 2; fi
            walltime=$2
            shift 2
            ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done
if [[ ! "$walltime" =~ ^[0-9]+:[0-5][0-9]:[0-5][0-9]$ ]]; then
    echo 'Use --time HH:MM:SS (hours may exceed 24).' >&2
    exit 2
fi
if [[ -e "$output" ]]; then
    echo "Choose a fresh output root: $output" >&2
    exit 2
fi
for mode in continuous gapped; do
    if [[ ! -f "$bundles/$mode.h5" ]]; then
        echo "Missing prepared bundle: $bundles/$mode.h5" >&2
        exit 2
    fi
done

if (( execute )); then mkdir -p "$output/logs"; fi
for mode in continuous gapped; do
    for model in Hagn Horb Hpara; do
        command=(sbatch --parsable --time="$walltime"
            --job-name="lisa-main-$model-$mode"
            --output="$output/logs/$model-$mode-%j.log"
            slurm/job.sbatch fit "$bundles/$mode.h5" "$output/$mode-$model"
            --profile paper --models "$model" --channels A)
        if (( execute )); then
            job_id=$("${command[@]}")
            printf '%s\t%s\t%s\n' "${job_id%%;*}" "$model" "$mode" >> "$output/jobs.tsv"
        else
            printf '%q ' "${command[@]}"; printf '\n'
        fi
    done
done
