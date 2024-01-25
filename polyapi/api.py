import os
from typing import Any, Dict, List, Tuple

from regex import W

from polyapi.constants import BASIC_PYTHON_TYPES, JSONSCHEMA_TO_PYTHON_TYPE_MAP
from polyapi.typedefs import PropertySpecification, PropertyType
from polyapi.utils import append_init, camelCase
from polyapi.schema import generate_schema_types, clean_title

# map the function type from the spec type to the function execute type
TEMPLATE_FUNCTION_TYPE_MAP = {
    "apiFunction": "api",
    "serverFunction": "server",
}

SERVER_DEFS_TEMPLATE = """
from typing import List, Dict, Any, TypedDict
{args_def}
{return_type_def}
"""

SERVER_FUNCTION_TEMPLATE = """
def {function_name}(
{args}
) -> {return_type_name}:
    "{function_description}"
    resp = execute("{function_type}", "{function_id}", {data})
    return {return_action}
"""

API_DEFS_TEMPLATE = """
from typing import List, Dict, Any, TypedDict
{args_def}
{return_type_def}
class {api_response_type}(TypedDict):
    status: int
    headers: Dict
    data: {return_type_name}
"""

API_FUNCTION_TEMPLATE = """
def {function_name}(
{args}
) -> {api_response_type}:
    "{function_description}"
    resp = execute("{function_type}", "{function_id}", {data})
    return {api_response_type}(resp.json())  # type: ignore
"""


def _map_primitive_types(type_: str) -> str:
    # Define your mapping logic here
    return JSONSCHEMA_TO_PYTHON_TYPE_MAP.get(type_, "Any")


def _get_type(type_spec: PropertyType) -> Tuple[str, str]:
    if type_spec["kind"] == "plain":
        value = type_spec["value"]
        if value.endswith("[]"):
            primitive = _map_primitive_types(value[:-2])
            return f"List[{primitive}]", ""
        else:
            return _map_primitive_types(value), ""
    elif type_spec["kind"] == "primitive":
        return _map_primitive_types(type_spec["type"]), ""
    elif type_spec["kind"] == "array":
        if type_spec.get("items"):
            items = type_spec["items"]
            if items.get("$ref"):
                return "ResponseType", generate_schema_types(type_spec, root="ResponseType")  # type: ignore
            else:
                item_type, _ = _get_type(items)
                title = f"List[{item_type}]"
                title = clean_title(title)
                return title, ""
        else:
            return "List", ""
    elif type_spec["kind"] == "void":
        return "None", ""
    elif type_spec["kind"] == "object":
        if type_spec.get("schema"):
            schema = type_spec["schema"]
            title = schema.get("title", "")
            if title:
                assert isinstance(title, str)
                title = clean_title(title)
                return title, generate_schema_types(schema, root=title)  # type: ignore
            elif schema.get("items"):
                # fallback to schema $ref name if no explicit title
                items = schema.get("items")  # type: ignore
                title = items.get("title", "")  # type: ignore
                if not title:
                    # title is actually a reference to another schema
                    title = items.get("$ref", "")  # type: ignore

                title = title.rsplit("/", 1)[-1]
                title = clean_title(title)
                if not title:
                    return "List", ""

                title = f"List[{title}]"
                return title, generate_schema_types(schema, root=title)
            else:
                return "Any", ""
        else:
            return "Dict", ""
    elif type_spec["kind"] == "any":
        return "Any", ""
    else:
        return "Any", ""


def _parse_arguments(function_name: str, arguments: List[PropertySpecification]) -> Tuple[str, str]:
    args_def = []
    arg_string = ""
    for idx, a in enumerate(arguments):
        arg_type, arg_def = _get_type(a["type"])
        if arg_def:
            args_def.append(arg_def)
        a["name"] = camelCase(a["name"])
        arg_string += f"    {a['name']}: {_add_type_import_path(function_name, arg_type)}"
        description = a.get("description", "")
        if description:
            if idx == len(arguments) - 1:
                arg_string += f"  # {description}\n"
            else:
                arg_string += f",  # {description}\n"
        else:
            arg_string += ",\n"
    return arg_string.rstrip("\n"), "\n\n".join(args_def)


