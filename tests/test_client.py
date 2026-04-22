import ast
import unittest

from polyapi.client import (
    _extract_type_definitions,
    _import_bound_names,
    _is_safe_import,
    _rhs_is_type_construct,
    _wrap_code_in_try_except,
    render_client_function
)


def _parse_stmt(src: str) -> ast.stmt:
    return ast.parse(src).body[0]


def _parse_expr(src: str) -> ast.expr:
    return ast.parse(src, mode="eval").body


class TestImportBoundNames(unittest.TestCase):
    def test_simple_import(self):
        self.assertEqual(_import_bound_names(_parse_stmt("import pydantic")), {"pydantic"})

    def test_dotted_import_uses_root(self):
        self.assertEqual(_import_bound_names(_parse_stmt("import os.path")), {"os"})

    def test_import_with_alias(self):
        self.assertEqual(_import_bound_names(_parse_stmt("import numpy as np")), {"np"})

    def test_from_import(self):
        self.assertEqual(_import_bound_names(_parse_stmt("from pydantic import BaseModel")), {"BaseModel"})

    def test_from_import_with_alias(self):
        self.assertEqual(_import_bound_names(_parse_stmt("from pydantic import BaseModel as BM")), {"BM"})

    def test_multi_name_import(self):
        self.assertEqual(
            _import_bound_names(_parse_stmt("import os, sys")),
            {"os", "sys"},
        )

    def test_non_import_node_returns_empty(self):
        self.assertEqual(_import_bound_names(_parse_stmt("x = 555555")), set())


# 
# _is_safe_import
# 

class TestIsSafeImport(unittest.TestCase):
    def test_typing_is_safe(self):
        self.assertTrue(_is_safe_import(_parse_stmt("import typing")))

    def test_from_typing_is_safe(self):
        self.assertTrue(_is_safe_import(_parse_stmt("from typing import Optional")))

    def test_stdlib_is_safe(self):
        self.assertTrue(_is_safe_import(_parse_stmt("import os")))

    def test_third_party_is_not_safe(self):
        self.assertFalse(_is_safe_import(_parse_stmt("import pydantic")))

    def test_from_third_party_is_not_safe(self):
        self.assertFalse(_is_safe_import(_parse_stmt("from pydantic import BaseModel")))

    def test_non_import_node_returns_false(self):
        self.assertFalse(_is_safe_import(_parse_stmt("x = 666")))


# 
# _rhs_is_type_construct
# 

class TestRhsIsTypeConstruct(unittest.TestCase):
    def _rhs(self, src: str) -> ast.expr:
        return ast.parse(src).body[0].value  # type: ignore[attr-defined]

    #  typing subscripts that SHOULD match 
    def test_literal_subscript(self):
        self.assertTrue(_rhs_is_type_construct(self._rhs('Literal["a", "b"]')))

    def test_dict_subscript(self):
        self.assertTrue(_rhs_is_type_construct(self._rhs("Dict[str, Any]")))

    def test_optional_subscript(self):
        self.assertTrue(_rhs_is_type_construct(self._rhs("Optional[int]")))

    def test_list_subscript(self):
        self.assertTrue(_rhs_is_type_construct(self._rhs("list[int]")))

    def test_union_subscript(self):
        self.assertTrue(_rhs_is_type_construct(self._rhs("Union[str, int]")))

    #  subscripts that must NOT match (the too-broad bug we fixed) 
    def test_dict_lookup_not_a_type(self):
        self.assertFalse(_rhs_is_type_construct(self._rhs('config["key"]')))

    def test_list_index_not_a_type(self):
        self.assertFalse(_rhs_is_type_construct(self._rhs("not_my_list[0]")))

    def test_arbitrary_subscript_not_a_type(self):
        self.assertFalse(_rhs_is_type_construct(self._rhs("someWeirdfunky()[0]")))

    #  union with | 
    def test_bitor_union(self):
        self.assertTrue(_rhs_is_type_construct(self._rhs("str | int")))

    def test_three_way_bitor_union(self):
        self.assertTrue(_rhs_is_type_construct(self._rhs("str | int | None")))

    #  functional TypedDict / NamedTuple / NewType 
    def test_typed_dict_call(self):
        self.assertTrue(_rhs_is_type_construct(self._rhs('TypedDict("X", {"a": int})')))

    def test_named_tuple_call(self):
        self.assertTrue(_rhs_is_type_construct(self._rhs('NamedTuple("P", [("x", int)])')))

    def test_new_type_call(self):
        self.assertTrue(_rhs_is_type_construct(self._rhs('NewType("UserId", int)')))

    #  plain values that must not match 
    def test_string_literal_not_a_type(self):
        self.assertFalse(_rhs_is_type_construct(self._rhs('"yelloooo"')))

    def test_function_call_not_a_type(self):
        self.assertFalse(_rhs_is_type_construct(self._rhs("someones_func()")))

    def test_integer_not_a_type(self):
        self.assertFalse(_rhs_is_type_construct(self._rhs("42")))


