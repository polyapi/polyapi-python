import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TRUSTSTORE_MINIMUM_PYTHON_313_VERSION = (0, 9, 1)


def _parse_requirement_version(requirement: str) -> tuple[int, ...]:
    match = re.fullmatch(r"truststore==(\d+)\.(\d+)\.(\d+)", requirement)
    assert match is not None
    return tuple(int(part) for part in match.groups())


def _truststore_pin() -> str:
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    pyproject_match = re.search(r'"(truststore==\d+\.\d+\.\d+)"', pyproject_text)
    assert pyproject_match is not None
    return pyproject_match.group(1)


def test_truststore_pin_supports_python_313_ssl_chain_api():
    if sys.version_info >= (3, 13):
        assert _parse_requirement_version(_truststore_pin()) >= TRUSTSTORE_MINIMUM_PYTHON_313_VERSION
