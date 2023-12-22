import os
from typing import Any, Dict, List, Tuple
from polyapi.constants import JSONSCHEMA_TO_PYTHON_TYPE_MAP
from polyapi.typedefs import PropertySpecification, PropertyType
from polyapi.utils import append_init
from polyapi.schema import generate_schema_types

# map the function type from the spec type to the function execute type
TEMPLATE_FUNCTION_TYPE_MAP = {
    "apiFunction": "api",
    "serverFunction": "server",
}

SERVER_TEMPLATE = """
import requests
from typing import List, Dict, Any
from polyapi.config import get_api_key_and_url
from polyapi.exceptions import PolyApiException
{args_def}
{return_type_def}
def {function_name}({args}) -> {return_type_name}:
    api_key, api_url = get_api_key_and_url()
    headers = {{"Authorization": f"Bearer {{api_key}}"}}
    url = f"{{api_url}}/functions/{function_type}/{function_id}/execute"
    data = {data}
    resp = requests.post(url, json=data, headers=headers)
    if resp.status_code != 200 and resp.status_code != 201:
        raise PolyApiException(f"{{resp.status_code}}: {{resp.content}}")

    return {return_action}
"""

API_TEMPLATE = """
import requests
from typing import List, Dict, Any, TypedDict
from polyapi.config import get_api_key_and_url
from polyapi.exceptions import PolyApiException
{args_def}
{return_type_def}
class ApiFunctionResponse(TypedDict):
    status: int
    headers: Dict
    data: {return_type_name}


def {function_name}({args}) -> ApiFunctionResponse:
    api_key, api_url = get_api_key_and_url()
    headers = {{"Authorization": f"Bearer {{api_key}}"}}
    url = f"{{api_url}}/functions/{function_type}/{function_id}/execute"
    data = {data}
    resp = requests.post(url, json=data, headers=headers)
    if resp.status_code != 200 and resp.status_code != 201:
        raise PolyApiException(f"{{resp.status_code}}: {{resp.content}}")
    return ApiFunctionResponse(resp.json())
"""


def _map_primitive_types(type_: str) -> str:
    # Define your mapping logic here
    return JSONSCHEMA_TO_PYTHON_TYPE_MAP.get(type_, "Any")


def _get_type(type_spec: PropertyType) -> Tuple[str, str]:
    if type_spec["kind"] == "plain":
        return _map_primitive_types(type_spec["value"]), ""
    elif type_spec["kind"] == "primitive":
        return _map_primitive_types(type_spec["type"]), ""
    elif type_spec["kind"] == "array":
        # TODO needs to be more general
        if type_spec.get("items"):
            items = type_spec["items"]
            if items.get("$ref"):
                return "Responsetype", generate_schema_types(type_spec)  # type: ignore
            else:
                item_type, _ = _get_type(items)
                return_type = f"List[{item_type}]"
                return return_type, ""
        else:
            return "List", ""
    elif type_spec["kind"] == "void":
        return "None", ""
    elif type_spec["kind"] == "object":
        if type_spec.get("schema"):
            schema = type_spec["schema"]
            title = schema.get("title", "").title()
            if not title:
                # fallback to schema $ref name if no explicit title
                # TODO fix type
                items = schema.get("items")  # type: ignore
                if not items:
                    # TODO fix this, key 5ce on develop has something that doesnt have items
                    # figure out what it is and fix!
                    return "Any", ""

                title = items.get("$ref", "")
                if title:
                    title = title.rsplit("/", 1)[-1].title()
                    title = f'List[{title}]'
                else:
                    # TODO figure out what the title should really be here!
                    title = "Any"
            return title, generate_schema_types(schema)  # type: ignore
        else:
            return "Dict", ""
    elif type_spec["kind"] == "any":
        return "Any", ""
    else:
        return "Any", ""


def _parseArgName(name: str) -> str:
    # HACK this should be snakeCase like Node client
    return name.replace("-", "_")


def _parse_arguments(arguments: List[PropertySpecification]) -> Tuple[str, str]:
    args_def = []
    arg_strings = []
    for a in arguments:
        arg_type, arg_def = _get_type(a["type"])
        if arg_def:
            args_def.append(arg_def)
        if "-" in a['name']:
            a['name'] = _parseArgName(a['name'])
            # arg_type = "Any"
        arg_strings.append(f"{a['name']}: {arg_type}")
    return ", ".join(arg_strings), "\n\n".join(args_def)


def render_function(
    function_type: str,
    function_name: str,
    function_id: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
) -> str:
    arg_names = [a["name"] for a in arguments]
    args, args_def = _parse_arguments(arguments)
    return_type_name, return_type_def = _get_type(return_type)  # type: ignore
    data = "{" + ", ".join([f"'{arg}': {_parseArgName(arg)}" for arg in arg_names]) + "}"
    if function_type == "apiFunction":
        rendered = API_TEMPLATE.format(
            function_type=TEMPLATE_FUNCTION_TYPE_MAP[function_type],
            function_name=function_name,
            function_id=function_id,
            args=args,
            args_def=args_def,
            return_type_name=return_type_name,
            return_type_def=return_type_def,
            data=data,
        )
    else:
        if return_type_def == "str":
            return_action = "resp.text"
        elif return_type_def == "int":
            return_action = "int(resp.text.replace('(int) ', ''))"
        elif return_type_def == "float":
            return_action = "float(resp.text.replace('(float) ', ''))"
        elif return_type_def == "bool":
            return_action = "False if resp.text == 'False' else True"
        else:
            return_action = "resp.json()"
        rendered = SERVER_TEMPLATE.format(
            function_type=TEMPLATE_FUNCTION_TYPE_MAP[function_type],
            function_name=function_name,
            function_id=function_id,
            args=args,
            args_def=args_def,
            return_type_name=return_type_name,
            return_type_def=return_type_def,
            return_action=return_action,
            data=data,
        )
    return rendered


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
