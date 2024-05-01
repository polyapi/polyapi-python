import unittest
from polyapi.schema import _fix_title


class T(unittest.TestCase):
    def test_fix_titles(self):
        input_data = {'properties': {'requestNumber': {'title': 'Requestnumber', 'type': 'integer'}}, 'required': ['requestNumber'], 'title': 'numOfCars', 'type': 'object', 'metadata': {'pydantic.internal.needs_apply_discriminated_union': False}}
        output = 'from typing import TypedDict\nfrom typing_extensions import Required\n\n\nclass Numofcars(TypedDict, total=False):\n    """ numOfCars. """\n\n    requestNumber: Required[int]\n    """\n    Requestnumber.\n\n    Required property\n    """\n\n'
        fixed = _fix_title(input_data, output)
        self.assertIn("class numOfCars", fixed)
