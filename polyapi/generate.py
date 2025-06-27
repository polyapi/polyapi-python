import json
import requests
import os
import shutil
import logging
import tempfile
from typing import Any, List, Optional, Tuple, cast

from .auth import render_auth_function
from .client import render_client_function
from .poly_schemas import generate_schemas
from .webhook import render_webhook_handle

from .typedefs import PropertySpecification, SchemaSpecDto, SpecificationDto, VariableSpecDto
from .api import render_api_function
from .server import render_server_function
from .utils import add_import_to_init, get_auth_headers, init_the_init, print_green, to_func_namespace
from .variables import generate_variables
from .config import get_api_key_and_url, get_direct_execute_config, get_cached_generate_args

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


def get_specs(contexts: Optional[List[str]] = None, names: Optional[List[str]] = None, function_ids: Optional[List[str]] = None, no_types: bool = False) -> List:
    api_key, api_url = get_api_key_and_url()
    assert api_key
    headers = get_auth_headers(api_key)
    url = f"{api_url}/specs"
    params: Any = {"noTypes": str(no_types).lower()}

    if contexts:
        params["contexts"] = contexts
    
    if names:
        params["names"] = names
        
    if function_ids:
        params["functionIds"] = function_ids

    # Add apiFunctionDirectExecute parameter if direct execute is enabled
    if get_direct_execute_config():
        params["apiFunctionDirectExecute"] = "true"

    resp = requests.get(url, headers=headers, params=params)
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


def replace_poly_refs_in_schemas(specs: List[SchemaSpecDto], schema_index):
    spec_idxs_to_remove = []
    for idx, spec in enumerate(specs):
        try:
            spec["definition"] = resolve_poly_refs(spec["definition"], schema_index)
        except Exception:
            # print()
            print(f"{spec['context']}.{spec['name']} (id: {spec['id']}) failed to resolve poly refs, skipping!")
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
        if not spec:
            continue

        # For no_types mode, we might not have function data, but we still want to include the spec
        # if it's a supported function type
        if spec["type"] not in SUPPORTED_FUNCTION_TYPES:
            continue

        # Skip if we have a limit and this spec is not in it
        if limit_ids and spec.get("id") not in limit_ids:
            continue

        # For customFunction, check language if we have function data
        if spec["type"] == "customFunction":
            if spec.get("language") and spec["language"] != "python":
                # poly libraries only support client functions of same language
                continue

        # Functions with serverSideAsync True will always return a Dict with execution ID
        if spec.get('serverSideAsync') and spec.get("function"):
            spec['function']['returnType'] = {'kind': 'plain', 'value': 'object'}  # type: ignore

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


def create_empty_schemas_module():
    """Create an empty schemas module for no-types mode so user code can still import from polyapi.schemas"""
    currdir = os.path.dirname(os.path.abspath(__file__))
    schemas_path = os.path.join(currdir, "schemas")
    
    # Create the schemas directory
    if not os.path.exists(schemas_path):
        os.makedirs(schemas_path)
    
    # Create an __init__.py file with dynamic schema resolution
    init_path = os.path.join(schemas_path, "__init__.py")
    with open(init_path, "w") as f:
        f.write('''"""Empty schemas module for no-types mode"""
from typing import Any, Dict

class _GenericSchema(Dict[str, Any]):
    """Generic schema type that acts like a Dict for no-types mode"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class _SchemaModule:
    """Dynamic module that returns itself for attribute access, allowing infinite nesting"""
    
    def __getattr__(self, name: str):
        # For callable access (like schemas.Response()), return the generic schema class
        # For further attribute access (like schemas.random.random2), return self to allow nesting
        return _NestedSchemaAccess()
    
    def __call__(self, *args, **kwargs):
        # If someone tries to call the module itself, return a generic schema
        return _GenericSchema(*args, **kwargs)
    
    def __dir__(self):
        # Return common schema names for introspection
        return ['Response', 'Request', 'Error', 'Data', 'Result']

class _NestedSchemaAccess:
    """Handles nested attribute access and final callable resolution"""
    
    def __getattr__(self, name: str):
        # Continue allowing nested access
        return _NestedSchemaAccess()
    
    def __call__(self, *args, **kwargs):
        # When finally called, return a generic schema instance
        return _GenericSchema(*args, **kwargs)
    
    def __class_getitem__(cls, item):
        # Support type annotations like schemas.Response[str]
        return _GenericSchema

# Replace this module with our dynamic module
import sys
sys.modules[__name__] = _SchemaModule()
''')


def generate_from_cache() -> None:
    """
    Generate using cached values after non-explicit call.
    """
    cached_contexts, cached_names, cached_function_ids, cached_no_types = get_cached_generate_args()
    
    generate(
        contexts=cached_contexts, 
        names=cached_names, 
        function_ids=cached_function_ids, 
        no_types=cached_no_types
    )


