"""Checksums and environment receipts for reproducible runs."""

import importlib.metadata
from pathlib import Path

import log_psplines

from .dataset_bundle import file_hash


def runtime_receipt() -> dict:
    """Record installed source files and dependency versions."""
    library = Path(log_psplines.__file__).parent
    analysis = Path(__file__).parent
    roots = {"package": library, "analysis": analysis}
    return {
        "package_version": importlib.metadata.version("LogPSplinePSD"),
        "code_sha256": {
            f"{label}/{p.relative_to(root)}": file_hash(p)
            for label, root in roots.items()
            for p in sorted(root.rglob("*"))
            if p.is_file() and p.suffix in (".py", ".json")
        },
        "dependencies": {
            d.metadata["Name"]: d.version
            for d in importlib.metadata.distributions()
            if d.metadata["Name"]
        },
    }


def git_receipt(root: Path) -> dict:
    """Record a source checkout commit and whether tracked/untracked work remains."""
    import subprocess

    def git(*args: str) -> str | None:
        process = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
        )
        return process.stdout.strip() if process.returncode == 0 else None

    sha = git("rev-parse", "HEAD")
    status = git("status", "--porcelain")
    return {"git_sha": sha, "dirty": bool(status) if status is not None else None}


def release_provenance(root: Path, seeds: dict, configs: dict) -> dict:
    """Generate an archival environment receipt; missing Git identity stays explicit."""
    import platform
    from datetime import UTC, datetime

    receipt = runtime_receipt()
    library_root = Path(log_psplines.__file__).resolve().parents[2]
    return {
        "schema": 1,
        "study_repository_url": "https://github.com/nz-gravity/lisa_timevarying_logpsplines_study",
        "study": git_receipt(root),
        "logpsplinepsd": {
            "version": receipt["package_version"],
            **git_receipt(library_root),
        },
        "python_version": platform.python_version(),
        "dependency_lock_sha256": file_hash(root / "uv.lock"),
        "jax_version": importlib.metadata.version("jax"),
        "numpyro_version": importlib.metadata.version("numpyro"),
        "platform": platform.platform(),
        "random_seeds": seeds,
        "paper_configs": configs,
        "created_at": datetime.now(UTC).isoformat(),
        "runtime": receipt,
    }
