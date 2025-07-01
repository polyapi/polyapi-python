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
LAST_GENERATE_CONTEXTS = None
LAST_GENERATE_NAMES = None
LAST_GENERATE_FUNCTION_IDS = None
LAST_GENERATE_NO_TYPES = None


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
        
        # Read and cache generate command arguments
        global LAST_GENERATE_CONTEXTS, LAST_GENERATE_NAMES, LAST_GENERATE_FUNCTION_IDS, LAST_GENERATE_NO_TYPES
        contexts_str = config.get("polyapi", "last_generate_contexts_used", fallback=None)
        LAST_GENERATE_CONTEXTS = contexts_str.split(",") if contexts_str else None
        names_str = config.get("polyapi", "last_generate_names_used", fallback=None)
        LAST_GENERATE_NAMES = names_str.split(",") if names_str else None
        function_ids_str = config.get("polyapi", "last_generate_function_ids_used", fallback=None)
        LAST_GENERATE_FUNCTION_IDS = function_ids_str.split(",") if function_ids_str else None
        LAST_GENERATE_NO_TYPES = config.get("polyapi", "last_generate_no_types_used", fallback="false").lower() == "true"

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


def get_cached_generate_args() -> Tuple[list | None, list | None, list | None, bool]:
    """Return cached generate command arguments"""
    global LAST_GENERATE_CONTEXTS, LAST_GENERATE_NAMES, LAST_GENERATE_FUNCTION_IDS, LAST_GENERATE_NO_TYPES
    if LAST_GENERATE_CONTEXTS is None and LAST_GENERATE_NAMES is None and LAST_GENERATE_FUNCTION_IDS is None and LAST_GENERATE_NO_TYPES is None:
        # Force a config read if values aren't cached
        get_api_key_and_url()
    return LAST_GENERATE_CONTEXTS, LAST_GENERATE_NAMES, LAST_GENERATE_FUNCTION_IDS, bool(LAST_GENERATE_NO_TYPES)


def cache_generate_args(contexts: list | None = None, names: list | None = None, function_ids: list | None = None, no_types: bool = False):
    """Cache generate command arguments to config file"""
    from typing import List
    
    # Read existing config
    path = get_config_file_path()
    config = configparser.ConfigParser()
    
    if os.path.exists(path):
        with open(path, "r") as f:
            config.read_file(f)
    
    # Ensure polyapi section exists
    if "polyapi" not in config:
        config["polyapi"] = {}
    
    # Update cached values
    global LAST_GENERATE_CONTEXTS, LAST_GENERATE_NAMES, LAST_GENERATE_FUNCTION_IDS, LAST_GENERATE_NO_TYPES
    LAST_GENERATE_CONTEXTS = contexts
    LAST_GENERATE_NAMES = names
    LAST_GENERATE_FUNCTION_IDS = function_ids
    LAST_GENERATE_NO_TYPES = no_types
    
    # Write values to config
    if contexts is not None:
        config.set("polyapi", "last_generate_contexts_used", ",".join(contexts))
    elif config.has_option("polyapi", "last_generate_contexts_used"):
        config.remove_option("polyapi", "last_generate_contexts_used")
        
    if names is not None:
        config.set("polyapi", "last_generate_names_used", ",".join(names))
    elif config.has_option("polyapi", "last_generate_names_used"):
        config.remove_option("polyapi", "last_generate_names_used")
        
    if function_ids is not None:
        config.set("polyapi", "last_generate_function_ids_used", ",".join(function_ids))
    elif config.has_option("polyapi", "last_generate_function_ids_used"):
        config.remove_option("polyapi", "last_generate_function_ids_used")
        
    config.set("polyapi", "last_generate_no_types_used", str(no_types).lower())
    
    with open(path, "w") as f:
        config.write(f)