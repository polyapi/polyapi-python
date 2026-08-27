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


# _is_safe_import

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


# _rhs_is_type_construct

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

    # attribute-qualified subscripts (typing.X[...]) 
    # node.value is ast.Attribute, not ast.Name — the Name guard silently
    # rejects these, so fully-qualified generics are never hoisted to module scope.

    def test_attribute_optional_is_type(self):
        # typing.Optional[int] — value is Attribute, currently returns False
        self.assertTrue(_rhs_is_type_construct(self._rhs("typing.Optional[int]")))

    def test_attribute_dict_is_type(self):
        # typing.Dict[str, Any] — same miss
        self.assertTrue(_rhs_is_type_construct(self._rhs("typing.Dict[str, Any]")))

    def test_attribute_union_is_type(self):
        # typing.Union[str, int]
        self.assertTrue(_rhs_is_type_construct(self._rhs("typing.Union[str, int]")))

    # TypeVar / ParamSpec / TypeVarTuple functional forms
    # These are missing from the ('TypedDict', 'NamedTuple', 'NewType') allowlist,
    # so TypeVar assignments are treated as runtime values and never hoisted.

    def test_typevar_call_is_type(self):
        # T = TypeVar("T") — currently returns False
        self.assertTrue(_rhs_is_type_construct(self._rhs('TypeVar("T")')))

    def test_typevar_with_bound_is_type(self):
        # T = TypeVar("T", bound=str)
        self.assertTrue(_rhs_is_type_construct(self._rhs('TypeVar("T", bound=str)')))

    def test_paramspec_call_is_type(self):
        # P = ParamSpec("P") — currently returns False
        self.assertTrue(_rhs_is_type_construct(self._rhs('ParamSpec("P")')))

    def test_typevartuple_call_is_type(self):
        # Ts = TypeVarTuple("Ts") — currently returns False
        self.assertTrue(_rhs_is_type_construct(self._rhs('TypeVarTuple("Ts")')))

    # attribute-qualified functional forms (typing.TypedDict / typing.NewType)
    # node.func is ast.Attribute — the isinstance(node.func, ast.Name) guard rejects these.

    def test_attribute_typed_dict_call_is_type(self):
        # typing.TypedDict("X", {"a": int}) — func is Attribute, currently False
        self.assertTrue(_rhs_is_type_construct(self._rhs('typing.TypedDict("X", {"a": int})')))

    def test_attribute_new_type_call_is_type(self):
        # typing.NewType("UserId", int) — same miss
        self.assertTrue(_rhs_is_type_construct(self._rhs('typing.NewType("UserId", int)')))


# Exhaustive parametric coverage of _rhs_is_type_construct

