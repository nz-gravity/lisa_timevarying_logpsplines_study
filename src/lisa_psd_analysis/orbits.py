"""Download ESA ephemerides and load sampled orbit positions."""

from pathlib import Path

import h5py
import numpy as np
from lisaorbits import InterpolatedOrbits, OEMOrbits


def load_orbits(path: Path) -> InterpolatedOrbits:
    """Interpolate sampled TCB positions without extrapolating beyond the file."""
    with h5py.File(path) as handle:
        start = float(handle.attrs["t0"])
        time = start + float(handle.attrs["dt"]) * np.arange(int(handle.attrs["size"]))
        positions = handle["tcb/x"][()]
    return InterpolatedOrbits(
        time, positions, t_init=start, interp_order=5, extrapolate=False
    )


def fetch_orbits(output: Path, *, version: str = "1.0.0", size: int = 632) -> Path:
    """Download CReMA OEM files and sample the Earth-trailing constellation."""
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    orbit = OEMOrbits.from_included("esa-trailing", version=version)
    orbit.write(str(output), t0=2073211130.8175, dt=100000.0, size=size)
    return output
