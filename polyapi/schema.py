import contextlib
from typing import Dict
from jsonschema_gentypes.cli import process_config
from jsonschema_gentypes import configuration
import tempfile
import json

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
                assert isinstance(enum, str)
                v[idx] = enum.replace('"', "'")




def _temp_store_input_data(input_data: Dict) -> str:
    """take in the input data and store it in a temporary json file"""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, prefix="polyapi_", suffix=".json"
    ) as temp_file:
        json.dump(input_data, temp_file)
        return temp_file.name


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
            }
        ],
    }

    # jsonschema_gentypes prints source to stdout
    # no option to surpress so we do this
    with contextlib.redirect_stdout(None):
        process_config(config)

    with open(tmp_output) as f:
        output = f.read()

    output = _fix_title(input_data, output)
    return output


def _fix_title(input_data, output) -> str:
    """ the jsonschema_gentypes library changes all titles to Pascalcase
    this function changes them back
    TODO fix bug in gentypes so this step is not necessary
    """
    for k, v in input_data.items():
        if isinstance(v, dict):
            output = _fix_title(v, output)
        elif k == "title":
            output = output.replace(f"class {v.title()}", f"class {v}")
    return output


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