_TRUE_CASES = [
    # Subscript — bare name (original set)
    ('Literal["a"]',              ast.Subscript),
    ('Dict[str, Any]',            ast.Subscript),
    ('Optional[int]',             ast.Subscript),
    ('list[int]',                 ast.Subscript),
    ('Union[str, int]',           ast.Subscript),
    # Subscript — qualified name (typing_extensions.X[...])
    ('typing_extensions.Optional[int]',   ast.Subscript),
    ('typing_extensions.Dict[str, Any]',  ast.Subscript),
    ('typing_extensions.Union[str, int]', ast.Subscript),
    # Subscript — full typing_extensions.__all__ subscriptable names
    ('ClassVar[int]',             ast.Subscript),
    ('Final[int]',                ast.Subscript),
    ('Annotated[int, ...]',       ast.Subscript),
    ('Required[int]',             ast.Subscript),
    ('NotRequired[int]',          ast.Subscript),
    ('ReadOnly[int]',             ast.Subscript),
    ('Type[int]',                 ast.Subscript),
    ('Concatenate[int, ...]',     ast.Subscript),
    ('Unpack[Ts]',                ast.Subscript),
    ('TypeGuard[int]',            ast.Subscript),
    ('TypeIs[int]',               ast.Subscript),
    ('LiteralString[str]',        ast.Subscript),  # used as annotation
    ('Self[int]',                 ast.Subscript),
    ('Never[int]',                ast.Subscript),
    ('NoReturn[int]',             ast.Subscript),
    ('Callable[[int], str]',      ast.Subscript),
    ('Awaitable[int]',            ast.Subscript),
    ('Coroutine[int, int, int]',  ast.Subscript),
    ('AsyncIterable[int]',        ast.Subscript),
    ('AsyncIterator[int]',        ast.Subscript),
    ('AsyncGenerator[int, int]',  ast.Subscript),
    ('AsyncContextManager[int]',  ast.Subscript),
    ('Iterable[int]',             ast.Subscript),
    ('Iterator[int]',             ast.Subscript),
    ('Generator[int, int, int]',  ast.Subscript),
    ('ContextManager[int]',       ast.Subscript),
    ('Container[int]',            ast.Subscript),
    ('Collection[int]',           ast.Subscript),
    ('Reversible[int]',           ast.Subscript),
    ('Mapping[str, int]',         ast.Subscript),
    ('MutableMapping[str, int]',  ast.Subscript),
    ('MappingView[str]',          ast.Subscript),
    ('KeysView[str]',             ast.Subscript),
    ('ItemsView[str, int]',       ast.Subscript),
    ('ValuesView[int]',           ast.Subscript),
    ('Sequence[int]',             ast.Subscript),
    ('MutableSequence[int]',      ast.Subscript),
    ('MutableSet[int]',           ast.Subscript),
    ('AbstractSet[int]',          ast.Subscript),
    ('IO[str]',                   ast.Subscript),
    ('Match[str]',                ast.Subscript),
    ('Pattern[str]',              ast.Subscript),
    ('FrozenSet[int]',            ast.Subscript),
    ('Tuple[int, str]',           ast.Subscript),
    ('Set[int]',                  ast.Subscript),
    ('DefaultDict[str, int]',     ast.Subscript),
    ('OrderedDict[str, int]',     ast.Subscript),
    ('Counter[str]',              ast.Subscript),
    ('Deque[int]',                ast.Subscript),
    ('ChainMap[str, int]',        ast.Subscript),
    ('Generic[T]',                ast.Subscript),
    ('Protocol[T]',               ast.Subscript),
    ('AnyStr[str]',               ast.Subscript),
    # BinOp with | — all leaves must be unambiguously type-like
    ('str | int',                         ast.BinOp),
    ('str | int | None',                  ast.BinOp),
    ('Optional[str] | None',              ast.BinOp),
    ('List[int] | None',                  ast.BinOp),
    # typing-module attributes are valid union leaves
    ('typing.Optional | None',            ast.BinOp),
    ('typing_extensions.Optional | None', ast.BinOp),
    # typing subscript on either side
    ('typing.Optional[str] | None',       ast.BinOp),
    # Call — bare name
    ('TypedDict("X", {})',           ast.Call),
    ('NamedTuple("P", [])',          ast.Call),
    ('NewType("U", int)',            ast.Call),
    ('TypeVar("T")',                 ast.Call),
    ('TypeVar("T", bound=str)',      ast.Call),
    ('ParamSpec("P")',               ast.Call),
    ('TypeVarTuple("Ts")',           ast.Call),
    ('TypeAliasType("MyAlias", int)', ast.Call),
    # Call — qualified name (typing_extensions.X(...))
    ('typing_extensions.TypedDict("X", {})', ast.Call),
    ('typing_extensions.NewType("U", int)',  ast.Call),
    ('typing_extensions.TypeVar("T")',       ast.Call),
]

_FALSE_CASES = [
    ('config["key"]',    ast.Subscript),   # dict lookup
    ('my_list[0]',       ast.Subscript),   # index
    ('foo()',            ast.Call),         # unknown call
    ('random_func("X")', ast.Call),        # unknown functional
    ('"hello"',          ast.Constant),
    ('42',               ast.Constant),
    ('x',                ast.Name),
    ('[1, 2]',           ast.List),
    ('(1, 2)',           ast.Tuple),
    ('{1, 2}',           ast.Set),
    ('x if y else z',    ast.IfExp),
    ('lambda: None',     ast.Lambda),
    ('x and y',          ast.BoolOp),
    ('-x',               ast.UnaryOp),
    ('x < y',            ast.Compare),
    ('{1: 2}',           ast.Dict),
    # bitwise OR on non-type operands must NOT be hoisted as a type alias
    ('1 | 2',                  ast.BinOp),   # integer literals
    ('0xFF | 0x01',            ast.BinOp),   # hex literals
    ('"a" | "b"',              ast.BinOp),   # string literals
    # non-typing module attributes rejected (FP-1 / FP-5)
    ('os.O_RDONLY | int',      ast.BinOp),   # stdlib flag + type anchor
    ('mod.SomeFlag | str',     ast.BinOp),   # arbitrary attribute + type anchor
    # named constants rejected even when mixed with a primitive (B-1)
    ('READ | int',             ast.BinOp),   # READ not in _BUILTIN_TYPE_NAMES
    # runtime subscript in union rejected (B-2)
    ('my_list[0] | None',      ast.BinOp),   # my_list not a typing name
    # two arbitrary class names with no known-type leaf (accepted false negative)
    ('MyClass | OtherClass',   ast.BinOp),
    ('[x for x in y]',   ast.ListComp),
    ('{x for x in y}',   ast.SetComp),
    ('{x: x for x in y}', ast.DictComp),
    ('(x for x in y)',   ast.GeneratorExp),
    ('os.path',          ast.Attribute),   # bare attribute access, not a type construct
]

# Node types that cannot appear as the RHS of a plain assignment statement
_CANT_BE_RHS = frozenset(filter(None, [
    ast.Starred,      # *x — only in unpacking targets
    ast.Slice,        # a[1:2] — slice object, not standalone
    ast.Await,        # await x — async context only
    ast.Yield,        # yield x — function body only
    ast.YieldFrom,    # yield from x — function body only
    ast.NamedExpr,    # (x := y) — not a sane type alias RHS
    # f-string / template internals (3.12+)
    getattr(ast, 'FormattedValue', None),
    getattr(ast, 'JoinedStr', None),
    getattr(ast, 'Interpolation', None),
    getattr(ast, 'TemplateStr', None),
]))


