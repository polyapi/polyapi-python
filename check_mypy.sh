#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
	PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
else
	PYTHON_BIN="python3"
fi

"${PYTHON_BIN}" -m mypy \
	--follow-imports=skip \
	--install-types \
	polyapi/config.py \
	polyapi/execute.py \
	polyapi/generate.py \
	polyapi/http_client.py \
	polyapi/schema.py \
	polyapi/schemas/__init__.py \
	polyapi/utils.py