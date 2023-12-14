import ast
import argparse
import sys
from typing import List
import requests
from polyapi.config import get_api_key_and_url
from polyapi.constants import PYTHON_TO_JSONSCHEMA_TYPE_MAP
from polyapi.utils import get_auth_headers


def _get_jsonschema_type(python_type: str):
    if python_type.startswith("List"):
        return "array"

    if python_type.startswith("Dict"):
        return "object"

    return PYTHON_TO_JSONSCHEMA_TYPE_MAP.get(python_type, "any")


def _get_arguments_from_ast(parsed_code: ast.AST, function_name: str):
    # Iterate over every function in the AST
    for node in ast.iter_child_nodes(parsed_code):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            function_args = [arg for arg in node.args.args]
            rv = []
            for arg in function_args:
                rv.append(
                    {
                        "key": arg.arg,
                        "name": arg.arg,
                        "type": _get_jsonschema_type(getattr(arg.annotation, "id", "any")),
                    }
                )
            return rv

    # if we get here, we didn't find the function
    print(
        f"Error: function named {function_name} not found as top-level function in file. Exiting."
    )
    sys.exit(1)


def function_add_or_update(
    context: str, description: str, server: bool, subcommands: List
):
    parser = argparse.ArgumentParser()
    parser.add_argument("subcommand", choices=["add"])
    parser.add_argument("function_name")
    parser.add_argument("filename")
    args = parser.parse_args(subcommands)

    with open(args.filename, "r") as f:
        code = f.read()

    # OK! let's parse the code and generate the arguments
    code_ast = ast.parse(code)
    arguments = _get_arguments_from_ast(code_ast, args.function_name)

    data = {
        "context": context,
        "name": args.function_name,
        "description": description,
        "code": code,
        "language": "python",
        "typeSchemas": {},
        "returnType": None,
        "returnTypeSchema": {},
        "arguments": arguments,
        "logsEnabled": None,
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
