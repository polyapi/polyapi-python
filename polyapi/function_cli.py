import ast
import argparse
import json
import types
import sys
from typing import Dict, List
import requests
from pydantic import BaseModel
from polyapi.generate import generate
from polyapi.config import get_api_key_and_url
from polyapi.constants import PYTHON_TO_JSONSCHEMA_TYPE_MAP
from polyapi.utils import get_auth_headers


def _get_schemas(code: str) -> List[Dict]:
    schemas = []
    user_code = types.SimpleNamespace()
    exec(code, user_code.__dict__)
    for name, obj in user_code.__dict__.items():
        if (
            isinstance(obj, type)
            and issubclass(obj, BaseModel)
            and obj.__name__ != "BaseModel"
        ):
            schemas.append(obj.model_json_schema())
    return schemas


def _get_list_return_type_schema(
    python_return_type: str, schemas: List[Dict]
) -> Dict | str:
    subtype = python_return_type[5:-1]
    for schema in schemas:
        if schema["title"] == subtype:
            return {"type": "array", "items": schema}

    # subtype somehow not in schema, just call it any
    return "any[]"


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


def get_python_type_from_ast(expr: ast.expr | None) -> str:
    if isinstance(expr, ast.Name):
        return str(expr.id)
    elif isinstance(expr, ast.Subscript):
        assert isinstance(expr, ast.Subscript)
        name = getattr(expr.value, "id", "")
        if name == "List":
            slice = getattr(expr.slice, "id", "Any")
            return f"List[{slice}]"
        return "Any"
    else:
        return "Any"


def _get_args_and_return_type_from_code(code: str, function_name: str):
    parsed_args = []
    python_return_type = ""
    return_type = None
    return_type_schema = None

    parsed_code = ast.parse(code)
    for node in ast.iter_child_nodes(parsed_code):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            function_args = [arg for arg in node.args.args]
            for arg in function_args:
                python_return_type = get_python_type_from_ast(arg.annotation)
                parsed_args.append(
                    {
                        "key": arg.arg,
                        "name": arg.arg,
                        "type": _get_jsonschema_type(python_return_type),
                    }
                )
            if node.returns:
                python_return_type = get_python_type_from_ast(node.returns)
                return_type = _get_jsonschema_type(python_return_type)
            else:
                return_type = "Any"
            break

    if not return_type:
        print(
            f"Error: function named {function_name} not found as top-level function in file. Exiting."
        )
        sys.exit(1)

    schemas = _get_schemas(code)
    if return_type.endswith("[]") or return_type == "Any" or return_type in PYTHON_TO_JSONSCHEMA_TYPE_MAP.values():
        # return type is simple and has no schema
        pass
    else:
        if python_return_type.startswith("List["):
            return_type_schema = _get_list_return_type_schema(
                python_return_type, schemas
            )
        else:
            for schema in schemas:
                if schema["title"] == return_type:
                    return_type_schema = schema
                    break

    return parsed_args, schemas, return_type, return_type_schema


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
    (
        arguments,
        type_schemas,
        return_type,
        return_type_schema,
    ) = _get_args_and_return_type_from_code(code, args.function_name)

    data = {
        "context": context,
        "name": args.function_name,
        "description": description,
        "code": code,
        "language": "python",
        "typeSchemas": type_schemas,
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
        print("Regenerating library...")
        generate()
    else:
        print("Error adding function.")
        print(resp.status_code)
        print(resp.content)
        sys.exit(1)
