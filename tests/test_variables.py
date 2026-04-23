import unittest
from polyapi.variables import render_variable

EXAMPLE = {
        "type": "serverVariable",
        "id": "181238j18231j",
        "name": "test",
        "context": "my3",
        "description": "a test variable",
        "visibilityMetadata": {
            "visibility": "ENVIRONMENT"
        },
        "variable": {
            "environmentId": "123818231",
            "secrecy": "NONE",
            "valueType": {
                "kind": "primitive",
                "type": "string"
            },
            "value": "some mock value"
        }
    }

OBJECT_EXAMPLE = {
        "type": "serverVariable",
        "id": "abc123",
        "name": "dict_vari",
        "context": "test",
        "description": "an object variable",
        "visibilityMetadata": {
            "visibility": "ENVIRONMENT"
        },
        "variable": {
            "environmentId": "123818231",
            "secrecy": "NONE",
            "valueType": {
                "kind": "object",
            },
            "value": '{"byebye": "world"}'
        }
    }


class T(unittest.TestCase):
    def test_render_variable(self):
        variable_str = render_variable(EXAMPLE)
        self.assertIn("class test", variable_str)

    def test_render_variable_string_uses_resp_text(self):
        variable_str = render_variable(EXAMPLE)
        self.assertIn("return resp.text", variable_str)
        self.assertNotIn("DotDict", variable_str)

    def test_render_object_variable_keeps_get_returning_str(self):
        variable_str = render_variable(OBJECT_EXAMPLE)
        self.assertIn("def get()", variable_str)
        self.assertIn("return resp.text", variable_str)

    def test_render_object_variable_adds_get_parsed(self):
        variable_str = render_variable(OBJECT_EXAMPLE)
        self.assertIn("def get_parsed()", variable_str)
        self.assertIn("def get_parsed_async()", variable_str)

    def test_render_object_variable_with_schema_generates_typed_dataclass(self):
        schema_example = {**OBJECT_EXAMPLE}
        schema_example["variable"] = {
            **OBJECT_EXAMPLE["variable"],
            "valueType": {
                "kind": "object",
                "schema": {
                    "type": "object",
                    "properties": {"hello": {"type": "string"}, "count": {"type": "integer"}},
                    "required": ["hello"],
                }
            }
        }
        variable_str = render_variable(schema_example)
        self.assertIn("@dataclass", variable_str)
        self.assertIn("class DictVari:", variable_str)
        self.assertIn("hello: str", variable_str)
        self.assertIn("count: Optional[int]", variable_str)
        self.assertIn("-> \"DictVari\"", variable_str)
        self.assertIn("return DictVari(**json.loads(resp.text))", variable_str)

    def test_render_string_variable_has_no_get_parsed(self):
        variable_str = render_variable(EXAMPLE)
        self.assertNotIn("get_parsed", variable_str)