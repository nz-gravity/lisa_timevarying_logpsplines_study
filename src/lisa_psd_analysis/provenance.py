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
