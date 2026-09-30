"""Held-out comparisons on each fitted analysis grid."""

import numpy as np


def heldout_metrics(result, truth, rows, *, t_min_frequency=None):
    q = np.diagonal(result.quantiles().values, axis1=-2, axis2=-1).real
    if truth.ndim == 2:
        truth = truth[..., None]
    mask = np.broadcast_to(rows[:, None, None], truth.shape).copy()
    if t_min_frequency is not None:
        mask[..., 2] &= result.frequency[None, :] >= t_min_frequency
    if not mask.any():
        return {"cells": 0}
    return dict(
        cells=int(mask.sum()),
        mean_absolute_log_error=float(np.abs(np.log(q[1] / truth))[mask].mean()),
        coverage_90=float(((q[0] <= truth) & (truth <= q[2]))[mask].mean()),
    )
