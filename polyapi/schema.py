""" NOTE: this file represents the schema parsing logic for jsonschema_gentypes
"""
import logging
import contextlib
import re
from typing import Dict
from jsonschema_gentypes.cli import process_config
from jsonschema_gentypes import configuration
import referencing
import tempfile
import json

import referencing.exceptions

from polyapi.constants import JSONSCHEMA_TO_PYTHON_TYPE_MAP


def _cleanup_input_for_gentypes(input_data: Dict):
    """ cleanup input_data in place to make it more suitable for jsonschema_gentypes
    """
    for k, v in input_data.items():
        if isinstance(v, dict):
            _cleanup_input_for_gentypes(v)
        elif k == "enum":
            # jsonschema_gentypes doesn't like double quotes in enums
            # TODO fix this upstream
            for idx, enum in enumerate(v):
                if isinstance(enum, str):
                    v[idx] = enum.replace('"', "'")


def _temp_store_input_data(input_data: Dict) -> str:
    """take in the input data and store it in a temporary json file"""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, prefix="polyapi_", suffix=".json"
    ) as temp_file:
        json.dump(input_data, temp_file)
        return temp_file.name


def wrapped_generate_schema_types(type_spec: dict, root, fallback_type):
    from polyapi.utils import pascalCase
    if not root:
        root = "List" if fallback_type == "List" else "Dict"
        if type_spec.get("x-poly-ref") and type_spec["x-poly-ref"].get("path"):
            # x-poly-ref occurs when we have an unresolved reference
            # lets name the root after the reference for some level of visibility
            root += pascalCase(type_spec["x-poly-ref"]["path"].replace(".", " "))
        else:
            # if we have no root, just add "My"
            root = "My" + root

    root = clean_title(root)

    try:
        return root, generate_schema_types(type_spec, root=root)
    except RecursionError:
        # some schemas are so huge, our library cant handle it
        # TODO identify critical recursion penalty and maybe switch underlying logic to iterative?
        return fallback_type, ""
    except referencing.exceptions.CannotDetermineSpecification:
        # just go with fallback_type here
        # we couldn't match the right $ref earlier in resolve_poly_refs
        # {'$ref': '#/definitions/FinanceAccountListModel'}
        return fallback_type, ""
    except:
        logging.error(f"Error when generating schema type: {type_spec}\nusing fallback type '{fallback_type}'")
        return fallback_type, ""


def generate_schema_types(input_data: Dict, root=None):
    """takes in a Dict representing a schema as input then appends the resulting python code to the output file"""
    _cleanup_input_for_gentypes(input_data)
    tmp_input = _temp_store_input_data(input_data)
    tmp_output = tempfile.NamedTemporaryFile(
        mode="w", delete=False, prefix="polyapi_", suffix=".py"
    ).name

    config: configuration.Configuration = {
        "python_version": None,  # type: ignore
        "generate": [
            {
                "source": tmp_input,
                "destination": tmp_output,
                "root_name": root,
                "api_arguments": {"get_name_properties": "UpperFirst"},
            }
        ],
    }

    # jsonschema_gentypes prints source to stdout
    # no option to surpress so we do this
    with contextlib.redirect_stdout(None):
        process_config(config, [tmp_input])

    with open(tmp_output) as f:
        output = f.read()

    output = clean_malformed_examples(output)

    return output


# Regex to match everything between "# example: {\n" and "^}$"
MALFORMED_EXAMPLES_PATTERN = re.compile(r"# example: \{\n.*?^\}$", flags=re.DOTALL | re.MULTILINE)


def clean_malformed_examples(example: str) -> str:
    """ there is a bug in the `jsonschmea_gentypes` library where if an example from a jsonchema is an object,
    it will break the code because the object won't be properly commented out
    """
    cleaned_example = MALFORMED_EXAMPLES_PATTERN.sub("", example)
    return cleaned_example


def clean_title(title: str) -> str:
    """ used by library generation, sometimes functions can be added with spaces in the title
    or other nonsense. fix them!
    """
    title = title.replace(" ", "")
    # certain reserved words cant be titles, let's replace them
    if title == "List":
        title = "List_"
    return title


def map_primitive_types(type_: str) -> str:
    # Define your mapping logic here
    return JSONSCHEMA_TO_PYTHON_TYPE_MAP.get(type_, "Any")


def is_primitive(type_: str) -> bool:
    return type_ in JSONSCHEMA_TO_PYTHON_TYPE_MAP
