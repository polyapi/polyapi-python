import ast
import types
import argparse
import sys
from typing import Dict, List
import requests
from pydantic import BaseModel
from polyapi.config import get_api_key_and_url
from polyapi.constants import PYTHON_TO_JSONSCHEMA_TYPE_MAP
from polyapi.utils import get_auth_headers


def _get_schemas(code: str) -> List[Dict]:
    schemas = []
    user_code = types.SimpleNamespace()
    exec(code, user_code.__dict__)
    for name, obj in user_code.__dict__.items():
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj.__name__ != "BaseModel":
            schemas.append(obj.model_json_schema())
    return schemas


def _get_jsonschema_type(python_type: str):
    if python_type == "Any":
        return "Any"

    if python_type.startswith("List"):
        # TODO do some stuff on items?
        # actually the schema should handle this right?
        return "array"

    if python_type.startswith("Dict"):
        return "object"

    rv = PYTHON_TO_JSONSCHEMA_TYPE_MAP.get(python_type)
    if rv:
        return rv

    # should be custom type
    return python_type


def get_python_type_from_ast(expr: ast.expr | None) -> str:
    return getattr(expr, "id", "Any")


def _get_args_and_return_type_from_code(code: str, function_name: str):
    parsed_args = []
    return_type = None
    return_type_schema = None

    parsed_code = ast.parse(code)
    for node in ast.iter_child_nodes(parsed_code):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            function_args = [arg for arg in node.args.args]
            for arg in function_args:
                python_type = get_python_type_from_ast(arg.annotation)
                parsed_args.append(
                    {
                        "key": arg.arg,
                        "name": arg.arg,
                        "type": _get_jsonschema_type(python_type),
                    }
                )
            if node.returns:
                python_type = get_python_type_from_ast(node.returns)
                return_type = _get_jsonschema_type(python_type)
            else:
                return_type = "Any"

    if not return_type:
        print(
            f"Error: function named {function_name} not found as top-level function in file. Exiting."
        )
        sys.exit(1)

    arg_schemas = _get_schemas(code)
    if return_type not in PYTHON_TO_JSONSCHEMA_TYPE_MAP.values():
        for idx, schema in enumerate(arg_schemas):
            if schema["title"] == return_type:
                return_type_schema = schema
                break

    return parsed_args, arg_schemas, return_type, return_type_schema


def function_add_or_update(
    context: str, description: str, server: bool, logs_enabled: bool, subcommands: List
):
    parser = argparse.ArgumentParser()
    parser.add_argument("subcommand", choices=["add"])
    parser.add_argument("function_name")
    parser.add_argument("filename")
    args = parser.parse_args(subcommands)

    with open(args.filename, "r") as f:
        code = f.read()

    # OK! let's parse the code and generate the arguments
    arguments, arg_type_schemas, return_type, return_type_schema = _get_args_and_return_type_from_code(code, args.function_name)

    data = {
        "context": context,
        "name": args.function_name,
        "description": description,
        "code": code,
        "language": "python",
        "typeSchemas": arg_type_schemas,
        "returnType": return_type,
        "returnTypeSchema": return_type_schema,
        "arguments": arguments,
        "logsEnabled": logs_enabled,
    }

    api_key, api_url = get_api_key_and_url()
    assert api_key
    if server:
        url = f"{api_url}/functions/server"
    else:
        raise NotImplementedError("Client functions not yet implemented.")
        # url = f"{base_url}/functions/client"

    headers = get_auth_headers(api_key)
    print("Adding function...")
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code == 201:
        function_id = resp.json()["id"]
        print(f"Function added successfully. Function id is {function_id}")
    else:
        print("Error adding function.")
        print(resp.status_code)
        print(resp.content)
        sys.exit(1)
