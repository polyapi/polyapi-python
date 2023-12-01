import os
from typing import Any, Dict, List
from polyapi.typedefs import PropertySpecification, PropertyType
from polyapi.utils import append_init
from polyapi.schema import generate_schema_types

# map the function type from the spec type to the function execute type
TEMPLATE_FUNCTION_TYPE_MAP = {
    "apiFunction": "api",
    "serverFunction": "server",
}

TEMPLATE = """
import requests
from typing import List, Dict, Any
from polyapi.config import get_api_key_and_url
from polyapi.exceptions import PolyApiException


def {function_name}({args}) -> {return_type}:
    api_key, api_url = get_api_key_and_url()
    return_str = {return_str}
    headers = {{"Authorization": f"Bearer {{api_key}}"}}
    url = f"{{api_url}}/functions/{function_type}/{function_id}/execute"
    data = {data}
    resp = requests.post(url, data=data, headers=headers)
    if resp.status_code != 200 and resp.status_code != 201:
        raise PolyApiException(f"{{resp.status_code}}: {{resp.content}}")
    if return_str:
        return resp.text
    else:
        return resp.json()
"""


PRIMITIVE_TYPE_MAP = {
    "integer": "int",
    "number": "float",
    "string": "str",
    "boolean": "bool",
}


def _map_primitive_types(type_: str) -> str:
    # Define your mapping logic here
    return PRIMITIVE_TYPE_MAP.get(type_, "Any")


def _get_type(type_spec: PropertyType) -> str:
    if type_spec["kind"] == "plain":
        return _map_primitive_types(type_spec["value"])
    elif type_spec["kind"] == "primitive":
        return _map_primitive_types(type_spec["type"])
    elif type_spec["kind"] == "array":
        # return f"List[{_get_type(type_spec['type'])}]"
        return "List"
    elif type_spec["kind"] == "void":
        return "None"
    elif type_spec["kind"] == "object":
        return "Dict"
    elif type_spec["kind"] == "any":
        return "Any"
    else:
        return "Any"


def _get_arg_string(arguments: List[PropertySpecification]) -> str:
    arg_strings = [f"{a['name']}: {_get_type(a['type'])}" for a in arguments]
    return ", ".join(arg_strings)


def render_function(
    function_type: str,
    function_name: str,
    function_id: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
) -> str:
    arg_names = [a["name"] for a in arguments]
    arg_string = _get_arg_string(arguments)
    return_type_string = _get_type(return_type)  # type: ignore
    return_str = return_type_string == "str"
    data = "{" + ", ".join([f"'{arg}': {arg}" for arg in arg_names]) + "}"
    return TEMPLATE.format(
        function_type=TEMPLATE_FUNCTION_TYPE_MAP[function_type],
        function_name=function_name,
        function_id=function_id,
        args=arg_string,
        return_type=return_type_string,
        return_str=return_str,
        data=data,
    )


def add_function_file(
    function_type: str,
    full_path: str,
    function_name: str,
    function_id: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
):
    # first lets add the import to the __init__
    init_path = os.path.join(full_path, "__init__.py")
    with open(init_path, "a") as f:
        f.write(f"from ._{function_name} import {function_name}\n")

    # now lets add the code!
    file_path = os.path.join(full_path, f"_{function_name}.py")
    with open(file_path, "w") as f:
        f.write(
            render_function(
                function_type, function_name, function_id, arguments, return_type
            )
        )


def create_function(
    function_type: str,
    path: str,
    function_id: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
) -> None:
    full_path = os.path.dirname(os.path.abspath(__file__))

    folders = path.split(".")
    for idx, folder in enumerate(folders):
        if idx + 1 == len(folders):
            # special handling for final level
            add_function_file(
                function_type, full_path, folder, function_id, arguments, return_type
            )
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
