import os
from typing import Any, Dict, List, Tuple

from polyapi.schema import wrapped_generate_schema_types
from polyapi.utils import add_import_to_init, init_the_init
from tests.test_schema import SCHEMA

from .typedefs import SchemaSpecDto

SCHEMA_CODE_IMPORTS = """from typing_extensions import TypedDict, NotRequired


"""


FALLBACK_SPEC_TEMPLATE = """class {name}(TypedDict, total=False):
    ''' unable to generate schema for {name}, defaulting to permissive type '''
    pass
"""


def generate_schemas(specs: List[SchemaSpecDto]):
    for spec in specs:
        create_schema(spec)


def create_schema(spec: SchemaSpecDto) -> None:
    folders = ["schemas"]
    if spec["context"]:
        folders += [s for s in spec["context"].split(".")]

    # build up the full_path by adding all the folders
    full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))

    for idx, folder in enumerate(folders):
        full_path = os.path.join(full_path, folder)
        if not os.path.exists(full_path):
            os.makedirs(full_path)
        next = folders[idx + 1] if idx + 1 < len(folders) else None
        if next:
            add_import_to_init(full_path, next, code_imports=SCHEMA_CODE_IMPORTS)

    add_schema_to_init(full_path, spec)


def add_schema_to_init(full_path: str, spec: SchemaSpecDto):
    init_the_init(full_path, code_imports="")
    init_path = os.path.join(full_path, "__init__.py")
    with open(init_path, "a") as f:
        f.write(render_poly_schema(spec) + "\n\n")


def render_poly_schema(spec: SchemaSpecDto) -> str:
    definition = spec["definition"]
    if not definition.get("type"):
        definition["type"] = "object"
    root, schema_types = wrapped_generate_schema_types(
        definition, root=spec["name"], fallback_type=Dict
    )
    return schema_types
    # return FALLBACK_SPEC_TEMPLATE.format(name=spec["name"])
