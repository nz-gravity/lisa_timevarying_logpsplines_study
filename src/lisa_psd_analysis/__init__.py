"""LISA spectral analysis with LogPSplinePSD."""

import os

os.environ.setdefault("JAX_ENABLE_X64", "true")
os.environ.setdefault("MPLBACKEND", "Agg")

import jax  # noqa: E402

# Physical strain spectra require float64, including in an existing notebook.
jax.config.update("jax_enable_x64", True)
