import re
import os
from typing import Tuple, List
from colorama import Fore, Style
from polyapi.constants import BASIC_PYTHON_TYPES
from polyapi.typedefs import PropertySpecification, PropertyType
from polyapi.schema import generate_schema_types, clean_title, map_primitive_types


# this string should be in every __init__ file.
# it contains all the imports needed for the function or variable code to run
CODE_IMPORTS = "from typing import List, Dict, Any, TypedDict, Optional\nimport requests\nimport socketio  # type: ignore\nfrom polyapi.config import get_api_key_and_url\nfrom polyapi.execute import execute, execute_post, variable_get, variable_update\n\n"


def init_the_init(full_path: str) -> None:
    init_path = os.path.join(full_path, "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, "w") as f:
            f.write(CODE_IMPORTS)


def add_import_to_init(full_path: str, next: str) -> None:
    init_the_init(full_path)

    init_path = os.path.join(full_path, "__init__.py")
    with open(init_path, "a+") as f:
        import_stmt = "from . import {}\n".format(next)
        f.seek(0)
        lines = f.readlines()
        if import_stmt not in set(lines):
            f.write(import_stmt)


def get_auth_headers(api_key: str):
    return {"Authorization": f"Bearer {api_key}"}


def camelCase(s):
    s = s.strip()
    if " " in s or "-" in s:
        s = re.sub(r"(_|-)+", " ", s).title().replace(" ", "")
        return ''.join([s[0].lower(), s[1:]])
    else:
        # s is already in camelcase as best as we can tell, just move on!
        return s


def print_green(s: str):
    print(Fore.GREEN + s + Style.RESET_ALL)


def print_yellow(s: str):
    print(Fore.YELLOW + s + Style.RESET_ALL)


def print_red(s: str):
    print(Fore.RED + s + Style.RESET_ALL)


def add_type_import_path(function_name: str, arg: str) -> str:
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
                sub = sub.replace('"', "")
                return f'List["_{function_name}.{camelCase(sub)}"]'
            else:
                return f'List[_{function_name}.{camelCase(sub)}]'

    return f'_{function_name}.{camelCase(arg)}'


def get_type_and_def(type_spec: PropertyType) -> Tuple[str, str]:
    if type_spec["kind"] == "plain":
        value = type_spec["value"]
        if value.endswith("[]"):
            primitive = map_primitive_types(value[:-2])
            return f"List[{primitive}]", ""
        else:
            return map_primitive_types(value), ""
    elif type_spec["kind"] == "primitive":
        return map_primitive_types(type_spec["type"]), ""
    elif type_spec["kind"] == "array":
        if type_spec.get("items"):
            items = type_spec["items"]
            if items.get("$ref"):
                return "ResponseType", generate_schema_types(type_spec, root="ResponseType")  # type: ignore
            else:
                item_type, _ = get_type_and_def(items)
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


def parse_arguments(function_name: str, arguments: List[PropertySpecification]) -> Tuple[str, str]:
    args_def = []
    arg_string = ""
    for idx, a in enumerate(arguments):
        arg_type, arg_def = get_type_and_def(a["type"])
        if arg_def:
            args_def.append(arg_def)
        a["name"] = camelCase(a["name"])
        arg_string += f"    {a['name']}: {add_type_import_path(function_name, arg_type)}"
        description = a.get("description", "")
        if description:
            if idx == len(arguments) - 1:
                arg_string += f"  # {description}\n"
            else:
                arg_string += f",  # {description}\n"
        else:
            arg_string += ",\n"
    return arg_string.rstrip("\n"), "\n\n".join(args_def)