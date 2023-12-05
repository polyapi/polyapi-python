import requests
import os
import shutil
from typing import Any, Dict, List, Tuple

from polyapi.typedefs import PropertySpecification
from .api import generate_api
from .variables import generate_variables
from .config import get_api_key_and_url, initialize_config


def get_specs() -> List:
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{api_url}/specs"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    else:
        raise NotImplementedError(resp.content)


def parse_specs(specs: List) -> List[Tuple[str, str, str, List[PropertySpecification], Dict[str, Any]]]:
    api_functions = []
    for spec in specs:
        if spec['type'] != 'apiFunction' and spec['type'] != 'serverFunction':
            # for now we only support api and server functions
            continue

        function_type = spec['type']
        function_name = f"poly.{spec['context']}.{spec['name']}"
        function_id = spec['id']
        arguments: List[PropertySpecification] = [arg for arg in spec['function']['arguments']]
        api_functions.append((function_type, function_name, function_id, arguments, spec['function']["returnType"]))
    return api_functions


def get_specs_and_parse():
    specs = get_specs()
    api_functions = parse_specs(specs)
    return api_functions


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
        rv.append((path, v['id'], v['secret']))
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

    functions = get_specs_and_parse()
    if functions:
        generate_api(functions)
    else:
        print("No functions seem to exist in this tenant! Please add some functions and try again.")
        exit(1)

    variables = get_variables_and_parse()
    if variables:
        generate_variables(variables)