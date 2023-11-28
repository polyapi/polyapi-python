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


class T(unittest.TestCase):
    def test_render_function(self):
        func_str = render_function(
            "apiFunction",
            "accuweatherGetlocation",
            ACCUWEATHER["id"],
            ACCUWEATHER["function"]["arguments"],
        )
        self.assertIn(ACCUWEATHER["id"], func_str)
        self.assertIn("locationId: int,", func_str)
        print(func_str)
