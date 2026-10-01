"""Validate current and historical stored results without rerunning inference."""

import json
from collections.abc import Iterator
from pathlib import Path

import h5py
import numpy as np

from .dataset_bundle import file_hash


def _blocks(dataset: h5py.Dataset) -> Iterator[np.ndarray]:
    """Read at most roughly 8 MiB per slice, preserving trailing matrix axes."""
    matrix = dataset.name.endswith("spectrum_summary__quantiles")
    candidates = range(dataset.ndim - 2 if matrix else dataset.ndim)
    axis = max(candidates, key=lambda i: dataset.shape[i])
    other = int(np.prod(dataset.shape)) // max(1, dataset.shape[axis])
    width = max(1, 8 * 1024**2 // max(1, other * dataset.dtype.itemsize))
    for start in range(0, dataset.shape[axis], width):
        selection = [slice(None)] * dataset.ndim
        selection[axis] = slice(start, start + width)
        yield dataset[tuple(selection)]


def verify_posterior_file(
    path: Path,
    *,
    label: str | None = None,
    bundle_sha256: str | None = None,
    settings: dict | None = None,
) -> dict:
    """Check native HDF5 result metadata/arrays, including pre-cache-metadata files.

    Stored summaries are checked directly; no claim about their all-draw cache
    provenance or convergence is introduced by this format compatibility path.
    """
    with h5py.File(path) as h:
        required = {
            "chain",
            "draw",
            "spectrum_summary__quantiles",
            "sample_stats__diverging",
            "log_likelihood__log_likelihood",
        }
        if (
            required - set(h)
            or not h.attrs.get("analysis")
            or not h.attrs.get("bundle_sha256")
        ):
            raise ValueError(f"Missing posterior metadata/arrays: {path}")
        if label is not None and h.attrs["analysis"] != label:
            raise ValueError(f"Posterior analysis label mismatch: {path}")
        if bundle_sha256 is not None and h.attrs["bundle_sha256"] != bundle_sha256:
            raise ValueError(f"Posterior input checksum mismatch: {path}")
        chains, draws = len(h["chain"]), len(h["draw"])
        if settings and (
            draws != settings["n_samples"] or chains != settings["num_chains"]
        ):
            raise ValueError(f"Posterior chain/draw counts mismatch: {path}")
        parameters = [key for key in h if key.startswith("posterior__")]
        if not parameters or min(chains, draws) < 1:
            raise ValueError(f"Empty posterior: {path}")
        for key in [
            *parameters,
            "log_likelihood__log_likelihood",
            "sample_stats__diverging",
        ]:
            dataset = h[key]
            if dataset.shape[:2] != (chains, draws) or any(
                not np.isfinite(block).all() for block in _blocks(dataset)
            ):
                raise ValueError(f"Invalid posterior array {key}: {path}")
        quantiles = h["spectrum_summary__quantiles"]
        if quantiles.ndim < 4 or quantiles.shape[-1] != quantiles.shape[-2]:
            raise ValueError(f"Invalid stored spectrum dimensions: {path}")
        for block in _blocks(quantiles):
            spectrum = np.diagonal(block, axis1=-2, axis2=-1).real
            if not np.isfinite(spectrum).all() or not (spectrum > 0).all():
                raise ValueError(f"Invalid stored positive spectra: {path}")
        return {
            "valid": True,
            "divergences": int(h["sample_stats__diverging"][()].sum()),
        }


def verify_run(output: Path, *, bundle: Path | None = None) -> dict:
    """Check input identity, finite samples/likelihoods, counts and stored spectra."""
    output = Path(output)
    receipt = json.loads((output / "run.json").read_text())
    if receipt.get("status") != "complete" or not receipt["analyses"]:
        raise ValueError("run is incomplete")
    bundle = Path(receipt["bundle"]) if bundle is None else Path(bundle)
    if file_hash(bundle) != receipt["bundle_sha256"]:
        raise ValueError("prepared bundle checksum does not match this run")
    checks = {
        label: verify_posterior_file(
            output / label / "inference_data.nc",
            label=label,
            bundle_sha256=receipt["bundle_sha256"],
            settings=receipt["settings"],
        )
        for label in receipt["analyses"]
    }
    return {"artifacts_valid": True, "convergence_assessed": False, "analyses": checks}
