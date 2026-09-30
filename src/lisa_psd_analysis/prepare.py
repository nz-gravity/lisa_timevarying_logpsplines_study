"""Prepare WDM powers, masks and response operators for LISA inference."""

from __future__ import annotations

import hashlib
import json
import tempfile
from importlib.metadata import version
from pathlib import Path

import h5py
import numpy as np
from log_psplines import (
    PowerData,
    PowerPartition,
    TimeSeries,
    coarse_grain_power,
    select_power_partition,
)
from log_psplines.preprocessing.wdm import wdm_periodogram

from .galactic import GalacticParameters
from .lisa_aet import (
    AET_CHANNELS,
    xyz_covariance_to_aet_diagonal,
    xyz_to_aet_series,
)
from .parametric_response import (
    projected_response_weights,
    projected_spectral_surface,
)
from .preparation import (
    analysis_row_split,
    gate_gaps,
    good_time_bins,
    load_gap_schedule,
    partition_starts,
    projected_analytic_channel_noise_components_psd,
    training_data_pilot_log_psd,
    wdm_valid_length,
)


def pooled_mean(values, time, frequency, partition):
    pooled = coarse_grain_power(
        PowerData(values, 1, frequency, time, channels=AET_CHANNELS), partition
    )
    return pooled.power / pooled.counts


