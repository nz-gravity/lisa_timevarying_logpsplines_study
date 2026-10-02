# LISA time-varying PSD study

Simulation, preparation and analysis code for the LISA time-varying PSD study.
The reusable Bayesian spectral models and samplers are provided by
[LogPSplinePSD](https://github.com/nz-gravity/LogPSplinePSD).

## Published data and results

[Zenodo dataset, v1.0.0](https://doi.org/10.5281/zenodo.23092878) contains the
raw simulated time series, continuous and gapped analysis datasets, and the
Hagn, Horb and Hpara posterior results. Start with the deposited
[`explore_lisa_results.ipynb`](https://zenodo.org/records/23092878/files/explore_lisa_results.ipynb)
to load the files and plot WDM power, median posterior surfaces and PSD slices.
The notebook runs independently of this repository with NumPy, h5py and Matplotlib.

| Model | Description | Channels |
| --- | --- | --- |
| Hagn | Tensor log-P-spline for total power | A |
| Horb | ANOVA correction to an instrument reference | A |
| Hpara | Five foreground parameters and two noise scales | A/E/T jointly |

Hpara uses a product of marginal channel likelihoods and excludes T below
3 mHz. See [model equations](docs/equations.md).

## Installation and smoke test

Use Python 3.12 and place the library checkout beside this repository:

```sh
git clone https://github.com/nz-gravity/LogPSplinePSD.git ../LogPSplinePSD
git -C ../LogPSplinePSD checkout d230c0fb883117dc6e65b46654103931eec96575
uv sync --locked
uv run lisa-study generate build/demo.h5 --demo
uv run lisa-study prepare build/demo.h5 build/demo-prepared.h5
uv run lisa-study fit build/demo-prepared.h5 results/smoke --channels A E
uv run lisa-study verify results/smoke
uv run lisa-study figures --results results/smoke --output figures/smoke
```

Choose fresh output paths. The synthetic fixture and eight-draw chains check
execution only; they are not manuscript results. For full analyses, see
[running](docs/running.md) and [reproduction](docs/reproducibility.md).

## Documentation

- [Data and simulation inputs](docs/data.md)
- [Running and checking analyses](docs/running.md)
- [Model equations](docs/equations.md)
- [Reproducing results](docs/reproducibility.md)
- [Manual OzSTAR jobs](docs/ozstar.md)

`src/lisa_psd_analysis/` contains LISA physics and analysis orchestration;
`configs/paper/` contains the dataset contract, gap schedule and fit settings.
Large data and results are kept outside Git.

## Citation

Data and posterior results: [10.5281/zenodo.23092878](https://doi.org/10.5281/zenodo.23092878).
Study software: [v0.1.1](https://github.com/nz-gravity/lisa_timevarying_logpsplines_study/releases/tag/v0.1.1),
[Zenodo archive](https://doi.org/10.5281/zenodo.23076396).
LogPSplinePSD, v0.2.0: [10.5281/zenodo.23076395](https://doi.org/10.5281/zenodo.23076395).
The saved run receipts record the software used for each fit.

Development checks: `uv run pytest`, `uv run ruff check .` and
`uv run ruff format --check .`. Tests use offline fixtures.
