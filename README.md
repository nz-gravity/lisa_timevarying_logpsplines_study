# LISA time-varying log-P-spline study

Computational supplement for the LISA time-varying PSD analysis in
[`nz-gravity/lisa_timevarying_logpsplines_study`](https://github.com/nz-gravity/lisa_timevarying_logpsplines_study).
It contains LISA physics, dataset preparation, study configurations, analysis
orchestration, validation, reconstruction figures and release tooling.

## Relationship to LogPSplinePSD

[LogPSplinePSD](https://github.com/nz-gravity/LogPSplinePSD) supplies the reusable
Bayesian PSD likelihoods, spline models, samplers and result containers.
This study uses its public `fit()` interface. The Python package remains
`lisa_psd_analysis`; the repository directory is `lisa_timevarying_logpsplines_study`.

## Paper workflow

1. Obtain the exact XYZ dataset from the authors, or regenerate it from its
   embedded noise/orbit inputs: [data and generation](docs/data.md).
2. Prepare continuous and gapped WDM bundles with `configs/paper/dataset.json`.
3. Fit Hagn, Horb and Hpara using the [paper configurations](configs/README.md).
4. Verify saved artifacts and assess convergence: [validation](docs/validation.md).
5. Regenerate reconstruction panels from saved results, then package the
   selected scientific files: [reproduction and release](docs/reproducibility.md).

## Quick start — offline smoke test

Use Python 3.12 and `uv`. Place the checkouts next to one another:

```text
projects/
├── LogPSplinePSD/
└── lisa_timevarying_logpsplines_study/
```

Clone the library at the commit recorded in `configs/library.json` (from the
study checkout):

```sh
git clone https://github.com/nz-gravity/LogPSplinePSD.git ../LogPSplinePSD
git -C ../LogPSplinePSD checkout d230c0fb883117dc6e65b46654103931eec96575
uv sync --locked
uv run lisa-study --help
uv run lisa-study generate build/demo.h5 --demo
uv run lisa-study prepare build/demo.h5 build/demo-prepared.h5
uv run lisa-study fit build/demo-prepared.h5 results/smoke --channels A E
uv run lisa-study verify results/smoke
uv run lisa-study figures --results results/smoke --output figures/smoke
uv run lisa-study package-release release/smoke --plan configs/release-smoke.json
uv run lisa-study verify-release release/smoke
```

Use fresh output paths. The synthetic fixture needs no dataset downloads and
is **not a LISA simulation or manuscript result**. Eight warmup/eight retained
draws per chain check execution only. [Running](docs/running.md) distinguishes
smoke tests, development runs and full paper settings.

## Paper analyses

| Hypothesis | Estimate | Channels |
|---|---|---|
| Hagn | Tensor log-P-spline for total power | A/E separately |
| Horb | ANOVA correction to an instrument reference | A/E separately |
| Hpara | Five foreground parameters and two noise scales | A/E/T jointly |

Truth is used only for diagnostics. Hpara uses independent marginal channel
likelihoods and excludes T below 3 mHz. The frozen surface layouts currently
cover **A only**. See [equations](docs/equations.md) and [OzSTAR](docs/ozstar.md).

## Data availability

The exact study dataset is not yet available through a published Zenodo URL.
Obtain `data/lisa.h5` from the study authors. Its embedded noise/orbits permit
regeneration; a fresh instrument-noise simulation recipe is not supplied.
Large datasets/results live outside Git in `data/`, `build/`, `results/` and
`figures/`, and belong in the scientific deposit.

## Reproducing manuscript results

[Reproducibility](docs/reproducibility.md) gives exact commands for the available
continuous/gapped A surface fits and joint Hpara fits. `figures` regenerates
saved reconstruction panels and exports their numerical data; final manuscript
figure numbering, common-support comparison panels and the full figure suite
remain to be supplied. Short runs do not establish manuscript reproduction.

## Repository layout

```text
configs/         versioned paper assets, library pin and release-plan example
docs/            data, running, equations, validation, reproduction, OzSTAR
src/lisa_psd_analysis/  flat LISA study package; private helpers start with _
scripts/         release compatibility entry point and manual staging helper
slurm/           preparation and analysis job scripts
tests/           study contracts, offline CLI execution and release integrity
```

## Zenodo / citation

No Zenodo DOI has been assigned. Release packaging creates a selected-file
manifest, provenance and checksums; it does not publish. Final datasets,
results, figure mapping, attribution/licensing and a versioned LogPSplinePSD
release are required before freezing the supplement. See the
[release checklist](docs/reproducibility.md).

For development: `uv run pytest`, `uv run ruff check .`,
`uv run ruff format --check .`. CI runs these checks without downloading LISA data.
