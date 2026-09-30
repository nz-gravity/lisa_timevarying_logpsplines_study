# Validation record

## Local cleanup validation — 2026-09-29

- Seven tests pass: foreground formula, differentiable density, covariance
  rotation, WDM projection, split boundaries, input integrity, installed CLI
  and small dataset generation.
- Continuous and gapped smoke runs completed for Hagn A/E, Horb A/E and
  joint Hpara A/E/T. All ten runs passed artifact verification.
- Every saved parameter draw in those ten fits is identical to its
  pre-cleanup counterpart. All 25 gapped preparation datasets are identical.
- The automatic ESA orbit download and HDF5 generation command completed.
- Ruff, Python compilation and shell syntax checks pass.

The local smoke runs use eight warmup and eight retained draws per chain.
These are execution and regression checks, not convergence tests. The full-year
foreground generator has not been rerun as part of the cleanup; its small-data
I/O and correlated-synthesis path are covered by a response-fixture test.

## OzSTAR pilot submitted — 2026-09-29

The isolated campaign is
`/fred/oz200/avajpeyi/projects/LISA_PSD/20260929_case_study/`.
It installs the locked environment against the sibling LogPSplinePSD snapshot.

| Mode | Preparation | Hagn A | Horb A | Hpara A/E/T |
| --- | --- | --- | --- | --- |
| Continuous | 17662596 | 17662597 | 17662598 | 17662599 |
| Gapped | 17662600 | 17662601 | 17662602 | 17662603 |

Both modes use full data resolution and the packaged A knot layouts, with eight
warmup/eight retained draws per chain and maximum tree depth six. Inference
jobs depend on preparation success. Job acceptance is not a completed
reproducibility check; inspect the logs, verification files and sampler
diagnostics after completion.
The release still needs converged full-duration comparisons and finalized E
surface layouts before claiming reproduction of every paper result.
