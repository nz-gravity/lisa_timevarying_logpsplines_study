# Reproducibility and deposits

The analysis release consists of two source snapshots plus scientific inputs
and results. Zenodo records have not yet been published.

## What fixes a run

- `uv.lock` fixes the dependency resolution for Python 3.12, including JAX and NumPyro.
- The sibling LogPSplinePSD source supplies the generic likelihood and sampler.
- Packaged JSON layouts and gap schedules fix the analysis configuration.
- Prepared bundles contain masks, powers, references, response operators and truth.
- Run receipts record source fingerprints, dependency versions, input checksums and sampler settings.

Seeds control stochastic choices. Different hardware and numerical libraries
can change NUTS trajectories; scientific agreement should be assessed through
converged posterior summaries, alongside fixed-parameter likelihood checks.

## Prepare release artifacts

```sh
uv run --locked python scripts/package_release.py dist/release-0.1.0
```

The command writes a source archive for each project, the library version and
`SHA256SUMS.json`. It does not upload or publish anything. Extract both source
archives into one parent directory. For a source-only library build, export
`SETUPTOOLS_SCM_PRETEND_VERSION_FOR_LOGPSPLINEPSD` from `logpspline-version.txt`
before running `uv sync --locked` in the case study.

Before publishing the two deposits:

1. Finalize full-resolution E layouts and run the matching analyses.
2. Complete the OzSTAR validation and retain job logs, receipts, prepared bundles and results.
3. Include `lisa.h5`, its SHA-256 manifest and input attribution; confirm redistribution permissions for the instrument-noise data.
4. Confirm authors and software licenses for both releases.
5. Assign release tags and version-specific DOIs; add them to citation metadata and the README.
6. Cross-link the two software records and the data/results records.

The source packager excludes local environments, data and outputs. Archive the
scientific files separately, with checksums, rather than assuming they are in
the software archives. A fresh full-year instrument-noise generator and the
complete publication figure suite are not currently included.

## Manuscript code links

Use [the equation map](equations.md) to select functions, then add immutable
GitHub links pinned to the released commit and line range. Cite the matching
Zenodo version DOI for archival access. Release commits and DOIs are needed
before those links can be finalized. The manuscript itself is not changed by
this project.