class TestExtractTypeDefinitions(unittest.TestCase):

    def _extract(self, code: str):
        return _extract_type_definitions(code)

    # safe imports go 2 type_imports 
    def test_typing_import_goes_to_type_imports(self):
        code = "from typing import Optional\nx = 1"
        type_imports, type_defs, runtime = self._extract(code)
        self.assertIn("Optional", type_imports)
        self.assertNotIn("Optional", runtime)

    def test_stdlib_import_goes_to_type_imports(self):
        code = "import os\nx = 1"
        type_imports, _, runtime = self._extract(code)
        self.assertIn("import os", type_imports)
        self.assertNotIn("import os", runtime)

    #  third-party import stays in runtime by default 
    def test_third_party_import_stays_in_runtime(self):
        code = "import requests\nresult = requests.get('http://x')"
        type_imports, type_defs, runtime = self._extract(code)
        self.assertNotIn("requests", type_imports)
        self.assertIn("requests", runtime)

    #  classes go to type_defs 
    def test_class_goes_to_type_defs(self):
        code = "class Foo:\n    x: int = 0\ndef bar(): pass"
        _, type_defs, runtime = self._extract(code)
        self.assertIn("class Foo", type_defs)
        self.assertNotIn("class Foo", runtime)

    def test_function_stays_in_runtime(self):
        code = "class Foo:\n    pass\ndef my_func(): return 1"
        _, type_defs, runtime = self._extract(code)
        self.assertIn("my_func", runtime)
        self.assertNotIn("my_func", type_defs)

    #  Literal / typing alias assignments go to type_defs 
    def test_literal_assignment_goes_to_type_defs(self):
        code = 'Status = Literal["active", "inactive"]\ndef f(): pass'
        _, type_defs, runtime = self._extract(code)
        self.assertIn("Status", type_defs)
        self.assertNotIn("Status", runtime)

    def test_bitor_union_assignment_goes_to_type_defs(self):
        code = "MyUnion = str | int\ndef f(): pass"
        _, type_defs, runtime = self._extract(code)
        self.assertIn("MyUnion", type_defs)
        self.assertNotIn("MyUnion", runtime)

    #  dict lookup stays in runtime (the narrow-subscript fix) 
    def test_dict_lookup_stays_in_runtime(self):
        code = 'DEFAULT = config["timeout"]\ndef f(): pass'
        _, type_defs, runtime = self._extract(code)
        self.assertIn("DEFAULT", runtime)
        self.assertNotIn("DEFAULT", type_defs)

    #  class dependencies are transitively hoisted 
    def test_class_dep_goes_to_type_defs(self):
        code = (
            "from typing import TypedDict\n"
            "class Inner(TypedDict):\n"
            "    val: int\n"
            "class Outer:\n"
            "    inner: Inner\n"
            "def f(): pass"
        )
        _, type_defs, runtime = self._extract(code)
        self.assertIn("Inner", type_defs)
        self.assertIn("Outer", type_defs)

    #  third-party import needed by a class is hoisted (pydantic fix) 
    def test_third_party_base_class_import_is_hoisted(self):
        code = (
            "import pydantic\n"
            "class MyModel(pydantic.BaseModel):\n"
            "    name: str\n"
            "def f(): pass"
        )
        type_imports, type_defs, runtime = self._extract(code)
        self.assertIn("pydantic", type_imports)
        self.assertNotIn("import pydantic", runtime)
        self.assertIn("MyModel", type_defs)

    def test_from_import_base_class_is_hoisted(self):
        code = (
            "from pydantic import BaseModel\n"
            "class MyModel(BaseModel):\n"
            "    name: str\n"
            "def f(): pass"
        )
        type_imports, type_defs, runtime = self._extract(code)
        self.assertIn("BaseModel", type_imports)
        self.assertNotIn("BaseModel", runtime)

    #  syntax error falls back to returning all code as runtime 
    def test_syntax_error_returns_all_as_runtime(self):
        bad = "def f(\n  broken syntax!!!"
        type_imports, type_defs, runtime = self._extract(bad)
        self.assertEqual(type_imports, "")
        self.assertEqual(type_defs, "")
        self.assertEqual(runtime, bad)

    #  empty input produces three empty strings 
    def test_empty_code(self):
        self.assertEqual(self._extract(""), ("", "", ""))


