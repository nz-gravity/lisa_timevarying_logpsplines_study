"""Preserve exact orbit/noise input files inside the single data archive.

Libraries needing a pathname receive a checksum-verified, disposable cache.
"""

import hashlib
import os
import tempfile
from pathlib import Path

import h5py
import numpy as np


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def embed_inputs(archive, noise, orbits):
    with h5py.File(archive, "a") as h:
        g = h.require_group("inputs")
        for name, path in [("noise", noise), ("orbits", orbits)]:
            if name in g:
                raise ValueError(f"Input already embedded: {name}")
            path = Path(path)
            checksum = file_hash(path)
            if name == "orbits" and checksum != h["model"].attrs["orbit_sha256"]:
                raise ValueError("Orbit input differs from simulation provenance")
            ds = g.create_dataset(
                name,
                shape=(path.stat().st_size,),
                dtype="u1",
                chunks=(min(path.stat().st_size, 1024**2),),
                compression="lzf",
            )
            with path.open("rb") as f:
                offset = 0
                for block in iter(lambda: f.read(8 * 1024**2), b""):
                    ds[offset : offset + len(block)] = np.frombuffer(block, dtype="u1")
                    offset += len(block)
            ds.attrs.update(
                sha256=checksum,
                original_filename=path.name,
                encoding="original HDF5 file bytes",
            )
        h.attrs["input_bundle_version"] = 1


def extract_input(archive, name):
    if name not in {"noise", "orbits"}:
        raise ValueError(name)
    with h5py.File(archive, "r") as h:
        if "inputs/" + name not in h:
            raise ValueError(f"{archive} has no embedded {name} input")
        ds = h["inputs/" + name]
        expected = ds.attrs["sha256"]
        cache = Path(archive).resolve().parent / ".cache/inputs" / expected
        cache.mkdir(parents=True, exist_ok=True)
        path = cache / ("tdi.h5" if name == "noise" else "orbits.h5")
        if path.exists() and file_hash(path) == expected:
            return path
        fd, tmp = tempfile.mkstemp(prefix=".extract-", dir=cache)
        try:
            digest = hashlib.sha256()
            with os.fdopen(fd, "wb") as f:
                for start in range(0, len(ds), 8 * 1024**2):
                    block = ds[start : start + 8 * 1024**2].tobytes()
                    f.write(block)
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise ValueError(f"Corrupt embedded {name}")
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return path