def generate(contexts: Optional[List[str]] = None, names: Optional[List[str]] = None, function_ids: Optional[List[str]] = None, no_types: bool = False) -> None:
    generate_msg = f"Generating Poly Python SDK for contexts ${contexts}..." if contexts else "Generating Poly Python SDK..."
    print(generate_msg, end="", flush=True)
    remove_old_library()

    specs = get_specs(contexts=contexts, names=names, function_ids=function_ids, no_types=no_types)
    cache_specs(specs)

    limit_ids: List[str] = []  # useful for narrowing down generation to a single function to debug
    functions = parse_function_specs(specs, limit_ids=limit_ids)

    # Only process schemas if no_types is False
    if not no_types:
        schemas = get_schemas()
        schema_index = build_schema_index(schemas)
        if schemas:
            schema_limit_ids: List[str] = []  # useful for narrowing down generation to a single function to debug
            schemas = replace_poly_refs_in_schemas(schemas, schema_index)
            generate_schemas(schemas, limit_ids=schema_limit_ids)
        
        functions = replace_poly_refs_in_functions(functions, schema_index)
    else:
        # When no_types is True, we still need to process functions but without schema resolution
        # Use an empty schema index to avoid poly-ref resolution
        schema_index = {}
        
        # Create an empty schemas module so user code can still import from polyapi.schemas
        create_empty_schemas_module()

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


def render_spec(spec: SpecificationDto) -> Tuple[str, str]:
    function_type = spec["type"]
    function_description = spec["description"]
    function_name = spec["name"]
    function_context = spec["context"]
    function_id = spec["id"]

    arguments: List[PropertySpecification] = []
    return_type: Any = {}
    if spec.get("function"):
        assert spec["function"]
        # Handle cases where arguments might be missing or None
        if spec["function"].get("arguments"):
            arguments = [
                arg for arg in spec["function"]["arguments"]
            ]
        
        # Handle cases where returnType might be missing or None
        if spec["function"].get("returnType"):
            return_type = spec["function"]["returnType"]
        else:
            # Provide a fallback return type when missing
            return_type = {"kind": "any"}

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
            spec.get("code", ""),
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
    """
    Atomically add a function file to prevent partial corruption during generation failures.
    
    This function generates all content first, then writes files atomically using temporary files
    to ensure that either the entire operation succeeds or no changes are made to the filesystem.
    """
    try:
        # first lets add the import to the __init__
        init_the_init(full_path)

        func_str, func_type_defs = render_spec(spec)

        if not func_str:
            # If render_spec failed and returned empty string, don't create any files
            raise Exception("Function rendering failed - empty function string returned")

        # Prepare all content first before writing any files
        func_namespace = to_func_namespace(function_name)
        init_path = os.path.join(full_path, "__init__.py")
        func_file_path = os.path.join(full_path, f"{func_namespace}.py")
        
        # Read current __init__.py content if it exists
        init_content = ""
        if os.path.exists(init_path):
            with open(init_path, "r") as f:
                init_content = f.read()
        
        # Prepare new content to append to __init__.py
        new_init_content = init_content + f"\n\nfrom . import {func_namespace}\n\n{func_str}"
        
        # Use temporary files for atomic writes
        # Write to __init__.py atomically
        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=full_path, suffix=".tmp") as temp_init:
            temp_init.write(new_init_content)
            temp_init_path = temp_init.name
        
        # Write to function file atomically  
        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=full_path, suffix=".tmp") as temp_func:
            temp_func.write(func_type_defs)
            temp_func_path = temp_func.name
        
        # Atomic operations: move temp files to final locations
        shutil.move(temp_init_path, init_path)
        shutil.move(temp_func_path, func_file_path)
        
    except Exception as e:
        # Clean up any temporary files that might have been created
        try:
            if 'temp_init_path' in locals() and os.path.exists(temp_init_path):
                os.unlink(temp_init_path)
            if 'temp_func_path' in locals() and os.path.exists(temp_func_path):
                os.unlink(temp_func_path)
        except:
            pass  # Best effort cleanup
        
        # Re-raise the original exception
        raise e


def create_function(
    spec: SpecificationDto
) -> None:
    """
    Create a function with atomic directory and file operations.
    
    Tracks directory creation to enable cleanup on failure.
    """
    full_path = os.path.dirname(os.path.abspath(__file__))
    folders = f"poly.{spec['context']}.{spec['name']}".split(".")
    created_dirs = []  # Track directories we create for cleanup on failure
    
    try:
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
                    created_dirs.append(full_path)  # Track for cleanup

                # append to __init__.py file if nested folders
                next = folders[idx + 1] if idx + 2 < len(folders) else ""
                if next:
                    init_the_init(full_path)
                    add_import_to_init(full_path, next)
                    
    except Exception as e:
        # Clean up directories we created (in reverse order)
        for dir_path in reversed(created_dirs):
            try:
                if os.path.exists(dir_path) and not os.listdir(dir_path):  # Only remove if empty
                    os.rmdir(dir_path)
            except:
                pass  # Best effort cleanup
        
        # Re-raise the original exception
        raise e


def generate_functions(functions: List[SpecificationDto]) -> None:
    failed_functions = []
    for func in functions:
        try:
            create_function(func)
        except Exception as e:
            function_path = f"{func.get('context', 'unknown')}.{func.get('name', 'unknown')}"
            function_id = func.get('id', 'unknown')
            failed_functions.append(f"{function_path} (id: {function_id})")
            logging.warning(f"WARNING: Failed to generate function {function_path} (id: {function_id}): {str(e)}")
            continue
    
    if failed_functions:
        logging.warning(f"WARNING: {len(failed_functions)} function(s) failed to generate:")
        for failed_func in failed_functions:
            logging.warning(f"  - {failed_func}")
