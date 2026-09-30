"""External LISA forward spectrum and paper prior specification; no sampler."""

import jax.numpy as jnp
import numpy as np
from log_psplines import ParametricSpectrum
from numpyro import distributions as dist

from .galactic import log_galactic_psd_jax, simulation_parameters

PARAMETER_NAMES = ("amplitude", "f1_hz", "f2_hz", "f_knee_hz", "alpha")


def parametric_spectrum(tm, oms, weights, frequency_nodes):
    """Hpara: shared physical parameters, independent A/E/T power likelihoods.

    Arrays have (time, frequency, channel[, node]) shape. Priors are fixed by
    the one-year prescription, independently of truth and the realized data.
    Foreground parameters are evaluated inside the supplied response operator.
    """
    tm, oms, weights, nodes = map(jnp.asarray, (tm, oms, weights, frequency_nodes))
    centers = simulation_parameters().to_dict()
    initial = {"log_" + name: np.log(centers[name]) for name in PARAMETER_NAMES}
    priors = {
        "log_" + name: dist.Normal(initial["log_" + name], width)
        for name, width in zip(PARAMETER_NAMES, (1.0, 0.5, 0.5, 0.5, 0.35), strict=True)
    }
    for name in ("log_tm_scale", "log_oms_scale"):
        initial[name] = 0.0
        priors[name] = dist.Normal(0.0, 0.5)

    def spectrum(parameters, section):
        foreground = jnp.exp(
            log_galactic_psd_jax(
                nodes[section],
                *(parameters["log_" + name] for name in PARAMETER_NAMES),
            )
        )
        galaxy = jnp.einsum("tfcq,fq->tfc", weights[:, section], foreground)
        noise = (
            jnp.exp(parameters["log_tm_scale"]) * tm[:, section]
            + jnp.exp(parameters["log_oms_scale"]) * oms[:, section]
        )
        return noise + galaxy

    return ParametricSpectrum(spectrum, priors, initial)
