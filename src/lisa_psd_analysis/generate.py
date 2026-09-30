"""Create a self-contained XYZ dataset from instrument noise and orbits."""

from pathlib import Path

from .dataset_bundle import embed_inputs, extract_input


def generate_dataset(
    output: Path,
    *,
    source: Path | None = None,
    noise: Path | None = None,
    orbits: Path | None = None,
) -> Path:
    """Combine a correlated foreground with supplied noise and embed both inputs."""
    from .generation import build_dataset

    if source is not None and (noise is not None or orbits is not None):
        raise ValueError("choose a source bundle or explicit noise and orbit files")
    if source is None and (noise is None or orbits is None):
        raise ValueError("provide --source, or both --noise and --orbits")
    if output.exists():
        raise FileExistsError(output)
    if source is not None:
        noise = extract_input(source, "noise")
        orbits = extract_input(source, "orbits")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".building.h5")
    if temporary.exists():
        raise FileExistsError(temporary)
    build_dataset(temporary, noise_path=noise, orbit_path=orbits)
    embed_inputs(temporary, noise, orbits)
    # An exclusive link avoids overwriting an output created during generation.
    output.hardlink_to(temporary)
    temporary.unlink()
    return output