def prepare(archive: Path, output: Path, *, profile="smoke", mode="continuous"):
    """Transform XYZ data into a portable analysis bundle."""
    archive, output = Path(archive), Path(output)
    if profile not in ("smoke", "paper") or mode not in ("continuous", "gapped"):
        raise ValueError("unknown preparation profile or observation mode")
    if output.exists():
        raise FileExistsError(output)
    nt = 32 if profile == "smoke" else 2048
    with h5py.File(archive) as h:
        if h["model"].attrs["gb_model"] != "karnesis2021_eq6_v1":
            raise ValueError(
                "requires an XYZ dataset with the Karnesis foreground response"
            )
        dt, t0 = float(h.attrs["dt_seconds"]), float(h.attrs["t0_tcb"])
        n = wdm_valid_length(
            8192 if profile == "smoke" else int(h.attrs["n_samples"]), nt
        )
        xyz = h["tdi/total"][:, :n]
        data_hash = hashlib.sha256(xyz.tobytes()).hexdigest()
        response = np.moveaxis(
            xyz_covariance_to_aet_diagonal(h["model/galactic_response_csd"][()]),
            -1,
            0,
        )
        source_time, source_frequency = (
            h["model/time_tcb"][()],
            h["model/frequency_hz"][()],
        )
        injection = GalacticParameters(
            **json.loads(h["model"].attrs["gb_parameters_json"])
        )
        injection_scale = float(h.attrs.get("galactic_amplitude_scale", 1.0))
        orbit_bytes = h["inputs/orbits"][()].tobytes()
        orbit_hash = hashlib.sha256(orbit_bytes).hexdigest()
        if orbit_hash != h["model"].attrs["orbit_sha256"]:
            raise ValueError("orbit checksum differs from the data-generation receipt")
    duration = n * dt
    config = Path(__file__).parent / "config"
    gap_file = config / "paper_gap_schedule.json"
    gap_hash = hashlib.sha256(gap_file.read_bytes()).hexdigest()
    if profile == "paper" and mode == "gapped":
        contract = json.loads((config / "contract.json").read_text())
        if gap_hash != contract["gap_schedule_sha256"]:
            raise ValueError("paper gap schedule checksum differs from its contract")
    gaps = []
    if mode == "gapped":
        gaps = (
            [(0.45 * duration, 0.47 * duration)]
            if profile == "smoke"
            else load_gap_schedule(config / "paper_gap_schedule.json", duration)
        )
    taper = min(3600.0, duration / 100) if profile == "smoke" else 3600.0
    nf = n // nt
    df = 1 / (2 * nf * dt)
    trim_low = max(1, int(np.ceil(1e-4 / df)))
    trim_high = max(1, int(nf - np.floor(0.1 / df)))
    channels = xyz_to_aet_series(xyz)
    del xyz
    powers = []
    for series in channels:
        if gaps:
            series = gate_gaps(series, dt, gaps, taper_s=taper)
        wdm = wdm_periodogram(
            TimeSeries(series, t=np.arange(n) * dt),
            nt=nt,
            trim_low=trim_low,
            trim_high=trim_high,
        )
        powers.append(wdm.power * (2 * dt / n))
    power = np.stack(powers, axis=-1)
    time, frequency = wdm.time, wdm.frequency
    absolute_time = t0 + time * duration
    good = good_time_bins(
        time,
        duration,
        gaps,
        nt,
        taper_s=taper,
        buffer_pixels=4,
        edge_buffer_pixels=4,
    )
    training, validation, test = analysis_row_split(len(time))
    ts = partition_starts(len(time), 4, good, validation, test)
    train = good & training
    fit_mask = np.broadcast_to(train[:, None], power.shape[:2])
    if not train.any():
        raise ValueError("no retained training rows")
    tm, oms, galaxy = [], [], []
    with tempfile.TemporaryDirectory() as temp:
        orbit = Path(temp) / "orbits.h5"
        orbit.write_bytes(orbit_bytes)
        for c, channel in enumerate(AET_CHANNELS):
            print(
                f"Projecting {channel} reference on {power.shape[:2]}",
                flush=True,
            )
            o, m = projected_analytic_channel_noise_components_psd(
                channel,
                orbit,
                absolute_time,
                frequency,
                df,
                projection_nodes=16,
            )
            oms.append(o)
            tm.append(m)
            galaxy.append(
                injection_scale
                * projected_spectral_surface(
                    response[c],
                    source_time,
                    source_frequency,
                    absolute_time,
                    frequency,
                    df,
                    injection,
                )
            )
    tm, oms, galaxy = (np.stack(value, axis=-1) for value in (tm, oms, galaxy))
    pilots = [
        training_data_pilot_log_psd(np.sqrt(power[..., c]), fit_mask) for c in range(3)
    ]
    frequency_starts = [
        select_power_partition(
            pilot, time, time_bin=4, max_frequency_bin=24, max_log_range=0.25
        ).frequency_starts
        for pilot in pilots
    ]
    para_starts = select_power_partition(
        np.concatenate(pilots),
        time,
        time_bin=4,
        max_frequency_bin=24,
        max_log_range=0.25,
    ).frequency_starts
    partition = PowerPartition(ts, para_starts)
    para_data = coarse_grain_power(
        PowerData(power, 1, frequency, time, units="Hz^2/Hz", channels=AET_CHANNELS),
        partition,
    )
    nodes, weights = projected_response_weights(
        response,
        source_time,
        source_frequency,
        absolute_time,
        frequency,
        df,
        para_starts,
        ts,
        projection_nodes=16,
        spectral_nodes=16,
    )
    # Every time block is split at train/validation/test/gap boundaries.
    para_mask = np.broadcast_to(train[ts, None, None], para_data.power.shape).copy()
    para_mask[:, :, 2] &= para_data.frequency[None, :] >= 0.003
    output.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(output, "x") as h:
        h.attrs.update(
            schema=1,
            preparation_dependencies=json.dumps(
                {
                    name: version(name)
                    for name in (
                        "backgrounds",
                        "lisaorbits",
                        "astropy",
                        "wdm-transform",
                        "jax",
                        "numpy",
                    )
                }
            ),
            gap_schedule_sha256=gap_hash
            if profile == "paper" and mode == "gapped"
            else "none_or_smoke",
            injection_scale=injection_scale,
            profile=profile,
            mode=mode,
            source_archive=str(archive.resolve()),
            tdi_total_sha256=data_hash,
            orbit_sha256=orbit_hash,
            nt=nt,
            n_samples=n,
            dt_seconds=dt,
            wdm_power_to_psd=2 * dt / n,
            projection_nodes=16,
            spectral_nodes=16,
            injection_json=json.dumps(injection.to_dict()),
        )

        def put(name, values):
            h.create_dataset(name, data=values, compression="gzip")

        for name, values in dict(
            time=time,
            frequency=frequency,
            power=power,
            tm=tm,
            oms=oms,
            truth=tm + oms + galaxy,
            training=train,
            validation=good & validation,
            test=good & test,
            good=good,
            time_starts=ts,
        ).items():
            put("native/" + name, values)
        for c in range(2):
            put(
                f"native/frequency_starts_{AET_CHANNELS[c]}",
                frequency_starts[c],
            )
        for name, values in dict(
            time=para_data.time,
            frequency=para_data.frequency,
            power=np.where(para_mask, para_data.power, 0),
            counts=np.where(para_mask, para_data.counts, 0),
            tm=pooled_mean(tm, time, frequency, partition),
            oms=pooled_mean(oms, time, frequency, partition),
            truth=pooled_mean(tm + oms + galaxy, time, frequency, partition),
            frequency_nodes=nodes,
            response_weights=np.moveaxis(weights, 0, 2),
            frequency_starts=para_starts,
            time_starts=ts,
            test=(good & test)[ts],
        ).items():
            put("para/" + name, values)
    return output
