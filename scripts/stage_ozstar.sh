#!/usr/bin/env bash
# Stage both source trees into a fresh, isolated directory on OzSTAR.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ $# != 1 ]]; then
    echo "Usage: bash scripts/stage_ozstar.sh /absolute/remote/campaign/path" >&2
    exit 2
fi
remote=$1
if [[ ! "$remote" =~ ^/[A-Za-z0-9_./-]+$ ]]; then
    echo 'Use an absolute remote path without spaces or shell characters.' >&2
    exit 2
fi
ssh ozstar "test ! -e '$remote' && mkdir -p '$remote/lisa_psd_analysis' '$remote/LogPSplinePSD'"
rsync -a --exclude='.git' --exclude='.venv' --exclude='output' --exclude='data' \
    --exclude='__pycache__' --exclude='*.egg-info' --exclude='.*cache' --exclude='dist' \
    ./ "ozstar:$remote/lisa_psd_analysis/"
# Include only the library's build inputs, implementation and tests.
rsync -a ../LogPSplinePSD/pyproject.toml ../LogPSplinePSD/README.rst \
    "ozstar:$remote/LogPSplinePSD/"
rsync -a --exclude='__pycache__' --exclude='*.egg-info' \
    ../LogPSplinePSD/src "ozstar:$remote/LogPSplinePSD/"
# setuptools-scm needs a version when a source snapshot has no .git directory.
version=$(.venv/bin/python -c 'from importlib.metadata import version; print(version("LogPSplinePSD"))')
printf '%s\n' "$version" | ssh ozstar "cat > '$remote/logpspline-version.txt'"
echo "Staged $remote. Follow docs/ozstar.md to install and submit."
