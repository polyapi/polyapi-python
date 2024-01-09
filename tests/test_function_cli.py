import unittest

from polyapi.function_cli import _get_args_and_return_type_from_code


SIMPLE_CODE = """
def foobar(n: int) -> int:
    return 9
"""

COMPLEX_RETURN_TYPE = """
from pydantic import BaseModel


class Barbar(BaseModel):
    count: int


def foobar(n: int) -> Barbar:
    return Barbar(count=n)
"""

LIST_COMPLEX_RETURN_TYPE = """
from typing import List
from pydantic import BaseModel


class Barbar(BaseModel):
    count: int


def foobar(n: int) -> List[Barbar]:
    return [Barbar(count=n)]
"""

COMPLEX_ARG_TYPE = """
from pydantic import BaseModel


class Barbar(BaseModel):
    count: int


def foobar(n: Barbar) -> int:
    return 7
"""


class T(unittest.TestCase):
    def test_simple_types(self):
        args, arg_schemas, return_type, return_type_schema = _get_args_and_return_type_from_code(SIMPLE_CODE, "foobar")
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0], {"key": "n", "name": "n", "type": "integer"})
        self.assertEqual(return_type, "integer")
        self.assertEqual(arg_schemas, [])
        self.assertIsNone(return_type_schema)

    def test_complex_return_type(self):
        args, arg_schemas, return_type, return_type_schema = _get_args_and_return_type_from_code(COMPLEX_RETURN_TYPE, "foobar")
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0], {"key": "n", "name": "n", "type": "integer"})
        self.assertEqual(return_type, "Barbar")
        self.assertEqual(return_type_schema['title'], "Barbar")

    def test_complex_arg_type(self):
        args, arg_schemas, return_type, return_type_schema = _get_args_and_return_type_from_code(COMPLEX_ARG_TYPE, "foobar")
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0], {"key": "n", "name": "n", "type": "Barbar"})
        self.assertEqual(len(arg_schemas), 1)
        self.assertEqual(return_type, "integer")
        self.assertIsNone(return_type_schema)

    def test_list_complex_return_type(self):
        args, arg_schemas, return_type, return_type_schema = _get_args_and_return_type_from_code(LIST_COMPLEX_RETURN_TYPE, "foobar")
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0], {"key": "n", "name": "n", "type": "integer"})
        self.assertEqual(return_type['items'], {"$ref": "#/definitions/Barbar"})