class TestWrapCodeInTryExcept(unittest.TestCase):

    def test_runtime_code_is_wrapped(self):
        code = "import requests\nresult = requests.get('http://x')"
        _, wrapped = _wrap_code_in_try_except("myFunc", code)
        self.assertIn("try:", wrapped)
        self.assertIn("except ImportError", wrapped)
        self.assertIn("myFunc", wrapped)

    def test_type_defs_go_to_module_scope(self):
        code = "from typing import Optional\nclass Foo:\n    x: Optional[int] = None\ndef f(): pass"
        module_scope, wrapped = _wrap_code_in_try_except("f", code)
        self.assertIn("Optional", module_scope)
        self.assertIn("Foo", module_scope)
        self.assertNotIn("class Foo", wrapped)

    def test_empty_runtime_emits_pass(self):
        # Code that is entirely type definitions — runtime body should be 'pass'
        code = "from typing import Optional\nclass Foo:\n    x: Optional[int] = None"
        _, wrapped = _wrap_code_in_try_except("myFunc", code)
        self.assertIn("pass", wrapped)
        self.assertIn("try:", wrapped)

    def test_whitespace_only_runtime_emits_pass(self):
        code = "from typing import List\n"
        _, wrapped = _wrap_code_in_try_except("myFunc", code)
        self.assertIn("pass", wrapped)

    def test_warning_message_contains_function_name(self):
        code = "x = 1"
        _, wrapped = _wrap_code_in_try_except("specialFunc", code)
        self.assertIn("specialFunc", wrapped)
        self.assertIn("logger.warning", wrapped)

    def test_multiline_runtime_is_indented(self):
        code = "import requests\na = 1\nb = 2"
        _, wrapped = _wrap_code_in_try_except("f", code)
        # Every line inside the try block should be indented
        try_block = wrapped.split("try:\n")[1].split("\nexcept")[0]
        for line in try_block.splitlines():
            if line.strip():
                self.assertTrue(line.startswith("    "), repr(line))


class TestRenderClientFunction(unittest.TestCase):
    _SIMPLE_CODE = (
        "import requests\n"
        "def execute(url: str) -> str:\n"
        "    return requests.get(url).text\n"
    )
    _SIMPLE_ARGS = [{"name": "url", "required": True, "type": {"kind": "string"}}]
    _SIMPLE_RETURN = {"kind": "string"}

    def test_returns_three_parts(self):
        result = render_client_function("myFunc", self._SIMPLE_CODE, self._SIMPLE_ARGS, self._SIMPLE_RETURN)
        self.assertEqual(len(result), 3)

    def test_module_scope_types_string(self):
        module_scope, _, _ = render_client_function("myFunc", self._SIMPLE_CODE, self._SIMPLE_ARGS, self._SIMPLE_RETURN)
        self.assertIsInstance(module_scope, str)

    def test_wrapped_runtime_contains_try(self):
        _, wrapped, _ = render_client_function("myFunc", self._SIMPLE_CODE, self._SIMPLE_ARGS, self._SIMPLE_RETURN)
        self.assertIn("try:", wrapped)

    def test_func_type_defs_contains_return_type(self):
        _, _, func_type_defs = render_client_function("myFunc", self._SIMPLE_CODE, self._SIMPLE_ARGS, self._SIMPLE_RETURN)
        self.assertIsInstance(func_type_defs, str)
        self.assertGreater(len(func_type_defs), 0)

    def test_pydantic_model_import_hoisted_to_module_scope(self):
        code = (
            "import pydantic\n"
            "class Item(pydantic.BaseModel):\n"
            "    name: str\n"
            "def execute() -> Item:\n"
            "    return Item(name='x')\n"
        )
        module_scope, wrapped, _ = render_client_function("execute", code, [], {"kind": "object"})
        self.assertIn("pydantic", module_scope)
        self.assertIn("Item", module_scope)
        self.assertNotIn("class Item", wrapped)

    def test_type_only_code_produces_pass_in_try(self):
        code = (
            "from typing import Optional\n"
            "class Foo:\n"
            "    x: Optional[int] = None\n"
        )
        _, wrapped, _ = render_client_function("myFunc", code, [], {"kind": "null"})
        self.assertIn("pass", wrapped)


if __name__ == "__main__":
    unittest.main()
