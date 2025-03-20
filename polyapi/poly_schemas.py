import os
from typing import Any, Dict, List, Tuple

from polyapi.utils import add_import_to_init, init_the_init, pascalCase

from .typedefs import SchemaSpecDto


SPEC_TEMPLATE = """class {name}(TypedDict):
    pass
"""


def generate_schemas(specs: List[SchemaSpecDto]):
    for spec in specs:
        create_schema(spec)


def create_schema(spec: SchemaSpecDto) -> None:
    folders = ["schemas"]
    if spec["context"]:
        folders += [pascalCase(s) for s in spec["context"].split(".")]

    # build up the full_path by adding all the folders
    full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))

    for idx, folder in enumerate(folders):
        full_path = os.path.join(full_path, folder)
        if not os.path.exists(full_path):
            os.makedirs(full_path)
        next = folders[idx + 1] if idx + 1 < len(folders) else None
        if next:
            add_import_to_init(full_path, next)

    add_schema_to_init(full_path, spec)


def add_schema_to_init(full_path: str, spec: SchemaSpecDto):
    init_the_init(full_path)
    init_path = os.path.join(full_path, "__init__.py")
    with open(init_path, "a") as f:
        f.write(render_poly_schema(spec) + "\n\n")


def render_poly_schema(spec: SchemaSpecDto) -> str:
    return SPEC_TEMPLATE.format(name=pascalCase(spec["name"]))