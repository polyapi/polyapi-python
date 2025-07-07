import os
import sys
import subprocess
from typing import List, Tuple, Literal
import requests

from polyapi.utils import get_auth_headers
from polyapi.config import get_api_key_and_url
from polyapi.parser import parse_function_code
from polyapi.deployables import (
    prepare_deployable_directory, write_cache_revision,
    save_deployable_records, get_all_deployable_files,
    is_cache_up_to_date, get_git_revision,
    write_updated_deployable, DeployableRecord
)

class FunctionArgumentDto:
    def __init__(self, name, type, description=None):
        self.name = name
        self.type = type
        self.description = description

def get_function_description(deploy_type: Literal["server-function", "client-function"], description: str, arguments, code: str) -> str:
    if deploy_type == "server-function":
        return get_server_function_description(description, arguments, code)
    elif deploy_type == "client-function":
        return get_client_function_description(description, arguments, code)
    else:
        raise ValueError("Unsupported deployable type")

def get_server_function_description(description: str, arguments, code: str) -> str:
    api_key, api_url = get_api_key_and_url()
    headers = get_auth_headers(api_key)
    data = {"description": description, "arguments": arguments, "code": code}
    response = requests.post(f"{api_url}/functions/server/description-generation", headers=headers, json=data)
    return response.json()

def get_client_function_description(description: str, arguments, code: str) -> str:
    api_key, api_url = get_api_key_and_url()
    headers = get_auth_headers(api_key)
    # Simulated API call to generate client function descriptions
    data = {"description": description, "arguments": arguments, "code": code}
    response = requests.post(f"{api_url}/functions/client/description-generation", headers=headers, json=data)
    return response.json()

def fill_in_missing_function_details(deployable: DeployableRecord, code: str) -> DeployableRecord:
    is_missing_descriptions = (
        not deployable["types"]["description"] or
        not deployable["types"]["returns"]["description"] or
        any(not param["description"] for param in deployable["types"]["params"])
    )
    if is_missing_descriptions:
        try:
            ai_generated = get_function_description(
                deployable["type"],
                deployable["types"]["description"], 
                [{"name": p["name"], "type": p["type"], "description": p.get("description")} for p in deployable["types"]["params"]],
                code
            )
            if not deployable["types"]["description"] and ai_generated.get("description"):
                deployable["types"]["description"] = ai_generated["description"]
                deployable["dirty"] = True

            for i, p in enumerate(deployable["types"]["params"]):
                ai_params = ai_generated.get("arguments", [])
                ai_param = ai_params[i] if ai_params else None
                if ai_param and not p.get("description"):
                    deployable["types"]["params"][i]["description"] =  ai_param["description"]

        except Exception as e:
            print(f"Failed to generate descriptions due to: {str(e)}")
    return deployable

def fill_in_missing_details(deployable: DeployableRecord, code: str) -> DeployableRecord:
    if deployable["type"] in ["server-function", "client-function"]:
        return fill_in_missing_function_details(deployable, code)
    else:
        raise ValueError(f'Unsupported deployable type: "{deployable["type"]}"')


def get_base_url() -> str:
    # Placeholder for getting base URL
    return "."

def get_all_deployables(disable_docs: bool, disable_ai: bool, git_revision: str) -> List[DeployableRecord]:
    print("Searching for poly deployables.")
    base_url = get_base_url() or "."
    possible_deployables = get_all_deployable_files({"includeDirs": [base_url]})
    print(f'Found {len(possible_deployables)} possible deployable file{"s" if len(possible_deployables) != 1 else ""}.')

    found = {}
    for possible in possible_deployables:
        deployable, code = parse_deployable(possible, base_url, git_revision)
        full_name = f'{deployable["context"]}.{deployable["name"]}'
        if full_name in found:
            print(f'ERROR: Prepared {deployable["type"].replace("-", " ")} {full_name}: DUPLICATE')
        else:
            if not disable_ai and not deployable.get("disableAi", False):
                deployable = fill_in_missing_details(deployable, code)
            found[full_name] = deployable
            status = "UPDATED" if deployable.get("dirty", False) and not disable_docs else "OK"
            print(f'Prepared {deployable["type"].replace("-", " ")} {full_name}: {status}')

    return list(found.values())

def parse_deployable(file_path: str, base_url: str, git_revision: str) -> Tuple[DeployableRecord, str]:
    # Simulate parsing deployable; adapt with actual logic to parse deployables
    # This function should return a tuple of (deployable_dict, code_string)
    code = ""
    with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()

    deployable = parse_function_code(code)
    deployable["gitRevision"] = git_revision
    deployable["file"] = file_path
    return deployable, code

def prepare_deployables(lazy: bool = False, disable_docs: bool = False, disable_ai: bool = False) -> None:
    if lazy and is_cache_up_to_date():
        print("Poly deployments are prepared.")
        return

    print("Preparing Poly deployments...")

    prepare_deployable_directory()
    git_revision = get_git_revision()
    # Parse deployable files
    parsed_deployables = get_all_deployables(disable_docs, disable_ai, git_revision)
    if not parsed_deployables:
        print("No deployable files found. Did you define a `polyConfig` within your deployment?")
        return sys.exit(1)
    dirty_deployables = [d for d in parsed_deployables if d["dirty"]]
    if dirty_deployables:
        # Write back deployables files with updated comments
        print(f'Fixing {len(dirty_deployables)} deployable file{"" if len(dirty_deployables) == 1 else "s"}.')
        # NOTE: write_updated_deployable has side effects that update deployable.fileRevision which is in both this list and parsed_deployables
        for deployable in dirty_deployables:
            write_updated_deployable(deployable, disable_docs)
        # Re-stage any updated staged files.
        staged = subprocess.check_output('git diff --name-only --cached', shell=True, text=True, ).split('\n')
        rootPath = subprocess.check_output('git rev-parse --show-toplevel', shell=True, text=True).replace('\n', '')
        for deployable in dirty_deployables:
            try:
                deployableName = deployable["file"].replace('\\', '/').replace(f"{rootPath}/", '')
                if deployableName in staged:
                    print(f'Staging {deployableName}')
                    subprocess.run(['git', 'add', deployableName])
            except:
                print('Warning: File staging failed, check that all files are staged properly.')


    print("Poly deployments are prepared.")
    save_deployable_records(parsed_deployables)
    write_cache_revision(git_revision)
    print("Cached deployables and generated typedefs into polyapi/cached_deployables directory.")
