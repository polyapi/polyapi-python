from typing import Dict
from jsonschema_gentypes.cli import process_config
from jsonschema_gentypes import configuration
import tempfile
import json


def _temp_store_input_data(input_data: Dict) -> str:
    """take in the input data and store it in a temporary json file"""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, prefix="polyapi_", suffix=".json"
    ) as temp_file:
        json.dump(input_data, temp_file)
        return temp_file.name


def generate_schema_types(input_data: Dict):
    """takes in a Dict representing a schema as input then appends the resulting python code to the output file"""
    tmp_input = _temp_store_input_data(input_data)
    tmp_output = tempfile.NamedTemporaryFile(
        mode="w", delete=False, prefix="polyapi_", suffix=".json"
    ).name

    config: configuration.Configuration = {
        "python_version": None,  # type: ignore
        "generate": [
            {
                "source": tmp_input,
                "destination": tmp_output,
            }
        ],
    }
    process_config(config)

    with open(tmp_output) as f:
        output = f.read()

    return output
