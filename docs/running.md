# Running an analysis

## Gapped data

```sh
uv run --locked lisa-study prepare data/lisa.h5 output/gapped.h5 --mode gapped
uv run --locked lisa-study fit output/gapped.h5 output/gapped-run --channels A E
```

The smoke profile uses a short time-series prefix and one artificial gap.
It does not represent the year-long gap schedule.

## Full resolution

```sh
uv run --locked lisa-study prepare data/lisa.h5 output/paper.h5 --profile paper
uv run --locked lisa-study fit output/paper.h5 output/paper-run --profile paper
```

Use `--mode gapped` during preparation for the fixed gap schedule. Preparation
uses the full dataset, WDM `nt=2048`, 16 frequency-projection nodes and 16
spectral-interpolation nodes. The fit defaults are 2200 warmup and 4000 retained
samples per chain, two chains, target acceptance .99 and maximum tree depth 12.
For a full-resolution execution check, add `--warmup 8 --samples 8 --max-tree-depth 6` to `fit`.

Both preparation and fitting must select `--profile paper`. Increasing only
the iterations of a smoke run cannot reproduce the full-resolution analysis.

Select hypotheses with `--models Hagn Horb Hpara`. The supplied full-resolution
spline layouts cover **A**: Hagn has 10 time and 128 frequency interior knots;
Horb has 3 time and 12 frequency interior knots. Both use HalfNormal(10)
smoothing scales; Horb has a HalfNormal(.5) interaction amplitude.

For another dataset or a full-resolution E fit, select one surface model and
channel and supply `--knots path/to/layout.json`. The JSON fields are `channel`,
`mode`, `model` (`agn` or `orb`), `knots_hz`, and, for Hagn, `knots_time`.
The supplied layouts check the dataset identity before use. Full-resolution E
layouts still need to be finalized for the reproducibility release.

## Outputs

Each hypothesis saves:

- `inference_data.nc`: parameter draws, sampler statistics, truth and spectral summaries.
- `posterior_spectrum.png`: truth, posterior median and log-ratio panels.
- `diagnostics/`: sampling statistics, spectrum statistics and an energy plot.
- `physical_parameters.json`: Hpara physical parameter draws.

`run.json` records completion, settings, input checksum, code fingerprints,
dependency versions and held-out metrics. `lisa-study verify RUN` checks
artifact integrity, draw counts, finite likelihoods and positive spectra.
If the prepared bundle has moved, use `verify RUN --bundle NEW_PATH`.
Verification does not establish MCMC convergence: inspect R-hat, ESS,
divergences, energy diagnostics and parameter recovery.

Every parameter draw is saved. Spectral arrays store two preview draws per
chain to bound file size; means and 5/50/95 percentiles use every draw.
Keep the prepared bundle with the results, especially for Hpara reconstruction.

The held-out metrics use each fit's native or pooled grid. They are not a
substitute for a comparison on common support or the complete publication
figure suite.
