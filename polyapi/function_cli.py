import ast
import argparse
import json
import types
import sys
from typing import Dict, List, Mapping, Optional, Tuple
from typing import _TypedDictMeta as BaseTypedDict  # type: ignore
from typing_extensions import _TypedDictMeta  # type: ignore
import requests
from stdlib_list import stdlib_list
from pydantic import TypeAdapter
from importlib.metadata import packages_distributions
from polyapi.generate import get_functions_and_parse, generate_functions
from polyapi.config import get_api_key_and_url
from polyapi.constants import PYTHON_TO_JSONSCHEMA_TYPE_MAP
# from polyapi.rendered_spec import update_rendered_spec
from polyapi.utils import get_auth_headers, print_green, print_red, print_yellow
import importlib


# these libraries are already installed in the base docker image
# and shouldnt be included in additional requirements
BASE_REQUIREMENTS = {
    "polyapi",
    "requests",
    "typing_extensions",
    "jsonschema-gentypes",
    "pydantic",
    "cloudevents",
}
all_stdlib_symbols = stdlib_list(".".join([str(v) for v in sys.version_info[0:2]]))
BASE_REQUIREMENTS.update(
    all_stdlib_symbols
)  # dont need to pip install stuff in the python standard library


def _get_schemas(code: str) -> List[Dict]:
    schemas = []
    user_code = types.SimpleNamespace()
    exec(code, user_code.__dict__)
    for name, obj in user_code.__dict__.items():
        if isinstance(obj, BaseTypedDict):
            print_red("ERROR")
            print_red("\nERROR DETAILS: ")
            print(
                "It looks like you have used TypedDict in a custom function. Please use `from typing_extensions import TypedDict` instead. The `typing_extensions` version is more powerful and better allows us to provide rich types for your function."
            )
            sys.exit(1)
        elif (
            isinstance(obj, type)
            and isinstance(obj, _TypedDictMeta)
            and name != "TypedDict"
        ):
            schemas.append(TypeAdapter(obj).json_schema())
    return schemas


def _get_jsonschema_type(python_type: str):
    if python_type == "Any":
        return "Any"

    if python_type == "List":
        return "array"

    if python_type.startswith("List["):
        # the actual type will be returned as return_type_schema
        subtype = python_type[5:-1]
        if subtype == "Any":
            return "any[]"
        elif subtype in ["int", "float", "str", "bool"]:
            jsonschema_type = PYTHON_TO_JSONSCHEMA_TYPE_MAP.get(subtype)
            return f"{jsonschema_type}[]"
        else:
            # the schema will handle it!
            return "object"

    if python_type.startswith("Dict"):
        return "object"

    rv = PYTHON_TO_JSONSCHEMA_TYPE_MAP.get(python_type)
    if rv:
        return rv

    # should be custom type
    return python_type


def get_python_type_from_ast(expr: ast.expr) -> str:
    if isinstance(expr, ast.Name):
        return str(expr.id)
    elif isinstance(expr, ast.Subscript):
        assert isinstance(expr, ast.Subscript)
        name = getattr(expr.value, "id", "")
        if name == "List":
            slice = getattr(expr.slice, "id", "Any")
            return f"List[{slice}]"
        elif name == "Dict":
            if expr.slice and isinstance(expr.slice, ast.Tuple):
                key = get_python_type_from_ast(expr.slice.dims[0])
                value = get_python_type_from_ast(expr.slice.dims[1])
                return f"Dict[{key}, {value}]"
            else:
                return "Dict"
        return "Any"
    else:
        return "Any"


def _get_type_schema(json_type: str, python_type: str, schemas: List[Dict]):
    if python_type.startswith("List["):
        subtype = python_type[5:-1]
        for schema in schemas:
            if schema["title"] == subtype:
                return {"type": "array", "items": schema}

        # subtype somehow not in schema, just call it any
        return None
    else:
        for schema in schemas:
            if schema["title"] == json_type:
                return schema


def _get_type(expr: ast.expr | None, schemas: List[Dict]) -> Tuple[str, Dict | None]:
    if not expr:
        return "Any", None
    python_type = get_python_type_from_ast(expr)
    json_type = _get_jsonschema_type(python_type)
    return json_type, _get_type_schema(json_type, python_type, schemas)


