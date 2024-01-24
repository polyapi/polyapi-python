import json
import requests
import os
import shutil
from typing import Any, Dict, List, Tuple

from .typedefs import PropertySpecification
from .utils import get_auth_headers
from .api import generate_api
from .variables import generate_variables
from .config import get_api_key_and_url, initialize_config


def get_specs() -> List:
    api_key, api_url = get_api_key_and_url()
    assert api_key
    headers = get_auth_headers(api_key)
    url = f"{api_url}/specs"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    else:
        raise NotImplementedError(resp.content)


def parse_specs(
    specs: List,
) -> List[Tuple[str, str, str, str, List[PropertySpecification], Dict[str, Any]]]:
    # optional array of ids to include in the generated library
    # currently just used for testing/development purposes
    allowed_ids: List[str] = []

    api_functions = []
    for spec in specs:
        if allowed_ids and spec["id"] not in allowed_ids:
            continue

        if spec["type"] != "apiFunction" and spec["type"] != "serverFunction":
            # for now we only support api and server functions
            continue

        function_type = spec["type"]
        function_name = f"poly.{spec['context']}.{spec['name']}"
        function_id = spec["id"]
        arguments: List[PropertySpecification] = [
            arg for arg in spec["function"]["arguments"]
        ]
        api_functions.append(
            (
                function_type,
                function_name,
                function_id,
                spec["description"],
                arguments,
                spec["function"]["returnType"],
            )
        )
    return api_functions


def cache_specs(specs):
    supported = []
    for spec in specs:
        # this needs to stay in sync with logic in parse_specs
        if spec["type"] == "apiFunction" or spec["type"] == "serverFunction":
            supported.append(spec)

    full_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(full_path, "poly")
    if not os.path.exists(full_path):
        os.makedirs(full_path)

    with open(os.path.join(full_path, "specs.json"), "w") as f:
        f.write(json.dumps(supported))


def get_functions_and_parse():
    specs = get_specs()
    cache_specs(specs)
    functions = parse_specs(specs)
    return functions


def get_variables_and_parse() -> List[Tuple[str, str, bool]]:
    raw = get_variables()
    variables = parse_variables(raw)
    return variables


def get_variables():
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{api_url}/variables"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    else:
        raise NotImplementedError(resp.content)


def parse_variables(variables: List) -> List[Tuple[str, str, bool]]:
    rv = []
    for v in variables:
        path = f"vari.{v['context']}.{v['name']}"
        rv.append((path, v["id"], v["secret"]))
    return rv


def remove_old_library():
    currdir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(currdir, "poly")
    if os.path.exists(path):
        shutil.rmtree(path)

    path = os.path.join(currdir, "vari")
    if os.path.exists(path):
        shutil.rmtree(path)


def generate() -> None:
    initialize_config()

    remove_old_library()

    functions = get_functions_and_parse()
    if functions:
        generate_api(functions)
    else:
        print(
            "No functions exist yet in this tenant! Empty library initialized. Let's add some functions!"
        )
        exit()

    variables = get_variables_and_parse()
    if variables:
        generate_variables(variables)


def clear() -> None:
    base = os.path.dirname(os.path.abspath(__file__))
    poly_path = os.path.join(base, "poly")
    if os.path.exists(poly_path):
        shutil.rmtree(poly_path)

    vari_path = os.path.join(base, "vari")
    if os.path.exists(vari_path):
        shutil.rmtree(vari_path)
    print("Cleared!")
