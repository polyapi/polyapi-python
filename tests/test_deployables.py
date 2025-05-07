import unittest

from polyapi.parser import parse_function_code
from polyapi.deployables import update_deployable_function_comments, update_deployment_comments


INITIAL_SERVER_FN_DEPLOYMENTS = """
# Poly deployed @ 2024-11-11T14:43:22.631113 - testing.foobar - https://dev.polyapi.io/canopy/polyui/collections/server-functions/jh23h5g3h5b24jh5b2j3h45v2jhg43v52j3h - 086aedd
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

EXPECTED_SERVER_FN_DEPLOYMENTS = '''# Poly deployed @ 2024-11-12T14:43:22.631113 - testing.foobar - https://na1.polyapi.io/canopy/polyui/collections/server-functions/jh23h5g3h5b24jh5b2j3h45v2jhg43v52j3h - 086aedd
# Poly deployed @ 2024-11-11T14:43:22.631113 - testing.foobar - https://dev.polyapi.io/canopy/polyui/collections/server-functions/jh23h5g3h5b24jh5b2j3h45v2jhg43v52j3h - 086aedd

from polyapi.typedefs import PolyServerFunction

polyConfig: PolyServerFunction = {
    "name": "foobar",
    "context": "testing",
    "logsEnabled": True,
}

def foobar() -> int:
    print("Okay then!")
    return 7
'''

INITIAL_SERVER_FN_DOCSTRINGS = '''
from typing import Dict
from polyapi.typedefs import PolyServerFunction

polyConfig: PolyServerFunction = {
    "name": "foobar",
    "context": "testing",
    "logsEnabled": True,
}

def foobar(foo: str, bar: Dict[str, str]) -> int:
    """A function that does something really import.
    """
    print("Okay then!")
    return 7
'''

EXPECTED_SERVER_FN_DOCSTRINGS = '''
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
        foo (str):
        bar (Dict[str, str]):

    Returns:
        int:
    """
    print("Okay then!")
    return 7
'''

class T(unittest.TestCase):
    def test_parse_and_write_deployment_comment(self):
        test_deployable = parse_function_code(EXPECTED_SERVER_FN_DEPLOYMENTS, "foobar")
        deployable_comment_ranges = test_deployable["deploymentCommentRanges"]
        updated_file_contents = update_deployment_comments(EXPECTED_SERVER_FN_DEPLOYMENTS, test_deployable)
        self.assertEqual(updated_file_contents, EXPECTED_SERVER_FN_DEPLOYMENTS)
        # Deployment comment ranges collapsed into one of equal size
        self.assertEqual(test_deployable["deploymentCommentRanges"][0][0], deployable_comment_ranges[0][0])
        self.assertEqual(test_deployable["deploymentCommentRanges"][0][1], deployable_comment_ranges[1][1])

    def test_write_deployment_comment(self):
        test_deployable = {
            "deployments": [
                {
                    'context': 'testing',
                    'deployed': '2024-11-12T14:43:22.631113',
                    'fileRevision': '086aedd',
                    'id': 'jh23h5g3h5b24jh5b2j3h45v2jhg43v52j3h',
                    'instance': 'https://na1.polyapi.io',
                    'name': 'foobar',
                    'type': 'server-function'
                },
                {
                    'context': 'testing',
                    'deployed': '2024-11-11T14:43:22.631113',
                    'fileRevision': '086aedd',
                    'id': 'jh23h5g3h5b24jh5b2j3h45v2jhg43v52j3h',
                    'instance': 'https://dev.polyapi.io',
                    'name': 'foobar',
                    'type': 'server-function'
                }
            ],
            "deploymentCommentRanges": [[0, 177]]
        }
        updated_file_contents = update_deployment_comments(INITIAL_SERVER_FN_DEPLOYMENTS, test_deployable)
        self.assertEqual(updated_file_contents, EXPECTED_SERVER_FN_DEPLOYMENTS)

    def test_parse_and_write_deployable_docstring(self):
        parsed_deployable = parse_function_code(INITIAL_SERVER_FN_DOCSTRINGS)
        updated_file_contents = update_deployable_function_comments(INITIAL_SERVER_FN_DOCSTRINGS, parsed_deployable)
        self.assertEqual(updated_file_contents, EXPECTED_SERVER_FN_DOCSTRINGS)

    def test_parse_and_overwrite_docstring(self):
        parsed_deployable = parse_function_code(EXPECTED_SERVER_FN_DOCSTRINGS)
        updated_file_contents = update_deployable_function_comments(EXPECTED_SERVER_FN_DOCSTRINGS, parsed_deployable)
        self.assertEqual(EXPECTED_SERVER_FN_DOCSTRINGS, updated_file_contents)