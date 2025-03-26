import json
import requests
import os
import shutil
from typing import List, cast

from .auth import render_auth_function
from .client import render_client_function
from .poly_schemas import generate_schemas
from .webhook import render_webhook_handle

from .typedefs import PropertySpecification, SchemaSpecDto, SpecificationDto, VariableSpecDto
from .api import render_api_function
from .server import render_server_function
from .utils import add_import_to_init, get_auth_headers, init_the_init, print_green, to_func_namespace
from .variables import generate_variables
from .config import get_api_key_and_url

SUPPORTED_FUNCTION_TYPES = {
    "apiFunction",
    "authFunction",
    "customFunction",  # client function - this is badly named in /specs atm
    "serverFunction",
    "webhookHandle",
}

SUPPORTED_TYPES = SUPPORTED_FUNCTION_TYPES | {"serverVariable", "schema", "snippet"}


X_POLY_REF_WARNING = '''"""
x-poly-ref:
  path:'''

X_POLY_REF_BETTER_WARNING = '''"""
Unresolved schema, please add the following schema to complete it:
  path:'''


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


def build_schema_index(items):
    index = {}
    for item in items:
        if item.get("type") == "schema" and "contextName" in item:
            index[item["contextName"]] = {**item.get("definition", {}), "name": item.get("name")}
    return index


def resolve_poly_refs(obj, schema_index):
    if isinstance(obj, dict):
        if "x-poly-ref" in obj:
            ref = obj["x-poly-ref"]
            if isinstance(ref, dict) and "path" in ref:
                path = ref["path"]
                if path in schema_index:
                    return resolve_poly_refs(schema_index[path], schema_index)
                else:
                    return obj
        return {k: resolve_poly_refs(v, schema_index) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_poly_refs(item, schema_index) for item in obj]
    else:
        return obj


def replace_poly_refs_in_functions(specs: List[SpecificationDto], schema_index):
    spec_idxs_to_remove = []
    for idx, spec in enumerate(specs):
        if spec.get("type") in ("apiFunction", "customFunction", "serverFunction"):
            func = spec.get("function")
            if func:
                try:
                    spec["function"] = resolve_poly_refs(func, schema_index)
                except Exception:
                    # print()
                    # print(f"{spec['context']}.{spec['name']} (id: {spec['id']}) failed to resolve poly refs, skipping!")
                    spec_idxs_to_remove.append(idx)

    # reverse the list so we pop off later indexes first
    spec_idxs_to_remove.reverse()

    for idx in spec_idxs_to_remove:
        specs.pop(idx)

    return specs


def parse_function_specs(
    specs: List[SpecificationDto],
    limit_ids: List[str] | None = None,  # optional list of ids to limit to
) -> List[SpecificationDto]:
    functions = []
    for spec in specs:
        if not spec or "function" not in spec:
            continue

        if not spec["function"]:
            continue

        if limit_ids and spec["id"] not in limit_ids:
            continue

        if spec["type"] not in SUPPORTED_FUNCTION_TYPES:
            continue

        if spec["type"] == "customFunction" and spec["language"] != "python":
            # poly libraries only support client functions of same language
            continue

        functions.append(spec)

    return functions


def cache_specs(specs: List[SpecificationDto]):
    supported = []
    for spec in specs:
        # this needs to stay in sync with logic in parse_specs
        if spec["type"] in SUPPORTED_TYPES:
            supported.append(spec)

    full_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(full_path, "poly")
    try:
        if not os.path.exists(full_path):
            os.makedirs(full_path)

        with open(os.path.join(full_path, "specs.json"), "w") as f:
            f.write(json.dumps(supported))
    except Exception as e:
        print("Failed to cache specs", e)


def read_cached_specs() -> List[SpecificationDto]:
    full_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(full_path, "poly")
    with open(os.path.join(full_path, "specs.json"), "r") as f:
        return json.loads(f.read())


