# Equation-to-code map

Use these semantic entry points when adding code links near manuscript
equations. Line numbers should be generated from the final release commit.

| Manuscript label | Implementation |
| --- | --- |
| `eq:karnesis_foreground` | [`galactic.log_galactic_psd`](../src/lisa_psd_analysis/galactic.py), and its JAX counterpart |
| `eq:lisa_aet_matrix` | [`lisa_aet.XYZ_TO_AET`](../src/lisa_psd_analysis/lisa_aet.py) |
| `eq:lisa_gap_guard` | [`preparation.good_time_bins`](../src/lisa_psd_analysis/preparation.py) |
| `eq:h_agn` | [`fitting.fit_surface`](../src/lisa_psd_analysis/fitting.py), selecting tensor structure |
| `eq:lisa_reference_definition` | [`preparation.projected_analytic_channel_noise_components_psd`](../src/lisa_psd_analysis/preparation.py) |
| `eq:h_orb`, `eq:lisa_residual_decomposition` | [`fitting.fit_surface`](../src/lisa_psd_analysis/fitting.py), selecting ANOVA structure |
| `eq:h_para_amplitude`, `eq:h_para_total` | [`models.parametric_spectrum`](../src/lisa_psd_analysis/models.py) |
| WDM response projection | [`wdm_projection.wdm_frequency_projection_grid`](../src/lisa_psd_analysis/wdm_projection.py) |
| Parameter-dependent foreground pooling | [`parametric_response.projected_response_weights`](../src/lisa_psd_analysis/parametric_response.py) |

Generic mathematics lives in the separately released LogPSplinePSD library:

| Manuscript label | Library module and function |
| --- | --- |
| `eq:whittle`, `eq:h_orb_likelihood` | `log_psplines.likelihoods.whittle.power_whittle_log_likelihood` |
| `eq:h_orb_scaled_power` | `log_psplines.inference.power.fit_power` |
| `eq:h_orb_stationary_prior`, `eq:h_orb_interaction_prior` | `log_psplines.inference.anova_power.prepare_anova_power_model` |
| Centered time interaction | `log_psplines.models.anova.centered_time_basis` |

The symbolic labels come from the manuscript and support future links. They
do not imply that every result table or figure has been reproduced by this release.
