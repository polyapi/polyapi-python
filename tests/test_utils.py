import unittest
from polyapi.schema import _fix_title
from polyapi.utils import get_type_and_def

OPENAPI_FUNCTION = {'kind': 'function', 'spec': {'arguments': [{'name': 'event', 'required': False, 'type': {'kind': 'object', 'schema': {'$schema': 'http://json-schema.org/draft-06/schema#', 'type': 'array', 'items': {'$ref': '#/definitions/WebhookEventTypeElement'}, 'definitions': {'WebhookEventTypeElement': {'type': 'object', 'additionalProperties': False, 'properties': {'title': {'type': 'string'}, 'manufacturerName': {'type': 'string'}, 'carType': {'type': 'string'}, 'id': {'type': 'integer'}}, 'required': ['carType', 'id', 'manufacturerName', 'title'], 'title': 'WebhookEventTypeElement'}}}}}, {'name': 'headers', 'required': False, 'type': {'kind': 'object', 'typeName': 'Record<string, any>'}}, {'name': 'params', 'required': False, 'type': {'kind': 'object', 'typeName': 'Record<string, any>'}}, {'name': 'polyCustom', 'required': False, 'type': {'kind': 'object', 'properties': [{'name': 'responseStatusCode', 'type': {'type': 'number', 'kind': 'primitive'}, 'required': True}, {'name': 'responseContentType', 'type': {'type': 'string', 'kind': 'primitive'}, 'required': True, 'nullable': True}]}}], 'returnType': {'kind': 'void'}, 'synchronous': True}}


class T(unittest.TestCase):
    def test_fix_titles(self):
        input_data = {'properties': {'requestNumber': {'title': 'Requestnumber', 'type': 'integer'}}, 'required': ['requestNumber'], 'title': 'numOfCars', 'type': 'object', 'metadata': {'pydantic.internal.needs_apply_discriminated_union': False}}
        output = 'from typing import TypedDict\nfrom typing_extensions import Required\n\n\nclass Numofcars(TypedDict, total=False):\n    """ numOfCars. """\n\n    requestNumber: Required[int]\n    """\n    Requestnumber.\n\n    Required property\n    """\n\n'
        fixed = _fix_title(input_data, output)
        self.assertIn("class numOfCars", fixed)

    def test_get_type_and_def(self):
        arg_type, arg_def = get_type_and_def(OPENAPI_FUNCTION)
        self.assertEqual(arg_type, "Callable[[List[WebhookEventTypeElement], Dict, Dict, Dict], None]")
