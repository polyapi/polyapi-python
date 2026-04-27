import os
import re
import keyword
import logging
import tempfile
import shutil
from typing import List

from polyapi.schema import map_primitive_types
from polyapi.typedefs import PropertyType, VariableSpecDto, Secrecy
from polyapi.utils import add_import_to_init, init_the_init


# GET is only included if the variable is not SECRET
GET_TEMPLATE = """
    @staticmethod
    def get() -> {variable_type}:
        resp = variable_get("{variable_id}")
        return resp.text

    @staticmethod
    async def get_async() -> {variable_type}:
        resp = await variable_get_async("{variable_id}")
        return resp.text
"""

# Appended to GET_TEMPLATE for object variables; opt-in parsed access with dot notation
GET_PARSED_TEMPLATE = """
    @staticmethod
    def get_parsed() -> "{parsed_type}":
        resp = variable_get("{variable_id}")
        return {parsed_type}.from_dict(json.loads(resp.text))

    @staticmethod
    async def get_parsed_async() -> "{parsed_type}":
        resp = await variable_get_async("{variable_id}")
        return {parsed_type}.from_dict(json.loads(resp.text))
"""


TEMPLATE = """
from polyapi.poly.client_id import client_id
{type_class}

class {variable_name}:{get_method}
    variable_id = "{variable_id}"

    @staticmethod
    def update(value: {variable_type}):
        resp = variable_update("{variable_id}", value)
        return resp.json()

    @staticmethod
    async def update_async(value: {variable_type}):
        resp = await variable_update_async("{variable_id}", value)
        return resp.json()

    @classmethod
    async def onUpdate(cls, callback):
        api_key, base_url = get_api_key_and_url()
        socket = socketio.AsyncClient()
        await socket.connect(base_url, transports=['websocket'], namespaces=['/events'])

        async def unregisterEventHandler():
            # TODO
            # socket.off("handleVariableChangeEvent:{variable_id}");
            await socket.emit("unregisterVariableChangeEventHandler", {{
                "clientID": client_id,
                "variableId": cls.variable_id,
                "apiKey": api_key,
            }}, namespace='/events')

        def registerCallback(registered):
            if registered:
                socket.on("handleVariableChangeEvent:{variable_id}", callback, namespace="/events")

        await socket.emit("registerVariableChangeEventHandler", {{
            "clientID": client_id,
            "variableId": cls.variable_id,
            "apiKey": api_key,
        }}, namespace='/events', callback=registerCallback)

        await socket.wait()

        return unregisterEventHandler

    @staticmethod
    def inject(path=None) -> {variable_type}:
        return {{
            "type": "PolyVariable",
            "id": "{variable_id}",
            "path": path,
        }}  # type: ignore
"""


def generate_variables(variables: List[VariableSpecDto]):
    failed_variables = []
    for variable in variables:
        try:
            create_variable(variable)
        except Exception as e:
            variable_path = f"{variable.get('context', 'unknown')}.{variable.get('name', 'unknown')}"
            variable_id = variable.get('id', 'unknown')
            failed_variables.append(f"{variable_path} (id: {variable_id})")
            logging.warning(f"WARNING: Failed to generate variable {variable_path} (id: {variable_id}): {str(e)}")
            continue
    
    if failed_variables:
        logging.warning(f"WARNING: {len(failed_variables)} variable(s) failed to generate:")
        for failed_var in failed_variables:
            logging.warning(f"  - {failed_var}")


def _sanitize_field_name(name: str) -> str:
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if sanitized and sanitized[0].isdigit():
        sanitized = '_' + sanitized
    if not sanitized:
        sanitized = 'field_'
    if keyword.iskeyword(sanitized):
        sanitized += '_'
    return sanitized


def _schema_to_dataclass(variable_name: str, schema: dict) -> tuple:
    """Generate a @dataclass from a variable's JSON schema properties.

    Returns (class_name, class_code), or (None, None) if schema has no properties.
    """
    properties = schema.get("properties", {})
    if not properties:
        return None, None

    required = set(schema.get("required", []))
    class_name = "".join(w.capitalize() for w in variable_name.replace("-", "_").split("_"))

    _TYPE_MAP = {"string": "str", "integer": "int", "number": "float", "boolean": "bool", "object": "Dict", "array": "List"}
    req_fields, opt_fields = [], []
    # (json_key, python_field_name) pairs for from_dict
    field_map = []
    for prop, prop_schema in properties.items():
        py_type = _TYPE_MAP.get(prop_schema.get("type", "string"), "Any")
        safe = _sanitize_field_name(prop)
        field_map.append((prop, safe))
        if prop in required:
            req_fields.append(f"    {safe}: {py_type}")
        else:
            opt_fields.append(f"    {safe}: Optional[{py_type}] = field(default=None)")

    from_dict_args = ", ".join(f'{safe}=d.get("{key}")' for key, safe in field_map)
    from_dict_lines = [
        "",
        "    @classmethod",
        "    def from_dict(cls, d):",
        f"        return cls({from_dict_args})",
    ]

    lines = ["from dataclasses import dataclass, field", "", "@dataclass", f"class {class_name}:"]
    lines.extend(req_fields)
    lines.extend(opt_fields)
    if not req_fields and not opt_fields:
        lines.append("    pass")
    lines.extend(from_dict_lines)
    return class_name, "\n".join(lines)


