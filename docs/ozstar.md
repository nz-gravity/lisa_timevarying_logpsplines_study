# OzSTAR

The supplied Slurm scripts use account `oz200`, six CPUs and 32 GB per job.
OzSTAR chooses the partition from the requested resources. Change the resource
requests for another allocation or cluster. All sampling runs on compute nodes.

## Stage an isolated copy

From the local case-study checkout:

```sh
bash scripts/stage_ozstar.sh /fred/oz200/avajpeyi/projects/LISA_PSD/run-YYYYMMDD
```

The destination must be new. The script copies the case-study source and the
current LogPSplinePSD implementation, including uncommitted changes. It excludes
local environments, output data and Git internals. It does not alter existing
campaigns.

## Install on the login node

```sh
ssh ozstar
cd /fred/oz200/avajpeyi/projects/LISA_PSD/run-YYYYMMDD/lisa_psd_analysis
module load gcc/13.3.0 python/3.12.3
export SETUPTOOLS_SCM_PRETEND_VERSION_FOR_LOGPSPLINEPSD="$(cat ../logpspline-version.txt)"
uv sync --locked
```

The version variable lets the library build from a source snapshot without
Git metadata. Supply the study dataset at an absolute path on the cluster.
Check it against the input hashes accompanying the deposit.

## Preview and submit

```sh
bash slurm/submit.sh /absolute/path/lisa.h5 output/pilot --warmup 8 --samples 8 --max-tree-depth 6
bash slurm/submit.sh /absolute/path/lisa.h5 output/pilot --execute --warmup 8 --samples 8 --max-tree-depth 6
```

The first command prints the job commands. The second submits two
full-resolution preparation jobs, followed by six fits: Hagn A, Horb A and
joint Hpara A/E/T, each for continuous and gapped observations. Each fit waits
for its corresponding preparation job to succeed. Job IDs go to
`output/pilot/jobs.tsv`; logs go to `output/pilot/logs/`.

After the execution pilot is valid, omit `--warmup`/`--samples` and choose a
fresh output root to use the paper-length sampler settings. E surface jobs
require their explicit layouts before they can join this campaign.

```sh
squeue -u "$USER"
sacct -j JOB_ID --format=JobID,JobName,State,ExitCode,Elapsed,MaxRSS
.venv/bin/lisa-study verify output/pilot/continuous-Hagn
```

Check all six fit directories. A scheduler success is an execution result;
assess convergence and recovery separately before interpreting the posteriors.

## Main fits using the pilot's prepared bundles

The full-resolution pilot bundles can be reused. This submits six fits with the
paper defaults: 2200 warmup and 4000 retained draws per chain, two chains,
target acceptance .99 and maximum tree depth 12. Hagn and Horb fit A; Hpara
fits A/E/T jointly. Use a fresh output root.

First copy the new submission helper from your local case-study checkout to
the existing staged checkout:

```sh
rsync -av slurm/submit_main.sh ozstar:/fred/oz200/avajpeyi/projects/LISA_PSD/20260929_case_study/lisa_psd_analysis/slurm/
```

Then, on OzSTAR, from the staged case-study checkout:

```sh
bash slurm/submit_main.sh output/repro-pilot output/main-20260929
bash slurm/submit_main.sh output/repro-pilot output/main-20260929 --execute
```

The first command previews all six `sbatch` calls. The second submits them
and writes IDs to `output/main-20260929/jobs.tsv`. Jobs use a 24-hour walltime
by default; `--time HH:MM:SS` overrides it if the partition allows a longer
request. Check the partition limit before raising it. These fits do not depend
on a new preparation job because both prepared bundles already exist.

Full-resolution Hagn/Horb E runs need separately validated E knot layouts;
the old WDM test-code layouts are not interchangeable with the A layouts
frozen here. They are not part of this submission.
