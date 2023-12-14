import argparse
from typing import List
import requests
from polyapi.config import get_api_key_and_url
from polyapi.utils import get_auth_headers


def function_add_or_update(context: str, description: str, server: bool, subcommands: List):
    parser = argparse.ArgumentParser()
    parser.add_argument("subcommand", choices=["add"])
    parser.add_argument("function_name")
    parser.add_argument("filename")
    args = parser.parse_args(subcommands)

    with open(args.filename, "r") as f:
        code = f.read()

    data = {
        "context": context,
        "name": args.function_name,
        "description": description,
        "code": code,
        "language": "python",
        "typeSchemas": {},
        "returnType": None,
        "returnTypeSchema": {},
        "arguments": [],
        "logsEnabled": None
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
        exit(1)