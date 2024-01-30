import json
import requests
import os
import shutil
from typing import Any, Dict, List, Tuple

from .typedefs import PropertySpecification, SpecificationDto, VariableSpecDto
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
    limit_ids: List[str] | None  # optional list of ids to limit to
) -> List[Tuple[str, str, str, str, List[PropertySpecification], Dict[str, Any]]]:
    api_functions = []
    for spec in specs:
        if limit_ids and spec["id"] not in limit_ids:
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


def cache_specs(specs: List[SpecificationDto]):
    supported = []
    for spec in specs:
        # this needs to stay in sync with logic in parse_specs
        if spec["type"] == "apiFunction" or spec["type"] == "serverFunction" or spec["type"] == "serverVariable":
            supported.append(spec)

    full_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(full_path, "poly")
    if not os.path.exists(full_path):
        os.makedirs(full_path)

    with open(os.path.join(full_path, "specs.json"), "w") as f:
        f.write(json.dumps(supported))


def get_functions_and_parse(limit_ids: List[str] | None = None):
    specs = get_specs()
    cache_specs(specs)
    functions = parse_specs(specs, limit_ids=limit_ids)
    return functions


def get_variables() -> List[VariableSpecDto]:
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    # TODO do some caching so this and get_functions just do 1 function call
    url = f"{api_url}/specs"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        specs = resp.json()
        return [spec for spec in specs if spec['type'] == "serverVariable"]
    else:
        raise NotImplementedError(resp.content)


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

    variables = get_variables()
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
