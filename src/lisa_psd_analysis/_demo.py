"""Offline deterministic fixtures for execution checks, never paper data."""

import json
import tempfile
from pathlib import Path

import h5py
import numpy as np

from .dataset_bundle import embed_inputs, file_hash
from .galactic import simulation_parameters


def generate_demo(output: Path) -> Path:
    """Write 8192 synthetic XYZ samples and a static triangular orbit fixture."""
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        orbit = Path(directory) / "orbits.h5"
        noise = Path(directory) / "noise.h5"
        time = np.linspace(-100000.0, 200000.0, 8)
        angle = np.arange(3) * 2 * np.pi / 3
        triangle = np.column_stack(
            (
                1.5e11 + 2.5e9 / np.sqrt(3) * np.cos(angle),
                2.5e9 / np.sqrt(3) * np.sin(angle),
                np.zeros(3),
            )
        )
        with h5py.File(orbit, "x") as h:
            h.attrs.update(t0=time[0], dt=time[1] - time[0], size=len(time))
            h["tcb/x"] = np.broadcast_to(triangle, (len(time), 3, 3))
        samples = np.random.default_rng(12345).normal(scale=1e-4, size=(3, 8192))
        with h5py.File(noise, "x") as h:
            h.attrs.update(t0=0.0, dt=2.0)
            for i, name in enumerate(("X2", "Y2", "Z2")):
                h[name] = samples[i]
        with h5py.File(output, "x") as h:
            h.attrs.update(
                t0_tcb=0.0,
                dt_seconds=2.0,
                n_samples=8192,
                demo=True,
                random_seed=12345,
                description="Synthetic execution fixture; not a LISA realization",
            )
            h["tdi/total"] = samples
            model = h.create_group("model")
            model.attrs.update(
                gb_model="karnesis2021_eq6_v1",
                gb_parameters_json=json.dumps(simulation_parameters().to_dict()),
                orbit_sha256=file_hash(orbit),
            )
            model["time_tcb"] = [0.0, 20000.0]
            model["frequency_hz"] = np.geomspace(1e-4, 0.1, 8)
            model["galactic_response_csd"] = np.broadcast_to(
                np.eye(3) * 1e40, (2, 8, 3, 3)
            )
        embed_inputs(output, noise, orbit)
    return output
