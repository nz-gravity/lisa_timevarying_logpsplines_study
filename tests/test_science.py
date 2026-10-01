"""Numerical contracts for the LISA response and power model."""

import jax.numpy as jnp
import numpy as np
from log_psplines import PowerData
from log_psplines.inference.parametric_power import prepare_parametric_power_model
from numpyro import distributions as dist
from numpyro.infer.util import log_density

from lisa_psd_analysis._preparation import analysis_row_split, partition_starts
from lisa_psd_analysis.galactic import (
    galactic_psd,
    log_galactic_psd_jax,
    simulation_parameters,
)
from lisa_psd_analysis.lisa_aet import XYZ_TO_AET, xyz_covariance_to_aet_diagonal
from lisa_psd_analysis.models import parametric_spectrum
from lisa_psd_analysis.wdm_projection import wdm_frequency_projection_grid


def test_foreground_formula_and_differentiable_version():
    p = simulation_parameters()
    f = np.geomspace(1e-4, 0.03, 40)
    expected = (
        p.amplitude
        * f ** (-7 / 3)
        * np.exp(-((f / p.f1_hz) ** p.alpha))
        * 0.5
        * (1 + np.tanh((p.f_knee_hz - f) / p.f2_hz))
    )
    np.testing.assert_allclose(galactic_psd(f, p), expected, atol=1e-50)
    actual = np.exp(
        log_galactic_psd_jax(jnp.asarray(f), *np.log(list(p.to_dict().values())))
    )
    np.testing.assert_allclose(actual, galactic_psd(f, p), rtol=1e-12, atol=0)


def test_covariance_rotation_preserves_null_channel():
    covariance = np.eye(3) - np.ones((3, 3)) / 3
    expected = np.diag(XYZ_TO_AET @ covariance @ XYZ_TO_AET.T)
    np.testing.assert_allclose(
        xyz_covariance_to_aet_diagonal(covariance), expected, atol=1e-15
    )
    assert abs(expected[2]) < 1e-15
    assert min(expected[:2]) > 0.99


def test_projection_and_splits():
    frequency, weights = wdm_frequency_projection_grid(
        np.array([0.01, 0.02]), 0.001, n_nodes=16
    )
    assert frequency.shape == (2, 16)
    np.testing.assert_allclose(weights.sum(), 1.0)
    training, validation, test = analysis_row_split(60)
    assert not np.any(training & (validation | test))
    starts = partition_starts(60, 4, training, validation, test)
    for lo, hi in zip(starts, np.r_[starts[1:], 60], strict=True):
        for state in (training, validation, test):
            assert np.all(state[lo:hi] == state[lo])


def test_seven_parameter_joint_density():
    shape = (2, 4, 3)
    tm, oms = np.ones(shape) * 2, np.ones(shape) * 3
    weights = np.ones((*shape, 3)) * 1e40
    nodes = np.geomspace(0.0002, 0.01, 12).reshape(4, 3)
    model = parametric_spectrum(tm, oms, weights, nodes)
    counts = np.ones(shape)
    counts[0, 0, 2] = 0
    powers = counts * 4
    data = PowerData(
        powers, counts, np.arange(1.0, 5.0), np.arange(2.0), channels=("A", "E", "T")
    )
    parameters = {name: value + 0.1 for name, value in model.initial_values.items()}
    foreground = np.exp(
        log_galactic_psd_jax(
            nodes,
            *(
                parameters["log_" + name]
                for name in ("amplitude", "f1_hz", "f2_hz", "f_knee_hz", "alpha")
            ),
        )
    )
    variance = np.exp(0.1) * (tm + oms) + np.einsum("tfcq,fq->tfc", weights, foreground)
    widths = (1.0, 0.5, 0.5, 0.5, 0.35, 0.5, 0.5)
    priors = sum(
        float(dist.Normal(model.initial_values[k], w).log_prob(parameters[k]))
        for k, w in zip(parameters, widths, strict=True)
    )
    expected = -0.5 * np.sum(counts * np.log(variance) + powers / variance) + priors
    actual, _ = log_density(
        prepare_parametric_power_model(data, model), (), {}, parameters
    )
    np.testing.assert_allclose(actual, expected, rtol=1e-12)
