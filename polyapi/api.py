import os
from typing import List

from polyapi.utils import append_init

# map the function type from the spec type to the function execute type
TEMPLATE_FUNCTION_TYPE_MAP = {
    "apiFunction": "api",
    "serverFunction": "server",
}

TEMPLATE = """
import requests
from polyapi.config import get_api_key, get_api_base_url
from polyapi.exceptions import PolyApiException


def {function_name}({args}):
    api_key = get_api_key()
    headers = {{"Authorization": f"Bearer {{api_key}}"}}
    url = f"{{get_api_base_url()}}/functions/{function_type}/{function_id}/execute"
    data = {data}
    resp = requests.post(url, data=data, headers=headers)
    if resp.status_code != 200 and resp.status_code != 201:
        raise PolyApiException(f"{{resp.status_code}}: {{resp.content}}")
    return resp.text
"""


def add_function_file(
    function_type: str, full_path: str, function_name: str, function_id: str, *args
):
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
                function_type=TEMPLATE_FUNCTION_TYPE_MAP[function_type],
                function_name=function_name,
                function_id=function_id,
                args=arg_string,
                data=data,
            )
        )


def create_function(function_type: str, path: str, function_id: str, *args) -> None:
    full_path = os.path.dirname(os.path.abspath(__file__))

    folders = path.split(".")
    for idx, folder in enumerate(folders):
        if idx + 1 == len(folders):
            # special handling for final level
            add_function_file(function_type, full_path, folder, function_id, *args)
        else:
            full_path = os.path.join(full_path, folder)
            if not os.path.exists(full_path):
                os.makedirs(full_path)

            # append to __init__.py file if nested folders
            next = folders[idx + 1] if idx + 2 < len(folders) else ""
            if next:
                append_init(full_path, next)


def generate_api(api_functions: List) -> None:
    for func in api_functions:
        create_function(*func)
    print("API functions generated!")
