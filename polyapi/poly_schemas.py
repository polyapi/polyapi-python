import os
from typing import Any, Dict, List, Tuple

from polyapi.schema import wrapped_generate_schema_types
from polyapi.utils import add_import_to_init, init_the_init, to_func_namespace

from .typedefs import SchemaSpecDto

SCHEMA_CODE_IMPORTS = """from typing_extensions import TypedDict, NotRequired

__all__ = []


"""


FALLBACK_SPEC_TEMPLATE = """class {name}(TypedDict, total=False):
    ''' unable to generate schema for {name}, defaulting to permissive type '''
    pass
"""


def generate_schemas(specs: List[SchemaSpecDto], limit_ids: List[str] = None):
    if limit_ids:
        for spec in specs:
            if spec["id"] in limit_ids:
                create_schema(spec)
    else:
        for spec in specs:
            create_schema(spec)


def add_schema_file(
    full_path: str,
    schema_name: str,
    spec: SchemaSpecDto,
):
    # first lets add the import to the __init__
    init_the_init(full_path, SCHEMA_CODE_IMPORTS)

    if not spec["definition"].get("title"):
        # very empty schemas like mews.Unit are possible
        # add a title here to be sure they render
        spec["definition"]["title"] = schema_name

    schema_defs = render_poly_schema(spec)

    if schema_defs:
        # add function to init
        init_path = os.path.join(full_path, "__init__.py")
        with open(init_path, "a") as f:
            f.write(f"\n\nfrom ._{to_func_namespace(schema_name)} import {schema_name}\n__all__.append('{schema_name}')\n")

        # add type_defs to underscore file
        file_path = os.path.join(full_path, f"_{to_func_namespace(schema_name)}.py")
        with open(file_path, "w") as f:
            f.write(schema_defs)


def create_schema(
    spec: SchemaSpecDto
) -> None:
    full_path = os.path.dirname(os.path.abspath(__file__))
    folders = f"schemas.{spec['context']}.{spec['name']}".split(".")
    for idx, folder in enumerate(folders):
        if idx + 1 == len(folders):
            # special handling for final level
            add_schema_file(
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
                init_the_init(full_path, SCHEMA_CODE_IMPORTS)
                add_import_to_init(full_path, next)


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
