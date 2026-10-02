# Reproducing the analysis

## Explore the published results

Download the nine files from [Zenodo](https://doi.org/10.5281/zenodo.23092878)
and open `explore_lisa_results.ipynb`. The deposit contains:

- `raw_data.h5`: original simulated XYZ time series and embedded inputs.
- `data_continuous.h5`, `data_gapped.h5`: prepared powers, masks, responses and truth.
- `posterior_Hagn.zip`, `posterior_Horb.zip`, `posterior_Hpara.zip`: paired continuous/gapped fits and run receipts.
- The notebook, short README and `checksums.sha256`.

```sh
shasum -a 256 -c checksums.sha256
```

The notebook plots raw time series, WDM power, median posterior surfaces and
PSD slices against truth. It reads stored posterior summaries without running
inference. Hagn and Horb use A; Hpara uses A/E/T. Saved 5/50/95 percentiles use
all posterior draws; stored spectral draws are a small preview.

## Run the analysis

Install following the README and save the deposited `raw_data.h5` as
`data/lisa.h5`. Run from the study checkout:

```sh
for mode in continuous gapped; do
  uv run lisa-study prepare data/lisa.h5 "build/$mode.h5" \
    --config configs/paper/dataset.json --mode "$mode"
  for model in hagn horb hpara; do
    uv run lisa-study fit "build/$mode.h5" "results/paper/$mode/$model" \
      --config "configs/paper/$model.json"
    uv run lisa-study verify "results/paper/$mode/$model"
  done
done
uv run lisa-study figures --results results/paper --output figures/paper
```

These are full inference runs. Choose fresh output paths and check convergence.
For cluster execution, use the [manual OzSTAR instructions](ozstar.md).

`configs/paper/` records preparation, knot layouts, masks, seeds and sampler
settings. `uv.lock` and `configs/library.json` fix the development environment.
The deposited run receipts record the environment of the original fits,
including library version `0.0.15.dev397+g0b7ef2b9d.d20260928`; the current
installation pin differs. Reruns with different software or hardware need not
produce identical draws. Compare posterior summaries and likelihoods using the
recorded configuration and matching inputs.

## Regenerate reconstruction panels

`lisa-study figures` reads `run.json` and `inference_data.nc` files. It writes
truth/median/log-ratio panels, numerical summaries in `figure_data/*.npz`,
held-out metrics in `heldout_metrics.csv` and source hashes in `figures.json`.
The exploration notebook provides the deposited-file plotting path.
Held-out metrics use each fit's grid; compare models on common support.
