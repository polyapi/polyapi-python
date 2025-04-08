import unittest
from polyapi.utils import get_type_and_def, rewrite_reserved

OPENAPI_FUNCTION = {
    "kind": "function",
    "spec": {
        "arguments": [
            {
                "name": "event",
                "required": False,
                "type": {
                    "kind": "object",
                    "schema": {
                        "$schema": "http://json-schema.org/draft-06/schema#",
                        "type": "array",
                        "items": {"$ref": "#/definitions/WebhookEventTypeElement"},
                        "definitions": {
                            "WebhookEventTypeElement": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "title": {"type": "string"},
                                    "manufacturerName": {"type": "string"},
                                    "carType": {"type": "string"},
                                    "id": {"type": "integer"},
                                },
                                "required": [
                                    "carType",
                                    "id",
                                    "manufacturerName",
                                    "title",
                                ],
                                "title": "WebhookEventTypeElement",
                            }
                        },
                    },
                },
            },
            {
                "name": "headers",
                "required": False,
                "type": {"kind": "object", "typeName": "Record<string, any>"},
            },
            {
                "name": "params",
                "required": False,
                "type": {"kind": "object", "typeName": "Record<string, any>"},
            },
            {
                "name": "polyCustom",
                "required": False,
                "type": {
                    "kind": "object",
                    "properties": [
                        {
                            "name": "responseStatusCode",
                            "type": {"type": "number", "kind": "primitive"},
                            "required": True,
                        },
                        {
                            "name": "responseContentType",
                            "type": {"type": "string", "kind": "primitive"},
                            "required": True,
                            "nullable": True,
                        },
                    ],
                },
            },
        ],
        "returnType": {"kind": "void"},
        "synchronous": True,
    },
}


class T(unittest.TestCase):
    def test_get_type_and_def(self):
        arg_type, arg_def = get_type_and_def(OPENAPI_FUNCTION)
        self.assertEqual(
            arg_type,
            "Callable[[List[WebhookEventTypeElement], Dict, Dict, Dict], None]",
        )

    def test_rewrite_reserved(self):
        rv = rewrite_reserved("from")
        self.assertEqual(rv, "_from")
