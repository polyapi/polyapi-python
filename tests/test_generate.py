import unittest
import os
import shutil
import importlib.util
from polyapi.utils import get_type_and_def, rewrite_reserved
from polyapi.generate import render_spec, create_empty_schemas_module

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

# Test spec with missing function data (simulating no_types=true)
NO_TYPES_SPEC = {
    "id": "test-id-123",
    "type": "serverFunction",
    "context": "test",
    "name": "testFunction",
    "description": "A test function for no-types mode",
    # Note: no "function" field, simulating no_types=true response
}

# Test spec with minimal function data
MINIMAL_FUNCTION_SPEC = {
    "id": "test-id-456",
    "type": "apiFunction",
    "context": "test",
    "name": "minimalFunction",
    "description": "A minimal function spec",
    "function": {
        # Note: no "arguments" or "returnType" fields
    }
}


class T(unittest.TestCase):
    def test_get_type_and_def(self):
        arg_type, arg_def = get_type_and_def(OPENAPI_FUNCTION)
        self.assertEqual(arg_type, "Callable[[List[WebhookEventTypeElement], Dict, Dict, Dict], None]")

    def test_rewrite_reserved(self):
        rv = rewrite_reserved("from")
        self.assertEqual(rv, "_from")

    def test_render_spec_no_function_data(self):
        """Test that render_spec handles specs with no function data gracefully"""
        func_str, func_type_defs = render_spec(NO_TYPES_SPEC)
        
        # Should generate a function even without function data
        self.assertIsNotNone(func_str)
        self.assertIsNotNone(func_type_defs)
        self.assertIn("testFunction", func_str)
        self.assertIn("test-id-123", func_str)

    def test_render_spec_minimal_function_data(self):
        """Test that render_spec handles specs with minimal function data"""
        func_str, func_type_defs = render_spec(MINIMAL_FUNCTION_SPEC)
        
        # Should generate a function with fallback types
        self.assertIsNotNone(func_str)
        self.assertIsNotNone(func_type_defs)
        self.assertIn("minimalFunction", func_str)
        self.assertIn("test-id-456", func_str)
        # Should use Any as fallback return type in the type definitions
        self.assertIn("Any", func_type_defs)

    def test_create_empty_schemas_module(self):
        """Test that create_empty_schemas_module creates the necessary files"""
        # Clean up any existing schemas directory
        schemas_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "polyapi", "schemas")
        if os.path.exists(schemas_path):
            shutil.rmtree(schemas_path)
        
        # Create empty schemas module
        create_empty_schemas_module()
        
        # Verify the directory and __init__.py file were created
        self.assertTrue(os.path.exists(schemas_path))
        init_path = os.path.join(schemas_path, "__init__.py")
        self.assertTrue(os.path.exists(init_path))
        
        # Verify the content of __init__.py includes dynamic schema handling
        with open(init_path, "r") as f:
            content = f.read()
            self.assertIn("Empty schemas module for no-types mode", content)
            self.assertIn("_GenericSchema", content)
            self.assertIn("_SchemaModule", content)
            self.assertIn("__getattr__", content)
        
        # Clean up
        shutil.rmtree(schemas_path)

    def test_no_types_workflow(self):
        """Test the complete no-types workflow including schema imports and function parsing"""
        import tempfile
        import sys
        from unittest.mock import patch
        
        # Clean up any existing schemas directory
        schemas_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "polyapi", "schemas")
        if os.path.exists(schemas_path):
            shutil.rmtree(schemas_path)
        
        # Mock get_specs to return empty list (simulating no functions)
        with patch('polyapi.generate.get_specs', return_value=[]):
            try:
                # This should exit with SystemExit due to no functions
                from polyapi.generate import generate
                generate(no_types=True)
            except SystemExit:
                pass  # Expected when no functions exist
        
        # Verify schemas module was created
        self.assertTrue(os.path.exists(schemas_path))
        init_path = os.path.join(schemas_path, "__init__.py")
        self.assertTrue(os.path.exists(init_path))
        
        # Test that we can import schemas and use arbitrary schema names
        from polyapi import schemas
        
        # Test various schema access
        Response = schemas.Response
        CustomType = schemas.CustomType
        AnyName = schemas.SomeArbitrarySchemaName
        
        # All should return the same generic schema class type
        self.assertEqual(type(Response).__name__, '_NestedSchemaAccess')
        self.assertEqual(type(CustomType).__name__, '_NestedSchemaAccess')
        self.assertEqual(type(AnyName).__name__, '_NestedSchemaAccess')
        
        # Test creating instances
        response_instance = Response()
        custom_instance = CustomType()
        
        self.assertIsInstance(response_instance, dict)
        self.assertIsInstance(custom_instance, dict)
        
        # Test that function code with schema references can be parsed
        test_code = '''
from polyapi import polyCustom, schemas

def test_function() -> schemas.Response:
    polyCustom["executionId"] = "123"
    return polyCustom
'''
        
        # Create a temporary file with the test code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_code)
            temp_file = f.name
        
        try:
            # Test that the parser can handle this code
            from polyapi.parser import parse_function_code
            result = parse_function_code(test_code, 'test_function', 'test_context')
            
            self.assertEqual(result['name'], 'test_function')
            self.assertEqual(result['context'], 'test_context')
            # Return type should be Any since we're in no-types mode
            self.assertEqual(result['types']['returns']['type'], 'Any')
            
        finally:
            # Clean up temp file
            os.unlink(temp_file)
        
        # Clean up schemas directory
        shutil.rmtree(schemas_path)

    def test_nested_schema_access(self):
        """Test that nested schema access like schemas.random.random2.random3 works"""
        # Clean up any existing schemas directory
        schemas_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "polyapi", "schemas")
        if os.path.exists(schemas_path):
            shutil.rmtree(schemas_path)
        
        # Create empty schemas module
        create_empty_schemas_module()
        
        # Test that we can import and use nested schemas
        from polyapi import schemas
        
        # Test various levels of nesting
        simple = schemas.Response
        nested = schemas.random.random2
        deep_nested = schemas.api.v1.user.profile.data
        very_deep = schemas.some.very.deep.nested.schema.access
        
        # All should be _NestedSchemaAccess instances
        self.assertEqual(type(simple).__name__, '_NestedSchemaAccess')
        self.assertEqual(type(nested).__name__, '_NestedSchemaAccess')
        self.assertEqual(type(deep_nested).__name__, '_NestedSchemaAccess')
        self.assertEqual(type(very_deep).__name__, '_NestedSchemaAccess')
        
        # Test that they can be called and return generic schemas
        simple_instance = simple()
        nested_instance = nested()
        deep_instance = deep_nested()
        very_deep_instance = very_deep()
        
        # All should be dictionaries
        self.assertIsInstance(simple_instance, dict)
        self.assertIsInstance(nested_instance, dict)
        self.assertIsInstance(deep_instance, dict)
        self.assertIsInstance(very_deep_instance, dict)
        
        # Test that function code with nested schemas can be parsed
        test_code = '''
from polyapi import polyCustom, schemas

def test_nested_function() -> schemas.api.v1.user.profile:
    return schemas.api.v1.user.profile()
'''
        
        from polyapi.parser import parse_function_code
        result = parse_function_code(test_code, 'test_nested_function', 'test_context')
        
        self.assertEqual(result['name'], 'test_nested_function')
        self.assertEqual(result['context'], 'test_context')
        # Return type should be Any since we're in no-types mode
        self.assertEqual(result['types']['returns']['type'], 'Any')
        
        # Clean up schemas directory
        shutil.rmtree(schemas_path)
