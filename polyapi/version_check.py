import importlib.metadata
import logging
import os
import re
import subprocess
import sys
from urllib.parse import urlparse

from packaging.version import InvalidVersion, Version

from .config import get_api_key_and_url
from .http_client import get as http_get

logger = logging.getLogger("poly")

_REEXEC_GUARD_ENV = "POLY_VERSION_REEXEC_GUARD"


def _get_client_version() -> str | None:
    try:
        return importlib.metadata.version("polyapi-python")
    except Exception:
        return None


def _normalize_version(version: str | None) -> Version | None:
    if not version:
        return None

    candidate = version.strip()
    if not candidate:
        return None

    try:
        return Version(candidate)
    except InvalidVersion:
        pass

    match = re.search(r"(\d+(?:\.\d+){0,2}(?:[a-zA-Z]+\d*)?)", candidate)
    if not match:
        return None

    try:
        return Version(match.group(1))
    except InvalidVersion:
        return None


def get_instance_tag_from_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None

    try:
        host = urlparse(base_url).hostname
        if not host:
            return None
        host_prefix = host.lower().split(".")[0]

        if host_prefix in ("dev", "develop"):
            return "develop"
        if host_prefix == "staging":
            return "staging"
        if host_prefix == "test":
            return "test"
        if host_prefix == "na2":
            return "na2"
        if host_prefix == "eu1":
            return "eu1"
        return "na1"
    except Exception:
        return None


def _resolve_instance_tag(base_url: str | None) -> str | None:
    explicit = os.getenv("POLY_INSTANCE_TAG")
    if explicit:
        return explicit.strip()
    return get_instance_tag_from_base_url(base_url)


def _get_client_versions(base_url: str) -> dict:
    url = f"{base_url.rstrip('/')}/config-variables/SupportedClientVersions"
    api_key, _ = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = http_get(url, headers=headers, timeout=5.0)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, dict):
        raise ValueError("Invalid SupportedClientVersions config variablepayload.")

    value = payload.get("value")
    if isinstance(value, dict):
        return value

    if isinstance(payload.get("python"), str):
        return payload

    raise ValueError("Invalid SupportedClientVersions config variable payload.")

def _resolve_target_version(versions_payload: dict) -> str | None:
    if isinstance(versions_payload, dict):
        value = versions_payload.get("python")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _run_update(target_version: str) -> bool:
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        f"polyapi-python=={target_version}",
    ]
    try:
        subprocess.run(cmd, check=True)
        return True
    except Exception as ex:
        logger.error("Failed to update polyapi-python to %s: %s", target_version, ex)
        return False


def _reexec_process(base_url: str | None = None, api_key: str | None = None) -> None:
    os.environ[_REEXEC_GUARD_ENV] = "1"

    # preserve already-resolved config values so initialize_config won't prompt again
    if base_url:
        os.environ["POLY_API_BASE_URL"] = base_url
    if api_key:
        os.environ["POLY_API_KEY"] = api_key

    argv = [sys.executable, "-m", "polyapi", *sys.argv[1:]]
    os.execv(sys.executable, argv)


def check_for_client_version_update() -> None:
    # prevent update/re-exec loops
    if os.getenv(_REEXEC_GUARD_ENV) == "1":
        return

    # Reuse existing config flow for base URL retrieval
    api_key, base_url = get_api_key_and_url()
    base_url = base_url or os.getenv("POLY_API_BASE_URL")
    if not base_url:
        return

    instance_tag = _resolve_instance_tag(base_url)
    if not instance_tag:
        return

    current_version = _get_client_version()
    normalized_current = _normalize_version(current_version)
    if not current_version or not normalized_current:
        return

    try:
        versions_payload = _get_client_versions(base_url)
    except Exception as ex:
        logger.error("Failed to fetch client versions from the service: %s", ex)
        return

    available_version = _resolve_target_version(versions_payload)
    normalized_available = _normalize_version(available_version)
    if not available_version or not normalized_available:
        return

    using_older_version = normalized_current < normalized_available
    using_newer_version = normalized_current > normalized_available

    if not using_older_version and not using_newer_version:
        return

    warning_message = (
        f'Instance "{instance_tag}" uses '
        f'{"a later" if using_older_version else "an older"} version of the Poly client. '
        f"Current: {current_version}, Instance: {available_version}."
    )

    non_interactive_mode = bool(
        os.getenv("POLY_API_KEY") or os.getenv("POLY_API_BASE_URL")
    )

    if non_interactive_mode:
        print(f"{warning_message} Please update to avoid any issues.")
        return

    should_update_input = input(f"{warning_message} Update now? [Y/n]: ").strip().lower()
    should_update = should_update_input in ("", "y", "yes")

    if should_update:
        updated = _run_update(available_version)
        if updated:
            _reexec_process(base_url=base_url, api_key=api_key)
        return

    print(
        f'Continuing with {"older" if using_older_version else "newer"} '
        f"Poly client version {current_version}. Please update to avoid any issues."
    )