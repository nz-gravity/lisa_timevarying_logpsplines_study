# Data, orbits and generation

## Reproduce the study realization

The study input is one HDF5 file, `lisa.h5`, containing:

| Group | Contents |
| --- | --- |
| `tdi` | XYZ instrument noise, Galactic foreground and their sum |
| `model` | Nominal noise spectra, Galactic response matrices and coordinates |
| `truth` | Component and total spectra used for diagnostics |
| `inputs` | Exact instrument-noise and sampled-orbit files, with SHA-256 checksums |

Preparation reads this file without needing network access. Share it alongside
the software deposits to reproduce the same realization. It is not currently
included in the source tree or available through a published deposit URL.

## Download ESA orbits

**Orbit downloads are automatic through LISA Orbits.** The
`OEMOrbits.from_included("esa-trailing", version="1.0.0")` method downloads and
caches the OEM ephemerides from the [ESA orbit repository](https://github.com/esa/lisa-orbit-files).
LISA Instrument uses orbit information supplied to it; this case study calls
LISA Orbits directly:

```sh
uv run --locked lisa-study fetch-orbits data/orbits.h5
```

This samples the Earth-trailing CReMA 1.0 constellation at 100000-second spacing
for 632 samples. The orbit version is explicit; `--version` changes it.

The embedded study orbit file was produced with LISA Orbits 2.3. This project
pins 3.0.3 for response evaluation and new downloads. A newly written file may
have different metadata or numerical details. Use the embedded file when
reproducing the exact study input; a new download is an input for a new run.
ESA provides the OEM files under CC BY 4.0; retain their attribution in a data
deposit. See the [upstream license](https://github.com/esa/lisa-orbit-files/blob/main/LICENSE).

## Generate XYZ data

To regenerate the foreground and combine it with the same instrument noise:

```sh
uv run --locked lisa-study generate build/generated.h5 --source data/lisa.h5
```

Alternatively, supply both inputs explicitly:

```sh
uv run --locked lisa-study generate build/generated.h5 \
  --noise data/instrument-noise.h5 --orbits data/orbits.h5
```

The noise file must contain `X2`, `Y2`, `Z2` datasets and `dt`/`t0` attributes.
The orbit file must cover the full observation and contain sampled TCB positions.
Generation uses seed 20260805, a correlated XYZ foreground, and overlap-add
segments of length 2^19 with half-segment overlap. It retains full covariance
matrices before the A/E/T rotation. Outputs use one-sided `Hz^2/Hz` PSDs.

**This command does not simulate fresh instrument noise.** An orbit download
provides trajectories, not the particular instrument-noise realization. A
fully independent noise simulation would also require a specified LISA
Instrument configuration, random seed, processing and TDI construction. That
recipe is not currently part of this case study. Reproduction from the bundled
noise input is supported.

Full-duration foreground generation can be expensive. A quick demonstration
can prepare the supplied dataset directly without repeating generation.

## Offline execution fixture

`lisa-study generate build/demo.h5 --demo` creates fixed-seed Gaussian XYZ
samples with a static triangular orbit and an artificial foreground response.
It needs no downloaded or authored dataset. It is a synthetic I/O fixture,
not a physical LISA simulation; paper preparation rejects it. The real
`generate --source` and `generate --noise ... --orbits ...` paths are unchanged.
