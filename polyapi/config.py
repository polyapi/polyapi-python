import sys
import os
import configparser
from typing import Tuple

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


def initialize_config():
    key, url = get_api_key_and_url()
    if not key or not url:
        print("Please setup your connection to PolyAPI.")
        url = input("? Poly API Base URL (https://na1.polyapi.io): ") or "https://na1.polyapi.io"
        key = input("? Poly App Key or User Key: ")

        if url and key:
            set_api_key_and_url(key, url)

    if not key or not url:
        print("Poly API Key and Poly API Base URL are required.")
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