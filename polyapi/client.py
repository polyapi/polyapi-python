import ast
import symtable as symtable_mod
from typing import Any, Dict, List, Tuple

from polyapi.typedefs import PropertySpecification
from polyapi.utils import parse_arguments, get_type_and_def
from polyapi.constants import SAFE_IMPORT_MODULES

DEFS_TEMPLATE = """
from typing import List, Dict, Any, TypedDict
{args_def}
{return_type_def}
"""


def _is_safe_import(node: ast.stmt) -> bool:
    """Check if an import statement is safe to place at module scope.

    Safe imports are stdlib and typing modules that will never raise ImportError.
    """
    if isinstance(node, ast.Import):
        return all(
            alias.name.split('.')[0] in SAFE_IMPORT_MODULES
            for alias in node.names
        )
    if isinstance(node, ast.ImportFrom):
        module = node.module or ''
        return module.split('.')[0] in SAFE_IMPORT_MODULES
    return False


def _rhs_is_type_construct(node: ast.expr) -> bool:
    """Check if an assignment RHS is a typing construct.

    This is the ONE narrow heuristic we still need because symtable
    can't distinguish `X = Literal["a"]` (type alias) from `x = foo()` (runtime).

    We check the VALUE, not the name — much more reliable than naming conventions.
    """
    # X = Literal[...], X = Dict[str, Any], X = list[Foo], X = Union[...]
    if isinstance(node, ast.Subscript):
        return True
    # X = str | int | float new Union
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return True
    # X = TypedDict("X", {...}) — functional form
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in ('TypedDict', 'NamedTuple', 'NewType'):
            return True
    return False


def _extract_type_definitions(code: str) -> Tuple[str, str, str]:
    """Split client function code into type definitions and runtime code.

    Uses symtable for definitive classification + dependency tracking.
    Uses AST only for source line extraction.

    Returns:
        (type_imports_code, type_defs_code, runtime_code)
    """
    try:
        tree = ast.parse(code)
        st = symtable_mod.symtable(code, '<client_fn>', 'exec')
    except SyntaxError:
        return "", "", code

    lines = code.split('\n')

    # Phase 1: Build child table index — name -> type ('class' | 'function')
    child_types: dict[str, str] = {}
    child_tables: dict[str, symtable_mod.SymbolTable] = {}
    for child in st.get_children():
        child_types[child.get_name()] = child.get_type()
        child_tables[child.get_name()] = child

    # Phase 2: Identify all class names — these are ALWAYS module-scope
    class_names: set[str] = {
        name for name, kind in child_types.items() if kind == 'class'
    }

    # Phase 2b: type aliases (Python 3.12+): type X = ...
    if hasattr(ast, 'TypeAlias'):
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
                class_names.add(node.name.id)

    # Phase 3: Compute transitive dependencies of all classes
    # Any module-level symbol that a class references (directly or transitively)
    # must also be at module scope
    module_scope_names: set[str] = set(class_names)

    # Get all module-level assigned symbol names for reference
    module_level_symbols: set[str] = {
        sym.get_name() for sym in st.get_symbols() if sym.is_assigned()
    }

    # BFS: find all module-level symbols reachable from classes
    queue = list(class_names)
    while queue:
        name = queue.pop()
        if name not in child_tables:
            continue
        for sym in child_tables[name].get_symbols():
            if sym.is_free() or (sym.is_global() and sym.is_referenced()):
                dep = sym.get_name()
                if dep in module_level_symbols and dep not in module_scope_names:
                    module_scope_names.add(dep)
                    queue.append(dep)  # transitively check this dep's deps

    # Phase 4: Classify each AST node using the symtable results
    type_import_lines: set[int] = set()
    type_def_lines: set[int] = set()

    prev_was_type_def = False

    for node in ast.iter_child_nodes(tree):
        start = node.lineno - 1
        end = node.end_lineno or start + 1

        is_type_import = False
        is_type_def = False

        # Imports: safe typing/stdlib imports go to module scope
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            is_type_import = _is_safe_import(node)

        # Class definitions: symtable confirmed these are classes
        elif isinstance(node, ast.ClassDef):
            is_type_def = node.name in class_names  # always True, but explicit

        # type aliases (Python 3.12+): type X = ...
        elif hasattr(ast, 'TypeAlias') and isinstance(node, ast.TypeAlias):
            is_type_def = True

        # Assignments: check if target is in our module_scope_names set
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name):
                is_type_def = node.targets[0].id in module_scope_names

        # Annotated assignments with value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                is_type_def = node.target.id in module_scope_names

        # Function definitions: NEVER module scope (these are runtime)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            is_type_def = False

        # Docstrings following type defs: keep with them
        elif (isinstance(node, ast.Expr)
              and isinstance(node.value, ast.Constant)
              and isinstance(node.value.value, str)
              and prev_was_type_def):
            is_type_def = True

        if is_type_import:
            for i in range(start, end):
                type_import_lines.add(i)
        if is_type_def:
            for i in range(start, end):
                type_def_lines.add(i)

        prev_was_type_def = is_type_def or is_type_import

    # Phase 5: Also promote assignments that LOOK like type aliases
    # even if no class references them yet.
    # This catches stuff like: DatadogStatus = Literal[...] when only used by functions
    # symtable can't distinguish type aliases from variables,
    # so this is the ONE remaining heuristic — but scoped narrowly to
    # assignments whose RHS is a typing construct (Subscript/BinOp with |)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id not in module_scope_names:
                if _rhs_is_type_construct(node.value):
                    start = node.lineno - 1
                    end = node.end_lineno or start + 1
                    for i in range(start, end):
                        type_def_lines.add(i)
                    module_scope_names.add(target.id)

    # Build output
    imports_out: list[str] = []
    types_out: list[str] = []
    runtime_out: list[str] = []
    for i, line in enumerate(lines):
        if i in type_import_lines:
            imports_out.append(line)
        elif i in type_def_lines:
            types_out.append(line)
        else:
            runtime_out.append(line)

    return (
        '\n'.join(imports_out).strip(),
        '\n'.join(types_out).strip(),
        '\n'.join(runtime_out).strip(),
    )


