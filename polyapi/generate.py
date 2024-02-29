import json
import requests
import os
import shutil
from typing import Any, Dict, List, Tuple

from polyapi.auth import render_auth_function
from polyapi.execute import execute_post
from polyapi.webhook import render_webhook_handle

from .typedefs import PropertySpecification, SpecificationDto, VariableSpecDto
from .api import render_api_function
from .server import render_server_function
from .utils import add_import_to_init, get_auth_headers, init_the_init
from .variables import generate_variables
from .config import get_api_key_and_url, initialize_config

SUPPORTED_FUNCTION_TYPES = {
    "apiFunction",
    "authFunction",
    "serverFunction",
    "webhookHandle",
}

SUPPORTED_TYPES = SUPPORTED_FUNCTION_TYPES | {"serverVariable"}


def get_specs() -> List:
    api_key, api_url = get_api_key_and_url()
    assert api_key
    headers = get_auth_headers(api_key)
    url = f"{api_url}/specs"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    else:
        raise NotImplementedError(resp.content)


def parse_function_specs(
    specs: List, limit_ids: List[str] | None  # optional list of ids to limit to
) -> List[Tuple[str, str, str, str, List[PropertySpecification], Dict[str, Any]]]:
    functions = []
    for spec in specs:
        if limit_ids and spec["id"] not in limit_ids:
            continue

        if spec["type"] not in SUPPORTED_FUNCTION_TYPES:
            continue

        function_type = spec["type"]
        function_name = f"poly.{spec['context']}.{spec['name']}"
        function_id = spec["id"]
        arguments: List[PropertySpecification] = [
            arg for arg in spec["function"]["arguments"]
        ]
        functions.append(
            (
                function_type,
                function_name,
                function_id,
                spec["description"],
                arguments,
                spec["function"]["returnType"],
            )
        )
    return functions


def cache_specs(specs: List[SpecificationDto]):
    supported = []
    for spec in specs:
        # this needs to stay in sync with logic in parse_specs
        if spec["type"] in SUPPORTED_TYPES:
            supported.append(spec)

    full_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(full_path, "poly")
    if not os.path.exists(full_path):
        os.makedirs(full_path)

    with open(os.path.join(full_path, "specs.json"), "w") as f:
        f.write(json.dumps(supported))


def read_cached_specs() -> List[SpecificationDto]:
    full_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(full_path, "poly")
    with open(os.path.join(full_path, "specs.json"), "r") as f:
        return json.loads(f.read())


def get_functions_and_parse(limit_ids: List[str] | None = None):
    specs = get_specs()
    cache_specs(specs)
    functions = parse_function_specs(specs, limit_ids=limit_ids)
    return functions


def get_variables() -> List[VariableSpecDto]:
    api_key, api_url = get_api_key_and_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    # TODO do some caching so this and get_functions just do 1 function call
    url = f"{api_url}/specs"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        specs = resp.json()
        return [spec for spec in specs if spec["type"] == "serverVariable"]
    else:
        raise NotImplementedError(resp.content)


def remove_old_library():
    currdir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(currdir, "poly")
    if os.path.exists(path):
        shutil.rmtree(path)

    path = os.path.join(currdir, "vari")
    if os.path.exists(path):
        shutil.rmtree(path)


def generate() -> None:
    initialize_config()

    remove_old_library()

    functions = get_functions_and_parse()
    if functions:
        generate_functions(functions)
    else:
        print(
            "No functions exist yet in this tenant! Empty library initialized. Let's add some functions!"
        )
        exit()

    variables = get_variables()
    if variables:
        generate_variables(variables)

    # indicator to vscode extension that this is a polyapi-python project
    file_path = os.path.join(os.getcwd(), ".polyapi-python")
    open(file_path, "w").close()


def clear() -> None:
    base = os.path.dirname(os.path.abspath(__file__))
    poly_path = os.path.join(base, "poly")
    if os.path.exists(poly_path):
        shutil.rmtree(poly_path)

    vari_path = os.path.join(base, "vari")
    if os.path.exists(vari_path):
        shutil.rmtree(vari_path)
    print("Cleared!")


def save_rendered_specs() -> None:
    specs = read_cached_specs()
    # right now we just support rendered apiFunctions
    api_specs = [spec for spec in specs if spec["type"] == "apiFunction"]
    for spec in api_specs:
        assert spec["function"]
        func_str, type_defs = render_spec(
            spec["type"],
            spec["name"],
            spec["id"],
            spec["description"],
            spec["function"]["arguments"],
            spec["function"]["returnType"],
        )
        data = {
            "language": "python",
            "apiFunctionId": spec["id"],
            "signature": func_str,
            "typedefs": type_defs,
        }
        resp = execute_post("/functions/rendered-specs", data)
        print("adding", spec["context"], spec["name"])
        assert resp.status_code == 201, (resp.text, resp.status_code)


def render_spec(
    function_type: str,
    function_name: str,
    function_id: str,
    function_description: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
):
    if function_type == "apiFunction":
        func_str, func_type_defs = render_api_function(
            function_type,
            function_name,
            function_id,
            function_description,
            arguments,
            return_type,
        )
    elif function_type == "serverFunction":
        func_str, func_type_defs = render_server_function(
            function_type,
            function_name,
            function_id,
            function_description,
            arguments,
            return_type,
        )
    elif function_type == "authFunction":
        func_str, func_type_defs = render_auth_function(
            function_type,
            function_name,
            function_id,
            function_description,
            arguments,
            return_type,
        )
    elif function_type == "webhookHandle":
        func_str, func_type_defs = render_webhook_handle(
            function_type,
            function_name,
            function_id,
            function_description,
            arguments,
            return_type,
        )
    return func_str, func_type_defs


def add_function_file(
    function_type: str,
    full_path: str,
    function_name: str,
    function_id: str,
    function_description: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
):
    # first lets add the import to the __init__
    init_the_init(full_path)

    func_str, func_type_defs = render_spec(
        function_type,
        function_name,
        function_id,
        function_description,
        arguments,
        return_type,
    )

    if func_str:
        # add function to init
        init_path = os.path.join(full_path, "__init__.py")
        with open(init_path, "a") as f:
            f.write(f"\n\nfrom . import _{function_name}\n\n{func_str}")

        # add type_defs to underscore file
        file_path = os.path.join(full_path, f"_{function_name}.py")
        with open(file_path, "w") as f:
            f.write(func_type_defs)


def create_function(
    function_type: str,
    path: str,
    function_id: str,
    function_description: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
) -> None:
    full_path = os.path.dirname(os.path.abspath(__file__))

    folders = path.split(".")
    for idx, folder in enumerate(folders):
        if idx + 1 == len(folders):
            # special handling for final level
            add_function_file(
                function_type,
                full_path,
                folder,
                function_id,
                function_description,
                arguments,
                return_type,
            )
        else:
            full_path = os.path.join(full_path, folder)
            if not os.path.exists(full_path):
                os.makedirs(full_path)

            # append to __init__.py file if nested folders
            next = folders[idx + 1] if idx + 2 < len(folders) else ""
            if next:
                init_the_init(full_path)
                add_import_to_init(full_path, next)


# TODO create the socket and pass to create_function?


def generate_functions(functions: List) -> None:
    for func in functions:
        create_function(*func)
