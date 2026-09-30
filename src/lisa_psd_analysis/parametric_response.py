"""Precompute a positive response operator for the five-parameter foreground.

The spectrum is linearly interpolated in log frequency within each pooled
frequency bin. Increase spectral_nodes to check this numerical approximation.
The response, WDM quadrature and time/frequency pooling are applied first to
the interpolation basis; no parameter-dependent spectrum is evaluated at a
bin centre. Response inputs contain no injected spectral parameters.
"""

import numpy as np
from scipy.interpolate import RegularGridInterpolator

from .wdm_projection import wdm_frequency_projection_grid


def projected_spectral_surface(
    source,
    source_time,
    source_frequency,
    target_time,
    target_frequency,
    delta_f,
    parameters,
    *,
    projection_nodes=16,
):
    """Direct single-channel truth projection, without spectral interpolation."""
    from .galactic import galactic_psd

    interp = RegularGridInterpolator(
        (source_time, np.log(source_frequency)), source, bounds_error=True
    )
    grid, q = wdm_frequency_projection_grid(
        target_frequency, delta_f, n_nodes=projection_nodes
    )
    out = np.empty((len(target_time), len(target_frequency)))
    for start in range(0, len(target_frequency), 32):
        stop = min(start + 32, len(target_frequency))
        f = grid[start:stop].ravel()
        inside = (f >= source_frequency[0]) & (f <= source_frequency[-1])
        values = np.zeros((len(target_time), len(f)))
        tt, ff = np.meshgrid(target_time, np.log(f[inside]), indexing="ij")
        values[:, inside] = interp(np.stack((tt, ff), axis=-1)) * galactic_psd(
            f[inside], parameters
        )
        out[:, start:stop] = np.einsum(
            "tfq,q->tf",
            values.reshape(len(target_time), stop - start, projection_nodes),
            q,
        )
    return out


def projected_response_weights(
    source,
    source_time,
    source_frequency,
    target_time,
    target_frequency,
    delta_f,
    bin_starts,
    time_starts,
    *,
    projection_nodes=16,
    spectral_nodes=16,
):
    if spectral_nodes < 2:
        raise ValueError("spectral_nodes must be at least two")
    source = np.asarray(source)
    if source.shape != (3, len(source_time), len(source_frequency)):
        raise ValueError("response must have shape (3,time,frequency)")
    if np.any(~np.isfinite(source)) or np.any(source < 0):
        raise ValueError("response diagonal must be finite and nonnegative")
    grid, quadrature = wdm_frequency_projection_grid(
        target_frequency, delta_f, n_nodes=projection_nodes
    )
    bin_stops = np.r_[bin_starts[1:], len(target_frequency)]
    time_stops = np.r_[time_starts[1:], len(target_time)]
    weights = np.zeros((3, len(time_starts), len(bin_starts), spectral_nodes))
    nodes = np.empty((len(bin_starts), spectral_nodes))
    interpolators = [
        RegularGridInterpolator(
            (source_time, np.log(source_frequency)), c, bounds_error=True
        )
        for c in source
    ]
    for b, (start, stop) in enumerate(zip(bin_starts, bin_stops, strict=True)):
        f = grid[start:stop].reshape(-1)
        positive = f[f > 0]
        nodes[b] = np.geomspace(positive.min(), positive.max(), spectral_nodes)
        inside = (f >= source_frequency[0]) & (f <= source_frequency[-1])
        if not inside.any():
            continue
        f = f[inside]
        q = np.broadcast_to(quadrature, grid[start:stop].shape).reshape(-1)[inside] / (
            stop - start
        )
        log_nodes = np.log(nodes[b])
        log_f = np.log(f)
        left = np.clip(np.searchsorted(log_nodes, log_f) - 1, 0, spectral_nodes - 2)
        frac = (log_f - log_nodes[left]) / (log_nodes[left + 1] - log_nodes[left])
        hats = np.zeros((len(f), spectral_nodes))
        hats[np.arange(len(f)), left] = 1 - frac
        hats[np.arange(len(f)), left + 1] = frac
        hats *= q[:, None]
        tt, ff = np.meshgrid(target_time, log_f, indexing="ij")
        coords = np.stack((tt, ff), axis=-1)
        for c, interp in enumerate(interpolators):
            fine = interp(coords) @ hats
            for t, (lo, hi) in enumerate(zip(time_starts, time_stops, strict=True)):
                weights[c, t, b] = fine[lo:hi].mean(axis=0)
    return nodes, weights
