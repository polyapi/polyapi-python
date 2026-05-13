import unittest

from polyapi.poly_schemas import _fix_typed_dict_imports


class TestFixTypedDictImports(unittest.TestCase):
    """Tests for _fix_typed_dict_imports, which rewrites TypedDict/NotRequired
    from `typing` to `typing_extensions` in jsonschema_gentypes output."""

    # TypedDict moved out of `typing`

    def test_typeddict_removed_from_typing_import(self):
        code = "from typing import Union, List, TypedDict\n\nclass Foo(TypedDict):\n    x: int"
        result = _fix_typed_dict_imports(code)
        self.assertNotIn("from typing import Union, List, TypedDict", result)
        self.assertNotIn("TypedDict", result.split("from typing_extensions")[0].split("from typing")[-1] if "from typing import" in result else "")

    def test_typeddict_present_in_typing_extensions(self):
        code = "from typing import Union, List, TypedDict\n\nclass Foo(TypedDict):\n    x: int"
        result = _fix_typed_dict_imports(code)
        self.assertIn("from typing_extensions import", result)
        self.assertIn("TypedDict", result)

    def test_notrequired_removed_from_typing_import(self):
        code = "from typing import Union, List, TypedDict, NotRequired\n\nclass Foo(TypedDict):\n    x: int"
        result = _fix_typed_dict_imports(code)
        # NotRequired must NOT appear in a `from typing import` line
        for line in result.splitlines():
            if line.startswith("from typing import"):
                self.assertNotIn("NotRequired", line)

    def test_notrequired_present_in_typing_extensions(self):
        code = "from typing import Union, TypedDict, NotRequired\n\nclass Foo(TypedDict):\n    x: NotRequired[int]"
        result = _fix_typed_dict_imports(code)
        self.assertIn("NotRequired", result)
        te_line = next(l for l in result.splitlines() if "from typing_extensions import" in l)
        self.assertIn("NotRequired", te_line)

    # Remaining typing imports preserved

    def test_other_typing_names_kept(self):
        code = "from typing import Union, List, TypedDict, Optional"
        result = _fix_typed_dict_imports(code)
        typing_line = next((l for l in result.splitlines() if l.startswith("from typing import")), "")
        self.assertIn("Union", typing_line)
        self.assertIn("List", typing_line)
        self.assertIn("Optional", typing_line)

    def test_typing_line_dropped_when_only_typeddict(self):
        # If TypedDict was the only import, the `from typing import` line should be gone
        code = "from typing import TypedDict\n\nclass Foo(TypedDict):\n    pass"
        result = _fix_typed_dict_imports(code)
        self.assertNotIn("from typing import", result)

    # Existing typing_extensions import is merged, not duplicated

    def test_existing_te_import_gets_typeddict_merged(self):
        code = (
            "from typing import Union, TypedDict\n"
            "from typing_extensions import NotRequired\n"
            "\nclass Foo(TypedDict):\n    x: NotRequired[int]"
        )
        result = _fix_typed_dict_imports(code)
        te_lines = [l for l in result.splitlines() if "from typing_extensions import" in l]
        self.assertEqual(len(te_lines), 1, "Should have exactly one typing_extensions import line")
        self.assertIn("TypedDict", te_lines[0])
        self.assertIn("NotRequired", te_lines[0])

    def test_no_duplicate_typing_extensions_line(self):
        code = (
            "from typing_extensions import NotRequired\n"
            "from typing import List, TypedDict\n"
        )
        result = _fix_typed_dict_imports(code)
        te_lines = [l for l in result.splitlines() if "from typing_extensions import" in l]
        self.assertEqual(len(te_lines), 1)

    # No existing typing_extensions import — one is prepended

    def test_te_import_prepended_when_absent(self):
        code = "from typing import Union, TypedDict\n\nclass Foo(TypedDict):\n    pass"
        result = _fix_typed_dict_imports(code)
        first_meaningful = next(l for l in result.splitlines() if l.strip())
        self.assertIn("from typing_extensions import", first_meaningful)

    # Code with no TypedDict at all is left structurally intact

    def test_code_without_typeddict_unchanged_structure(self):
        code = "from typing import Union, List\n\nx: List[int] = []"
        result = _fix_typed_dict_imports(code)
        # typing_extensions is prepended (no existing te import)
        self.assertIn("from typing_extensions import", result)
        # original typing import preserved
        self.assertIn("from typing import Union, List", result)
        # original assignment preserved
        self.assertIn("x: List[int] = []", result)

    def test_code_with_no_imports_gets_te_prepended(self):
        code = "x = 1\ny = 2"
        result = _fix_typed_dict_imports(code)
        self.assertTrue(result.startswith("from typing_extensions import"))

    # The rewrite doesn't break class bodies that use TypedDict

    def test_typeddict_class_body_preserved(self):
        code = (
            "from typing import Union, List, TypedDict\n"
            "\nclass Item(TypedDict):\n"
            "    name: str\n"
            "    value: Union[int, None]\n"
        )
        result = _fix_typed_dict_imports(code)
        self.assertIn("class Item(TypedDict):", result)
        self.assertIn("name: str", result)
        self.assertIn("value: Union[int, None]", result)

    def test_empty_string_input(self):
        result = _fix_typed_dict_imports("")
        # Should at minimum prepend the typing_extensions import
        self.assertIn("from typing_extensions import", result)


if __name__ == "__main__":
    unittest.main()
