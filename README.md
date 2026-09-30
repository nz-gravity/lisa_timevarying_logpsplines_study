# LISA Time-varying PSD case study

Estimate a time-varying LISA power spectrum with **LogPSplinePSD**.
This project supplies the LISA data preparation, response model and analysis
settings. The library supplies Bayesian inference and posterior summaries.

## Quick start

Use Python 3.12 and [uv](https://docs.astral.sh/uv/). Keep the two checkouts
next to each other:

```text
projects/
├── LogPSplinePSD/
└── lisa_psd_analysis/
```

From `lisa_psd_analysis`:

```sh
uv sync --locked
uv run --locked lisa-study --help
```

Place the study dataset at `data/lisa.h5`, then run a small example:

```sh
uv run --locked lisa-study prepare data/lisa.h5 output/smoke.h5
uv run --locked lisa-study fit output/smoke.h5 output/smoke-run --channels A E
uv run --locked lisa-study verify output/smoke-run
```

The example uses 8192 time samples and two chains with eight warmup and eight
retained draws each. It demonstrates execution; it is too short to assess
convergence or recover annual modulation. Use a new output path for each run.

**Data availability:** the dataset is not yet published on Zenodo. Until the
deposit is available, obtain `lisa.h5` from the study authors. The file contains
the XYZ data, response, simulation truth, instrument-noise input and orbit input.

## Three hypotheses

| Model | What it estimates | Channels |
| --- | --- | --- |
| Hagn | Tensor log-P-spline for total power | A and E separately |
| Horb | ANOVA log correction to an instrument reference PSD | A and E separately |
| Hpara | Five foreground parameters and two instrument-noise scales | A/E/T jointly |

Truth is used only for diagnostics. Hpara uses independent marginal channel
likelihoods and excludes T below 3 mHz. All LISA-specific definitions live in
this project; no new NumPyro model is needed in a calling script or notebook.

## Next steps

- [Run locally](docs/running.md): gapped data, full-resolution settings and outputs.
- [Data and orbits](docs/data.md): automatic ESA downloads and dataset generation.
- [Run on OzSTAR](docs/ozstar.md): environment setup and Slurm jobs.
- [Reproducibility](docs/reproducibility.md): locked dependencies, checksums and deposits.
- [Equation-to-code map](docs/equations.md): entry points for manuscript code links.

## Develop

```sh
uv run --locked pytest
uv run --locked ruff check src tests scripts
uv run --locked ruff format --check src tests scripts
```

The Python entry points are `prepare.prepare()`, `run.run_analysis()` and
`generate.generate_dataset()` in the `lisa_psd_analysis` package. Imports enable
JAX float64 because the physical strain spectra require that precision.
