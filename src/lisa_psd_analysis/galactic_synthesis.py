"""PSD-preserving response interpolation shared by injection and inference."""

import numpy as np
from scipy.interpolate import RegularGridInterpolator

from .galactic import galactic_psd


def spectral_covariance_evaluator(
    time, frequency, kernel, parameters, amplitude_scale=1.0
):
    """Interpolate the Hermitian response, then apply the analytic spectrum.

    Convex interpolation of PSD matrices stays PSD and commutes with XYZ/AET
    rotation. Interpolating individual log powers/correlations does neither.
    The input kernel includes the carrier-frequency unit conversion exactly once.
    """
    interp = RegularGridInterpolator(
        (time, np.log(frequency)), kernel, bounds_error=True
    )

    def evaluate(epoch, f):
        f = np.asarray(f)
        result = np.zeros((len(f), 3, 3), dtype=complex)
        inside = (f >= frequency[0]) & (f <= frequency[-1])
        selected = f[inside]
        coords = np.column_stack((np.full(len(selected), epoch), np.log(selected)))
        result[inside] = (
            interp(coords)
            * galactic_psd(selected, parameters)[:, None, None]
            * amplitude_scale
        )
        return result

    return evaluate
