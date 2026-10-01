# Validation

Artifact verification and convergence are separate gates. `verify` checks
input identity, posterior metadata, finite likelihoods, positive spectra and
draw/chain counts. `verify-release` additionally checks the full manifest,
checksums, config/provenance consistency and relocated scientific artifacts.
Neither certifies convergence or manuscript completeness.

## Local cleanup — 2026-10-01

The offline synthetic fixture exercises generation, real WDM preparation,
Hagn A/E, Horb A/E and joint Hpara fits, saved-result verification, reconstruction
figures and an explicit scientific release. The fixture and short chains are
execution checks; they do not validate LISA recovery or annual modulation.

The test suite covers A/E/T rotation, foreground formulas, the seven-parameter
LISA adapter density, WDM projection/split boundaries, deterministic fixtures,
preparation axes/metadata, input integrity, paper configs, provenance,
release traversal/missing-input/tampering failures and saved-result figures.
It does not run expensive paper chains or fetch study datasets.

The final local checks and fresh-checkout smoke result are recorded in
`docs/cleanup.md`. CI runs `uv sync --locked`, `pytest`, `ruff check .` and
`ruff format --check .` against the pinned sibling library.

Existing 2026-09-29 validation/campaign products are local, ignored artifacts.
They have not been promoted to final publication results or rerun during this
cleanup. No OzSTAR connection or submission was performed.

## Publication gates

Inspect R-hat, ESS, divergences, tree-depth saturation, E-BFMI, posterior
recovery and comparison on common support. Final E layouts, selected converged
results and the complete manuscript figure/table mapping remain prerequisites;
see the [freeze checklist](reproducibility.md).

The library currently writes complex/HDF5-backed `.nc` files using h5netcdf's
nonstandard NetCDF features. This study verifies them through `PSDResult`;
portability to arbitrary NetCDF clients is not established here. This is an
external library format limitation, not an inference change in this study.
