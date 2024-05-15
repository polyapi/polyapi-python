import unittest
from polyapi.schema import wrapped_generate_schema_types

SCHEMA = {
    "$schema": "http://json-schema.org/draft-06/schema#",
    "type": "object",
    "properties": {"name": {"type": "string"}},
    "required": ["name"],
    "additionalProperties": False,
    "definitions": {},
}


class T(unittest.TestCase):
    def test_fix_titles(self):
        output = wrapped_generate_schema_types(SCHEMA, "", "Dict")
        self.assertEqual("MyDict", output[0])
        self.assertIn("class MyDict", output[1])

        # should not throw with unknown dialect error
