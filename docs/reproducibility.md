# Reproduction and scientific releases

## Available paper analysis path

Install following the README, obtain the authors' exact `data/lisa.h5`, then
run the following from the study checkout. These commands are expensive and
were not executed during repository cleanup:

```sh
uv sync --locked
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

This reproduces the configured A surface analyses and joint Hpara path,
subject to the matching dataset and successful convergence. It does not
claim to reproduce unfinished E surface analyses or every manuscript figure.
Use [OzSTAR](ozstar.md) for manual staging/submission.

## Figure scope

`figures` reads completed `run.json` receipts and existing `inference_data.nc`
files. It writes one truth/median/log-ratio reconstruction panel per saved
analysis, numerical quantiles/truth in `figure_data/*.npz`, and the recorded
held-out metrics in `heldout_metrics.csv`. `figures.json` links panels to
source hashes and records that final manuscript numbering is pending.
Outputs are deterministic for the same inputs and plotting environment.

These are the only figure sources currently in this repository: the standard
LogPSplinePSD saved-result renderer and this study's regeneration command.
No unused exploratory plotting scripts were present. The final publication
figure suite, common-support comparison plots and table extraction sources
must be supplied before claiming complete manuscript reproduction.

## What fixes a run

- `uv.lock` pins dependency resolution for Python 3.12; the sibling Git commit
  is recorded in `configs/library.json` (an editable dependency is not itself
  frozen by a lock file).
- `configs/paper/` fixes sampler settings, dataset identity, A knot layouts
  and the gap schedule. Never edit released assets; tag a new release instead.
- Prepared HDF5 bundles preserve powers, masks, references, response and truth.
- Run receipts preserve effective settings, seeds, input/config hashes and
  code fingerprints. Overrides denote a different development run.

Different hardware/numerical libraries can change NUTS trajectories. Compare
converged posterior summaries and fixed-parameter likelihoods, not just seeds.

## Build a Zenodo scientific bundle

Each JSON release plan lists **individual files**, their type, description,
source, manuscript reference and generating command. Source paths are relative
to the plan file (absolute sources are supported); deposited paths are contained
under `data/`, `results/`, `configs/` or `figure_data/`. Symlinks, duplicate
names, missing files and incomplete receipts fail packaging. The release
output must be new. Paper configs, the dependency lock and source attribution
are always added automatically.

The README smoke sequence has a runnable `configs/release-smoke.json` inventory.
The available full paper workflow has `configs/release-paper.json`. Its
references explicitly remain provisional; finalize them before publication.

```sh
uv run lisa-study package-release release/paper --plan configs/release-paper.json
uv run lisa-study verify-release release/paper
```

The compatibility script runs the same implementation:

```sh
uv run python scripts/package_release.py release/paper-copy --plan configs/release-paper.json
```

The deposit contains:

```text
release/paper/
├── README.md            human-readable artifact manifest
├── MANIFEST.csv         path/type/description/source/manuscript_reference/generated_by/sha256
├── provenance.json      generated environment/source/settings receipt
├── checksums.sha256     every deposited file except this checksum file
├── data/
├── results/
├── configs/
└── figure_data/
```

Verification checks the complete file inventory, checksums, config schemas,
provenance, openable scientific files and complete runs against the deposited
prepared inputs. It works after relocation without the original absolute input
paths. It establishes integrity, not convergence or publication readiness.
The packager never runs inference, archives the whole repository or uploads.

Provenance includes the study URL/commit/dirty state, installed library
version/commit/dirty state when available, Python/JAX/NumPyro versions,
platform, dependency-lock hash, seeds, paper-config hashes, creation timestamp
and complete run receipts. Missing library Git identity remains explicit.
`docs/source-attribution.json` retains the original imported-code receipts;
it is historical attribution, not current runtime provenance.

## Freeze blockers

Before assigning immutable release tags and Zenodo DOIs:

1. Publish the exact dataset and embedded inputs, with checksums and verified
   redistribution permissions/ESA attribution. The public dataset URL is absent.
2. Finalize any manuscript E surface layouts and obtain their matching results.
3. Select the final converged posterior files/receipts and assess diagnostics.
   Six completed 4000-draw candidate fits exist locally in
   `output/main-20260929`; their prepared bundles are in
   `output/ozstar-repro-pilot`. Their receipts refer to historical cluster
   paths, so use `verify --bundle LOCAL_PATH`. They record library version
   `0.0.15.dev397+g0b7ef2b9d.d20260928`, older than the installation pin used
   for current cleanup tests. Preserve and release that matching source
   snapshot for exact historical reproduction; do not label current-library
   reruns as byte-identical reproduction.
4. Supply the complete manuscript figure/table sources and final figure mapping.
   Current reconstruction panels do not cover the full publication suite.
5. Release/tag LogPSplinePSD and cross-link its immutable version/DOI. The
   pinned Git snapshot is usable for development, not a published DOI.
6. Confirm study authors/licenses/data permissions, make clean tagged source
   snapshots, update the release plan to final manuscript references, and
   assign/cross-link software and data/results DOIs.

The manuscript itself is outside this repository and has not been changed.
