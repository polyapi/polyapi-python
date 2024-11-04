import sys
import os
import configparser
from typing import Tuple

from polyapi.utils import is_valid_polyapi_url, is_valid_uuid, print_green, print_yellow

# cached values
API_KEY = None
API_URL = None


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

    return key, url


def set_api_key_and_url(key: str, url: str):
    config = configparser.ConfigParser()
    config["polyapi"] = {}
    config.set("polyapi", "poly_api_key", key)
    config.set("polyapi", "poly_api_base_url", url)
    with open(get_config_file_path(), "w") as f:
        config.write(f)


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
            if not is_valid_uuid(key):
                errors.append(f"{key} is not a valid Poly App Key or User Key")
            if errors:
                print_yellow("\n".join(errors))
                sys.exit(1)

            set_api_key_and_url(key, url)
            print_green(f"Poly setup complete.")

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