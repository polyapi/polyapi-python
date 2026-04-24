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

_TYPING_SUBSCRIPT_NAMES = frozenset({
    # Special forms
    'ClassVar', 'Final', 'Annotated', 'Required', 'NotRequired', 'ReadOnly',
    'Optional', 'Union', 'Literal', 'Type',
    'Concatenate', 'Unpack', 'TypeGuard', 'TypeIs',
    # Standalone-but-subscriptable specials
    'LiteralString', 'Self', 'Never', 'NoReturn',
    # Generic ABCs (collections.abc / contextlib)
    'Callable', 'Awaitable', 'Coroutine',
    'AsyncIterable', 'AsyncIterator', 'AsyncGenerator', 'AsyncContextManager',
    'Iterable', 'Iterator', 'Generator', 'ContextManager',
    'Container', 'Collection', 'Reversible', 'Sized', 'Hashable',
    'Mapping', 'MutableMapping', 'MappingView', 'KeysView', 'ItemsView', 'ValuesView',
    'Sequence', 'MutableSequence', 'MutableSet', 'AbstractSet',
    'IO', 'BinaryIO', 'TextIO', 'Match', 'Pattern',
    # Concrete generic aliases
    'Dict', 'List', 'Set', 'FrozenSet', 'Tuple',
    'DefaultDict', 'OrderedDict', 'Counter', 'Deque', 'ChainMap',
    # Base classes used with subscript (Generic[T], Protocol[T])
    'Generic', 'Protocol',
    # AnyStr is a TypeVar but appears in subscript position
    'AnyStr',
    # lowercase builtins (3.9+)
    'dict', 'list', 'set', 'frozenset', 'tuple', 'type',
})

_TYPING_FUNCTIONAL_NAMES = frozenset({
    'TypedDict', 'NamedTuple', 'NewType',
    'TypeVar', 'ParamSpec', 'TypeVarTuple',
    'TypeAliasType',
})


def _import_bound_names(node: ast.stmt) -> set:
    """Names bound in the local namespace by an import statement."""
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return {alias.asname or alias.name.split('.')[0] for alias in node.names}
    return set()


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


def _is_type_union_leaf(node: ast.expr) -> bool:
    """Return True if node is a valid leaf in latest type union op (X | Y | None).

    Rejects non-type leaves like integer/string constants so that bitwise OR
    expressions (FLAGS = 1 | 2) are not misidentified as type aliases.
    """
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _is_type_union_leaf(node.left) and _is_type_union_leaf(node.right)
    if isinstance(node, ast.Name):
        return True  # str, int, MyClass, None (as a name), ...
    if isinstance(node, ast.Attribute):
        return True  # typing.Optional, module.MyClass, ...
    if isinstance(node, ast.Subscript):
        return True  # Optional[int], List[str], ...
    if isinstance(node, ast.Constant) and node.value is None:
        return True  # literal None in  X | None
    return False     # int/str/bytes/... constants → bitwise OR, not a union


def _rhs_is_type_construct(node: ast.expr) -> bool:
    """Check if an assignment RHS is a typing construct.

    This is the ONE narrow heuristic we still need because symtable
    can't distinguish `X = Literal["a"]` (type alias) from `x = foo()` (runtime).

    We check the VALUE, not the name — much more reliable than naming conventions.
    """
    # X = Literal[...], X = Dict[str, Any], X = list[Foo], X = Union[...]
    # Also handles typing.Optional[int] where node.value is ast.Attribute
    if isinstance(node, ast.Subscript):
        val = node.value
        if isinstance(val, ast.Name):
            return val.id in _TYPING_SUBSCRIPT_NAMES
        if isinstance(val, ast.Attribute):
            return val.attr in _TYPING_SUBSCRIPT_NAMES
    # X = str | int | None — new-style union; validate leaves to reject FLAGS = 1 | 2
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _is_type_union_leaf(node)
    # X = TypedDict("X", {...}), T = TypeVar("T"), P = ParamSpec("P"), ...
    # Also handles typing.TypedDict(...) where node.func is ast.Attribute
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            return func.id in _TYPING_FUNCTIONAL_NAMES
        if isinstance(func, ast.Attribute):
            return func.attr in _TYPING_FUNCTIONAL_NAMES
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

    # Get all module-level defined symbol names for reference.
    # is_assigned() covers normal assignments; is_imported() covers import statements
    # (symtable tracks these separately via DEF_IMPORT vs DEF_LOCAL flags).
    module_level_symbols: set[str] = {
        sym.get_name() for sym in st.get_symbols()
        if sym.is_assigned() or sym.is_imported()
    }

    # AST-level deps from base classes and decorators: symtable misses these
    # because they're evaluated in the enclosing scope, not the class body.
    # e.g. `class A(pydantic.BaseModel)` — `pydantic` is in the module scope,
    # not in the class body's symbol table.
    class_outer_deps: dict[str, set[str]] = {}
    for _node in ast.iter_child_nodes(tree):
        if isinstance(_node, ast.ClassDef) and _node.name in class_names:
            outer: set[str] = set()
            exprs = list(_node.bases) + [kw.value for kw in _node.keywords] + list(_node.decorator_list)
            for expr in exprs:
                for n in ast.walk(expr):
                    if isinstance(n, ast.Name):
                        outer.add(n.id)
            class_outer_deps[_node.name] = outer

    # BFS: find all module-level symbols reachable from classes
    queue = list(class_names)
    while queue:
        name = queue.pop()
        # deps from class body via symtable
        if name in child_tables:
            for sym in child_tables[name].get_symbols():
                if sym.is_free() or (sym.is_global() and sym.is_referenced()):
                    dep = sym.get_name()
                    if dep in module_level_symbols and dep not in module_scope_names:
                        module_scope_names.add(dep)
                        queue.append(dep)
        # deps from base classes and decorators (not visible in class body symtable)
        for dep in class_outer_deps.get(name, set()):
            if dep in module_level_symbols and dep not in module_scope_names:
                module_scope_names.add(dep)
                queue.append(dep)

    # Phase 4: Classify each AST node using the symtable results
    type_import_lines: set[int] = set()
    type_def_lines: set[int] = set()

    prev_was_type_def = False

    for node in ast.iter_child_nodes(tree):
        start = getattr(node, 'lineno', 1) - 1
        end = getattr(node, 'end_lineno', None) or start + 1

        is_type_import = False
        is_type_def = False

        # Imports: safe typing/stdlib imports go to module scope;
        # also promote any import that binds a name required by a module-scope class.
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            is_type_import = (
                _is_safe_import(node)
                or bool(_import_bound_names(node) & module_scope_names)
            )

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
                    end = getattr(node, 'end_lineno', None) or start + 1
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

    body = runtime_code if runtime_code.strip() else 'pass'
    indented = '\n    '.join(body.split('\n'))
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
