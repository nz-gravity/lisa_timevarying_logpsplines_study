"""Noise references, data masks and training-only power summaries."""

from __future__ import annotations

import json
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lisaorbits import InterpolatedOrbits
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter

from .lisa_aet import xyz_covariance_to_aet_diagonal
from .orbits import load_orbits
from .wdm_projection import (
    collapse_wdm_frequency_projection,
    wdm_frequency_projection_grid,
)

SECONDS_PER_DAY = 86400.0
SECONDS_PER_YEAR = 365.25 * SECONDS_PER_DAY
CARRIER_FREQUENCY_HZ = 281600000000000.0
CHI_SQUARE_ONE_MEDIAN = 0.4549364231195727
XYZ_CHANNELS = ("X2", "Y2", "Z2")
AET_CHANNELS = ("A", "E", "T")
ALL_CHANNELS = XYZ_CHANNELS + AET_CHANNELS


def wdm_valid_length(n_requested: int, nt: int) -> int:
    """Largest valid WDM length no larger than ``n_requested``."""
    nf = n_requested // nt
    nf -= nf % 2
    if nt % 2 or nf < 2:
        raise ValueError("WDM requires even nt and even N / nt >= 2")
    return nt * nf


def robust_training_psd_scale(
    coefficients: np.ndarray,
    retained: np.ndarray,
    to_psd: float,
) -> float:
    """Return a truth-free numerical PSD scale from retained training cells.

    For one real Gaussian WDM coefficient, ``w**2 / S`` follows ``chi2_1``.
    Dividing the retained median power by the ``chi2_1`` median therefore gives
    a robust order-of-magnitude PSD scale. This value is only a numerical
    reparameterisation; excluded, validation, test, and gap cells cannot enter.
    """
    values = np.asarray(coefficients, dtype=float)
    mask = np.asarray(retained, dtype=bool)
    if values.shape != mask.shape:
        raise ValueError("retained mask must match coefficients")
    if not np.isfinite(to_psd) or to_psd <= 0.0:
        raise ValueError("to_psd must be finite and positive")
    selected = values[mask]
    finite = np.isfinite(selected)
    if not np.any(finite):
        raise ValueError("retained training coefficients contain no finite values")
    power_psd = selected[finite] ** 2 * to_psd
    positive = power_psd[power_psd > 0.0]
    if positive.size == 0:
        raise ValueError("retained training coefficients have no positive power")
    scale = float(np.median(positive) / CHI_SQUARE_ONE_MEDIAN)
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("could not construct a positive training-data scale")
    return scale


def _channel_diagonal(covariance: np.ndarray, channel: str) -> np.ndarray:
    """Extract a channel auto-PSD, rotating full XYZ covariances for A/E/T."""
    if channel in XYZ_CHANNELS:
        index = XYZ_CHANNELS.index(channel)
        return np.asarray(covariance[..., index, index].real)
    index = AET_CHANNELS.index(channel)
    return xyz_covariance_to_aet_diagonal(covariance)[..., index]


