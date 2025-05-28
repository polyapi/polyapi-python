import keyword
import re
import os
import uuid
from urllib.parse import urlparse
from typing import Tuple, List
from colorama import Fore, Style
from polyapi.constants import BASIC_PYTHON_TYPES
from polyapi.typedefs import PropertySpecification, PropertyType
from polyapi.schema import (
    wrapped_generate_schema_types,
    clean_title,
    map_primitive_types,
    is_primitive
)


# this string should be in every __init__ file.
# it contains all the imports needed for the function or variable code to run
CODE_IMPORTS = "from typing import List, Dict, Any, Optional, Callable\nfrom typing_extensions import TypedDict, NotRequired\nimport logging\nimport requests\nimport socketio  # type: ignore\nfrom polyapi.config import get_api_key_and_url, get_direct_execute_config\nfrom polyapi.execute import execute, execute_post, variable_get, variable_update, direct_execute\n\n"


def init_the_init(full_path: str, code_imports="") -> None:
    init_path = os.path.join(full_path, "__init__.py")
    if not os.path.exists(init_path):
        code_imports = code_imports or CODE_IMPORTS
        with open(init_path, "w") as f:
            f.write(code_imports)


def add_import_to_init(full_path: str, next: str, code_imports="") -> None:
    init_the_init(full_path, code_imports=code_imports)

    init_path = os.path.join(full_path, "__init__.py")
    with open(init_path, "a+") as f:
        import_stmt = "from . import {}\n".format(next)
        f.seek(0)
        lines = f.readlines()
        if import_stmt not in set(lines):
            f.write(import_stmt)


def get_auth_headers(api_key: str):
    return {"Authorization": f"Bearer {api_key}"}


def camelCase(s: str) -> str:
    s = s.strip()
    if " " in s or "-" in s:
        s = re.sub(r"(_|-)+", " ", s).title().replace(" ", "")
        return "".join([s[0].lower(), s[1:]])
    else:
        # s is already in camelcase as best as we can tell, just move on!
        return s


def pascalCase(s) -> str:
    return re.sub(r"(^|_)([a-z])", lambda match: match.group(2).upper(), s)


def print_green(s: str):
    print(Fore.GREEN + s + Style.RESET_ALL)


def print_yellow(s: str):
    print(Fore.YELLOW + s + Style.RESET_ALL)


def print_red(s: str):
    print(Fore.RED + s + Style.RESET_ALL)


def add_type_import_path(function_name: str, arg: str) -> str:
    """if not basic type, coerce to camelCase and add the import path"""
    # for now, just treat Callables as basic types
    if arg.startswith("Callable"):
        return arg

    if arg in BASIC_PYTHON_TYPES:
        return arg

    if arg.startswith("List["):
        sub = arg[5:-1]
        if sub in BASIC_PYTHON_TYPES:
            return arg
        else:
            if '"' in sub:
                sub = sub.replace('"', "")
                return f'List["{to_func_namespace(function_name)}.{camelCase(sub)}"]'
            else:
                return f"List[{to_func_namespace(function_name)}.{camelCase(sub)}]"

    return f"{to_func_namespace(function_name)}.{camelCase(arg)}"


def get_type_and_def(
    type_spec: PropertyType, title_fallback: str = ""
) -> Tuple[str, str]:
    """ returns type and type definition for a given PropertyType
    """
    # Handle cases where type_spec might be None or empty
    if not type_spec:
        return "Any", ""
    
    # Handle cases where kind might be missing
    if "kind" not in type_spec:
        return "Any", ""
    
    if type_spec["kind"] == "plain":
        value = type_spec.get("value", "")
        if value.endswith("[]"):
            primitive = map_primitive_types(value[:-2])
            return f"List[{primitive}]", ""
        else:
            return map_primitive_types(value), ""
    elif type_spec["kind"] == "primitive":
        return map_primitive_types(type_spec.get("type", "any")), ""
    elif type_spec["kind"] == "array":
        if type_spec.get("items"):
            items = type_spec["items"]
            if items.get("$ref"):
                # For no-types mode, avoid complex schema generation
                try:
                    return wrapped_generate_schema_types(type_spec, "ResponseType", "Dict")  # type: ignore
                except:
                    return "List[Dict]", ""
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
            title = schema.get("title", schema.get("name", title_fallback))
            if title and schema.get("type") == "array":
                # TODO fix me
                # we don't use ReturnType as name for the list type here, we use _ReturnTypeItem
                return "List", ""
            elif title and title == "ReturnType" and schema.get("type"):
                assert isinstance(title, str)
                schema_type = schema.get("type", "Any")
                root_type, generated_code = wrapped_generate_schema_types(schema, schema_type, "Dict")  # type: ignore
                return (map_primitive_types(root_type), "") if is_primitive(root_type) else (root_type, generated_code)  # type: ignore
            elif title:
                assert isinstance(title, str)
                # For no-types mode, avoid complex schema generation
                try:
                    root_type, generated_code = wrapped_generate_schema_types(schema, title, "Dict")  # type: ignore
                    return ("Any", "") if root_type == "ReturnType" else wrapped_generate_schema_types(schema, title, "Dict")  # type: ignore
                except:
                    return "Dict", ""
            elif schema.get("allOf") and len(schema["allOf"]):
                # we are in a case of a single allOf, lets strip off the allOf and move on!
                # our library doesn't handle allOf well yet
                allOf = schema["allOf"][0]
                title = allOf.get("title", allOf.get("name", title_fallback))
                try:
                    return wrapped_generate_schema_types(allOf, title, "Dict")
                except:
                    return "Dict", ""
            elif schema.get("items"):
                # fallback to schema $ref name if no explicit title
                items = schema.get("items")  # type: ignore
                title = items.get("title")  # type: ignore
                if not title:
                    # title is actually a reference to another schema
                    title = items.get("$ref", title_fallback)  # type: ignore

                title = title.rsplit("/", 1)[-1]
                if not title:
                    return "List", ""

                title = f"List[{title}]"
                try:
                    return wrapped_generate_schema_types(schema, title, "List")
                except:
                    return "List[Dict]", ""
            elif schema.get("properties"):
                result = wrapped_generate_schema_types(schema, "ResponseType", "Dict")  # type: ignore
                return result
            else:
                return "Dict", ""
        else:
            return "Dict", ""
    elif type_spec["kind"] == "function":
        arg_types = []
        arg_defs = []
        if "spec" in type_spec:
            return_type, _ = get_type_and_def(type_spec["spec"]["returnType"])
            if return_type not in BASIC_PYTHON_TYPES:
                # for now only Python only supports basic types as return types
                return_type = "Any"

            for argument in type_spec["spec"]["arguments"]:
                # do NOT add this fallback here
                # callable arguments don't understand the imports yet
                # if it's not a basic type here, we'll just do Any
                # _maybe_add_fallback_schema_name(argument)
                arg_type, arg_def = get_type_and_def(argument["type"])
                arg_types.append(arg_type)
                if arg_def:
                    arg_defs.append(arg_def)

            final_arg_type = "Callable[[{}], {}]".format(
                ", ".join(arg_types), return_type
            )
            return final_arg_type, "\n".join(arg_defs)
        else:
            return "Callable", ""
    elif type_spec["kind"] == "any":
        return "Any", ""
    else:
        return "Any", ""


