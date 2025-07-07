import os
import logging
import tempfile
import shutil
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
    failed_schemas = []
    successful_schemas = []
    if limit_ids:
        for spec in specs:
            if spec["id"] in limit_ids:
                try:
                    create_schema(spec)
                    successful_schemas.append(f"{spec.get('context', 'unknown')}.{spec.get('name', 'unknown')}")
                except Exception as e:
                    schema_path = f"{spec.get('context', 'unknown')}.{spec.get('name', 'unknown')}"
                    schema_id = spec.get('id', 'unknown')
                    failed_schemas.append(f"{schema_path} (id: {schema_id})")
                    logging.warning(f"WARNING: Failed to generate schema {schema_path} (id: {schema_id}): {str(e)}")
                    continue
    else:
        for spec in specs:
            try:
                create_schema(spec)
                successful_schemas.append(f"{spec.get('context', 'unknown')}.{spec.get('name', 'unknown')}")
            except Exception as e:
                schema_path = f"{spec.get('context', 'unknown')}.{spec.get('name', 'unknown')}"
                schema_id = spec.get('id', 'unknown')
                failed_schemas.append(f"{schema_path} (id: {schema_id})")
                logging.warning(f"WARNING: Failed to generate schema {schema_path} (id: {schema_id}): {str(e)}")
                continue
    
    if failed_schemas:
        logging.warning(f"WARNING: {len(failed_schemas)} schema(s) failed to generate:")
        for failed_schema in failed_schemas:
            logging.warning(f"  - {failed_schema}")
        logging.warning(f"Successfully generated {len(successful_schemas)} schema(s)")


def validate_schema_content(schema_content: str, schema_name: str) -> bool:
    """
    Validate that the schema content is meaningful and not just imports.
    Returns True if the schema is valid, False otherwise.
    """
    if not schema_content or not schema_content.strip():
        logging.debug(f"Schema {schema_name} failed validation: Empty content")
        return False
    
    lines = schema_content.strip().split('\n')
    
    # Check if the content has any actual class definitions or type aliases
    has_class_definition = any(line.strip().startswith('class ') for line in lines)
    has_type_alias = any(schema_name in line and '=' in line and not line.strip().startswith('#') for line in lines)
    
    # Check if it's essentially just imports (less than 5 lines and no meaningful definitions)
    meaningful_lines = [line for line in lines if line.strip() and not line.strip().startswith('from ') and not line.strip().startswith('import ') and not line.strip().startswith('#')]
    
    # Enhanced logging for debugging
    if not (has_class_definition or has_type_alias) or len(meaningful_lines) < 1:
        # Determine the specific reason for failure
        if len(meaningful_lines) == 0:
            logging.debug(f"Schema {schema_name} failed validation: No meaningful content (only imports) - likely empty object or unresolved reference")
        elif not has_class_definition and not has_type_alias:
            logging.debug(f"Schema {schema_name} failed validation: No class definition or type alias found")
        return False
    
    return True


def add_schema_file(
    full_path: str,
    schema_name: str,
    spec: SchemaSpecDto,
):
    """
    Atomically add a schema file to prevent partial corruption during generation failures.
    
    This function generates all content first, then writes files atomically using temporary files
    to ensure that either the entire operation succeeds or no changes are made to the filesystem.
    """
    try:
        # first lets add the import to the __init__
        init_the_init(full_path, SCHEMA_CODE_IMPORTS)

        if not spec["definition"].get("title"):
            # very empty schemas like mews.Unit are possible
            # add a title here to be sure they render
            spec["definition"]["title"] = schema_name

        schema_defs = render_poly_schema(spec)

        # Validate schema content before proceeding
        if not validate_schema_content(schema_defs, schema_name):
            raise Exception(f"Schema rendering failed or produced invalid content for {schema_name}")

        # Prepare all content first before writing any files
        schema_namespace = to_func_namespace(schema_name)
        init_path = os.path.join(full_path, "__init__.py")
        schema_file_path = os.path.join(full_path, f"_{schema_namespace}.py")
        
        # Read current __init__.py content if it exists
        init_content = ""
        if os.path.exists(init_path):
            with open(init_path, "r", encoding='utf-8') as f:
                init_content = f.read()
        
        # Prepare new content to append to __init__.py
        new_init_content = init_content + f"\n\nfrom ._{schema_namespace} import {schema_name}\n__all__.append('{schema_name}')\n"
        
        # Use temporary files for atomic writes
        # Write to __init__.py atomically
        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=full_path, suffix=".tmp", encoding='utf-8') as temp_init:
            temp_init.write(new_init_content)
            temp_init_path = temp_init.name
        
        # Write to schema file atomically  
        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=full_path, suffix=".tmp", encoding='utf-8') as temp_schema:
            temp_schema.write(schema_defs)
            temp_schema_path = temp_schema.name
        
        # Atomic operations: move temp files to final locations
        shutil.move(temp_init_path, init_path)
        shutil.move(temp_schema_path, schema_file_path)
        
    except Exception as e:
        # Clean up any temporary files that might have been created
        try:
            if 'temp_init_path' in locals() and os.path.exists(temp_init_path):
                os.unlink(temp_init_path)
            if 'temp_schema_path' in locals() and os.path.exists(temp_schema_path):
                os.unlink(temp_schema_path)
        except:
            pass  # Best effort cleanup
        
        # Re-raise the original exception
        raise e


def create_schema(
    spec: SchemaSpecDto
) -> None:
    """
    Create a schema with atomic directory and file operations.
    
    Tracks directory creation to enable cleanup on failure.
    """
    full_path = os.path.dirname(os.path.abspath(__file__))
    folders = f"schemas.{spec['context']}.{spec['name']}".split(".")
    created_dirs = []  # Track directories we create for cleanup on failure
    
    try:
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
                    created_dirs.append(full_path)  # Track for cleanup

                # append to __init__.py file if nested folders
                next = folders[idx + 1] if idx + 2 < len(folders) else ""
                if next:
                    init_the_init(full_path, SCHEMA_CODE_IMPORTS)
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


def add_schema_to_init(full_path: str, spec: SchemaSpecDto):
    init_the_init(full_path, code_imports="")
    init_path = os.path.join(full_path, "__init__.py")
    with open(init_path, "a", encoding='utf-8') as f:
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
