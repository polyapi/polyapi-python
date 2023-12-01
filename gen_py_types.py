#!/usr/bin/env python3
import yaml
import pkgutil
from jsonschema_gentypes.cli import process_config
from jsonschema_gentypes import configuration


def generate_schema_types():
    config: configuration.Configuration = {
        "python_version": None,
        "generate": [
            {
                "source": "polyapi/foo.json",
                "destination": "polyapi/foo.py",
            }
        ],
    }
    process_config(config)


if __name__ == "__main__":
    generate_schema_types()