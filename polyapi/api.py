import os
from typing import List

TEMPLATE = """
import requests
from polyapi.config import get_api_key, get_api_base_url


def {function_name}({args}):
    api_key = get_api_key()
    headers = {{"Authorization": f"Bearer {{api_key}}"}}
    url = f"{{get_api_base_url()}}/functions/api/{function_id}/execute"
    data = {data}
    resp = requests.post(url, data=data, headers=headers)
    assert resp.status_code == 201, resp.content
    return resp.json()
"""


def append_init(full_path: str, next: str) -> None:
    init_path = os.path.join(full_path, "__init__.py")
    with open(init_path, "a") as f:
        if next:
            f.write("from . import {}\n".format(next))
        else:
            f.write("")


def add_function(full_path: str, function_name: str, function_id: str, *args):
    # first lets add the import to the __init__
    init_path = os.path.join(full_path, "__init__.py")
    with open(init_path, "a") as f:
        f.write(f"from ._{function_name} import {function_name}\n")

    # now lets add the code!
    file_path = os.path.join(full_path, f"_{function_name}.py")
    arg_string = ", ".join(args)
    data = "{" + ", ".join([f"'{arg}': {arg}" for arg in args]) + "}"
    with open(file_path, "w") as f:
        f.write(
            TEMPLATE.format(
                function_name=function_name, function_id=function_id, args=arg_string, data=data
            )
        )


def create_function(path: str, function_id, *args) -> None:
    full_path = os.path.dirname(os.path.abspath(__file__))

    folders = path.split(".")
    for idx, folder in enumerate(folders):
        if idx + 1 == len(folders):
            # special handling for final level
            add_function(full_path, folder, function_id, *args)
        else:
            full_path = os.path.join(full_path, folder)
            if not os.path.exists(full_path):
                os.makedirs(full_path)
                # add the __init__.py file with special handling if it's the 2nd-to-last or last level
                next = folders[idx + 1] if idx + 2 < len(folders) else ""
                append_init(full_path, next)


def generate_api(api_functions: List) -> None:
    for t in api_functions:
        create_function(*t)
    print("API functions generated!")