def render_variable(variable: VariableSpecDto):
    variable_type = _get_variable_type(variable["variable"]["valueType"])
    is_secret = variable["variable"]["secrecy"] == "SECRET"
    is_object = variable_type in ("Dict", "Any")

    schema = variable["variable"]["valueType"].get("schema", {})
    class_name, type_class_code = _schema_to_dataclass(variable["name"], schema) if schema else (None, None)
    parsed_type = class_name or "DotDict"
    type_class = f"\n{type_class_code}\n" if type_class_code else ""

    if is_secret:
        get_method = ""
    else:
        get_method = GET_TEMPLATE.format(variable_id=variable["id"], variable_type=variable_type)
        if is_object:
            get_method += GET_PARSED_TEMPLATE.format(variable_id=variable["id"], parsed_type=parsed_type)

    return TEMPLATE.format(
        variable_name=variable["name"],
        variable_id=variable["id"],
        variable_type=variable_type,
        get_method=get_method,
        type_class=type_class,
    )


def _get_variable_type(type_spec: PropertyType) -> str:
    # simplified version of _get_type from api.py
    if type_spec["kind"] == "plain":
        value = type_spec["value"]
        if value.endswith("[]"):
            primitive = map_primitive_types(value[:-2])
            return f"List[{primitive}]"
        else:
            return map_primitive_types(value)
    elif type_spec["kind"] == "primitive":
        return map_primitive_types(type_spec["type"])
    elif type_spec["kind"] == "array":
        return "List"
    elif type_spec["kind"] == "void":
        return "None"
    elif type_spec["kind"] == "object":
        return "Dict"
    elif type_spec["kind"] == "any":
        return "Any"
    else:
        return "Any"


def create_variable(variable: VariableSpecDto) -> None:
    """
    Create a variable with atomic directory and file operations.
    
    Tracks directory creation to enable cleanup on failure.
    """
    folders = ["vari"]
    if variable["context"]:
        folders += variable["context"].split(".")

    # build up the full_path by adding all the folders
    full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    created_dirs = []  # Track directories we create for cleanup on failure

    try:
        for idx, folder in enumerate(folders):
            full_path = os.path.join(full_path, folder)
            if not os.path.exists(full_path):
                os.makedirs(full_path)
                created_dirs.append(full_path)  # Track for cleanup
            next = folders[idx + 1] if idx + 1 < len(folders) else None
            if next:
                add_import_to_init(full_path, next)

        add_variable_to_init(full_path, variable)
        
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


def add_variable_to_init(full_path: str, variable: VariableSpecDto):
    """
    Atomically add a variable to __init__.py to prevent partial corruption during generation failures.
    
    This function generates all content first, then writes the file atomically using temporary files
    to ensure that either the entire operation succeeds or no changes are made to the filesystem.
    """
    try:
        init_the_init(full_path)
        init_path = os.path.join(full_path, "__init__.py")
        
        # Generate variable content first
        variable_content = render_variable(variable)
        if not variable_content:
            raise Exception("Variable rendering failed - empty content returned")
        
        # Read current __init__.py content if it exists
        init_content = ""
        if os.path.exists(init_path):
            with open(init_path, "r") as f:
                init_content = f.read()
        
        # Prepare new content to append
        new_init_content = init_content + variable_content + "\n\n"
        
        # Write to temporary file first, then atomic move
        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=full_path, suffix=".tmp") as temp_file:
            temp_file.write(new_init_content)
            temp_file_path = temp_file.name
        
        # Atomic operation: move temp file to final location
        shutil.move(temp_file_path, init_path)
        
    except Exception as e:
        # Clean up temporary file if it exists
        try:
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        except:
            pass  # Best effort cleanup
        
        # Re-raise the original exception
        raise e
