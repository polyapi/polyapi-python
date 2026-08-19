import unittest
from polyapi.utils import add_type_import_path, get_type_and_def, rewrite_reserved, DotDict

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

    def test_plain_return_type_utility_normalizes_to_any(self):
        arg_type, arg_def = get_type_and_def({"kind": "plain", "value": "ReturnType<typeof fooFunc>"})
        self.assertEqual(arg_type, "Any")
        self.assertEqual(arg_def, "")

    def test_plain_promise_union_normalizes_to_python_union(self):
        arg_type, arg_def = get_type_and_def({"kind": "plain", "value": "Promise<string | null>"})
        self.assertEqual(arg_type, "str | None")
        self.assertEqual(arg_def, "")

    def test_add_type_import_path_never_qualifies_return_type_utility(self):
        arg_type = add_type_import_path("fooFunc", "ReturnType<typeof fooFunc>")
        self.assertEqual(arg_type, "Any")

    def test_plain_promise_array_union_normalizes_to_python_union(self):
        arg_type, arg_def = get_type_and_def({"kind": "plain", "value": "Promise<string[] | null>"})
        self.assertEqual(arg_type, "List[str] | None")
        self.assertEqual(arg_def, "")

    def test_add_type_import_path_keeps_array_union_primitives_valid(self):
        arg_type = add_type_import_path("fooFunc", "Promise<string[] | null>")
        self.assertEqual(arg_type, "List[str] | None")


class TestDotDict(unittest.TestCase):
    def test_dot_access(self):
        d = DotDict({"bye": "world"})
        self.assertEqual(d.bye, "world")

    def test_dict_access_still_works(self):
        d = DotDict({"hello": "world"})
        self.assertEqual(d["hello"], "world")

    def test_nested_dot_access(self):
        d = DotDict({"spider": {"bit": "man"}})
        self.assertEqual(d.spider.bit, "man")

    def test_nested_dict_access_still_works(self):
        d = DotDict({"spider": {"bit": "man"}})
        self.assertEqual(d["spider"]["bit"], "man")

    def test_missing_key_raises_attribute_error(self):
        d = DotDict({"hello": "world"})
        with self.assertRaises(AttributeError):
            _ = d.missing

    def test_set_via_attribute(self):
        d = DotDict({})
        d.foo = "bar"
        self.assertEqual(d["foo"], "bar")

    def test_non_dict_values_returned_as_is(self):
        d = DotDict({"count": 42, "tags": [1, 2, 3]})
        self.assertEqual(d.count, 42)
        self.assertEqual(d.tags, [1, 2, 3])
