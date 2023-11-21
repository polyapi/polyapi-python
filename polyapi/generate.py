import requests
import os
import shutil
from typing import List, Tuple
from .api import generate_api
from .config import get_api_key, get_api_base_url


def get_specs() -> List:
    api_key = get_api_key()
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{get_api_base_url()}/specs"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    else:
        raise NotImplementedError(resp.content)


def parse_specs(specs: List) -> List[List[str]]:
    api_functions = []
    for spec in specs:
        if spec['type'] != 'apiFunction' and spec['type'] != 'serverFunction':
            # for now we only support api functions
            continue

        function_name = f"poly.{spec['context']}.{spec['name']}"
        function_id = spec['id']
        args = [arg['name'] for arg in spec['function']['arguments']]
        api_functions.append([function_name, function_id] + args)
    return api_functions


def get_specs_and_parse():
    specs = get_specs()
    api_functions = parse_specs(specs)
    return api_functions


def remove_old_library():
    currdir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(currdir, "poly")
    if os.path.exists(path):
        shutil.rmtree(path)


def generate() -> None:
    remove_old_library()
    api_functions = get_specs_and_parse()
    if not api_functions:
        print("No Api Functions retrieved from specs endpoint, exiting!")
        exit(1)

    generate_api(api_functions)