def _wrap_code_in_try_except(function_name: str, code: str) -> Tuple[str, str]:
    """Split client code: types at module scope, runtime in try/except.

    Returns:
        (module_scope_code, try_except_code)

        module_scope_code: safe imports + type definitions (always available)
        try_except_code:   runtime code wrapped in try/except ImportError
    """
    type_imports, type_defs, runtime_code = _extract_type_definitions(code)

    # Build module-scope section
    module_parts = []
    if type_imports:
        module_parts.append(type_imports)
    if type_defs:
        module_parts.append(type_defs)
    module_scope = '\n\n'.join(module_parts)

    # Build try/except section for runtime code
    prefix = f'logger = logging.getLogger("poly")\ntry:\n    '
    suffix = (
        f"\nexcept ImportError as e:\n"
        f"    logger.warning(\"Failed to import client function "
        f"'{function_name}', function unavailable: \" + str(e))"
    )

    indented = '\n    '.join(runtime_code.split('\n'))
    wrapped = prefix + indented + suffix

    return module_scope, wrapped


def render_client_function(
    function_name: str,
    code: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
) -> Tuple[str, str, str]:
    """Render a client function into three parts.

    Returns:
        (module_scope_types, wrapped_runtime, func_type_defs)

        module_scope_types: type definitions to place at module scope (deduplicated by caller)
        wrapped_runtime:    function code wrapped in try/except
        func_type_defs:     SDK-generated type stubs for the {FuncName}.py file
    """
    args, args_def = parse_arguments(function_name, arguments)
    return_type_name, return_type_def = get_type_and_def(return_type)  # type: ignore
    func_type_defs = DEFS_TEMPLATE.format(
        args_def=args_def,
        return_type_def=return_type_def,
    )

    module_scope, wrapped = _wrap_code_in_try_except(function_name, code)

    return module_scope, wrapped + "\n\n", func_type_defs
