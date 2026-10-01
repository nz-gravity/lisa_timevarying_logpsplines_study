"""Command-line interface for the LISA case study."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser(
        "generate", help="generate XYZ data from supplied noise and orbits"
    )
    generate.add_argument("output", type=Path)
    generate.add_argument(
        "--source", type=Path, help="dataset containing embedded noise and orbits"
    )
    generate.add_argument(
        "--demo",
        action="store_true",
        help="offline synthetic execution fixture; never paper data",
    )
    generate.add_argument("--noise", type=Path)
    generate.add_argument("--orbits", type=Path)
    orbits = commands.add_parser(
        "fetch-orbits", help="download and sample ESA Earth-trailing orbits"
    )
    orbits.add_argument("output", type=Path)
    orbits.add_argument("--version", default="1.0.0", help="CReMA orbit version")
    orbits.add_argument("--size", type=int, default=632)
    prepare = commands.add_parser(
        "prepare", help="prepare WDM powers, masks and references"
    )
    prepare.add_argument("archive", type=Path)
    prepare.add_argument("output", type=Path)
    prepare.add_argument("--config", type=Path, help="paper preparation JSON")
    prepare.add_argument("--profile", choices=["smoke", "paper"], default="smoke")
    prepare.add_argument(
        "--mode", choices=["continuous", "gapped"], default="continuous"
    )
    fit = commands.add_parser("fit", help="fit Hagn, Horb and Hpara with LogPSplinePSD")
    fit.add_argument("bundle", type=Path)
    fit.add_argument("output", type=Path)
    fit.add_argument("--profile", choices=["smoke", "paper"], default="smoke")
    fit.add_argument(
        "--models",
        nargs="+",
        choices=["Hagn", "Horb", "Hpara"],
        default=None,
    )
    fit.add_argument("--channels", nargs="+", choices=["A", "E"], default=None)
    fit.add_argument(
        "--config", type=Path, help="paper analysis JSON; explicit flags override it"
    )
    fit.add_argument("--warmup", type=int)
    fit.add_argument("--samples", type=int)
    fit.add_argument("--chains", type=int)
    fit.add_argument("--knots", type=Path)
    fit.add_argument("--max-tree-depth", type=int)
    verify = commands.add_parser(
        "verify", help="verify a completed run and its input checksum"
    )
    verify.add_argument("output", type=Path)
    verify.add_argument(
        "--bundle", type=Path, help="prepared bundle, if moved since the run"
    )
    figures = commands.add_parser(
        "figures", help="regenerate reconstruction figures from saved posteriors"
    )
    figures.add_argument("--results", type=Path, required=True)
    figures.add_argument("--output", type=Path, required=True)
    release = commands.add_parser(
        "package-release",
        help="package explicitly selected scientific artifacts for Zenodo",
    )
    release.add_argument("output", type=Path)
    release.add_argument(
        "--plan",
        type=Path,
        required=True,
        help="JSON manifest of individual source files",
    )
    verify_release_parser = commands.add_parser(
        "verify-release",
        help="verify release inventory, checksums, metadata and saved results",
    )
    verify_release_parser.add_argument("output", type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    from .figures import make_figures
    from .generate import generate_dataset
    from .orbits import fetch_orbits
    from .prepare import prepare as prepare_dataset
    from .release import package_release, verify_release
    from .run import run_analysis
    from .verification import verify_run

    actions = {
        "generate": generate_dataset,
        "fetch-orbits": fetch_orbits,
        "prepare": prepare_dataset,
        "fit": run_analysis,
        "verify": verify_run,
        "figures": make_figures,
        "package-release": package_release,
        "verify-release": verify_release,
    }
    try:
        result = actions[command](**args)
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2) if isinstance(result, dict) else result)
