#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
	PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
else
	PYTHON_BIN="python3"
fi

pip install -r requirements.txt

"${PYTHON_BIN}" -m mypy \
	--follow-imports=skip \
	--install-types \
	--non-interactive \
	polyapi/config.py \
	polyapi/execute.py \
	polyapi/generate.py \
	polyapi/http_client.py \
	polyapi/schema.py \
	polyapi/utils.py