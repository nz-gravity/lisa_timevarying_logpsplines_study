"""Validate saved inference artifacts without treating short chains as converged."""

import json
from pathlib import Path

import numpy as np
from log_psplines import PSDResult

from .dataset_bundle import file_hash


def verify_run(output: Path, *, bundle: Path | None = None) -> dict:
    """Check input identity, draw counts, finite likelihoods and positive PSDs."""
    receipt = json.loads((output / "run.json").read_text())
    if receipt.get("status") != "complete" or not receipt["analyses"]:
        raise ValueError("run is incomplete")
    bundle = Path(receipt["bundle"]) if bundle is None else bundle
    if file_hash(bundle) != receipt["bundle_sha256"]:
        raise ValueError("prepared bundle checksum does not match this run")
    checks = {}
    for label in receipt["analyses"]:
        result = PSDResult.from_netcdf(output / label / "inference_data.nc")
        spectrum = np.diagonal(result.quantiles().values, axis1=-2, axis2=-1).real
        valid = (
            np.isfinite(spectrum).all()
            and (spectrum > 0).all()
            and np.isfinite(result.log_likelihood.to_array()).all()
            and result.posterior.sizes["draw"] == receipt["settings"]["n_samples"]
            and result.posterior.sizes["chain"] == receipt["settings"]["num_chains"]
        )
        if not valid:
            raise ValueError(f"invalid posterior artifacts: {label}")
        checks[label] = {
            "valid": True,
            "divergences": int(result.sample_stats.diverging.sum()),
        }
    return {"artifacts_valid": True, "convergence_assessed": False, "analyses": checks}