def _add_type_import_path(function_name: str, arg: str) -> str:
    """ if not basic type, coerce to camelCase and add the import path
    """
    if arg in BASIC_PYTHON_TYPES:
        return arg

    if arg.startswith("List["):
        sub = arg[5:-1]
        if sub in BASIC_PYTHON_TYPES:
            return arg
        else:
            if '"' in sub:
                return f'List[_{function_name}.{camelCase(sub)}]'
            else:
                return f'List["_{function_name}.{camelCase(sub)}"]'

    return f'_{function_name}.{camelCase(arg)}'


def render_function(
    function_type: str,
    function_name: str,
    function_id: str,
    function_description: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
) -> Tuple[str, str]:
    arg_names = [a["name"] for a in arguments]
    args, args_def = _parse_arguments(function_name, arguments)
    return_type_name, return_type_def = _get_type(return_type)  # type: ignore
    data = "{" + ", ".join([f"'{arg}': {camelCase(arg)}" for arg in arg_names]) + "}"
    if function_type == "apiFunction":
        api_response_type = f"{function_name}Response"
        func_type_defs = API_DEFS_TEMPLATE.format(
            args_def=args_def,
            api_response_type=api_response_type,
            return_type_name=return_type_name,
            return_type_def=return_type_def,
        )
        func_str = API_FUNCTION_TEMPLATE.format(
            function_type=TEMPLATE_FUNCTION_TYPE_MAP[function_type],
            function_name=function_name,
            function_id=function_id,
            function_description=function_description.replace('"', "'"),
            args=args,
            data=data,
            api_response_type=_add_type_import_path(function_name, api_response_type),
        )
    else:
        func_type_defs = SERVER_DEFS_TEMPLATE.format(
            args_def=args_def,
            return_type_def=return_type_def,
        )
        func_str = SERVER_FUNCTION_TEMPLATE.format(
            return_type_name=_add_type_import_path(function_name, return_type_name),
            function_type=TEMPLATE_FUNCTION_TYPE_MAP[function_type],
            function_name=function_name,
            function_id=function_id,
            function_description=function_description.replace('"', "'"),
            args=args,
            return_action=_get_server_return_action(return_type_name),
            data=data,
        )
    return func_str, func_type_defs


def _get_server_return_action(return_type_name: str) -> str:
    if return_type_name == "str":
        return_action = "resp.text"
    elif return_type_name == "Any":
        return_action = "resp.text"
    elif return_type_name == "int":
        return_action = "int(resp.text.replace('(int) ', ''))"
    elif return_type_name == "float":
        return_action = "float(resp.text.replace('(float) ', ''))"
    elif return_type_name == "bool":
        return_action = "False if resp.text == 'False' else True"
    else:
        return_action = "resp.json()"
    return return_action


def add_function_file(
    function_type: str,
    full_path: str,
    function_name: str,
    function_id: str,
    function_description: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
):
    # first lets add the import to the __init__
    init_path = os.path.join(full_path, "__init__.py")
    _init_the_init(init_path)

    func_str, func_type_defs = render_function(
        function_type,
        function_name,
        function_id,
        function_description,
        arguments,
        return_type,
    )

    with open(init_path, "a") as f:
        f.write(f"\n\nfrom . import _{function_name}\n\n{func_str}")

    # now lets add the code!
    file_path = os.path.join(full_path, f"_{function_name}.py")
    with open(file_path, "w") as f:
        f.write(func_type_defs)


def _init_the_init(init_path: str) -> None:
    if not os.path.exists(init_path):
        with open(init_path, "w") as f:
            f.write("from typing import List, Dict, Any, TypedDict\nfrom polyapi.execute import execute\nfrom polyapi.exceptions import PolyApiException\n")


def create_function(
    function_type: str,
    path: str,
    function_id: str,
    function_description: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
) -> None:
    full_path = os.path.dirname(os.path.abspath(__file__))

    folders = path.split(".")
    for idx, folder in enumerate(folders):
        if idx + 1 == len(folders):
            # special handling for final level
            add_function_file(
                function_type,
                full_path,
                folder,
                function_id,
                function_description,
                arguments,
                return_type,
            )
        else:
            full_path = os.path.join(full_path, folder)
            if not os.path.exists(full_path):
                os.makedirs(full_path)

            # append to __init__.py file if nested folders
            next = folders[idx + 1] if idx + 2 < len(folders) else ""
            if next:
                _init_the_init(os.path.join(full_path, "__init__.py"))
                append_init(full_path, next)


def generate_api(api_functions: List) -> None:
    for func in api_functions:
        create_function(*func)
    print("API functions generated!")
