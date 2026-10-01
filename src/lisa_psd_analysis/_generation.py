"""Generate correlated XYZ foregrounds and combine them with instrument noise."""

import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
from backgrounds import StochasticBackgroundResponse, signal, tdi
from backgrounds import noise as background_noise
from lisaorbits import InterpolatedOrbits
from scipy.signal import resample_poly

from .galactic import galactic_psd, simulation_parameters
from .galactic_synthesis import spectral_covariance_evaluator
from .orbits import load_orbits

CHANNELS = ("X2", "Y2", "Z2")
SECONDS_PER_YEAR = 365.25 * 24 * 3600
CARRIER_FREQUENCY_HZ = 281_600_000_000_000.0
TARGET_DT = 2.0
FREQ_MIN_HZ = 1.0e-4
FREQ_MAX_HZ = 1.0e-1
N_TRUTH_FREQUENCIES = 256
GALACTIC_MAP_NSIDE = 8
GALACTIC_MAP_RADIAL_POINTS = 400
GALACTIC_AMPLITUDE_SCALE = 1.0
GB_PRESET = "mean_snr7"
GB_SUBTRACTION_YEARS = 1.0
GB_PARAMETERS = simulation_parameters(GB_SUBTRACTION_YEARS, GB_PRESET)
SYNTHESIS_LENGTH = 2**19  # 12.1 d at 2 s
SYNTHESIS_HOP = SYNTHESIS_LENGTH // 2
SEED = 20260805


def galactic_sky_map(
    nside: int, radial_points: int
) -> tuple[np.ndarray, signal.Galaxy]:
    """An anisotropic Milky-Way amplitude map and its one-year strain PSD."""
    galaxy = signal.Galaxy(nside=nside, tobs_yrs=1.0)
    power = galaxy.compute_map(
        n_points=radial_points, lmin=1.0e-3, lmax=20.0, xsun=-8.1, coord="C"
    )
    if not np.all(np.isfinite(power)) or np.any(power < 0):
        raise RuntimeError("Galactic sky map is not a finite non-negative power map.")
    return np.sqrt(power / power.sum()), galaxy


def covariance_to_time_frequency(covariance: np.ndarray) -> np.ndarray:
    """Reorder a ``(frequency, time, 3, 3)`` covariance to ``(time, frequency, 3, 3)``.

    The XYZ channel pair occupies the trailing two axes.
    """
    return np.moveaxis(np.asarray(covariance), 0, 1)


def component_truth(
    orbits: InterpolatedOrbits,
    time_tcb: np.ndarray,
    frequency_hz: np.ndarray,
    *,
    return_kernel=False,
):
    """Compute ESA-orbit XYZ noise and Galactic covariance surfaces in physical Hz^2/Hz.

    Both components are returned as full Hermitian ``(time, frequency, 3, 3)``
    XYZ covariances.  The off-diagonal cross spectra are physical: they are what
    makes the TDI ``T`` channel a null channel after the A/E/T rotation, so
    discarding them here would make any A/E/T result meaningless.
    """
    sky_map, galaxy = galactic_sky_map(GALACTIC_MAP_NSIDE, GALACTIC_MAP_RADIAL_POINTS)

    # Nominal instrument amplitudes and sampled-noise convention.
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
    # backgrounds returns fractional-frequency PSDs. TDI samples are in Hz,
    # so convert *both* components to Hz^2 / Hz before combining or synthesizing.
    s_noise = (
        covariance_to_time_frequency(
            oms.compute_covariances(0.0) + test_mass.compute_covariances(0.0)
        )
        * CARRIER_FREQUENCY_HZ**2
    )

    response = StochasticBackgroundResponse(sky_map, orbits=orbits)
    galactic_kernel = response.compute_tdi_kernel(
        frequency_hz, time_tcb, tdi_var="xyz", gen="2.0"
    )
    s_galactic = (
        covariance_to_time_frequency(galactic_kernel)
        * galactic_psd(frequency_hz, GB_PARAMETERS)[None, :, None, None]
        * CARRIER_FREQUENCY_HZ**2
    )

    if not (np.all(np.isfinite(s_noise)) and np.all(np.isfinite(s_galactic))):
        raise RuntimeError(
            "Non-finite component truth PSD. Confirm JAX float64 is enabled."
        )
    if return_kernel:
        return (
            s_noise,
            s_galactic,
            covariance_to_time_frequency(galactic_kernel) * CARRIER_FREQUENCY_HZ**2,
        )
    return s_noise, s_galactic