def _analytic_noise_components_for_frequencies(
    channel: str,
    orbits: InterpolatedOrbits,
    time_tcb: np.ndarray,
    frequency_hz: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate one bounded frequency block with a preloaded orbit model."""
    from backgrounds import noise as background_noise
    from backgrounds import tdi

    oms = background_noise.AnalyticOMSNoiseModel(
        frequency_hz,
        time_tcb,
        orbits,
        tdi_tf_func=tdi.compute_tdi_tf,
        gen="2.0",
        oms_isi_carrier_asds=7.9e-12,
        fs=0.5,
        duration=SECONDS_PER_YEAR,
    )
    test_mass = background_noise.AnalyticTMNoiseModel(
        frequency_hz,
        time_tcb,
        orbits,
        tdi_tf_func=tdi.compute_tdi_tf_tm,
        gen="2.0",
        tm_isi_carrier_asds=2.4e-15,
        fs=0.5,
        duration=SECONDS_PER_YEAR,
    )
    oms_psd = (
        _channel_diagonal(oms.compute_covariances(0.0), channel).T
        * CARRIER_FREQUENCY_HZ**2
    )
    tm_psd = (
        _channel_diagonal(test_mass.compute_covariances(0.0), channel).T
        * CARRIER_FREQUENCY_HZ**2
    )
    return oms_psd, tm_psd


def projected_analytic_channel_noise_components_psd(
    channel: str,
    orbit_path: Path,
    time_tcb: np.ndarray,
    frequency_hz: np.ndarray,
    delta_f_hz: float,
    *,
    projection_nodes: int = 16,
    frequency_chunk: int = 384,
    spectral_tilt: float = 0.0,
    pivot_hz: float = 1.0e-2,
) -> tuple[np.ndarray, np.ndarray]:
    """Project analytic OMS and TM spectra onto interior WDM cells.

    The response is evaluated inside the exact compact support of each WDM
    frequency atom and collapsed with the squared Meyer-window weights. Work
    is chunked by the total number of quadrature frequencies, bounding the
    temporary covariance tensors on year-long grids.
    """
    if channel not in ALL_CHANNELS:
        raise ValueError(f"channel must be one of {ALL_CHANNELS}, got {channel!r}")
    if frequency_chunk < projection_nodes:
        raise ValueError("frequency_chunk must be at least projection_nodes")
    if pivot_hz <= 0.0:
        raise ValueError("pivot_hz must be positive")
    time_tcb = np.asarray(time_tcb, dtype=float)
    frequency_hz = np.asarray(frequency_hz, dtype=float)
    projection_grid, weights = wdm_frequency_projection_grid(
        frequency_hz,
        delta_f_hz,
        n_nodes=projection_nodes,
    )
    orbits = load_orbits(orbit_path)
    oms_result = np.empty((time_tcb.size, frequency_hz.size), dtype=float)
    tm_result = np.empty_like(oms_result)
    centers_per_chunk = max(1, int(frequency_chunk) // int(projection_nodes))
    for start in range(0, frequency_hz.size, centers_per_chunk):
        stop = min(start + centers_per_chunk, frequency_hz.size)
        sample_frequency = projection_grid[start:stop].reshape(-1)
        oms_sample, tm_sample = _analytic_noise_components_for_frequencies(
            channel,
            orbits,
            time_tcb,
            sample_frequency,
        )
        shape = (time_tcb.size, stop - start, projection_nodes)
        if spectral_tilt != 0.0:
            multiplier = (sample_frequency / pivot_hz) ** spectral_tilt
            oms_sample *= multiplier[None, :]
            tm_sample *= multiplier[None, :]
        oms_result[:, start:stop] = collapse_wdm_frequency_projection(
            oms_sample.reshape(shape), weights
        )
        tm_result[:, start:stop] = collapse_wdm_frequency_projection(
            tm_sample.reshape(shape), weights
        )
    return oms_result, tm_result


def load_gap_schedule(path: Path, t_obs_s: float) -> list[tuple[float, float]]:
    """Read gap intervals and validate the observation duration."""
    payload = json.loads(Path(path).read_text())
    if not np.isclose(payload["duration_seconds"], t_obs_s, rtol=0, atol=1e-6):
        raise ValueError("gap schedule duration differs from the analyzed record")
    gaps = np.asarray(payload["gaps_seconds"], dtype=float)
    if gaps.ndim != 2 or gaps.shape[1] != 2 or not np.all(np.isfinite(gaps)):
        raise ValueError("gap schedule must contain finite start/stop pairs")
    if (
        np.any(gaps[:, 0] < 0)
        or np.any(gaps[:, 1] > t_obs_s)
        or np.any(gaps[:, 1] <= gaps[:, 0])
    ):
        raise ValueError("gap schedule contains invalid bounds")
    return sorted(map(tuple, gaps.tolist()))


def gate_gaps(
    data: np.ndarray,
    dt: float,
    gaps: list[tuple[float, float]],
    *,
    taper_s: float = 3600.0,
) -> np.ndarray:
    """Zero gaps with one-hour cosine tapers, without a full time array."""
    output = np.asarray(data, dtype=float).copy()
    window = np.ones(output.size, dtype=float)
    for start_s, stop_s in gaps:
        start = max(0, int(np.floor(start_s / dt)))
        stop = min(output.size, int(np.ceil(stop_s / dt)) + 1)
        window[start:stop] = 0.0
        n_taper = max(1, int(np.ceil(taper_s / dt)))
        left = max(0, start - n_taper)
        if start > left:
            u = np.arange(start - left, dtype=float) / max(start - left, 1)
            window[left:start] = np.minimum(
                window[left:start], 0.5 + 0.5 * np.cos(np.pi * u)
            )
        right = min(output.size, stop + n_taper)
        if right > stop:
            u = np.arange(1, right - stop + 1, dtype=float) / max(right - stop, 1)
            window[stop:right] = np.minimum(
                window[stop:right], 0.5 - 0.5 * np.cos(np.pi * u)
            )
    return output * window


def good_time_bins(
    time_grid: np.ndarray,
    t_obs_s: float,
    gaps: list[tuple[float, float]],
    nt: int,
    *,
    taper_s: float = 3600.0,
    buffer_pixels: float = 1.0,
    edge_buffer_pixels: float = 0.0,
) -> np.ndarray:
    """Retained rows after explicit gap/taper and record-edge guards.

    Guards reduce boundary contamination; they do not imply exact independence.
    """
    if not np.isfinite(edge_buffer_pixels) or edge_buffer_pixels < 0:
        raise ValueError("edge_buffer_pixels must be finite and nonnegative")
    if not np.isfinite(buffer_pixels) or buffer_pixels < 0:
        raise ValueError("buffer_pixels must be finite and nonnegative")
    centers = np.asarray(time_grid) * t_obs_s
    pixel = buffer_pixels * t_obs_s / nt
    keep = np.ones(centers.size, dtype=bool)
    if edge_buffer_pixels > 0:
        edge = edge_buffer_pixels * t_obs_s / nt
        keep &= (centers > edge) & (centers < t_obs_s - edge)
    for start, stop in gaps:
        keep &= (centers < start - taper_s - pixel) | (centers > stop + taper_s + pixel)
    return keep


def analysis_row_split(
    n_time: int,
    *,
    block: int = 4,
    cycle: int = 7,
    validation_fold: int = 5,
    test_fold: int = 6,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Deterministic training/validation/test blocks for prospective scoring.

    The final test fold is excluded from every fit and pilot.  The validation
    fold is available for future tuning but is also excluded from the locked
    production fit. Validation and final-test cohorts remain separate.
    """
    if cycle < 3 or not (0 <= validation_fold < cycle) or not (0 <= test_fold < cycle):
        raise ValueError("validation/test folds must be distinct members of cycle >= 3")
    if validation_fold == test_fold:
        raise ValueError("validation and test folds must differ")
    fold = (np.arange(n_time) // block) % cycle
    validation = fold == validation_fold
    test = fold == test_fold
    training = ~(validation | test)
    return training, validation, test


def training_data_pilot_log_psd(
    coefficients: np.ndarray,
    retained_training_mask: np.ndarray,
    *,
    n_time_profiles: int = 32,
    frequency_width: int = 31,
) -> np.ndarray:
    """Build a truth-free smooth pilot from retained training coefficients.

    Training rows are reduced to robust time-block medians before frequency
    smoothing. Missing response cells are interpolated only for pilot
    construction; they remain absent from the likelihood. The pilot selects
    likelihood bins but is never used as an inferential observation. Returning
    a small ``(profile, frequency)`` array also avoids a full-grid median-filter
    temporary on year-long data.
    """
    coefficients = np.asarray(coefficients, dtype=float)
    retained = np.asarray(retained_training_mask, dtype=bool)
    if coefficients.shape != retained.shape or coefficients.ndim != 2:
        raise ValueError(
            "coefficients and retained_training_mask must share a 2-D shape"
        )
    positive = coefficients[retained] ** 2
    positive = positive[positive > 0.0]
    if positive.size == 0:
        raise ValueError("pilot mask retains no positive coefficient power")
    floor = float(np.min(positive)) * 1.0e-6
    raw = np.log(np.maximum(coefficients**2, floor))
    n_profiles = max(1, min(int(n_time_profiles), coefficients.shape[0]))
    edges = np.linspace(0, coefficients.shape[0], n_profiles + 1, dtype=int)
    filled = np.full((n_profiles, coefficients.shape[1]), np.nan)
    index_frequency = np.arange(coefficients.shape[1], dtype=float)
    for profile, (start, stop) in enumerate(zip(edges[:-1], edges[1:], strict=True)):
        block = np.where(retained[start:stop], raw[start:stop], np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            row = np.nanmedian(block, axis=0)
        valid = np.isfinite(row)
        if np.any(valid):
            filled[profile] = np.interp(
                index_frequency, index_frequency[valid], row[valid]
            )
    valid_profiles = np.flatnonzero(np.isfinite(filled[:, 0]))
    if valid_profiles.size == 0:
        raise ValueError("pilot has no retained training profiles")
    for profile in range(n_profiles):
        if not np.isfinite(filled[profile, 0]):
            nearest = valid_profiles[np.argmin(np.abs(valid_profiles - profile))]
            filled[profile] = filled[nearest]
    return median_filter(
        filled,
        size=(1, max(1, int(frequency_width)) | 1),
        mode="nearest",
    )


def partition_starts(n_time: int, block: int, *states: np.ndarray) -> np.ndarray:
    """Block starts augmented at every supplied state transition."""
    starts = set(range(0, n_time, block))
    for state in states:
        state = np.asarray(state, dtype=bool)
        starts.update((np.flatnonzero(state[1:] != state[:-1]) + 1).tolist())
    return np.asarray(sorted(starts), dtype=int)
