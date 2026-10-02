"""Offline data preparation and analysis workflow; no full paper inference."""

import json
import subprocess
import sys

import h5py
import numpy as np
import pytest

from lisa_psd_analysis.configuration import load_config, paper_config_dir
from lisa_psd_analysis.dataset_bundle import file_hash
from lisa_psd_analysis.generate import generate_dataset
from lisa_psd_analysis.lisa_aet import XYZ_TO_AET, xyz_to_aet_series


def cli(*arguments: str) -> str:
    process = subprocess.run(
        [sys.executable, "-m", "lisa_psd_analysis", *map(str, arguments)],
        capture_output=True,
        text=True,
        check=True,
    )
    return process.stdout


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("offline-study")
    archive, bundle, result = root / "demo.h5", root / "prepared.h5", root / "run"
    cli("generate", archive, "--demo")
    cli("prepare", archive, bundle)
    cli(
        "fit",
        bundle,
        result,
        "--models",
        "Hagn",
        "Horb",
        "Hpara",
        "--chains",
        "1",
        "--warmup",
        "4",
        "--samples",
        "4",
        "--max-tree-depth",
        "2",
    )
    checked = json.loads(cli("verify", result))
    assert checked["artifacts_valid"] and not checked["convergence_assessed"]
    return root, archive, bundle, result


def test_preparation_axes_metadata_and_determinism(smoke_run, tmp_path):
    _, archive, bundle, _ = smoke_run
    second = generate_dataset(tmp_path / "second.h5", demo=True)
    with h5py.File(archive) as original, h5py.File(second) as duplicate:
        np.testing.assert_array_equal(original["tdi/total"], duplicate["tdi/total"])
    with h5py.File(bundle) as h:
        assert h.attrs["channels"] == "A,E,T" and h.attrs["profile"] == "smoke"
        assert h.attrs["dt_seconds"] == 2.0
        nt, nf, nc = h["native/power"].shape
        assert (
            nc == 3 and nt == len(h["native/time"]) and nf == len(h["native/frequency"])
        )
        assert np.all(np.diff(h["native/time"]) > 0) and np.all(
            np.diff(h["native/frequency"]) > 0
        )
        assert np.isfinite(h["native/power"][()]).all()
        assert (h["native/truth"][()] > 0).all()
        assert h["para/power"].shape == h["para/counts"].shape
    from lisa_psd_analysis.prepare import prepare

    with pytest.raises(ValueError, match="Synthetic demo"):
        prepare(archive, tmp_path / "paper.h5", profile="paper")


def test_aet_series_round_trip():
    xyz = np.random.default_rng(42).normal(size=(3, 20))
    aet = xyz_to_aet_series(xyz)
    np.testing.assert_allclose(XYZ_TO_AET.T @ aet, xyz, atol=1e-14)
    np.testing.assert_allclose(
        np.sum(aet**2, axis=0), np.sum(xyz**2, axis=0), rtol=1e-14
    )


def test_configs_and_bad_fields(tmp_path):
    directory = paper_config_dir()
    assert load_config(directory / "dataset.json", "preparation")["nt"] == 2048
    for name in ("hagn", "horb", "hpara"):
        config = load_config(directory / f"{name}.json", "analysis")
        assert config["settings"]["n_samples"] == 4000
        assert config["settings"]["target_accept_prob"] == 0.99
        assert config["random_seeds"]["parametric"] == 20260906
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema": 1, "kind": "analysis", "profile": "paper"}')
    with pytest.raises(ValueError, match="fields"):
        load_config(bad, "analysis")
    contract = json.loads((directory / "contract.json").read_text())
    assert (
        file_hash(directory / "paper_gap_schedule.json")
        == contract["gap_schedule_sha256"]
    )


def test_figures_read_saved_results(smoke_run):
    root, _, _, run = smoke_run
    cli("figures", "--results", run, "--output", root / "figures")
    figures = json.loads((root / "figures/figures.json").read_text())
    assert len(figures) == 3
    for item in figures.values():
        assert (root / "figures" / item["panel"]).is_file()
    assert (root / "figures/figure_data/heldout_metrics.csv").is_file()


def test_historical_posterior_verification_without_new_cache_metadata(tmp_path):
    from lisa_psd_analysis.verification import verify_posterior_file

    path = tmp_path / "historical.nc"
    with h5py.File(path, "x") as h:
        h.attrs.update(analysis="Hagn_A", bundle_sha256="example")
        h["chain"] = [0, 1]
        h["draw"] = np.arange(4)
        h["posterior__weight"] = np.ones((2, 4, 3))
        h["sample_stats__diverging"] = np.zeros((2, 4), dtype=bool)
        h["log_likelihood__log_likelihood"] = np.zeros((2, 4))
        h["spectrum_summary__quantiles"] = np.ones((3, 2, 2, 1, 1), dtype=complex)
    assert verify_posterior_file(
        path,
        label="Hagn_A",
        bundle_sha256="example",
        settings={"n_samples": 4, "num_chains": 2},
    )["valid"]
    with h5py.File(path, "a") as h:
        h["posterior__weight"][0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="Invalid posterior array"):
        verify_posterior_file(path)