def draw_correlated_series(
    covariance: np.ndarray, dt_seconds: float, rng: np.random.Generator
) -> np.ndarray:
    """Draw three real series under S_ab(f_k) = 2 dt <rfft(x)_a rfft(x)_b^*>_k / n.

    The Cholesky factor preserves the XYZ cross spectra.
    """
    n_frequency = covariance.shape[0]
    n = 2 * (n_frequency - 1)
    spectrum = np.zeros((len(CHANNELS), n_frequency), dtype=complex)
    power = np.real(np.einsum("fcc->f", covariance))
    band = power > 0.0
    if not np.any(band):
        raise RuntimeError("Synthesis segment has no in-band power.")
    # Rank-deficient bins are legitimate (a fully correlated response), so the
    # factorization is regularized rather than assumed strictly positive.
    jitter = 1.0e-12 * power[band][:, None, None] * np.eye(len(CHANNELS))
    factor = np.linalg.cholesky(covariance[band] + jitter)
    white = rng.standard_normal(
        (int(band.sum()), len(CHANNELS))
    ) + 1j * rng.standard_normal((int(band.sum()), len(CHANNELS)))
    spectrum[:, band] = np.einsum("fab,fb->af", factor, white, optimize=True) * np.sqrt(
        n / (4.0 * dt_seconds)
    )
    for index in (0, n_frequency - 1):  # DC and Nyquist coefficients are real.
        if band[index]:
            spectrum[:, index] = np.sqrt(2.0) * np.real(spectrum[:, index])
    return np.fft.irfft(spectrum, n=n, axis=-1)


def synthesize_galactic_component(
    interpolators, start_tcb: float, n_samples: int, dt_seconds: float, rng
):
    """Segment-by-segment ESA Galactic realization with overlap-add."""
    if n_samples % SYNTHESIS_HOP:
        raise ValueError("n_samples must be a multiple of SYNTHESIS_HOP.")
    frequency = np.fft.rfftfreq(SYNTHESIS_LENGTH, dt_seconds)
    window = np.sin(np.pi * (np.arange(SYNTHESIS_LENGTH) + 0.5) / SYNTHESIS_LENGTH)
    padded = np.zeros((len(CHANNELS), n_samples + 2 * SYNTHESIS_HOP))
    n_segments = n_samples // SYNTHESIS_HOP + 1
    for index in range(n_segments):
        covariance = interpolators(
            start_tcb + index * SYNTHESIS_HOP * dt_seconds,
            frequency,
        )
        padded[:, index * SYNTHESIS_HOP : index * SYNTHESIS_HOP + SYNTHESIS_LENGTH] += (
            window[None, :] * draw_correlated_series(covariance, dt_seconds, rng)
        )
    return padded[:, SYNTHESIS_HOP : SYNTHESIS_HOP + n_samples]


def load_instrument_noise(path: Path) -> tuple[np.ndarray, float, float]:
    """Read X2/Y2/Z2 noise samples and resample to the analysis cadence."""
    with h5py.File(path, "r") as hdf:
        native_dt = float(hdf.attrs["dt"])
        t0 = float(hdf.attrs["t0"])
        factor = int(round(TARGET_DT / native_dt))
        if not np.isclose(native_dt * factor, TARGET_DT):
            raise ValueError(
                f"Cannot map native dt={native_dt} to TARGET_DT={TARGET_DT}."
            )
        data = np.stack(
            [
                hdf[channel][:]
                if factor == 1
                else resample_poly(hdf[channel][:], up=1, down=factor)
                for channel in CHANNELS
            ]
        )
    return data, t0, native_dt


