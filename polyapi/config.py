import sys
import os
import configparser
from typing import Tuple

from polyapi.utils import is_valid_polyapi_url, print_green, print_yellow

# cached values
API_KEY = None
API_URL = None
API_FUNCTION_DIRECT_EXECUTE = None
MTLS_CERT_PATH = None
MTLS_KEY_PATH = None
MTLS_CA_PATH = None


def get_config_file_path() -> str:
    currdir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(currdir, ".config.env")


def get_api_key_and_url() -> Tuple[str | None, str | None]:
    """ return the api key and api url
    """
    key = os.environ.get("POLY_API_KEY")
    url = os.environ.get("POLY_API_BASE_URL")
    if key and url:
        return key, url

    # check cached values to avoid disk read
    global API_KEY
    global API_URL
    if API_KEY and API_URL:
        return API_KEY, API_URL

    # read config from disk
    path = get_config_file_path()
    if os.path.exists(path):
        config = configparser.ConfigParser()
        with open(path, "r") as f:
            config.read_file(f)

        if not key:
            key = config.get("polyapi", "poly_api_key", fallback=None)
        if not url:
            url = config.get("polyapi", "poly_api_base_url", fallback=None)

        # cache values so we only read from disk once
        API_KEY = key
        API_URL = url

        # Read and cache MTLS and direct execute settings
        global API_FUNCTION_DIRECT_EXECUTE, MTLS_CERT_PATH, MTLS_KEY_PATH, MTLS_CA_PATH
        API_FUNCTION_DIRECT_EXECUTE = config.get("polyapi", "api_function_direct_execute", fallback="false").lower() == "true"
        MTLS_CERT_PATH = config.get("polyapi", "mtls_cert_path", fallback=None)
        MTLS_KEY_PATH = config.get("polyapi", "mtls_key_path", fallback=None)
        MTLS_CA_PATH = config.get("polyapi", "mtls_ca_path", fallback=None)

    return key, url


def set_api_key_and_url(key: str, url: str):
    config = configparser.ConfigParser()
    config["polyapi"] = {}
    config.set("polyapi", "poly_api_key", key)
    config.set("polyapi", "poly_api_base_url", url)
    with open(get_config_file_path(), "w") as f:
        config.write(f)
    global API_KEY
    global API_URL
    API_KEY = key
    API_URL = url


def initialize_config(force=False):
    key, url = get_api_key_and_url()
    if force or (not key or not url):
        url = url or "https://na1.polyapi.io"
        print("Please setup your connection to PolyAPI.")
        url = input(f"? Poly API Base URL ({url}): ").strip() or url

        if not key:
            key = input("? Poly App Key or User Key: ").strip()
        else:
            key_input = input(f"? Poly App Key or User Key ({key}): ").strip()
            key = key_input if key_input else key

        if url and key:
            errors = []
            if not is_valid_polyapi_url(url):
                errors.append(f"{url} is not a valid Poly API Base URL")
            if errors:
                print_yellow("\n".join(errors))
                sys.exit(1)

            set_api_key_and_url(key, url)
            print_green("Poly setup complete.")

    if not key or not url:
        print_yellow("Poly API Key and Poly API Base URL are required.")
        sys.exit(1)

    return key, url


def clear_config():
    if os.environ.get("POLY_API_KEY"):
        print("Using POLY_API_KEY from environment. Please unset environment variable to manually set api key.")
        return

    global API_KEY
    global API_URL
    API_KEY = None
    API_URL = None

    path = get_config_file_path()
    if os.path.exists(path):
        os.remove(path)


def get_mtls_config() -> Tuple[bool, str | None, str | None, str | None]:
    """Return MTLS configuration settings"""
    global MTLS_CERT_PATH, MTLS_KEY_PATH, MTLS_CA_PATH
    if MTLS_CERT_PATH is None or MTLS_KEY_PATH is None or MTLS_CA_PATH is None:
        # Force a config read if values aren't cached
        get_api_key_and_url()
    return bool(MTLS_CERT_PATH and MTLS_KEY_PATH and MTLS_CA_PATH), MTLS_CERT_PATH, MTLS_KEY_PATH, MTLS_CA_PATH


def get_direct_execute_config() -> bool:
    """Return whether direct execute is enabled"""
    global API_FUNCTION_DIRECT_EXECUTE
    if API_FUNCTION_DIRECT_EXECUTE is None:
        # Force a config read if value isn't cached
        get_api_key_and_url()
    return bool(API_FUNCTION_DIRECT_EXECUTE)