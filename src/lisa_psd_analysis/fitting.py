"""Translate LISA inputs into generic LogPSplinePSD fits."""

import numpy as np
import xarray as xr
from log_psplines import PowerConfig, PowerData, PowerPartition, fit, mask_power

from ._preparation import robust_training_psd_scale
from .models import parametric_spectrum
from .settings import surface_config


def fit_parametric(h, settings, *, seed: int = 20260906):
    """Fit the seven shared foreground and noise parameters to A/E/T powers."""
    g = h["para"]
    data = PowerData(
        g["power"][()],
        g["counts"][()],
        g["frequency"][()],
        g["time"][()],
        units="Hz^2/Hz",
        channels=("A", "E", "T"),
    )
    model = parametric_spectrum(
        *(
            g[key][()]
            for key in (
                "tm",
                "oms",
                "response_weights",
                "frequency_nodes",
            )
        )
    )
    config = PowerConfig(**settings, seed=seed, dense_mass=True)
    result = fit(data, config, model=model, true_psd=g["truth"][()])
    return result


def fit_surface(
    h, settings, name, channel, profile, knots=None, *, seed: int | None = None
):
    """Fit a tensor surface or reference-normalized ANOVA correction."""
    g = h["native"]
    c = ("A", "E", "T").index(channel)
    power, truth = g["power"][..., c], g["truth"][..., c]
    retained = np.broadcast_to(g["training"][()][:, None], power.shape)
    scale = robust_training_psd_scale(np.sqrt(power), retained, 1.0)
    data = mask_power(
        PowerData(power / scale, 1, g["frequency"][()], g["time"][()]),
        retained,
    )
    reference = (g["tm"][..., c] + g["oms"][..., c]) / scale if name == "Horb" else None
    config = PowerConfig(
        **settings,
        **surface_config(h, name, channel, profile, knots),
        seed=seed if seed is not None else 20260812 + int(h.attrs["mode"] == "gapped"),
    )
    result = fit(
        data,
        config,
        reference=reference,
        true_psd=truth / scale,
        partition=PowerPartition(
            g["time_starts"][()],
            g[f"frequency_starts_{channel}"][()],
        ),
    )
    result.spectrum *= scale
    result.spectrum_summary *= scale
    result.truth *= scale
    if "reference" in result.model_data:
        result.model_data["reference"] *= scale
    else:
        result.model_data["reference"] = xr.DataArray(
            np.full(power.shape, scale),
            dims=("time", "frequency"),
            coords={
                "time": data.time,
                "frequency": data.frequency,
            },
        )

    result.metadata.update(data_scale=scale, units="Hz^2/Hz")
    return result