def build_dataset(output_path: Path, *, noise_path: Path, orbit_path: Path) -> dict:
    """Write XYZ data, component spectra and the deterministic response."""
    if output_path.exists():
        raise FileExistsError(output_path)
    orbits = load_orbits(orbit_path)
    noise_series, data_t0, native_dt = load_instrument_noise(noise_path)
    n_samples = (noise_series.shape[1] // SYNTHESIS_HOP) * SYNTHESIS_HOP
    if n_samples < SYNTHESIS_HOP:
        raise ValueError(
            f"Instrument noise requires at least {SYNTHESIS_HOP} samples at {TARGET_DT} s cadence"
        )
    noise_series = noise_series[:, :n_samples]

    truth_time_tcb = (
        data_t0 + np.arange(n_samples // SYNTHESIS_HOP + 1) * SYNTHESIS_HOP * TARGET_DT
    )
    with h5py.File(orbit_path, "r") as orbit_file:
        orbit_t0 = float(orbit_file.attrs["t0"])
        orbit_end = orbit_t0 + float(orbit_file.attrs["dt"]) * (
            int(orbit_file.attrs["size"]) - 1
        )
    if truth_time_tcb[0] < orbit_t0 or truth_time_tcb[-1] > orbit_end:
        raise RuntimeError("Requested data span is outside the ESA orbit coverage.")
    truth_frequency_hz = np.geomspace(FREQ_MIN_HZ, FREQ_MAX_HZ, N_TRUTH_FREQUENCIES)

    noise_covariance, galactic_template_covariance, galactic_response_csd = (
        component_truth(orbits, truth_time_tcb, truth_frequency_hz, return_kernel=True)
    )
    # These are external model inputs for component inference, not fitted
    # realization truth: analytic TDI noise and an orbit/sky-response
    # Galactic template at unit amplitude.  The inference fits its amplitude.
    galactic_covariance = GALACTIC_AMPLITUDE_SCALE * galactic_template_covariance
    total_covariance = noise_covariance + galactic_covariance

    rng = np.random.default_rng(SEED)
    galactic_series = synthesize_galactic_component(
        spectral_covariance_evaluator(
            truth_time_tcb,
            truth_frequency_hz,
            galactic_response_csd,
            GB_PARAMETERS,
            GALACTIC_AMPLITUDE_SCALE,
        ),
        data_t0,
        n_samples,
        TARGET_DT,
        rng,
    )
    total_series = noise_series + galactic_series

    def to_channel_time_frequency(covariance: np.ndarray) -> np.ndarray:
        """(time, frequency, 3, 3) -> (channel, time, frequency) auto-PSDs."""
        return np.moveaxis(np.real(np.einsum("tfcc->tfc", covariance)), 2, 0)

    noise_psd = to_channel_time_frequency(noise_covariance)
    galactic_template_psd = to_channel_time_frequency(galactic_template_covariance)
    galactic_psd = to_channel_time_frequency(galactic_covariance)
    total_psd = to_channel_time_frequency(total_covariance)

    with h5py.File(output_path, "x") as hdf:
        hdf.attrs.update(
            {
                "random_seed": SEED,
                "synthesis_length": SYNTHESIS_LENGTH,
                "synthesis_hop": SYNTHESIS_HOP,
                "t0_tcb": data_t0,
                "dt_seconds": TARGET_DT,
                "native_noise_dt_seconds": native_dt,
                "n_samples": n_samples,
                "channels": ",".join(CHANNELS),
                "psd_convention": "one-sided TDI PSD, Hz^2/Hz",
                "csd_convention": "one-sided Hermitian XYZ CSD matrix, (time, frequency, 3, 3), Hz^2/Hz",
                "galactic_amplitude_scale": GALACTIC_AMPLITUDE_SCALE,
                "noise_source": str(noise_path),
                "orbit_source": str(orbit_path),
            }
        )
        hdf.create_dataset(
            "time_seconds",
            data=np.arange(n_samples) * TARGET_DT,
            compression="lzf",
        )
        tdi_group = hdf.create_group("tdi")
        for name, values in {
            "noise": noise_series,
            "galactic": galactic_series,
            "total": total_series,
        }.items():
            tdi_group.create_dataset(name, data=values, compression="lzf", shuffle=True)
        model = hdf.create_group("model")
        model.attrs.update(
            {
                "description": "External response-informed component-model inputs",
                "galactic_template_reference_f_knee_hz": GB_PARAMETERS.f_knee_hz,
                "gb_model": "karnesis2021_eq6_v1",
                "response_interpolation": "linear_matrix_log_frequency_v2",
                "gb_parameters_json": json.dumps(GB_PARAMETERS.to_dict()),
                "gb_preset": GB_PRESET,
                "gb_subtraction_years": GB_SUBTRACTION_YEARS,
                "orbit_sha256": hashlib.sha256(orbit_path.read_bytes()).hexdigest(),
                "galactic_template_amplitude": 1.0,
            }
        )
        model.create_dataset("time_tcb", data=truth_time_tcb)
        model.create_dataset("frequency_hz", data=truth_frequency_hz)
        model.create_dataset(
            "noise_baseline_psd",
            data=noise_psd,
            compression="lzf",
            shuffle=True,
        )
        model.create_dataset(
            "galactic_template_psd",
            data=galactic_template_psd,
            compression="lzf",
            shuffle=True,
        )
        model.create_dataset(
            "noise_baseline_csd", data=noise_covariance, compression="lzf"
        )
        model.create_dataset(
            "galactic_template_csd",
            data=galactic_template_covariance,
            compression="lzf",
        )
        model.create_dataset(
            "galactic_response_csd",
            data=galactic_response_csd,
            compression="lzf",
        )
        truth = hdf.create_group("truth")
        truth.create_dataset("time_tcb", data=truth_time_tcb)
        truth.create_dataset("frequency_hz", data=truth_frequency_hz)
        for name, values in {
            "noise_psd": noise_psd,
            "galactic_psd": galactic_psd,
            "total_psd": total_psd,
        }.items():
            truth.create_dataset(name, data=values, compression="lzf", shuffle=True)
        # The auto-PSDs above are the diagonal of these matrices.  A/E/T truth
        # must be rotated from the full covariance, never from the diagonal:
        # the cross spectra are what makes T a (near-)null channel.
        for name, values in {
            "noise_csd": noise_covariance,
            "galactic_csd": galactic_covariance,
            "total_csd": total_covariance,
        }.items():
            truth.create_dataset(name, data=values, compression="lzf")

    return {
        "output": str(output_path),
        "shape": tuple(total_series.shape),
        "duration_days": n_samples * TARGET_DT / 86400.0,
        "truth_shape": tuple(total_psd.shape),
        "csd_shape": tuple(total_covariance.shape),
    }