def _get_req_name_if_not_in_base(
    n: Optional[str], pip_name_lookup: Mapping[str, List[str]]
) -> Optional[str]:
    if not n:
        return None

    if "." in n:
        n = n.split(".")[0]

    if n in BASE_REQUIREMENTS:
        return None
    else:
        return pip_name_lookup[n][0]


def _parse_code(code: str, function_name: str):
    parsed_args = []
    return_type = None
    return_type_schema = None
    requirements: List[str] = []

    schemas = _get_schemas(code)

    parsed_code = ast.parse(code)

    # the pip name and the import name might be different
    # e.g. kube_hunter is the import name, but the pip name is kube-hunter
    # see https://stackoverflow.com/a/75144378
    pip_name_lookup = packages_distributions()

    for node in ast.iter_child_nodes(parsed_code):
        if isinstance(node, ast.Import):
            # TODO maybe handle `import foo.bar` case?
            for name in node.names:
                req = _get_req_name_if_not_in_base(name.name, pip_name_lookup)
                if req:
                    requirements.append(req)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                req = _get_req_name_if_not_in_base(node.module, pip_name_lookup)
                if req:
                    requirements.append(req)

        elif isinstance(node, ast.FunctionDef) and node.name == function_name:
            function_args = [arg for arg in node.args.args]
            for arg in function_args:
                json_type, type_schema = _get_type(arg.annotation, schemas)
                json_arg = {
                    "key": arg.arg,
                    "name": arg.arg,
                    "type": json_type,
                }
                if type_schema:
                    json_arg["typeSchema"] = json.dumps(type_schema)
                parsed_args.append(json_arg)
            if node.returns:
                return_type, return_type_schema = _get_type(node.returns, schemas)
            else:
                return_type = "Any"
            break

    return parsed_args, return_type, return_type_schema, requirements


def _func_already_exists(context: str, function_name: str) -> bool:
    try:
        module = importlib.import_module(f"polyapi.poly.{context}")
        return bool(getattr(module, function_name, False))
    except ModuleNotFoundError:
        return False


def function_add_or_update(
    context: str,
    description: str,
    client: bool,
    server: bool,
    logs_enabled: bool,
    subcommands: List,
):
    parser = argparse.ArgumentParser()
    parser.add_argument("subcommand", choices=["add"])
    parser.add_argument("function_name")
    parser.add_argument("filename")
    args = parser.parse_args(subcommands)

    verb = "Updating" if _func_already_exists(context, args.function_name) else "Adding"
    ftype = "server" if server else "client"
    print(f"{verb} custom {ftype} function...", end="")

    with open(args.filename, "r") as f:
        code = f.read()

    # OK! let's parse the code and generate the arguments
    (arguments, return_type, return_type_schema, requirements) = _parse_code(
        code, args.function_name
    )

    if not return_type:
        print_red("ERROR")
        print(
            f"Function {args.function_name} not found as top-level function in {args.filename}"
        )
        sys.exit(1)

    data = {
        "context": context,
        "name": args.function_name,
        "description": description,
        "code": code,
        "language": "python",
        "returnType": return_type,
        "returnTypeSchema": return_type_schema,
        "arguments": arguments,
        "logsEnabled": logs_enabled,
    }

    if server and requirements:
        print_yellow(
            "\nPlease note that deploying your functions will take a few minutes because it makes use of libraries other than polyapi."
        )
        data["requirements"] = requirements

    api_key, api_url = get_api_key_and_url()
    assert api_key
    if server:
        url = f"{api_url}/functions/server"
    elif client:
        url = f"{api_url}/functions/client"
    else:
        print_red("ERROR")
        print("Please specify type of function with --client or --server")
        sys.exit(1)

    headers = get_auth_headers(api_key)
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code == 201:
        print_green("DEPLOYED")
        function_id = resp.json()["id"]
        print(f"Function ID: {function_id}")
        print("Generating new custom function...", end="")
        functions = get_functions_and_parse(limit_ids=[function_id])
        # update_rendered_spec(functions[0])
        generate_functions(functions)
        print_green("DONE")
    else:
        print("Error adding function.")
        print(resp.status_code)
        print(resp.content)
        sys.exit(1)
