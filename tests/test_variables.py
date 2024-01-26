import unittest
from polyapi.variables import render_variable

EXAMPLE = {
        "type": "serverVariable",
        "id": "181238j18231j",
        "name": "test",
        "context": "my3",
        "description": "a test variable",
        "visibilityMetadata": {
            "visibility": "ENVIRONMENT"
        },
        "variable": {
            "environmentId": "123818231",
            "secret": False,
            "valueType": {
                "kind": "primitive",
                "type": "string"
            },
            "value": "some mock value"
        }
    }


class T(unittest.TestCase):
    def test_render_variable(self):
        variable_str = render_variable(EXAMPLE)
        self.assertIn("class test", variable_str)