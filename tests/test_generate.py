import unittest
import os
import shutil
import importlib.util
from unittest.mock import patch, MagicMock
from polyapi.utils import get_type_and_def, rewrite_reserved
from polyapi.generate import render_spec, create_empty_schemas_module, generate_functions, create_function
from polyapi.poly_schemas import generate_schemas, create_schema
from polyapi.variables import generate_variables, create_variable

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

    def test_error_handling_generate_functions(self):
        """Test that generate_functions handles errors gracefully and continues with other functions"""
        # Mock create_function to raise an exception for one function
        failing_spec = {
            "id": "failing-function-123",
            "type": "serverFunction",
            "context": "test",
            "name": "failingFunction",
            "description": "A function that will fail to generate",
        }
        
        working_spec = {
            "id": "working-function-456",
            "type": "serverFunction", 
            "context": "test",
            "name": "workingFunction",
            "description": "A function that will generate successfully",
        }
        
        specs = [failing_spec, working_spec]
        
        # Mock create_function to fail on the first call and succeed on the second
        with patch('polyapi.generate.create_function') as mock_create:
            mock_create.side_effect = [Exception("Schema generation failed"), None]
            
            # Capture logging output
            with patch('polyapi.generate.logging.warning') as mock_warning:
                generate_functions(specs)
                
                # Verify that create_function was called twice (once for each spec)
                self.assertEqual(mock_create.call_count, 2)
                
                # Verify that warning messages were logged  
                mock_warning.assert_any_call("WARNING: Failed to generate function test.failingFunction (id: failing-function-123): Schema generation failed")
                mock_warning.assert_any_call("WARNING: 1 function(s) failed to generate:")
                mock_warning.assert_any_call("  - test.failingFunction (id: failing-function-123)")

    def test_error_handling_generate_schemas(self):
        """Test that generate_schemas handles errors gracefully and continues with other schemas"""
        from polyapi.typedefs import SchemaSpecDto
        
        failing_spec = {
            "id": "failing-schema-123",
            "type": "schema",
            "context": "test",
            "name": "failingSchema",
            "description": "A schema that will fail to generate",
            "definition": {}
        }
        
        working_spec = {
            "id": "working-schema-456", 
            "type": "schema",
            "context": "test",
            "name": "workingSchema",
            "description": "A schema that will generate successfully",
            "definition": {}
        }
        
        specs = [failing_spec, working_spec]
        
        # Mock create_schema to fail on the first call and succeed on the second
        with patch('polyapi.poly_schemas.create_schema') as mock_create:
            mock_create.side_effect = [Exception("Schema generation failed"), None]
            
            # Capture logging output
            with patch('polyapi.poly_schemas.logging.warning') as mock_warning:
                generate_schemas(specs)
                
                # Verify that create_schema was called twice (once for each spec)
                self.assertEqual(mock_create.call_count, 2)
                
                # Verify that warning messages were logged
                mock_warning.assert_any_call("WARNING: Failed to generate schema test.failingSchema (id: failing-schema-123): Schema generation failed")
                mock_warning.assert_any_call("WARNING: 1 schema(s) failed to generate:")
                mock_warning.assert_any_call("  - test.failingSchema (id: failing-schema-123)")

    def test_error_handling_generate_variables(self):
        """Test that generate_variables handles errors gracefully and continues with other variables"""
        from polyapi.typedefs import VariableSpecDto
        
        failing_spec = {
            "id": "failing-variable-123",
            "type": "serverVariable",
            "context": "test",
            "name": "failingVariable",
            "description": "A variable that will fail to generate",
            "variable": {
                "valueType": {"kind": "primitive", "type": "string"},
                "secrecy": "PUBLIC"
            }
        }
        
        working_spec = {
            "id": "working-variable-456",
            "type": "serverVariable", 
            "context": "test",
            "name": "workingVariable",
            "description": "A variable that will generate successfully",
            "variable": {
                "valueType": {"kind": "primitive", "type": "string"},
                "secrecy": "PUBLIC"
            }
        }
        
        specs = [failing_spec, working_spec]
        
        # Mock create_variable to fail on the first call and succeed on the second
        with patch('polyapi.variables.create_variable') as mock_create:
            mock_create.side_effect = [Exception("Variable generation failed"), None]
            
            # Capture logging output
            with patch('polyapi.variables.logging.warning') as mock_warning:
                generate_variables(specs)
                
                # Verify that create_variable was called twice (once for each spec)
                self.assertEqual(mock_create.call_count, 2)
                
                # Verify that warning messages were logged
                mock_warning.assert_any_call("WARNING: Failed to generate variable test.failingVariable (id: failing-variable-123): Variable generation failed")
                mock_warning.assert_any_call("WARNING: 1 variable(s) failed to generate:")
                mock_warning.assert_any_call("  - test.failingVariable (id: failing-variable-123)")

    def test_error_handling_webhook_generation(self):
        """Test that render_webhook_handle handles errors gracefully during generation"""
        from polyapi.webhook import render_webhook_handle
        
        # Test with problematic arguments that might cause rendering to fail
        with patch('polyapi.webhook.parse_arguments') as mock_parse:
            mock_parse.side_effect = Exception("Invalid webhook arguments")
            
            with patch('polyapi.webhook.logging.warning') as mock_warning:
                func_str, func_defs = render_webhook_handle(
                    function_type="webhookHandle",
                    function_context="test", 
                    function_name="failingWebhook",
                    function_id="webhook-123",
                    function_description="A webhook that fails to generate",
                    arguments=[],
                    return_type={}
                )
                
                # Should return empty strings on failure
                self.assertEqual(func_str, "")
                self.assertEqual(func_defs, "")
                
                # Should log a warning
                mock_warning.assert_called_once_with("Failed to render webhook handle test.failingWebhook (id: webhook-123): Invalid webhook arguments")

    def test_atomic_function_generation_failure(self):
        """Test that function generation failures don't leave partial corrupted files"""
        import tempfile
        from polyapi.generate import add_function_file
        
        failing_spec = {
            "id": "failing-function-123",
            "type": "serverFunction",
            "context": "test",
            "name": "failingFunction", 
            "description": "A function that will fail to generate",
        }
        
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock render_spec to fail after being called
            with patch('polyapi.generate.render_spec') as mock_render:
                mock_render.side_effect = Exception("Rendering failed")
                
                # Verify that the function generation fails
                with self.assertRaises(Exception):
                    add_function_file(temp_dir, "failingFunction", failing_spec)
                
                # Verify no partial files were left behind
                files_in_dir = os.listdir(temp_dir)
                # Should only have __init__.py from init_the_init, no corrupted function files
                self.assertNotIn("failing_function.py", files_in_dir)
                self.assertNotIn("failingFunction.py", files_in_dir)
                
                # If __init__.py exists, it should not contain partial imports
                init_path = os.path.join(temp_dir, "__init__.py")
                if os.path.exists(init_path):
                    with open(init_path, "r") as f:
                        init_content = f.read()
                    self.assertNotIn("from . import failing_function", init_content)
                    self.assertNotIn("from . import failingFunction", init_content)

    def test_atomic_variable_generation_failure(self):
        """Test that variable generation failures don't leave partial corrupted files"""
        import tempfile
        from polyapi.variables import add_variable_to_init
        
        failing_spec = {
            "id": "failing-variable-123",
            "type": "serverVariable",
            "context": "test",
            "name": "failingVariable",
            "description": "A variable that will fail to generate",
            "variable": {
                "valueType": {"kind": "primitive", "type": "string"},
                "secrecy": "PUBLIC"
            }
        }
        
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock render_variable to fail
            with patch('polyapi.variables.render_variable') as mock_render:
                mock_render.side_effect = Exception("Variable rendering failed")
                
                # Verify that the variable generation fails
                with self.assertRaises(Exception):
                    add_variable_to_init(temp_dir, failing_spec)
                
                # Verify no partial files were left behind and __init__.py wasn't corrupted
                init_path = os.path.join(temp_dir, "__init__.py")
                if os.path.exists(init_path):
                    with open(init_path, "r") as f:
                        init_content = f.read()
                    # Should not contain partial variable content or broken imports
                    self.assertNotIn("failingVariable", init_content)
                    self.assertNotIn("class failingVariable", init_content)

    def test_atomic_schema_generation_failure(self):
        """Test that schema generation failures don't leave partial files or directories"""
        with patch('tempfile.TemporaryDirectory') as mock_temp_dir:
            mock_temp_dir.return_value.__enter__.return_value = "/tmp/test_dir"
            
            # Mock the render function to fail
            with patch('polyapi.poly_schemas.render_poly_schema', side_effect=Exception("Schema generation failed")):
                with patch('logging.warning') as mock_warning:
                    # This should not crash and should log a warning
                    schemas = [
                        {
                            "id": "schema1",
                            "name": "TestSchema",
                            "context": "",
                            "type": "schema",
                            "definition": {"type": "object", "properties": {"test": {"type": "string"}}}
                        }
                    ]
                    generate_schemas(schemas)
                    
                    # Should have logged a warning about the failed schema
                    mock_warning.assert_called()
                    warning_calls = [call[0][0] for call in mock_warning.call_args_list]
                    # Check that both the main warning and summary warning are present
                    self.assertTrue(any("Failed to generate schema" in call for call in warning_calls))
                    self.assertTrue(any("TestSchema" in call for call in warning_calls))
                    self.assertTrue(any("schema1" in call for call in warning_calls))

    def test_broken_imports_not_left_on_function_failure(self):
        """Test that if a function fails after directories are created, we don't leave broken imports"""
        import tempfile
        import shutil
        import os
        from polyapi import generate
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock polyapi directory structure
            polyapi_dir = os.path.join(temp_dir, "polyapi")
            os.makedirs(polyapi_dir)
            
            # Mock spec that would create a nested structure: poly/context/function_name
            spec = {
                "id": "test-func-id",
                "name": "test_function",
                "context": "test_context", 
                "type": "apiFunction",
                "description": "Test function",
                "function": {
                    "arguments": [],
                    "returnType": {"kind": "any"}
                }
            }
            
            # Mock the add_function_file to fail AFTER directories are created
            
            def failing_add_function_file(*args, **kwargs):
                raise Exception("Function file creation failed")
            
            with patch('polyapi.generate.add_function_file', side_effect=failing_add_function_file):
                with patch('os.path.dirname') as mock_dirname:
                    mock_dirname.return_value = polyapi_dir
                    with patch('logging.warning') as mock_warning:
                        
                        # This should fail gracefully 
                        try:
                            generate.create_function(spec)
                        except:
                            pass  # Expected to fail
                        
                        # Check that no intermediate directories were left behind
                        poly_dir = os.path.join(polyapi_dir, "poly")
                        if os.path.exists(poly_dir):
                            context_dir = os.path.join(poly_dir, "test_context")
                            
                            # If intermediate directories exist, they should not have broken imports
                            if os.path.exists(context_dir):
                                init_file = os.path.join(context_dir, "__init__.py")
                                if os.path.exists(init_file):
                                    with open(init_file, 'r') as f:
                                        content = f.read()
                                    # Should not contain import for the failed function
                                    self.assertNotIn("test_function", content)
                                    
                                # The function directory should not exist
                                func_dir = os.path.join(context_dir, "test_function") 
                                self.assertFalse(os.path.exists(func_dir))

    def test_intermediate_init_files_handle_failure_correctly(self):
        """Test that intermediate __init__.py files are handled correctly when function generation fails"""
        import tempfile
        import os
        from polyapi import generate
        
        with tempfile.TemporaryDirectory() as temp_dir:
            polyapi_dir = os.path.join(temp_dir, "polyapi") 
            os.makedirs(polyapi_dir)
            
            # Create a poly directory and context directory beforehand
            poly_dir = os.path.join(polyapi_dir, "poly")
            context_dir = os.path.join(poly_dir, "test_context")
            os.makedirs(context_dir)
            
            # Put some existing content in the context __init__.py
            init_file = os.path.join(context_dir, "__init__.py")
            with open(init_file, 'w') as f:
                f.write("# Existing context init file\nfrom . import existing_function\n")
            
            spec = {
                "id": "test-func-id", 
                "name": "failing_function",
                "context": "test_context",
                "type": "apiFunction", 
                "description": "Test function",
                "function": {
                    "arguments": [],
                    "returnType": {"kind": "any"}
                }
            }
            
            # Mock add_function_file to fail
            def failing_add_function_file(full_path, function_name, spec):
                # This simulates failure AFTER intermediate directories are processed
                # but BEFORE the final function file is written
                raise Exception("Function file creation failed")
            
            with patch('polyapi.generate.add_function_file', side_effect=failing_add_function_file):
                with patch('os.path.dirname') as mock_dirname:
                    mock_dirname.return_value = polyapi_dir
                    
                    # This should fail but handle cleanup gracefully
                    try:
                        generate.create_function(spec)
                    except:
                        pass  # Expected to fail
                    
                    # The context __init__.py should not contain import for failed function
                    with open(init_file, 'r') as f:
                        content = f.read()
                    
                    # Should still have existing content
                    self.assertIn("existing_function", content)
                    # Should NOT have the failed function
                    self.assertNotIn("failing_function", content)
                    
                    # The failed function directory should not exist
                    func_dir = os.path.join(context_dir, "failing_function")
                    self.assertFalse(os.path.exists(func_dir))
