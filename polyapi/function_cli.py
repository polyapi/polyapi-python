import ast
import types
import argparse
import sys
from typing import List
import requests
from pydantic import BaseModel
from polyapi.config import get_api_key_and_url
from polyapi.constants import PYTHON_TO_JSONSCHEMA_TYPE_MAP
from polyapi.utils import get_auth_headers


def _get_jsonschema_type(python_type: str, code: str):
    if python_type == "Any":
        return "Any"

    if python_type.startswith("List"):
        # TODO do some stuff on items?
        return "array"

    if python_type.startswith("Dict"):
        return "object"

    # TODO find the matching type in the code and recursively turn it into JSONSchema?

    rv = PYTHON_TO_JSONSCHEMA_TYPE_MAP.get(python_type)
    if rv:
        return rv

    user_code = types.SimpleNamespace()
    exec(code, user_code.__dict__)
    type_obj = getattr(user_code, python_type, None)
    if type_obj and issubclass(type_obj, BaseModel):
        return type_obj.model_json_schema()
    else:
        return "Any"


def _get_args_and_return_type_from_code(code: str, function_name: str):
    return_type_schema = None
    parsed_code = ast.parse(code)
    # Iterate over every function in the AST
    for node in ast.iter_child_nodes(parsed_code):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            function_args = [arg for arg in node.args.args]
            parsed_args = []
            for arg in function_args:
                parsed_args.append(
                    {
                        "key": arg.arg,
                        "name": arg.arg,
                        "type": _get_jsonschema_type(getattr(arg.annotation, "id", "Any"), code),
                    }
                )
            if node.returns:
                return_type_schema = _get_jsonschema_type(getattr(node.returns, "id", "Any"), code)
                return_type = "object"
            else:
                return_type = "Any"
            return parsed_args, return_type, return_type_schema

    # if we get here, we didn't find the function
    print(
        f"Error: function named {function_name} not found as top-level function in file. Exiting."
    )
    sys.exit(1)


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
    arguments, return_type, return_type_schema = _get_args_and_return_type_from_code(code, args.function_name)

    data = {
        "context": context,
        "name": args.function_name,
        "description": description,
        "code": code,
        "language": "python",
        "typeSchemas": None,
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
