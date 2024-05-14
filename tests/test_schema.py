import unittest
from polyapi.schema import generate_schema_types


class T(unittest.TestCase):
    def test_fix_titles(self):
        # schema = json.loads(SCHEMA)
        schema = {"$schema": "http://json-schema.org/draft-06/schema#"}
        try:
            a, b = generate_schema_types(schema)
        except AssertionError:
            pass

        # should not throw with unknown dialect error