#!/bin/sh
set -eu

source_package="${JFO_SOURCE:-${1:-jev-file-organizer}}"
python_version="${JFO_PYTHON_VERSION:-3.13}"

if command -v uv >/dev/null 2>&1; then
    uv tool install --force --python "$python_version" "$source_package"
elif command -v pipx >/dev/null 2>&1; then
    python_command="python$python_version"
    if ! command -v "$python_command" >/dev/null 2>&1; then
        echo "JFO requires Python 3.12 or 3.13. Install uv or $python_command first." >&2
        exit 1
    fi
    pipx install --force --python "$python_command" "$source_package"
else
    echo "Install uv (recommended) or pipx, then run this installer again." >&2
    exit 1
fi

echo
echo "JFO installed. Verify it with: jfo doctor"
echo "Configure your API key with: jfo configure"
