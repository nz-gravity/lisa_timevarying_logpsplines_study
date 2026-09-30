"""Build source archives and a checksum manifest for a reproducibility deposit."""

import argparse
import hashlib
import json
import tarfile
from pathlib import Path

EXCLUDED = {
    ".git",
    ".venv",
    "output",
    "data",
    "logs",
    "dist",
    "build",
    "__pycache__",
    ".cache",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "graphify-out",
    "test-output",
}


def package(source: Path, output: Path, name: str) -> Path:
    """Archive source and configuration files; keep large data separate."""
    target = output / f"{name}.tar.gz"
    with (
        target.open("xb") as stream,
        tarfile.open(fileobj=stream, mode="w:gz") as archive,
    ):
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if (
                not path.is_file()
                or any(p in EXCLUDED or p.endswith(".egg-info") for p in relative.parts)
                or path.suffix in (".pyc", ".png", ".npz", ".h5", ".nc")
                or path.name == ".DS_Store"
            ):
                continue
            archive.add(path, arcname=str(Path(name) / relative), recursive=False)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True, exist_ok=False)
    files = [
        package(root, args.output, "lisa_psd_analysis"),
        package(root.parent / "LogPSplinePSD", args.output, "LogPSplinePSD"),
    ]
    from importlib.metadata import version

    (args.output / "logpspline-version.txt").write_text(version("LogPSplinePSD") + "\n")
    files.append(args.output / "logpspline-version.txt")
    checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (args.output / "SHA256SUMS.json").write_text(json.dumps(checksums, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
