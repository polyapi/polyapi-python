import os
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
"""


TEMPLATE = """
import uuid


client_id = uuid.uuid4().hex


class {variable_name}:{get_method}
    variable_id = "{variable_id}"

    @staticmethod
    def update(value: {variable_type}):
        resp = variable_update("{variable_id}", value)
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


def render_variable(variable: VariableSpecDto):
    variable_type = _get_variable_type(variable["variable"]["valueType"])
    # Only include get() method if secrecy is not SECRET
    get_method = (
        ""
        if variable["variable"]["secrecy"] == "SECRET"
        else GET_TEMPLATE.format(
            variable_id=variable["id"], variable_type=variable_type
        )
    )
    return TEMPLATE.format(
        variable_name=variable["name"],
        variable_id=variable["id"],
        variable_type=variable_type,
        get_method=get_method,
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
