"""Regenerate reconstruction panels and export their data from saved posteriors."""

import csv
import json
from pathlib import Path

import numpy as np
from log_psplines import PSDResult
from log_psplines.plotting.results import plot_posterior_spectrum

from .dataset_bundle import file_hash


def make_figures(results: Path, output: Path) -> Path:
    """Render saved reconstructions; never resample or recompute inference."""
    results, output = Path(results), Path(output)
    receipts = sorted(results.rglob("run.json"))
    if not receipts:
        raise ValueError(f"No run.json receipts found beneath {results}")
    if output.exists():
        raise FileExistsError(f"Choose a new figure directory: {output}")
    runs = []
    for receipt in receipts:
        run = json.loads(receipt.read_text())
        if run.get("status") != "complete":
            raise ValueError(f"Incomplete run: {receipt}")
        for label in run["analyses"]:
            path = receipt.parent / label / "inference_data.nc"
            if not path.is_file():
                raise FileNotFoundError(f"Missing saved posterior: {path}")
            identifier = (
                (receipt.parent.relative_to(results) / label)
                .as_posix()
                .replace("/", "__")
            )
            runs.append((identifier, path, run["analyses"][label]))
    if not runs or len({r[0] for r in runs}) != len(runs):
        raise ValueError("No analyses or duplicate figure identifiers")
    output.mkdir(parents=True)
    data_dir = output / "figure_data"
    data_dir.mkdir()
    metadata = {}
    with (data_dir / "heldout_metrics.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("analysis", "cells", "mean_absolute_log_error", "coverage_90"),
        )
        writer.writeheader()
        for identifier, path, metrics in runs:
            result = PSDResult.from_netcdf(path)
            # Older scalar results used the generic channel name "0".
            label = result.metadata.get("analysis", "")
            if result.spectrum.sizes["channel"] == 1 and label.endswith(("_A", "_E")):
                result.spectrum = result.spectrum.assign_coords(
                    channel=[label.rsplit("_", 1)[1]]
                )
            panel = output / f"reconstruction_{identifier}"
            panel.mkdir()
            plot_posterior_spectrum(result, panel, true_psd=result.truth)
            np.savez(
                data_dir / f"reconstruction_{identifier}.npz",
                time=result.time,
                frequency=result.frequency,
                quantiles=result.quantiles().values,
                truth=np.asarray(result.truth)
                if result.truth is not None
                else np.array([]),
            )
            writer.writerow({"analysis": identifier, **metrics["heldout"]})
            metadata[identifier] = {
                "source": str(path),
                "sha256": file_hash(path),
                "panel": str(panel.relative_to(output) / "posterior_spectrum.png"),
                "manuscript_reference": "Reconstruction panel; final figure numbering pending",
            }
    (output / "figures.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return output
