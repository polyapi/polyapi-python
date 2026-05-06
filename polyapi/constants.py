JSONSCHEMA_TO_PYTHON_TYPE_MAP = {
    "integer": "int",
    "number": "float",
    "string": "str",
    "boolean": "bool",
    "array": "list",
    "object": "dict",
    "function": "Callable",
    "void": "None",
}


PYTHON_TO_JSONSCHEMA_TYPE_MAP = {
    "int": "integer",
    "float": "number",
    "str": "string",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "Callable": "function",
    "None": "void",
    # Keep uppercase aliases for backwards compatibility
    "List": "array",
    "Dict": "object",
}

BASIC_PYTHON_TYPES = set(PYTHON_TO_JSONSCHEMA_TYPE_MAP.keys())

# initial pass
SAFE_IMPORT_MODULES = {
    "typing", "typing_extensions", "types",
    "re", "os", "sys", "json", "datetime", "math",
    "collections", "enum", "dataclasses", "abc",
    "functools", "itertools", "operator",
    "urllib", "urllib.parse", "pathlib",
    "copy", "hashlib", "uuid",
}

# TODO wire this up to config-variables in future so clients can modify
SUPPORT_EMAIL = 'support@polyapi.io'