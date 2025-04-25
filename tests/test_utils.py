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


SCHEMA_OOB_TYPE_SPEC = {
    "kind": "object",
    "schema": {
        "$schema": "http://json-schema.org/draft-06/schema#",
        "allOf": [
            {
                "x-poly-ref": {
                    "path": "mews.CustomerSearchResult",
                    "publicNamespace": "OOB",
                }
            }
        ],
    },
}


ALLOF_TYPE_SPEC = {
    "kind": "object",
    "schema": {
        "title": "Pet",
        "$schema": "http://json-schema.org/draft-06/schema#",
        "allOf": [
            {
                "required": ["id", "name"],
                "properties": {
                    "id": {"type": "number", "format": "int64"},
                    "name": {"type": "string"},
                    "tag": {"type": "string"},
                },
                "$schema": "http://json-schema.org/draft-06/schema#",
                "name": "Pet",
            }
        ],
    },
}

OBJECT_TYPE_SPEC = {
    "kind": "object",
    "schema": {
        "title": "Pet",
        "$schema": "http://json-schema.org/draft-06/schema#",
        "required": ["id", "name"],
        "properties": {
            "id": {"type": "number", "format": "int64"},
            "name": {"type": "string"},
            "tag": {"type": "string"},
        }
    },
}

ARRAY_TYPE_SPEC = {
    "kind": "object",
    "schema": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"id": {"type": "string"}, "stay_date": {"type": "string"}},
            "required": ["id", "stay_date"],
        },
    },
}


class T(unittest.TestCase):
    def test_get_type_and_def(self):
        arg_type, arg_def = get_type_and_def(OPENAPI_FUNCTION)
        self.assertEqual(
            arg_type,
            "Callable[[List[WebhookEventTypeElement], Dict, Dict, Dict], None]",
        )

    def test_get_type_and_def_array(self):
        arg_type, arg_def = get_type_and_def(ARRAY_TYPE_SPEC, "ResponseType")
        self.assertEqual(arg_type, "ResponseType")
        self.assertIn('ResponseType = List["_ResponseTypeitem"]', arg_def)

    def test_get_type_and_def_object(self):
        arg_type, arg_def = get_type_and_def(OBJECT_TYPE_SPEC)
        self.assertEqual(arg_type, "Pet")
        self.assertIn('class Pet(', arg_def)

    def test_get_type_and_def_allof(self):
        arg_type, arg_def = get_type_and_def(ALLOF_TYPE_SPEC)
        self.assertEqual(arg_type, "Pet")
        self.assertNotEqual(arg_def, "")
        self.assertIn('class Pet(', arg_def)

    def test_rewrite_reserved(self):
        rv = rewrite_reserved("from")
        self.assertEqual(rv, "_from")