class TestRhsIsTypeConstructExhaustive(unittest.TestCase):

    @staticmethod
    def _rhs(src: str) -> ast.expr:
        return ast.parse(src).body[0].value  # type: ignore[attr-defined]

    def test_true_cases(self):
        for src, expected_type in _TRUE_CASES:
            with self.subTest(src=src):
                node = self._rhs(src)
                self.assertIsInstance(node, expected_type,
                    f"fixture parses to wrong node type for {src!r}")
                self.assertTrue(_rhs_is_type_construct(node),
                    f"expected True for {src!r}")

    def test_false_cases(self):
        for src, expected_type in _FALSE_CASES:
            with self.subTest(src=src):
                node = self._rhs(src)
                self.assertIsInstance(node, expected_type,
                    f"fixture parses to wrong node type for {src!r}")
                self.assertFalse(_rhs_is_type_construct(node),
                    f"expected False for {src!r}")

    def test_all_expr_subtypes_are_classified(self):
        """Fail if a new ast.expr subclass appears that has no row in either table."""
        covered = {type(self._rhs(src)) for src, _ in _TRUE_CASES + _FALSE_CASES}
        for cls in ast.expr.__subclasses__():
            if cls in _CANT_BE_RHS:
                continue
            with self.subTest(cls=cls.__name__):
                self.assertIn(cls, covered,
                    f"{cls.__name__} has no row in _TRUE_CASES or _FALSE_CASES — add one")


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
    def test_third_party_base_class_stays_in_runtime(self):
        # Third-party imports are not safe to hoist (missing dep crashes the module).
        # The class and its import both stay in the try/except runtime block.
        code = (
            "import pydantic\n"
            "class MyModel(pydantic.BaseModel):\n"
            "    name: str\n"
            "def f(): pass"
        )
        type_imports, type_defs, runtime = self._extract(code)
        self.assertNotIn("pydantic", type_imports)
        self.assertIn("pydantic", runtime)
        self.assertNotIn("MyModel", type_defs)
        self.assertIn("MyModel", runtime)

    def test_from_import_base_class_stays_in_runtime(self):
        # Same as above for from-import style.
        code = (
            "from pydantic import BaseModel\n"
            "class MyModel(BaseModel):\n"
            "    name: str\n"
            "def f(): pass"
        )
        type_imports, type_defs, runtime = self._extract(code)
        self.assertNotIn("BaseModel", type_imports)
        self.assertIn("BaseModel", runtime)

    #  multi-target chained assignments (X = Y = List[int])
    def test_chained_assignment_both_targets_hoisted(self):
        code = "X = Y = List[int]\ndef f(): pass"
        _, type_defs, runtime = self._extract(code)
        self.assertIn("X", type_defs)
        self.assertIn("Y", type_defs)
        self.assertNotIn("X", runtime)
        self.assertNotIn("Y", runtime)

    #  nested class free variables are transitively hoisted
    def test_nested_class_dep_is_hoisted(self):
        # ENCODER is only referenced inside Inner (nested in Outer).
        # Without the recursive symtable walk it would be missed.
        code = (
            "import json\n"
            "ENCODER = json.JSONEncoder\n"
            "class Outer:\n"
            "    class Inner:\n"
            "        encoder = ENCODER\n"
            "def f(): pass\n"
        )
        _, type_defs, runtime = self._extract(code)
        self.assertIn("ENCODER", type_defs)
        self.assertNotIn("ENCODER", runtime)

    #  FP-4: only the first bare string after a class is hoisted, not a cascade
    def test_only_first_docstring_after_class_is_hoisted(self):
        code = (
            "class Foo:\n"
            "    pass\n"
            '"first"\n'
            '"second"\n'
            '"third"\n'
            "def f(): pass\n"
        )
        _, type_defs, runtime = self._extract(code)
        self.assertIn('"first"', type_defs)
        self.assertNotIn('"second"', type_defs)
        self.assertNotIn('"third"', type_defs)
        self.assertIn('"second"', runtime)
        self.assertIn('"third"', runtime)

    #  FP-5: CRLF line endings must not corrupt indentation
    def test_crlf_line_endings_normalized(self):
        code = "import requests\r\nresult = requests.get('http://x')\r\n"
        type_imports, type_defs, runtime = self._extract(code)
        for part in (type_imports, type_defs, runtime):
            self.assertNotIn('\r', part)

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

    def test_pydantic_model_stays_in_try_block(self):
        # Third-party imports are not safe to hoist — pydantic and Item both stay
        # inside the try/except so a missing dep only silences that function.
        code = (
            "import pydantic\n"
            "class Item(pydantic.BaseModel):\n"
            "    name: str\n"
            "def execute() -> Item:\n"
            "    return Item(name='x')\n"
        )
        module_scope, wrapped, _ = render_client_function("execute", code, [], {"kind": "object"})
        self.assertNotIn("pydantic", module_scope)
        self.assertNotIn("Item", module_scope)
        self.assertIn("class Item", wrapped)

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
