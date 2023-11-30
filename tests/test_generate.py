import unittest

from polyapi.api import render_function

ACCUWEATHER = {
    "id": "f7588018-2364-4586-b60d-b08a285f1ea3",
    "name": "accuweatherGetlocation",
    "context": "",
    "description": "",
    "type": "apiFunction",
    "function": {
        "arguments": [
            {
                "name": "locationId",
                "description": "",
                "type": {"kind": "primitive", "type": "integer"},
                "required": True,
            },
            {
                "name": "AAPIKey",
                "description": "",
                "type": {"kind": "primitive", "type": "string"},
                "required": True,
            },
        ],
        "returnType": {"kind": "void"},
    },
}


ZILLOW = {
    "id": "1231234",
    "name": "zillowGetLocation",
    "context": "",
    "description": "",
    "type": "apiFunction",
    "function": {
        "arguments": [
            {
                "name": "locationId",
                "description": "",
                "type": {"kind": "primitive", "type": "integer"},
                "required": True,
            },
            {
                "name": "AAPIKey",
                "description": "",
                "type": {"kind": "primitive", "type": "string"},
                "required": True,
            },
        ],
        "returnType": {"kind": "primitive", "type": "string"},
    },
}


class T(unittest.TestCase):
    def test_render_function_accuweather(self):
        func_str = render_function(
            ACCUWEATHER["type"],
            ACCUWEATHER["name"],
            ACCUWEATHER["id"],
            ACCUWEATHER["function"]["arguments"],
            ACCUWEATHER["function"]["returnType"],
        )
        self.assertIn(ACCUWEATHER["id"], func_str)
        self.assertIn("locationId: int,", func_str)
        self.assertIn("-> None", func_str)

    def test_render_function_zillow(self):
        func_str = render_function(
            ZILLOW["type"],
            ZILLOW["name"],
            ZILLOW["id"],
            ZILLOW["function"]["arguments"],
            ZILLOW["function"]["returnType"],
        )
        self.assertIn(ZILLOW["id"], func_str)
        self.assertIn("locationId: int,", func_str)
        self.assertIn("-> str", func_str)