def _maybe_add_fallback_schema_name(a: PropertySpecification):
    # Handle cases where type might be missing
    if not a.get("type"):
        return
    
    if a["type"].get("kind") == "object" and a["type"].get("schema"):
        schema = a["type"].get("schema", {})
        if not schema.get("title") and not schema.get("name") and a.get("name"):
            schema["title"] = a["name"].title()


def _clean_description(text: str) -> str:
    """Flatten new-lines and collapse excess whitespace."""
    text = text.replace("\\n", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_arguments(
    function_name: str, arguments: List[PropertySpecification]
) -> Tuple[str, str]:
    args_def = []
    arg_string = ""
    for idx, a in enumerate(arguments):
        _maybe_add_fallback_schema_name(a)
        
        # Handle cases where type might be missing
        arg_type_spec = a.get("type", {"kind": "any"})
        arg_type, arg_def = get_type_and_def(arg_type_spec)
        if arg_def:
            args_def.append(arg_def)
        
        # Handle cases where name might be missing
        arg_name = a.get("name", f"arg{idx}")
        a["name"] = rewrite_arg_name(arg_name)
        
        arg_string += (
            f"    {a['name']}: {add_type_import_path(function_name, arg_type)}"
        )
        
        # Handle cases where required might be missing
        if not a.get("required", True):
            arg_string += " = None"

        description = _clean_description(a.get("description", ""))

        if description:
            if idx == len(arguments) - 1:
                arg_string += f"  # {description}\n"
            else:
                arg_string += f",  # {description}\n"
        else:
            arg_string += ",\n"
    return arg_string.rstrip("\n"), "\n\n".join(args_def)


def poly_full_path(context, name) -> str:
    """get the functions path as it will be exposed in the poly library"""
    if context:
        path = context + "." + name
    else:
        path = name
    return f"poly.{path}"


RESERVED_WORDS = {"List", "Dict", "Any", "Optional", "Callable"} | set(keyword.kwlist)


def to_func_namespace(s: str) -> str:
    """convert a function name to some function namespace
    by default it is
    """
    rv = s[0].upper() + s[1:]
    rv = rewrite_reserved(rv)
    return rv


def rewrite_reserved(s: str) -> str:
    if s in RESERVED_WORDS:
        return "_" + s
    else:
        return s


def rewrite_arg_name(s: str):
    return rewrite_reserved(camelCase(s))


# def get_return_type_name(function_name: str) -> str:
#     return function_name[0].upper() + function_name[1:] + "ReturnType"


valid_subdomains = ["na[1-2]", "eu[1-2]", "dev"]


def is_valid_polyapi_url(_url: str):
    # in dev allow localhost (and 127.0.0.1) over http *or* https
    parsed = urlparse(_url)
    if parsed.scheme in ("http", "https") and parsed.hostname in ("localhost", "127.0.0.1"):
        return True
    
    # Join the subdomains into a pattern
    subdomain_pattern = "|".join(valid_subdomains)
    pattern = rf"^https://({subdomain_pattern})\.polyapi\.io$"
    return re.match(pattern, _url) is not None

def return_type_already_defined_in_args(return_type_name: str, args_def: str) -> bool:
    """
    Checks if the return_type_name preceded optionally by 'class ' and followed by ' =' exists in args_def.

    Args:
        return_type_name (str): The name of the return type to check.
        args_def (str): The string containing argument definitions.

    Returns:
        bool: True if the pattern exists, False otherwise.
    """
    basic_pattern = rf"^{re.escape(return_type_name)}\s="
    basic_match = bool(re.search(basic_pattern, args_def, re.MULTILINE))
    class_pattern = rf"^class {re.escape(return_type_name)}\(TypedDict"
    class_match = bool(re.search(class_pattern, args_def, re.MULTILINE))
    return basic_match or class_match