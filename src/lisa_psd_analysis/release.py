"""Package selected scientific artifacts and verify a relocatable Zenodo deposit."""

import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import h5py
import numpy as np

from .configuration import load_config, paper_config_dir
from .dataset_bundle import file_hash
from .provenance import release_provenance
from .verification import verify_run

COLUMNS = (
    "path",
    "type",
    "description",
    "source",
    "manuscript_reference",
    "generated_by",
    "sha256",
)
SECTIONS = {"data", "results", "configs", "figure_data"}
CONTROL_FILES = {"README.md", "MANIFEST.csv", "provenance.json", "checksums.sha256"}


def _relative(value: str) -> Path:
    path = Path(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in ("..", ".") for part in path.parts)
    ):
        raise ValueError(f"Release paths must be relative and contained: {value}")
    return path


def package_release(output: Path, *, plan: Path) -> Path:
    """Copy only the plan's selected files, paper configs and lock; never archive a tree."""
    output, plan = Path(output).resolve(), Path(plan).resolve()
    if output.exists():
        raise FileExistsError(f"Choose a new release directory: {output}")
    specification = json.loads(plan.read_text())
    if specification.get("schema") != 1 or not specification.get("artifacts"):
        raise ValueError("Release plan requires schema=1 and a nonempty artifacts list")
    if specification.get("release_scope") not in {
        "smoke",
        "development",
        "paper_candidate",
        "paper",
    }:
        raise ValueError("Release plan requires an explicit release_scope")
    if not specification.get("random_seeds"):
        raise ValueError("Release plan must record random_seeds")
    selected = []
    for item in specification["artifacts"]:
        if set(item) != set(COLUMNS) - {"sha256"} or any(
            not isinstance(v, str) or not v.strip() for v in item.values()
        ):
            raise ValueError(f"Every artifact needs fields {COLUMNS[:-1]}")
        destination = _relative(item["path"])
        if destination.parts[0] not in SECTIONS or len(destination.parts) < 2:
            raise ValueError(
                f"Artifact must be within {sorted(SECTIONS)}: {destination}"
            )
        source = plan.parent / item["source"]
        if not source.is_file() or source.is_symlink():
            raise ValueError(
                f"Select an existing regular file, not a directory/symlink: {source}"
            )
        if output == source.resolve() or output in source.resolve().parents:
            raise ValueError("Release output cannot contain its inputs")
        selected.append((item, source))
    # Versioned paper assets are always deposited; plan-selected extras cannot replace them.
    for source in sorted(paper_config_dir().glob("*.json")):
        selected.append(
            (
                dict(
                    path=f"configs/paper/{source.name}",
                    type="configuration",
                    description=f"Frozen paper study asset: {source.name}",
                    source=str(source),
                    manuscript_reference="Paper analysis settings",
                    generated_by="version-controlled study configuration",
                ),
                source,
            )
        )
    root = Path(__file__).resolve().parents[2]
    if not (root / "uv.lock").is_file():
        root = Path.cwd()
    if (
        not (root / "uv.lock").is_file()
        or not (root / "configs/library.json").is_file()
    ):
        raise ValueError(
            "Package releases from the study checkout containing uv.lock and configs/library.json"
        )
    for source, kind, description in (
        (
            root / "configs/library.json",
            "configuration",
            "Pinned library source checkout",
        ),
        (root / "uv.lock", "dependency_lock", "Locked Python dependencies"),
        (
            root / "docs/source-attribution.json",
            "attribution",
            "Imported scientific source attribution",
        ),
    ):
        selected.append(
            (
                dict(
                    path=f"configs/{source.name}",
                    type=kind,
                    description=description,
                    source=str(source),
                    manuscript_reference="Computational supplement",
                    generated_by="version-controlled study metadata",
                ),
                source,
            )
        )
    paths = [item["path"] for item, _ in selected]
    if not any(
        Path(p).name == "run.json" and p.startswith("results/") for p in paths
    ) or not any(p.startswith("results/") and p.endswith(".nc") for p in paths):
        raise ValueError("Select completed run receipts and posterior results")
    if len(set(paths)) != len(paths):
        raise ValueError("Duplicate destinations in release plan")
    if not any(p.startswith("data/") for p in paths) or not any(
        p.startswith("results/") for p in paths
    ):
        raise ValueError(
            "Select both input data and result artifacts for a scientific release"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".release-", dir=output.parent
    ) as temporary:
        stage = Path(temporary) / "deposit"
        stage.mkdir()
        for section in SECTIONS:
            (stage / section).mkdir()
        rows = []
        for item, source in selected:
            target = stage / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            # APFS clones are independent files and avoid duplicating multi-GB deposits.
            cloned = (
                sys.platform == "darwin"
                and subprocess.run(
                    ["/bin/cp", "-c", str(source), str(target)],
                    capture_output=True,
                    check=False,
                ).returncode
                == 0
            )
            if not cloned:
                shutil.copyfile(source, target)
            rows.append({**item, "sha256": file_hash(target)})
        rows.sort(key=lambda row: row["path"])
        with (stage / "MANIFEST.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        configs = {
            row["path"]: row["sha256"] for row in rows if row["type"] == "configuration"
        }
        provenance = release_provenance(root, specification["random_seeds"], configs)
        # Preserve actual recorded seeds and run metadata, not just the plan's description.
        provenance["release_scope"] = specification["release_scope"]
        provenance["runs"] = {
            row["path"]: json.loads((stage / row["path"]).read_text())
            for row in rows
            if Path(row["path"]).name == "run.json"
        }
        (stage / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
        text = "# LISA study scientific release\n\nSelected artifacts; no inference is rerun. See MANIFEST.csv for sources,\ncommands, manuscript references and SHA256 identities.\n\nVerify after download: `lisa-study verify-release RELEASE_DIRECTORY`.\nA valid deposit establishes integrity, not posterior convergence.\n\n"
        if specification.get("readme"):
            text = (
                plan.parent / specification["readme"]
            ).read_text() + "\n\n## Artifact manifest\n\n"
        text += f"Release scope: {specification['release_scope']}.\n\n"
        text += "| Artifact | Description | Manuscript reference |\n|---|---|---|\n"
        text += "".join(
            f"| {r['path']} | {r['description']} | {r['manuscript_reference']} |\n"
            for r in rows
        )
        (stage / "README.md").write_text(text)
        files = sorted(p for p in stage.rglob("*") if p.is_file())
        (stage / "checksums.sha256").write_text(
            "".join(
                f"{file_hash(p)}  {p.relative_to(stage).as_posix()}\n" for p in files
            )
        )
        verify_release(stage)
        stage.rename(output)
    return output


def verify_release(output: Path) -> dict:
    """Check the complete inventory, config/provenance fields and open scientific files."""
    output = Path(output)
    for name in CONTROL_FILES | SECTIONS:
        if not (output / name).exists():
            raise ValueError(f"Release is missing {name}")
    if any(p.is_symlink() for p in output.rglob("*")):
        raise ValueError("Release must not contain symlinks")
    checksums = {}
    for line in (output / "checksums.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        _relative(name)
        if name in checksums or len(digest) != 64:
            raise ValueError(f"Invalid or duplicate checksum entry: {name}")
        checksums[name] = digest
        if not (output / name).is_file() or file_hash(output / name) != digest:
            raise ValueError(f"Checksum mismatch or missing file: {name}")
    actual = {
        p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()
    }
    if actual != set(checksums) | {"checksums.sha256"}:
        raise ValueError("Release inventory differs from checksums")
    with (output / "MANIFEST.csv").open(newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError("Manifest columns are incomplete")
        rows = list(reader)
    if not rows or len({r["path"] for r in rows}) != len(rows):
        raise ValueError("Manifest must contain unique artifacts")
    if actual != {r["path"] for r in rows} | CONTROL_FILES:
        raise ValueError("Manifest does not cover every deposited artifact")
    for row in rows:
        _relative(row["path"])
        if (
            any(not row.get(key) for key in COLUMNS)
            or checksums.get(row["path"]) != row["sha256"]
        ):
            raise ValueError(f"Invalid manifest metadata/checksum: {row['path']}")
        path = output / row["path"]
        if path.suffix in (".h5", ".hdf5"):
            with h5py.File(path) as handle:
                if not list(handle):
                    raise ValueError(f"Empty HDF5 artifact: {path}")
                if row["type"] == "prepared_data":
                    for key in (
                        "schema",
                        "profile",
                        "mode",
                        "tdi_total_sha256",
                        "orbit_sha256",
                    ):
                        if key not in handle.attrs:
                            raise ValueError(f"Prepared data missing {key}: {path}")
                    for key in (
                        "native/power",
                        "native/time",
                        "native/frequency",
                        "para/power",
                    ):
                        if key not in handle:
                            raise ValueError(f"Prepared data missing {key}: {path}")
        elif path.suffix == ".nc":
            with h5py.File(path) as handle:
                if (
                    "draw" not in handle
                    or not handle.attrs.get("analysis")
                    or not any(key.startswith("posterior__") for key in handle)
                ):
                    raise ValueError(f"Missing posterior metadata: {path}")
        elif path.suffix == ".npz":
            with np.load(path, allow_pickle=False) as arrays:
                if not arrays.files:
                    raise ValueError(f"Empty numerical artifact: {path}")
                for key in arrays.files:
                    arrays[key]  # Read each array to check archive integrity.
        elif path.suffix == ".json":
            json.loads(path.read_text())
    provenance = json.loads((output / "provenance.json").read_text())
    required = {
        "schema",
        "study_repository_url",
        "study",
        "logpsplinepsd",
        "python_version",
        "dependency_lock_sha256",
        "jax_version",
        "numpyro_version",
        "platform",
        "random_seeds",
        "paper_configs",
        "created_at",
        "runtime",
        "runs",
        "release_scope",
    }
    if required - provenance.keys() or any(
        not provenance.get(k) for k in required - {"runs"}
    ):
        raise ValueError("Provenance is incomplete")
    if (
        set(provenance["study"]) != {"git_sha", "dirty"}
        or not provenance["study"].get("git_sha")
        or not provenance["logpsplinepsd"].get("version")
        or "git_sha" not in provenance["logpsplinepsd"]
    ):
        raise ValueError("Source/version provenance is incomplete")
    if provenance["dependency_lock_sha256"] != checksums["configs/uv.lock"]:
        raise ValueError("Lock provenance does not match deposited lock")
    for name in ("dataset", "hagn", "horb", "hpara"):
        relative = f"configs/paper/{name}.json"
        if (
            relative not in checksums
            or provenance["paper_configs"].get(relative) != checksums[relative]
        ):
            raise ValueError(f"Missing or mismatched paper config: {relative}")
        load_config(
            output / relative, "preparation" if name == "dataset" else "analysis"
        )
    for relative, digest in provenance["paper_configs"].items():
        if checksums.get(relative) != digest:
            raise ValueError(f"Paper asset differs from provenance: {relative}")
    prepared = {
        r["sha256"]: output / r["path"] for r in rows if r["type"] == "prepared_data"
    }
    if not provenance["runs"]:
        raise ValueError("Release must contain completed run receipts")
    if set(provenance["runs"]) != {
        r["path"] for r in rows if Path(r["path"]).name == "run.json"
    }:
        raise ValueError("Run receipt inventory differs from provenance")
    for relative, receipt in provenance["runs"].items():
        path = output / _relative(relative)
        if not path.is_file() or json.loads(path.read_text()) != receipt:
            raise ValueError(f"Run receipt differs from provenance: {relative}")
        bundle = prepared.get(receipt.get("bundle_sha256"))
        if bundle is None:
            raise ValueError(f"Run's prepared input must be deposited: {relative}")
        if any(
            checksums.get(f"configs/paper/{name}") != digest
            for name, digest in receipt.get("paper_assets_sha256", {}).items()
        ):
            raise ValueError(f"Run paper assets differ from release: {relative}")
        verify_run(path.parent, bundle=bundle)
    return {
        "release_valid": True,
        "artifacts": len(rows),
        "convergence_assessed": False,
    }
