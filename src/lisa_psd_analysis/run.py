"""Run and save the selected LISA hypotheses."""

import json
from pathlib import Path

import h5py
import numpy as np
from log_psplines import PowerConfig

from .dataset_bundle import file_hash
from .diagnostics import heldout_metrics
from .fitting import fit_parametric, fit_surface
from .provenance import runtime_receipt
from .settings import surface_config


def run_analysis(
    bundle: Path,
    output: Path,
    *,
    profile="smoke",
    models=("Hagn", "Horb", "Hpara"),
    channels=("A",),
    warmup=None,
    samples=None,
    chains=2,
    knots=None,
    max_tree_depth=None,
):
    """Fit selected hypotheses and save posterior results with a run receipt."""
    bundle, output = Path(bundle), Path(output)
    if profile not in ("smoke", "paper") or not models or not channels:
        raise ValueError("choose a profile, at least one model and one channel")
    if set(models) - {"Hagn", "Horb", "Hpara"} or set(channels) - {"A", "E"}:
        raise ValueError("unknown model or channel")
    if output.exists():
        raise FileExistsError(output)
    if knots is not None and (
        len(models) != 1 or len(channels) != 1 or models[0] == "Hpara"
    ):
        raise ValueError("--knots requires one surface model and one channel")
    settings = dict(
        n_warmup=warmup if warmup is not None else (2200 if profile == "paper" else 8),
        n_samples=samples
        if samples is not None
        else (4000 if profile == "paper" else 8),
        num_chains=chains,
        max_tree_depth=max_tree_depth
        if max_tree_depth is not None
        else (12 if profile == "paper" else 4),
        target_accept_prob=0.99 if profile == "paper" else 0.85,
        spectrum_draws=2,
        spectrum_chunk_size=4,
        progress_bar=False,
    )
    PowerConfig(**settings)  # Validate sampler settings before creating outputs.
    receipt = dict(
        profile=profile,
        settings=settings,
        bundle=str(bundle.resolve()),
        bundle_sha256=file_hash(bundle),
        analyses={},
        status="running",
        **runtime_receipt(),
    )
    with h5py.File(bundle) as h:
        if profile == "paper" and h.attrs["profile"] != "paper":
            raise ValueError(
                "paper analysis requires full-resolution paper preparation"
            )
        # Validate all requested fits before creating an output directory.
        for name in models:
            if name != "Hpara":
                for channel in channels:
                    surface_config(h, name, channel, profile, knots)
        output.mkdir(parents=True)
        receipt["data_receipt"] = {
            k: v.item() if isinstance(v, np.generic) else v for k, v in h.attrs.items()
        }
        (output / "run.json").write_text(json.dumps(receipt, indent=2))
        for name in models:
            for channel in ("AET",) if name == "Hpara" else channels:
                label = f"{name}_{channel}"
                print(
                    f"Fitting {label}: {settings['n_warmup']} warmup, {settings['n_samples']} draws/chain",
                    flush=True,
                )
                if name == "Hpara":
                    g = h["para"]
                    result = fit_parametric(h, settings)
                    truth = g["truth"][()]
                else:
                    g = h["native"]
                    result = fit_surface(h, settings, name, channel, profile, knots)
                    truth = g["truth"][..., ("A", "E", "T").index(channel)]
                result.metadata.update(
                    analysis=label,
                    profile=profile,
                    bundle_sha256=receipt["bundle_sha256"],
                )
                result.save(str(output / label))
                metrics = heldout_metrics(
                    result,
                    truth,
                    g["test"][()],
                    t_min_frequency=0.003 if name == "Hpara" else None,
                )
                receipt["analyses"][label] = dict(
                    heldout=metrics,
                    divergences=int(result.sample_stats["diverging"].sum()),
                    finite_log_likelihood=bool(
                        np.isfinite(result.log_likelihood.to_array()).all()
                    ),
                )
                if name == "Hpara":
                    physical = {
                        key.removeprefix("log_"): np.exp(value.values).tolist()
                        for key, value in result.posterior.data_vars.items()
                        if key.startswith("log_")
                    }
                    (output / label / "physical_parameters.json").write_text(
                        json.dumps(physical, indent=2)
                    )
                (output / "run.json").write_text(json.dumps(receipt, indent=2))
    receipt["status"] = "complete"
    (output / "run.json").write_text(json.dumps(receipt, indent=2))
    return output