def get_variables() -> List[VariableSpecDto]:
    specs = read_cached_specs()
    return [cast(VariableSpecDto, spec) for spec in specs if spec["type"] == "serverVariable"]


def get_schemas() -> List[SchemaSpecDto]:
    specs = read_cached_specs()
    return [cast(SchemaSpecDto, spec) for spec in specs if spec["type"] == "schema"]


def remove_old_library():
    currdir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(currdir, "poly")
    if os.path.exists(path):
        shutil.rmtree(path)

    path = os.path.join(currdir, "vari")
    if os.path.exists(path):
        shutil.rmtree(path)

    path = os.path.join(currdir, "schemas")
    if os.path.exists(path):
        shutil.rmtree(path)


def generate() -> None:
    print("Generating Poly Python SDK...", end="", flush=True)
    remove_old_library()

    limit_ids: List[str] = []  # useful for narrowing down generation to a single function to debug

    specs = get_specs()
    cache_specs(specs)
    functions = parse_function_specs(specs, limit_ids=limit_ids)

    schemas = get_schemas()
    if schemas:
        generate_schemas(schemas)

    schema_index = build_schema_index(schemas)
    functions = replace_poly_refs_in_functions(functions, schema_index)

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

    print_green("DONE")


def clear() -> None:
    base = os.path.dirname(os.path.abspath(__file__))
    poly_path = os.path.join(base, "poly")
    if os.path.exists(poly_path):
        shutil.rmtree(poly_path)

    vari_path = os.path.join(base, "vari")
    if os.path.exists(vari_path):
        shutil.rmtree(vari_path)
    print("Cleared!")


def render_spec(spec: SpecificationDto):
    function_type = spec["type"]
    function_description = spec["description"]
    function_name = spec["name"]
    function_context = spec["context"]
    function_id = spec["id"]

    arguments: List[PropertySpecification] = []
    return_type = {}
    if spec["function"]:
        arguments = [
            arg for arg in spec["function"]["arguments"]
        ]
        return_type = spec["function"]["returnType"]

    if function_type == "apiFunction":
        func_str, func_type_defs = render_api_function(
            function_type,
            function_name,
            function_id,
            function_description,
            arguments,
            return_type,
        )
    elif function_type == "customFunction":
        func_str, func_type_defs = render_client_function(
            function_name,
            spec["code"],
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
            function_context,
            function_name,
            function_id,
            function_description,
            arguments,
            return_type,
        )

    if X_POLY_REF_WARNING in func_type_defs:
        # this indicates that jsonschema_gentypes has detected an x-poly-ref
        # let's add a more user friendly error explaining what is going on
        func_type_defs = func_type_defs.replace(X_POLY_REF_WARNING, X_POLY_REF_BETTER_WARNING)

    return func_str, func_type_defs


def add_function_file(
    full_path: str,
    function_name: str,
    spec: SpecificationDto,
):
    # first lets add the import to the __init__
    init_the_init(full_path)

    func_str, func_type_defs = render_spec(spec)

    if func_str:
        # add function to init
        init_path = os.path.join(full_path, "__init__.py")
        with open(init_path, "a") as f:
            f.write(f"\n\nfrom . import {to_func_namespace(function_name)}\n\n{func_str}")

        # add type_defs to underscore file
        file_path = os.path.join(full_path, f"{to_func_namespace(function_name)}.py")
        with open(file_path, "w") as f:
            f.write(func_type_defs)


def create_function(
    spec: SpecificationDto
) -> None:
    full_path = os.path.dirname(os.path.abspath(__file__))
    folders = f"poly.{spec['context']}.{spec['name']}".split(".")
    for idx, folder in enumerate(folders):
        if idx + 1 == len(folders):
            # special handling for final level
            add_function_file(
                full_path,
                folder,
                spec,
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


def generate_functions(functions: List[SpecificationDto]) -> None:
    for func in functions:
        create_function(func)
