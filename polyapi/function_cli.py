import sys
from typing import Any, List, Optional
import requests
from polyapi.generate import generate as generate_library
from polyapi.config import get_api_key_and_url
from polyapi.utils import get_auth_headers, print_green, print_red, print_yellow
from polyapi.parser import parse_function_code, get_jsonschema_type
import importlib


def _func_already_exists(context: str, function_name: str) -> bool:
    try:
        module = importlib.import_module(f"polyapi.poly.{context}")
        return bool(getattr(module, function_name, False))
    except ModuleNotFoundError:
        return False


def function_add_or_update(
    name: str,
    file: str,
    context: str,
    description: str,
    client: bool,
    server: bool,
    logs_enabled: Optional[bool],
    generate_contexts: Optional[str],
    generate: bool = True,
    execution_api_key: str = ""
):
    verb = "Updating" if _func_already_exists(context, name) else "Adding"
    ftype = "server" if server else "client"
    print(f"{verb} custom {ftype} function...", end="")

    with open(file, "r") as f:
        code = f.read()

    # OK! let's parse the code and generate the arguments
    parsed = parse_function_code(code, name, context)
    return_type = parsed["types"]["returns"]["type"]

    if not return_type:
        print_red("ERROR")
        print(
            f"Function {name} not found as top-level function in {name}"
        )
        sys.exit(1)

    if logs_enabled is None:
        logs_enabled = parsed["config"].get("logs_enabled", None)

    data = {
        "context": context or parsed["context"],
        "name": name,
        "description": description or parsed["types"]["description"],
        "code": code,
        "language": "python",
        "returnType": get_jsonschema_type(return_type),
        "arguments": [{**p, "key": p["name"], "type": get_jsonschema_type(p["type"])} for p in parsed["types"]["params"]],
        "logsEnabled": logs_enabled,
    }

    if generate_contexts:
        data["generateContexts"] = generate_contexts.split(",")

    if server and parsed["dependencies"]:
        print_yellow(
            "\nPlease note that deploying your functions will take a few minutes because it makes use of libraries other than polyapi."
        )
        data["requirements"] = parsed["dependencies"]

    api_key, api_url = get_api_key_and_url()
    assert api_key
    if server:
        url = f"{api_url}/functions/server"

        if execution_api_key:
            data["executionApiKey"] = execution_api_key

    elif client:
        url = f"{api_url}/functions/client"
    else:
        print_red("ERROR")
        print("Please specify type of function with --client or --server")
        sys.exit(1)

    headers = get_auth_headers(api_key)
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code in [200, 201]:
        print_green("DEPLOYED")
        function_id = resp.json()["id"]
        print(f"Function ID: {function_id}")
        if generate:
            generate_library()
    else:
        print("Error adding function.")
        print(resp.status_code)
        print(resp.content)
        sys.exit(1)


def function_execute(context: str, name: str, args: List) -> Any:
    context_code = importlib.import_module(f"polyapi.poly.{context}")
    print(f"Executing poly.{context}.{name}... ")
    fn = getattr(context_code, name)
    return fn(*args)


def spec_delete(function_type: str, function_id: str):
    api_key, api_url = get_api_key_and_url()
    assert api_key
    if function_type == "api":
        url = f"{api_url}/functions/api/{function_id}"
    elif function_type == "serverFunction":
        url = f"{api_url}/functions/server/{function_id}"
    elif function_type == "customFunction":
        url = f"{api_url}/functions/client/{function_id}"
    elif function_type == "webhookHandle":
        url = f"{api_url}/webhooks/{function_id}"
    else:
        print_red("ERROR")
        print(f"Unknown function type: {function_type}")
        sys.exit(1)
    headers = get_auth_headers(api_key)
    resp = requests.delete(url, headers=headers)
    return resp