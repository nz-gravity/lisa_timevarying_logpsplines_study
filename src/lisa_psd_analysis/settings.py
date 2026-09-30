"""Spline structures and data-bound knot layouts."""

import json
from pathlib import Path

import numpy as np


def surface_config(h, name, channel, profile, knot_file=None):
    """Choose a spline structure and validate any explicit knot layout."""
    options = dict(
        structure="anova" if name == "Horb" else "tensor",
        centered=True,
        roughness_scale=10.0,
        interaction_scale=0.5,
        n_interior_knots_time=1,
        n_interior_knots_freq=3,
    )
    if profile == "paper" or knot_file is not None:
        if knot_file is None:
            if channel != "A":
                raise ValueError(
                    "Paper E fits require an explicit --knots file for this model/channel"
                )
            config_dir = Path(__file__).parent / "config"
            contract = json.loads((config_dir / "contract.json").read_text())
            if (
                h.attrs["tdi_total_sha256"] != contract["tdi_total_sha256"]
                or h.attrs["dt_seconds"] != contract["dt_seconds"]
            ):
                raise ValueError(
                    "Frozen paper knots require the matching dataset; supply --knots for another dataset"
                )
            knot_file = config_dir / f"{h.attrs['mode']}_{name[1:]}_{channel}.json"
        layout = json.loads(Path(knot_file).read_text())
        for key, expected in dict(
            channel=channel, mode=h.attrs["mode"], model=name[1:]
        ).items():
            if layout[key] != expected:
                raise ValueError(f"knot layout {key} must be {expected}")
        options.update(
            n_interior_knots_freq=len(layout["knots_hz"]),
            interior_knots_freq=np.asarray(layout["knots_hz"]),
            n_interior_knots_time=3 if name == "Horb" else len(layout["knots_time"]),
        )
        if name == "Hagn":
            options["interior_knots_time"] = np.asarray(layout["knots_time"])
    return options
