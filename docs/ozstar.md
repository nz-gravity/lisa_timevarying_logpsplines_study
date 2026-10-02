# Manual OzSTAR runs

These instructions and scripts are for the researcher to run manually. No
remote jobs are submitted by the local tests.
The supplied jobs request account `oz200`, six CPUs and 32 GB. Adjust resources
for your allocation. All inference runs on compute nodes.

## Stage and install

Choose a new campaign directory, then run locally:

```sh
bash scripts/stage_ozstar.sh /absolute/remote/campaign/path
```

The helper uses SSH/rsync to copy both checkouts into that new directory.
It excludes data, results, environments and Git internals. It copies the
current library implementation; ensure the checkout matches
`configs/library.json` and is clean before staging a paper campaign.

After logging into OzSTAR yourself, install from the staged study directory:

```sh
cd /absolute/remote/campaign/path/lisa_timevarying_logpsplines_study
module load gcc/13.3.0 python/3.12.3
export SETUPTOOLS_SCM_PRETEND_VERSION_FOR_LOGPSPLINEPSD="$(cat ../logpspline-version.txt)"
uv sync --locked
```

Supply the exact study dataset separately and compare its deposit checksums.
A staged snapshot has no Git checkout identity: preserve the local source
commit receipts alongside the campaign before publication.

## Preview and submit

From the staged study checkout:

```sh
bash slurm/submit.sh /absolute/path/lisa.h5 results/pilot --warmup 8 --samples 8 --max-tree-depth 6
bash slurm/submit.sh /absolute/path/lisa.h5 results/pilot --execute --warmup 8 --samples 8 --max-tree-depth 6
```

The first command previews. The second submits two full-resolution preparation
jobs followed by dependent Hagn A, Horb A and Hpara A/E/T fits for both modes.
IDs and logs live beneath the output root. This pilot checks execution only.

Reuse valid prepared bundles for full paper settings:

```sh
bash slurm/submit_main.sh results/pilot results/paper-cluster
bash slurm/submit_main.sh results/pilot results/paper-cluster --execute
```

The six fits use the versioned paper settings via the backwards-compatible
`--profile paper` interface. Walltime defaults to 24 hours; `--time HH:MM:SS`
overrides it. Choose a new output root. The supplied surface configurations use A.

```sh
squeue -u "$USER"
sacct -j JOB_ID --format=JobID,JobName,State,ExitCode,Elapsed,MaxRSS
.venv/bin/lisa-study verify results/paper-cluster/continuous-Hagn
```

Check every result directory and convergence diagnostics. Scheduler success
alone does not establish scientific recovery. These cluster output names
differ from the local workflow; adapt an explicit release plan accordingly.
