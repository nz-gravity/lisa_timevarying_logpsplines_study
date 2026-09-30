"""Input integrity, exclusive outputs and installed CLI behavior."""

import hashlib
import subprocess
import sys

import h5py
import numpy as np
import pytest

from lisa_psd_analysis.dataset_bundle import embed_inputs, extract_input, file_hash
from lisa_psd_analysis.generate import generate_dataset


def test_embedded_inputs_and_corrupt_cache(tmp_path):
    orbit = tmp_path / "orbits.h5"
    orbit.write_bytes(b"example orbit bytes")
    noise = tmp_path / "noise.h5"
    noise.write_bytes(b"example noise bytes")
    archive = tmp_path / "data.h5"
    with h5py.File(archive, "x") as h:
        h.create_group("model").attrs["orbit_sha256"] = file_hash(orbit)
    embed_inputs(archive, noise, orbit)
    cached = extract_input(archive, "noise")
    assert cached.read_bytes() == noise.read_bytes()
    cached.write_bytes(b"corruption")
    assert extract_input(archive, "noise").read_bytes() == noise.read_bytes()
    with h5py.File(archive, "a") as h:
        h["inputs/noise"].attrs["sha256"] = hashlib.sha256(b"different").hexdigest()
    with pytest.raises(ValueError, match="Corrupt"):
        extract_input(archive, "noise")


def test_generation_input_contract_and_cli(tmp_path):
    with pytest.raises(ValueError, match="provide"):
        generate_dataset(tmp_path / "dataset.h5")
    process = subprocess.run(
        [sys.executable, "-m", "lisa_psd_analysis", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "fetch-orbits" in process.stdout and "verify" in process.stdout


def test_generate_small_dataset_with_response_fixture(tmp_path, monkeypatch):
    from lisa_psd_analysis import generation

    monkeypatch.setattr(generation, "SYNTHESIS_LENGTH", 32)
    monkeypatch.setattr(generation, "SYNTHESIS_HOP", 16)
    monkeypatch.setattr(generation, "load_orbits", lambda _: None)

    def components(orbits, time, frequency, *, return_kernel):
        response = np.broadcast_to(
            np.eye(3) * 1e40, (len(time), len(frequency), 3, 3)
        ).copy()
        galaxy = (
            response
            * generation.galactic_psd(frequency, generation.GB_PARAMETERS)[
                None, :, None, None
            ]
        )
        noise = np.broadcast_to(np.eye(3) * 1e-10, response.shape).copy()
        return noise, galaxy, response

    monkeypatch.setattr(generation, "component_truth", components)
    orbit = tmp_path / "orbit.h5"
    with h5py.File(orbit, "x") as h:
        h.attrs.update(t0=0.0, dt=1000.0, size=10)
    noise = tmp_path / "noise.h5"
    with h5py.File(noise, "x") as h:
        h.attrs.update(t0=100.0, dt=2.0)
        for name in ("X2", "Y2", "Z2"):
            h[name] = np.zeros(64)
    output = generate_dataset(tmp_path / "dataset.h5", noise=noise, orbits=orbit)
    with h5py.File(output) as h:
        assert h["tdi/total"].shape == (3, 64)
        assert np.isfinite(h["tdi/total"][()]).all()
        np.testing.assert_array_equal(h["tdi/total"], h["tdi/galactic"])
        assert h["inputs/orbits"].attrs["sha256"] == file_hash(orbit)
    with pytest.raises(FileExistsError):
        generate_dataset(output, noise=noise, orbits=orbit)
