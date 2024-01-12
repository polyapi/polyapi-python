import unittest

from polyapi.function_cli import _parse_code


SIMPLE_CODE = """
def foobar(n: int) -> int:
    return 9
"""

COMPLEX_RETURN_TYPE = """
from typing_extensions import TypedDict


class Barbar(TypedDict):
    count: int


def foobar(n: int) -> Barbar:
    return Barbar(count=n)
"""

LIST_COMPLEX_RETURN_TYPE = """
from typing import List
from typing_extensions import TypedDict


class Barbar(TypedDict):
    count: int


def foobar(n: int) -> List[Barbar]:
    return [Barbar(count=n)]
"""

COMPLEX_ARG_TYPE = """
from typing_extensions import TypedDict


class Barbar(TypedDict):
    count: int


def foobar(n: Barbar) -> int:
    return 7
"""


class T(unittest.TestCase):
    def test_simple_types(self):
        args, return_type, return_type_schema, additional_requirements = _parse_code(SIMPLE_CODE, "foobar")
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0], {"key": "n", "name": "n", "type": "integer"})
        self.assertEqual(return_type, "integer")
        self.assertIsNone(return_type_schema)
        self.assertEqual(additional_requirements, [])

    def test_complex_return_type(self):
        args, return_type, return_type_schema, _ = _parse_code(COMPLEX_RETURN_TYPE, "foobar")
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0], {"key": "n", "name": "n", "type": "integer"})
        self.assertEqual(return_type, "Barbar")
        self.assertEqual(return_type_schema['title'], "Barbar")

    def test_complex_arg_type(self):
        args, return_type, return_type_schema, _ = _parse_code(COMPLEX_ARG_TYPE, "foobar")
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0]["type"], "Barbar")
        self.assertEqual(return_type, "integer")
        self.assertIsNone(return_type_schema)

    def test_list_complex_return_type(self):
        args, return_type, return_type_schema, _ = _parse_code(LIST_COMPLEX_RETURN_TYPE, "foobar")
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0], {"key": "n", "name": "n", "type": "integer"})
        self.assertEqual(return_type, "object")
        self.assertEqual(return_type_schema["items"]['title'], "Barbar")

    def test_parse_import_basic(self):
        code = "import flask\n\n\ndef foobar(n: int) -> int:\n    return 9\n"
        _, _, _, additional_requirements = _parse_code(code, "foobar")
        self.assertEqual(additional_requirements, ["flask"])

    def test_parse_import_from(self):
        code = "from flask import Request, Response\n\n\ndef foobar(n: int) -> int:\n    return 9\n"
        _, _, _, additional_requirements = _parse_code(code, "foobar")
        self.assertEqual(additional_requirements, ["flask"])

    def test_parse_import_base(self):
        code = "import requests\n\n\ndef foobar(n: int) -> int:\n    return 9\n"
        _, _, _, additional_requirements = _parse_code(code, "foobar")
        self.assertEqual(additional_requirements, [])