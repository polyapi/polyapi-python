import unittest

from polyapi.parser import parse_function_code


CODE_NO_TYPES = """
def foobar(a, b):
    return a + b
"""

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

GLIDE_SIMPLE_SERVER_FN = """
from polyapi.typedefs import PolyServerFunction

polyConfig: PolyServerFunction = {
    "name": "foobar",
    "context": "testing",
    "logsEnabled": True,
}

def foobar() -> int:
    print("Okay then!")
    return 7
"""

GLIDE_DOCSTRING_BAD_SERVER_FN = '''
from polyapi.typedefs import PolyServerFunction

polyConfig: PolyServerFunction = {
    "name": "foobar",
    "context": "testing",
    "logsEnabled": True,
}

def foobar(foo, bar):
    """A function that does something really import.

    Args:
        foo (str): The foo in question
        bar (Dict[str, str]): Configuration of bars

    Returns:
        int: import number please keep handy
    """
    print("Okay then!")
    return 7
'''

GLIDE_DOCSTRING_OK_SERVER_FN = '''
from typing import Dict
from polyapi.typedefs import PolyServerFunction

polyConfig: PolyServerFunction = {
    "name": "foobar",
    "context": "testing",
    "logsEnabled": True,
}

def foobar(foo: str, bar: Dict[str, str]) -> int:
    """A function that does something really import.

    Args:
        foo (str): The foo in question
        bar (Dict[str, str]): Configuration of bars

    Returns:
        int: import number please keep handy
    """
    print("Okay then!")
    return 7
'''

GLIDE_DEPLOYMENTS_SERVER_FN = '''
# Poly deployed @ 2024-11-12T14:43:22.631113 - testing.foobar - https://na1.polyapi.io/canopy/polyui/collections/server-functions/jh23h5g3h5b24jh5b2j3h45v2jhg43v52j3h - 086aedd
# Poly deployed @ 2024-11-11T14:43:22.631113 - testing.foobar - https://dev.polyapi.io/canopy/polyui/collections/server-functions/jh23h5g3h5b24jh5b2j3h45v2jhg43v52j3h - 086aedd
from typing import Dict
from polyapi.typedefs import PolyServerFunction

polyConfig: PolyServerFunction = {
    "name": "foobar",
    "context": "testing",
    "logsEnabled": True,
}

def foobar(foo: str, bar: Dict[str, str]) -> int:
    print("Okay then!")
    return 7
'''


