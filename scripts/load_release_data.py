"""Inspect deposited LISA data and posterior samples without the inference library."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import h5py
import numpy as np


def load_xyz(
    root: Path, *, start: int = 0, stop: int = 4096, component: str = "total"
) -> tuple[np.ndarray, np.ndarray]:
    """Return absolute TCB seconds (N,) and XYZ samples (3, N); read a slice only."""
    with h5py.File(Path(root) / "data/lisa.h5") as h:
        if component not in {"total", "noise", "galactic"}:
            raise ValueError("component must be total, noise or galactic")
        n = h[f"tdi/{component}"].shape[1]
        if not 0 <= start < stop <= n:
            raise ValueError(f"Select samples within [0, {n}]")
        time = float(h.attrs["t0_tcb"]) + np.arange(start, stop) * float(
            h.attrs["dt_seconds"]
        )
        return time, h[f"tdi/{component}"][:, start:stop]


def load_power(
    root: Path, mode: str = "continuous", *, rows: int = 8, frequencies: int = 16
) -> dict[str, np.ndarray]:
    """Read a native WDM preview: power/truth (T,F,3), coordinates (T,) and (F,)."""
    if mode not in {"continuous", "gapped"} or rows < 1 or frequencies < 1:
        raise ValueError("Choose continuous/gapped and positive slice sizes")
    with h5py.File(Path(root) / f"data/{mode}.h5") as h:
        return {
            "time": h["native/time"][:rows],
            "frequency": h["native/frequency"][:frequencies],
            "power": h["native/power"][:rows, :frequencies, :],
            "truth": h["native/truth"][:rows, :frequencies, :],
            "channels": np.array(["A", "E", "T"]),
        }


def load_parameter(root: Path, mode: str, model: str, parameter: str) -> np.ndarray:
    """Load one named posterior variable, keeping chain/draw axes; log variables stay logged."""
    if mode not in {"continuous", "gapped"} or model not in {"Hagn", "Horb", "Hpara"}:
        raise ValueError("Unknown mode/model")
    label = model + ("_AET" if model == "Hpara" else "_A")
    path = Path(root) / f"results/{mode}/{model}/{label}/inference_data.nc"
    with h5py.File(path) as h:
        key = f"posterior__{parameter}"
        if key not in h:
            names = [
                k.removeprefix("posterior__") for k in h if k.startswith("posterior__")
            ]
            raise ValueError(f"Unknown parameter {parameter}; choose {names}")
        return h[key][()]


def extract_input(root: Path, name: str, output: Path) -> Path:
    """Extract the exact embedded instrument-noise/orbit file and verify its checksum."""
    if name not in {"noise", "orbits"}:
        raise ValueError("Choose noise or orbits")
    digest = hashlib.sha256()
    with h5py.File(Path(root) / "data/lisa.h5") as h, Path(output).open("xb") as stream:
        dataset = h[f"inputs/{name}"]
        for start in range(0, len(dataset), 8 * 1024**2):
            block = dataset[start : start + 8 * 1024**2].tobytes()
            stream.write(block)
            digest.update(block)
        if digest.hexdigest() != dataset.attrs["sha256"]:
            raise ValueError(f"Embedded {name} checksum mismatch")
    return Path(output)


def verify_checksums(root: Path) -> int:
    """Stream SHA256 verification of every deposited file; the original checkout is unnecessary."""
    count = 0
    root = Path(root).resolve()
    for line in (root / "checksums.sha256").read_text().splitlines():
        expected, name = line.split("  ", 1)
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Unsafe manifest path: {name}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024**2), b""):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError(f"Checksum mismatch: {name}")
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="deposit root",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="verify all deposited checksums (reads ~9 GB)",
    )
    parser.add_argument("--extract", choices=["noise", "orbits"])
    parser.add_argument("--output", type=Path, help="new destination for --extract")
    args = parser.parse_args()
    try:
        if args.verify:
            print(f"Verified {verify_checksums(args.root)} files")
        elif args.extract:
            if args.output is None:
                raise ValueError("--extract needs --output")
            print(extract_input(args.root, args.extract, args.output))
        else:
            time, xyz = load_xyz(args.root)
            power = load_power(args.root)
            amplitude = load_parameter(
                args.root, "continuous", "Hpara", "log_amplitude"
            )
            print(
                json.dumps(
                    {
                        "xyz_preview_shape": list(xyz.shape),
                        "time_tcb_range": [float(time[0]), float(time[-1])],
                        "power_preview_shape": list(power["power"].shape),
                        "channels": power["channels"].tolist(),
                        "log_amplitude_shape": list(amplitude.shape),
                    },
                    indent=2,
                )
            )
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
