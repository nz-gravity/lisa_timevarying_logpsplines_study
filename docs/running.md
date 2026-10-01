# Running an analysis

All commands run from the study checkout with its `.venv`, managed by
`uv sync --locked`. Keep the sibling library at `configs/library.json`'s commit.
Choose new output paths: existing datasets, results and figure directories are
never overwritten.

## Smoke test

Follow the README's offline sequence. `generate --demo` creates synthetic
Gaussian XYZ samples, an artificial response and a static triangle orbit
fixture. It exercises the real preparation and all three fit paths, but has
no scientific recovery interpretation. Paper preparation rejects this fixture.
The default smoke profile prepares 8192 samples and fits two chains with eight
warmup/eight retained draws, acceptance .85 and tree depth four.

For a smoke check on the real dataset instead:

```sh
uv run lisa-study prepare data/lisa.h5 build/smoke-real.h5
uv run lisa-study fit build/smoke-real.h5 results/smoke-real --channels A E
uv run lisa-study verify results/smoke-real
```

`prepare --mode gapped` uses one artificial short gap in the smoke profile.

## Development run

Use explicit overrides for an execution check on the full-resolution bundle:

```sh
uv run lisa-study prepare data/lisa.h5 build/development.h5 --config configs/paper/dataset.json
uv run lisa-study fit build/development.h5 results/development \
  --config configs/paper/horb.json --warmup 8 --samples 8 --max-tree-depth 6
uv run lisa-study verify results/development
```

This is a full-resolution **execution check**, not a converged paper analysis.
The supplied config selects the paper profile; flags override its settings
and the effective values are recorded in `run.json`.

## Full paper settings

[Reproducibility](reproducibility.md) lists the complete available run sequence.
Preparation uses full data, WDM `nt=2048`, the original masks/partitions,
16 projection nodes and 16 spectral nodes. Fits use 2200 warmup, 4000 retained
draws per chain, two chains, acceptance .99 and maximum tree depth 12.
The legacy `--profile paper` interface still selects these versioned settings.

Hagn's A layouts have 10 time/128 frequency interior knots; Horb has 3 time/12
frequency knots. HalfNormal(10) roughness and Horb's HalfNormal(.5) interaction
are unchanged. Layouts check the dataset identity before use. Paper E layouts
remain unfinished; do not apply A layouts to E.

For another dataset or an E surface fit, select one model/channel and provide
`--knots path/to/layout.json`. Fields: `channel`, `mode`, `model` (`agn`/`orb`),
`knots_hz`, and `knots_time` for Hagn. This defines a separate development
analysis until its settings and results have been validated for the paper.
Hpara fits A/E/T jointly; `--channels` selects only surface-model channels.

## Outputs and validation

Each analysis writes `inference_data.nc`, reconstruction and diagnostic PNGs,
and diagnostic statistics. Hpara also writes `physical_parameters.json`.
`run.json` records completion, effective sampler settings, input identity,
code/dependency receipts, config hashes, seeds and held-out metrics.

`lisa-study verify RUN` checks artifacts and the prepared input checksum.
Use `--bundle NEW_PATH` if that bundle has moved. Verification checks finite
likelihoods, positive spectra and draw counts, not convergence. Assess R-hat,
ESS, divergences, energy and recovery before interpreting any run.

Every parameter draw is saved. Spectral arrays retain two preview draws per
chain; means and 5/50/95 percentiles use every draw. Keep prepared bundles for
inspection/reconstruction, especially Hpara response operators.

The held-out metrics use each fit's native/pooled grid; they are not a
common-support model comparison. `figures` exports reconstruction panels and
these existing metrics without rerunning inference.
