import unittest

from polyapi.function_cli import _get_args_and_return_type_from_code


SIMPLE_CODE = """
def foobar(n: int) -> int:
    return 9
"""


class T(unittest.TestCase):
    def test_simple_types(self):
        args, return_type = _get_args_and_return_type_from_code(SIMPLE_CODE, "foobar")
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0], {"key": "n", "name": "n", "type": "integer"})