class T(unittest.TestCase):
    maxDiff = 640

    def test_no_types(self):
        deployable = parse_function_code(CODE_NO_TYPES, "foobar")
        types = deployable["types"]
        self.assertEqual(len(types["params"]), 2)
        self.assertEqual(types["params"][0], {"name": "a", "type": "Any", "typeSchema": None, "description": ""})
        self.assertEqual(types["params"][1], {"name": "b", "type": "Any", "typeSchema": None, "description": ""})
        self.assertEqual(types["returns"]["type"], "Any")
        self.assertIsNone(types["returns"]["typeSchema"])
        self.assertEqual(deployable["dependencies"], [])

    def test_simple_types(self):
        deployable = parse_function_code(SIMPLE_CODE, "foobar")
        types = deployable["types"]
        self.assertEqual(len(types["params"]), 1)
        self.assertEqual(types["params"][0], {"name": "n", "type": "int", "typeSchema": None, "description": ""})
        self.assertEqual(types["returns"]["type"], "int")
        self.assertIsNone(types["returns"]["typeSchema"])
        self.assertEqual(deployable["dependencies"], [])

    def test_complex_return_type(self):
        deployable = parse_function_code(COMPLEX_RETURN_TYPE, "foobar")
        types = deployable["types"]
        self.assertEqual(len(types["params"]), 1)
        self.assertEqual(types["params"][0], {"name": "n", "type": "int", "typeSchema": None, "description": ""})
        self.assertEqual(types["returns"]["type"], "Barbar")
        self.assertEqual(types["returns"]["typeSchema"]['title'], "Barbar")

    def test_complex_arg_type(self):
        deployable = parse_function_code(COMPLEX_ARG_TYPE, "foobar")
        types = deployable["types"]
        self.assertEqual(len(types["params"]), 1)
        self.assertEqual(types["params"][0]["type"], "Barbar")
        self.assertEqual(types["returns"]["type"], "int")
        self.assertIsNone(types["returns"]["typeSchema"])

    def test_list_complex_return_type(self):
        deployable = parse_function_code(LIST_COMPLEX_RETURN_TYPE, "foobar")
        types = deployable["types"]
        self.assertEqual(len(types["params"]), 1)
        self.assertEqual(types["params"][0], {"name": "n", "type": "int", "typeSchema": None, "description": ""})
        self.assertEqual(types["returns"]["type"], "List[Barbar]")
        self.assertEqual(types["returns"]["typeSchema"]["items"]['title'], "Barbar")

    def test_parse_import_basic(self):
        code = "import flask\n\n\ndef foobar(n: int) -> int:\n    return 9\n"
        deployable = parse_function_code(code, "foobar")
        self.assertEqual(deployable["dependencies"], ["Flask"])

    def test_parse_import_from(self):
        code = "from flask import Request, Response\n\n\ndef foobar(n: int) -> int:\n    return 9\n"
        deployable = parse_function_code(code, "foobar")
        self.assertEqual(deployable["dependencies"], ["Flask"])

    def test_parse_import_base(self):
        code = "import requests\n\n\ndef foobar(n: int) -> int:\n    return 9\n"
        deployable = parse_function_code(code, "foobar")
        self.assertEqual(deployable["dependencies"], [])

    def test_parse_glide_server_function_no_docstring(self):
        code = GLIDE_SIMPLE_SERVER_FN
        deployable = parse_function_code(code, "foobar")
        self.assertEqual(deployable["name"], "foobar")
        self.assertEqual(deployable["context"], "testing")
        self.assertEqual(deployable["config"]["logsEnabled"], True)

    def test_parse_glide_server_function_bad_docstring(self):
        code = GLIDE_DOCSTRING_BAD_SERVER_FN
        deployable = parse_function_code(code, "foobar")
        self.assertEqual(deployable["types"]["description"], "A function that does something really import.")
        self.assertEqual(deployable["types"]["params"][0], {
            "name": "foo",
            "type": "Any",
            "typeSchema": None,
            "description": "The foo in question"
        })
        self.assertEqual(deployable["types"]["params"][1], {
            "name": "bar",
            "type": "Any",
            "typeSchema": None,
            "description": "Configuration of bars"
        })
        self.assertEqual(deployable["types"]["returns"], {
            "type": "Any",
            "description": "import number please keep handy"
        })

    def test_parse_glide_server_function_ok_docstring(self):
        code = GLIDE_DOCSTRING_OK_SERVER_FN
        deployable = parse_function_code(code, "foobar")
        self.assertEqual(deployable["types"]["description"], "A function that does something really import.")
        self.assertEqual(deployable["types"]["params"][0], {
            "name": "foo",
            "type": "str",
            "typeSchema": None,
            "description": "The foo in question"
        })
        self.assertEqual(deployable["types"]["params"][1], {
            "name": "bar",
            "type": "Dict[str, str]",
            "typeSchema": None,
            "description": "Configuration of bars"
        })
        self.assertEqual(deployable["types"]["returns"], {
            "type": "int",
            "typeSchema": None,
            "description": "import number please keep handy"
        })

    @unittest.skip("TODO fix test")
    def test_parse_glide_server_function_deploy_receipt(self):
        code = GLIDE_DEPLOYMENTS_SERVER_FN
        deployable = parse_function_code(code, "foobar")

        self.assertEqual(len(deployable["deployments"]), 2)
        self.assertEqual(deployable["deployments"][0], {
            'context': 'testing',
            'deployed': '2024-11-12T14:43:22.631113',
            'fileRevision': '086aedd',
            'id': 'jh23h5g3h5b24jh5b2j3h45v2jhg43v52j3h',
            'instance': 'https://na1.polyapi.io',
            'name': 'foobar',
            'type': 'server-function'
        })
        self.assertEqual(deployable["deployments"][1], {
            'context': 'testing',
            'deployed': '2024-11-11T14:43:22.631113',
            'fileRevision': '086aedd',
            'id': 'jh23h5g3h5b24jh5b2j3h45v2jhg43v52j3h',
            'instance': 'https://dev.polyapi.io',
            'name': 'foobar',
            'type': 'server-function'
        })