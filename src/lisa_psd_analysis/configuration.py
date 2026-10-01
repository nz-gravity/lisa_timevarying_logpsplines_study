"""Versioned study assets and explicit paper-run configuration."""

import json
import sys
from pathlib import Path
from typing import Any


def paper_config_dir() -> Path:
    """Locate checkout assets, or their installed wheel copy."""
    checkout = Path(__file__).resolve().parents[2] / "configs" / "paper"
    installed = Path(sys.prefix) / "share" / "lisa-study" / "configs" / "paper"
    if checkout.is_dir():
        return checkout
    if installed.is_dir():
        return installed
    raise FileNotFoundError("Missing paper configs; reinstall the study package")


def load_config(path: Path, kind: str) -> dict[str, Any]:
    """Load a schema-1 JSON analysis or preparation configuration."""
    try:
        config = json.loads(Path(path).read_text())
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON configuration: {path}: {error}") from error
    if (
        not isinstance(config, dict)
        or config.get("schema") != 1
        or config.get("kind") != kind
    ):
        raise ValueError(f"Expected schema=1, kind={kind} configuration: {path}")
    if config.get("profile") != "paper":
        raise ValueError("Study configurations must explicitly select profile=paper")
    if kind == "analysis":
        required = {
            "schema",
            "kind",
            "profile",
            "models",
            "channels",
            "settings",
            "random_seeds",
        }
        keys = {
            "n_warmup",
            "n_samples",
            "num_chains",
            "max_tree_depth",
            "target_accept_prob",
            "spectrum_draws",
            "spectrum_chunk_size",
            "progress_bar",
        }
        if (
            set(config) != required
            or not isinstance(config["settings"], dict)
            or set(config["settings"]) != keys
        ):
            raise ValueError(
                f"Unexpected or missing analysis configuration fields: {path}"
            )
        if (
            not config["models"]
            or set(config["models"]) - {"Hagn", "Horb", "Hpara"}
            or not config["channels"]
            or set(config["channels"]) - {"A", "E"}
        ):
            raise ValueError(f"Unknown or empty models/channels: {path}")
        seeds = config["random_seeds"]
        if (
            not isinstance(seeds, dict)
            or set(seeds) != {"surface", "gapped_surface", "parametric"}
            or any(type(value) is not int or value < 0 for value in seeds.values())
        ):
            raise ValueError(f"Invalid random_seeds: {path}")
        from log_psplines import PowerConfig

        try:
            PowerConfig(**config["settings"])
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid sampler settings: {path}: {error}") from error
    elif kind == "preparation":
        required = {
            "schema",
            "kind",
            "profile",
            "nt",
            "taper_seconds",
            "projection_nodes",
            "spectral_nodes",
        }
        if (
            set(config) != required
            or config["nt"] < 2
            or config["nt"] % 2
            or config["taper_seconds"] < 0
            or min(config["projection_nodes"], config["spectral_nodes"]) < 1
        ):
            raise ValueError(f"Invalid preparation settings: {path}")
    else:
        raise ValueError(f"Unknown configuration kind: {kind}")
    return config
