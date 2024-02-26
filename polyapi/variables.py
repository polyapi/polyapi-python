import os
from typing import List

from polyapi.schema import map_primitive_types
from polyapi.typedefs import PropertyType, VariableSpecDto
from polyapi.utils import add_import_to_init, init_the_init


# GET is only included if the variable is not a secret
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
    for variable in variables:
        create_variable(variable)


def render_variable(variable: VariableSpecDto):
    variable_type = _get_variable_type(variable["variable"]["valueType"])
    get_method = (
        ""
        if variable["variable"]["secret"]
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
    folders = ["vari"]
    if variable["context"]:
        folders += variable["context"].split(".")

    # build up the full_path by adding all the folders
    full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))

    for idx, folder in enumerate(folders):
        full_path = os.path.join(full_path, folder)
        if not os.path.exists(full_path):
            os.makedirs(full_path)
        next = folders[idx + 1] if idx + 1 < len(folders) else None
        if next:
            add_import_to_init(full_path, next)

    add_variable_to_init(full_path, variable)


def add_variable_to_init(full_path: str, variable: VariableSpecDto):
    init_the_init(full_path)
    init_path = os.path.join(full_path, "__init__.py")
    with open(init_path, "a") as f:
        f.write(render_variable(variable) + "\n\n")
