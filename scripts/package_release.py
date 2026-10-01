"""Compatibility entry point for the explicit scientific release packager."""

import argparse
from pathlib import Path

from lisa_psd_analysis.release import package_release


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--plan", type=Path, required=True, help="JSON artifact inventory"
    )
    args = parser.parse_args()
    try:
        print(package_release(args.output, plan=args.plan))
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
