import unittest
from polyapi.schema import generate_schema_types


class T(unittest.TestCase):
    def test_fix_titles(self):
        # schema = json.loads(SCHEMA)
        schema = {"$schema": "https://json-schema.org/draft-06/schema#"}
        a, b = generate_schema_types(schema)
        # shouldnt error with unknown dialect
        self.assertTrue(b)