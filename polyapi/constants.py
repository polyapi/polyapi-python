# TODO figure out arrays and dicts

JSONSCHEMA_TO_PYTHON_TYPE_MAP = {
    "integer": "int",
    "number": "float",
    "string": "str",
    "boolean": "bool",
    "array": "List",
    "object": "Dict",
}


PYTHON_TO_JSONSCHEMA_TYPE_MAP = {
    "int": "integer",
    "float": "number",
    "str": "string",
    "bool": "boolean",
    "List": "array",
    "Dict": "object",
}