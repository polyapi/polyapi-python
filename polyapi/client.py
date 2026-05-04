import ast
import copy
import importlib
import re
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
    'TypeAliasType', 'ForwardRef',
})

_TYPING_MODULES = frozenset({'typing', 'typing_extensions'})

# Names that are unambiguously types when they appear as leaves in X | Y expressions.
# This anchors the union heuristic so that flag constants (READ | WRITE) are rejected.
_BUILTIN_TYPE_NAMES = frozenset({
    'str', 'int', 'float', 'bool', 'bytes', 'complex', 'object', 'bytearray', 'None',
}) | _TYPING_SUBSCRIPT_NAMES


def _collect_free_names(table: symtable_mod.SymbolTable) -> set[str]:
    """Recursively collect all module-scope-referenced names from a symtable tree.

    A flat get_symbols() only sees the direct class body. Nested classes (Inner
    inside Outer) have their own child tables — their free/global references would
    be missed without this recursive walk.
    """
    names: set[str] = set()
    for sym in table.get_symbols():
        if sym.is_free() or (sym.is_global() and sym.is_referenced()):
            names.add(sym.get_name())
    for child in table.get_children():
        names.update(_collect_free_names(child))
    return names


def _collect_class_body_names(table: symtable_mod.SymbolTable) -> set[str]:
    """Collect module-referenced names evaluated at class definition time only.

    Unlike _collect_free_names, this does NOT descend into function/method
    scopes — method bodies run at call time, not when the class is defined.
    Nested class scopes ARE descended because their bodies run at the enclosing
    class's definition time.
    """
    names: set[str] = set()
    for sym in table.get_symbols():
        if sym.is_free() or (sym.is_global() and sym.is_referenced()):
            names.add(sym.get_name())
    for child in table.get_children():
        if child.get_type() == 'class':
            names.update(_collect_class_body_names(child))
    return names


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
        if module.split('.')[0] not in SAFE_IMPORT_MODULES:
            return False
        # The root module is safe, but a specific name may not exist 
        # Verify each imported name is actually there so we don't hoist a from-import 
        # Doing that would raise ImportError at module scope.
        try:
            mod = importlib.import_module(module)
            return all(
                alias.name == '*' or hasattr(mod, alias.name)
                for alias in node.names
            )
        except ImportError:
            return False
    return False


def _is_type_union_leaf(
    node: ast.expr,
    local_shadows: frozenset[str] = frozenset(),
) -> bool:
    """Return True if node is a valid leaf in a new-style type union (X | Y | None).

    Every leaf must be an unambiguous type — we reject anything that could
    plausibly be a runtime value (flag constant, arbitrary subscript, etc.).
    local_shadows removes whitelisted names that were redefined at module scope
    (e.g. `Optional = []`), so they are not trusted as typing constructs.
    """
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return (
            _is_type_union_leaf(node.left, local_shadows)
            and _is_type_union_leaf(node.right, local_shadows)
        )
    # Name: only known typing / builtin type names, minus any local shadows.
    if isinstance(node, ast.Name):
        return node.id in (_BUILTIN_TYPE_NAMES - local_shadows)
    # Attribute: only from typing / typing_extensions (rejects os.O_RDONLY, etc.)
    if isinstance(node, ast.Attribute):
        return isinstance(node.value, ast.Name) and node.value.id in _TYPING_MODULES
    # Subscript: head must itself be a known typing name, minus any local shadows.
    if isinstance(node, ast.Subscript):
        val = node.value
        if isinstance(val, ast.Name):
            return val.id in (_TYPING_SUBSCRIPT_NAMES - local_shadows)
        if isinstance(val, ast.Attribute):
            return (
                isinstance(val.value, ast.Name)
                and val.value.id in _TYPING_MODULES
                and val.attr in (_TYPING_SUBSCRIPT_NAMES - local_shadows)
            )
        return False
    if isinstance(node, ast.Constant) and node.value is None:
        return True  # None in X | None
    return False


def _union_has_type_anchor(node: ast.expr) -> bool:
    """Return True if the BinOr tree contains at least one vague type leaf.

    Prevents named flag constants (READ | WRITE) from being misidentified as type
    unions. A 'type anchor' is a leaf that could never plausibly be a flag value:
    a known primitive/typing name, a None constant, or a subscript expression.
    """
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _union_has_type_anchor(node.left) or _union_has_type_anchor(node.right)
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    if isinstance(node, ast.Name):
        return node.id in _BUILTIN_TYPE_NAMES
    if isinstance(node, ast.Subscript):
        return True
    return False


def _collect_local_shadows(tree: ast.Module) -> frozenset[str]:
    """Typing-set names that are redefined at module scope (assignments or defs).

    If `List = get_runtime_list()` or `def TypeVar(...):` appears in the file,
    those names must not be trusted as typing constructs in Phase 5 even though
    they appear in the static whitelist.
    """
    all_typing = _TYPING_SUBSCRIPT_NAMES | _TYPING_FUNCTIONAL_NAMES
    shadowed: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                # Walk the target so destructuring like `Optional, other = ...` caught — the outer target is a Tuple, not a plain Name.
                for name_node in ast.walk(t):
                    if isinstance(name_node, ast.Name) and name_node.id in all_typing:
                        shadowed.add(name_node.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in all_typing:
                shadowed.add(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in all_typing:
                shadowed.add(node.name)
        elif isinstance(node, ast.ClassDef):
            if node.name in all_typing:
                shadowed.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            # A non-typing import that binds a typing-looking name shadows it.
            # Phase 5 would otherwise trust the static whitelist and hoist
            # X = Optional[str] even when Optional came from a third-party module
            # whose import stays in the try block — producing a NameError.
            module = node.module or ''
            if module.split('.')[0] not in _TYPING_MODULES:
                for alias in node.names:
                    bound = alias.asname or alias.name
                    if bound in all_typing:
                        shadowed.add(bound)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split('.')[0]
                if bound in all_typing:
                    shadowed.add(bound)
    return frozenset(shadowed)


def _collect_typing_bound_names(tree: ast.Module) -> frozenset[str]:
    """Names actually imported from typing/typing_extensions in this module.

    Used to validate RHS names by provenance rather than a static whitelist,
    so `X = MyAlias[str]` is only hoisted if MyAlias came from a typing import
    in this file — not just because the name string happens to look typing-ish.
    """
    bound: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ''
            if module.split('.')[0] in _TYPING_MODULES:
                for alias in node.names:
                    bound.add(alias.asname or alias.name)
    return frozenset(bound)


def _dotted_name_info(node: ast.expr) -> tuple[str, str] | None:
    """If node is a pure dotted name (a.b.c), return (root_name, full_dotted_str). Else None."""
    parts: list[str] = []
    n: ast.expr = node
    while isinstance(n, ast.Attribute):
        parts.append(n.attr)
        n = n.value
    if isinstance(n, ast.Name):
        parts.append(n.id)
        return n.id, '.'.join(reversed(parts))
    return None


def _quote_expr(node: ast.expr, all_known: set[str] | frozenset[str]) -> ast.expr:
    """Recursively replace unresolved names with string constants.

    Attribute chains (foo.Bar.Baz) whose root is unresolved are replaced with a
    single string constant ("foo.Bar.Baz") rather than quoting only the base Name,
    which would produce "foo".Bar.Baz — a string attribute lookup that raises at
    module scope before the per-function import guard can fire.
    """
    if isinstance(node, ast.Name):
        return ast.Constant(value=node.id) if node.id not in all_known else node
    if isinstance(node, ast.Attribute):
        info = _dotted_name_info(node)
        if info is not None and info[0] not in all_known:
            return ast.Constant(value=info[1])
        node.value = _quote_expr(node.value, all_known)
        return node
    for field, val in ast.iter_fields(node):
        if isinstance(val, ast.expr):
            setattr(node, field, _quote_expr(val, all_known))
        elif isinstance(val, list):
            for i, item in enumerate(val):
                if isinstance(item, ast.expr):
                    val[i] = _quote_expr(item, all_known)
    return node


def _quote_unresolved_names(node: ast.expr, all_known: set[str] | frozenset[str]) -> ast.expr:
    """Return a deep copy of node with unresolved Name refs replaced by string literals.

    Produces forward references like Union["UnknownType", KnownType] so the
    hoisted assignment is valid Python even when the name is defined later
    (same-file) or in another module (cross-context).
    """
    return _quote_expr(copy.deepcopy(node), all_known)


def _rhs_is_type_construct(
    node: ast.expr,
    typing_bound: frozenset[str] = frozenset(),
    local_shadows: frozenset[str] = frozenset(),
) -> bool:
    """Check if an assignment RHS is a typing construct.

    This is the ONE narrow heuristic we still need because symtable
    can't distinguish `X = Literal["a"]` (type alias) from `x = foo()` (runtime).

    We check the VALUE, not the name. `typing_bound` extends the static sets with
    names actually imported from typing/typing_extensions in the current file.
    `local_shadows` removes names from the static sets that were redefined at module
    scope (e.g. `List = []` or `def TypeVar(...)`), preventing wrong hoists.
    """
    all_subscript = (_TYPING_SUBSCRIPT_NAMES | typing_bound) - local_shadows
    # Don't extend all_functional with typing_bound — typing_bound includes utilities
    # like cast/overload/get_type_hints which are not type constructors. The static
    # list covers all legitimate functional type forms (TypeVar, TypedDict, NewType...).
    all_functional = _TYPING_FUNCTIONAL_NAMES - local_shadows

    # X = Literal[...], X = Dict[str, Any], X = list[Foo], X = Union[...]
    # Also handles typing.Optional[int] where node.value is ast.Attribute
    if isinstance(node, ast.Subscript):
        val = node.value
        head_ok = False
        if isinstance(val, ast.Name):
            head_ok = val.id in all_subscript
        elif isinstance(val, ast.Attribute):
            head_ok = (
                isinstance(val.value, ast.Name)
                and val.value.id in _TYPING_MODULES
                and val.attr in all_subscript
            )
        if head_ok:
            # Reject dynamic subscripts like Literal[*runtime_list] — the slice
            # contains a starred unpack whose value is a runtime variable, not a
            # static type expression. Hoisting this would produce a NameError.
            if any(isinstance(n, ast.Starred) for n in ast.walk(node.slice)):
                return False
            return True
        return False
    # X = str | int | None — new-style union.
    # _is_type_union_leaf validates every leaf strictly, so FLAGS = 1 | 2 and
    # READ | WRITE are both rejected without a separate anchor check.
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _is_type_union_leaf(node, local_shadows) and _union_has_type_anchor(node)
    # X = TypedDict("X", {...}), T = TypeVar("T"), P = ParamSpec("P"), ...
    # Also handles typing.TypedDict(...) where node.func is ast.Attribute
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            return func.id in all_functional
        if isinstance(func, ast.Attribute):
            return (
                isinstance(func.value, ast.Name)
                and func.value.id in _TYPING_MODULES
                and func.attr in all_functional
            )
    return False


def _extract_type_definitions(code: str) -> Tuple[str, str, str]:
    """Split client function code into type definitions and runtime code.

    Uses symtable for definitive classification + dependency tracking.
    Uses AST only for source line extraction.

    Returns:
        (type_imports_code, type_defs_code, runtime_code)
    """
    code = code.replace('\r\n', '\n').replace('\r', '\n')

    try:
        tree = ast.parse(code)
        st = symtable_mod.symtable(code, '<client_fn>', 'exec')
    except SyntaxError:
        return "", "", code

    typing_bound = _collect_typing_bound_names(tree)
    local_shadows = _collect_local_shadows(tree)

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
        # deps from class body via symtable — recursive so nested classes
        # (Inner inside Outer) contribute their free/global refs too
        if name in child_tables:
            for dep in _collect_free_names(child_tables[name]):
                if dep in module_level_symbols and dep not in module_scope_names:
                    module_scope_names.add(dep)
                    queue.append(dep)
        # deps from base classes and decorators (not visible in class body symtable)
        for dep in class_outer_deps.get(name, set()):
            if dep in module_level_symbols and dep not in module_scope_names:
                module_scope_names.add(dep)
                queue.append(dep)

    # Phase 3b: Prune module_scope_names — remove names bound by non-safe imports,
    # then cascade: any class that depends on a pruned name can't safely sit at module
    # scope either (its base class / decorator would be undefined if the dep is missing).
    unsafe_import_names: set[str] = set()
    for _node in ast.iter_child_nodes(tree):
        if isinstance(_node, (ast.Import, ast.ImportFrom)) and not _is_safe_import(_node):
            unsafe_import_names.update(_import_bound_names(_node) & module_scope_names)

    if unsafe_import_names:
        to_remove: set[str] = set(unsafe_import_names)
        prune_queue = list(unsafe_import_names)
        while prune_queue:
            unsafe_name = prune_queue.pop()
            for cls_name in list(module_scope_names - to_remove):
                if cls_name not in child_tables:
                    continue
                deps = _collect_free_names(child_tables[cls_name]) | class_outer_deps.get(cls_name, set())
                if unsafe_name in deps:
                    to_remove.add(cls_name)
                    prune_queue.append(cls_name)
        module_scope_names -= to_remove

    # Phase 3c: Prune module_scope_names — remove assignment targets whose RHS
    # contains a starred subscript (e.g. Literal[*runtime_list]).  These are
    # dynamic type expressions that require a runtime value not available at
    # module scope; hoisting them produces a NameError or used-before-def.
    # Cascade using the same logic as Phase 3b.
    dynamic_names: set[str] = set()
    for _node in ast.iter_child_nodes(tree):
        if isinstance(_node, ast.Assign):
            if any(isinstance(n, ast.Starred) for n in ast.walk(_node.value)):
                for t in _node.targets:
                    if isinstance(t, ast.Name) and t.id in module_scope_names:
                        dynamic_names.add(t.id)

    if dynamic_names:
        dyn_remove: set[str] = set(dynamic_names)
        dyn_queue = list(dynamic_names)
        while dyn_queue:
            dyn_name = dyn_queue.pop()
            for cls_name in list(module_scope_names - dyn_remove):
                if cls_name not in child_tables:
                    continue
                deps = _collect_free_names(child_tables[cls_name]) | class_outer_deps.get(cls_name, set())
                if dyn_name in deps:
                    dyn_remove.add(cls_name)
                    dyn_queue.append(cls_name)
        module_scope_names -= dyn_remove

    # Phase 3d: Prune classes that depend on module-level functions at class-definition
    # time. Functions are never hoisted (always runtime_out). If the class BODY
    # (excluding method bodies, which only run at call time) references a local
    # function, hoisting the class would crash at import time before the guard fires.
    # We use _collect_class_body_names (non-recursive into function scopes) rather
    # than _collect_free_names so that method-body refs to local functions don't
    # cause unnecessary pruning.
    local_function_names: set[str] = {
        name for name, typ in child_types.items() if typ == 'function'
    }
    if local_function_names:
        fn_remove: set[str] = set()
        for cls_name in list(module_scope_names):
            if cls_name not in child_tables:
                continue
            class_body_deps = _collect_class_body_names(child_tables[cls_name])
            outer_deps = class_outer_deps.get(cls_name, set())
            if (class_body_deps | outer_deps) & local_function_names:
                fn_remove.add(cls_name)
        # Cascade: classes that depended on just-removed classes also can't be hoisted
        fn_queue = list(fn_remove)
        while fn_queue:
            removed = fn_queue.pop()
            for cls_name in list(module_scope_names - fn_remove):
                if cls_name not in child_tables:
                    continue
                deps = _collect_free_names(child_tables[cls_name]) | class_outer_deps.get(cls_name, set())
                if removed in deps:
                    fn_remove.add(cls_name)
                    fn_queue.append(cls_name)
        module_scope_names -= fn_remove

    # Names available at module scope: builtins, typing module names, anything that
    # survived Phase 3b/3c/3d, and names bound by safe imports (hoisted by Phase 4).
    # Used to guard Phase 4 assignment hoisting — if a RHS name isn't in this set
    # it won't be defined when the hoisted assignment runs.
    safe_import_bound: set[str] = set()
    for _node in ast.iter_child_nodes(tree):
        if isinstance(_node, (ast.Import, ast.ImportFrom)) and _is_safe_import(_node):
            safe_import_bound.update(_import_bound_names(_node))
    module_scope_available = (
        _BUILTIN_TYPE_NAMES | _TYPING_MODULES | module_scope_names | safe_import_bound
    ) - local_shadows

    # Phase 4: Classify each AST node using the symtable results
    type_import_lines: set[int] = set()
    type_def_lines: set[int] = set()
    modified_type_lines: dict[int, str] = {}  # line index -> replacement source

    prev_was_type_def = False

    for node in ast.iter_child_nodes(tree):
        start = getattr(node, 'lineno', 1) - 1
        end = getattr(node, 'end_lineno', None) or start + 1

        is_type_import = False
        is_type_def = False

        # Imports: only safe (stdlib/typing) imports go to module scope.
        # Non-safe imports stay in try/except — hoisting them risks crashing the whole
        # generated module if the dependency is missing (before the guard can fire).
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            is_type_import = _is_safe_import(node)

        # Class definitions: use module_scope_names not class_names so that
        # Phase 3b pruning (unsafe-import cascade) is respected here too.
        elif isinstance(node, ast.ClassDef):
            is_type_def = node.name in module_scope_names
            if is_type_def and node.decorator_list:
                # node.lineno is the 'class' keyword line; decorators sit above it.
                # Extend start backwards so the decorator lines are hoisted with the
                # class — otherwise a dangling decorator stays in runtime_out and
                # silently decorates the next generated function.
                start = node.decorator_list[0].lineno - 1

        # type aliases (Python 3.12+): type X = ...
        elif hasattr(ast, 'TypeAlias') and isinstance(node, ast.TypeAlias):
            is_type_def = (
                isinstance(node.name, ast.Name)
                and node.name.id in module_scope_names
            )

        # Assignments: check if any target is in our module_scope_names set,
        # AND that all RHS names are available at module scope. The Phase 3b
        # cascade only follows class symtable deps — a non-class alias like
        # STATUS = SomeType can land in module_scope_names via BFS without
        # SomeType being checked, causing a NameError when hoisted.
        elif isinstance(node, ast.Assign):
            # Require ALL targets to be in scope: a chained `a = b = expr` would
            # drag non-scope targets to module scope if we used `any()` here.
            target_in_scope = bool(node.targets) and all(
                isinstance(t, ast.Name) and t.id in module_scope_names
                for t in node.targets
            )
            rhs_names_available = all(
                n.id in module_scope_available
                for n in ast.walk(node.value)
                if isinstance(n, ast.Name)
            )
            is_type_def = target_in_scope and rhs_names_available

        # Annotated assignments with value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                rhs_names_available = all(
                    n.id in module_scope_available
                    for n in ast.walk(node.value)
                    if isinstance(n, ast.Name)
                )
                is_type_def = node.target.id in module_scope_names and rhs_names_available

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

        # Expr nodes (bare strings) don't propagate the chain — only real
        # type defs / imports do. This prevents consecutive bare strings after
        # a class from all being hoisted.
        if isinstance(node, ast.Expr):
            prev_was_type_def = False
        else:
            prev_was_type_def = is_type_def or is_type_import

    # Phase 5: Also promote assignments that LOOK like type aliases
    # even if no class references them yet.
    # This catches stuff like: DatadogStatus = Literal[...] when only used by functions.
    # symtable can't distinguish type aliases from variables, so this is the ONE
    # remaining heuristic — scoped narrowly to typing-construct RHS shapes.
    #
    # Unresolved names (defined later in the same file or in another module) are
    # replaced with string forward references via _quote_unresolved_names so the
    # hoisted line is always valid Python and mypy can resolve same-file refs.
    all_known_names = _BUILTIN_TYPE_NAMES | typing_bound | module_scope_names
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        new_names = [
            t.id for t in node.targets
            if isinstance(t, ast.Name) and t.id not in module_scope_names
        ]
        if not new_names or not _rhs_is_type_construct(node.value, typing_bound, local_shadows):
            continue

        start = node.lineno - 1
        end = getattr(node, 'end_lineno', None) or start + 1

        # _TYPING_MODULES are module names (typing, typing_extensions), not bound names —
        # they're never in all_known_names but must not be quoted or the generated
        # expression becomes invalid Python (e.g. "typing".Optional[int]).
        quotable_known = all_known_names | _TYPING_MODULES
        unresolved = {
            n.id for n in ast.walk(node.value)
            if isinstance(n, ast.Name) and n.id not in quotable_known
        }
        if unresolved:
            # Hoist with string-quoted forward refs for unknown names.
            # Union["UnknownType", KnownType] is valid at runtime and mypy resolves
            # same-file forward refs; cross-file refs degrade silently (unknown type).
            quoted_rhs = _quote_unresolved_names(node.value, quotable_known)
            target_src = ' = '.join(
                t.id for t in node.targets if isinstance(t, ast.Name)
            )
            modified_type_lines[start] = f"{target_src} = {ast.unparse(quoted_rhs)}"
            for i in range(start + 1, end):
                modified_type_lines[i] = ''  # suppress continuation lines

        for i in range(start, end):
            type_def_lines.add(i)
        module_scope_names.update(new_names)
        all_known_names = all_known_names | set(new_names)

    # Build output
    imports_out: list[str] = []
    types_out: list[str] = []
    runtime_out: list[str] = []
    for i, line in enumerate(lines):
        if i in type_import_lines:
            imports_out.append(line)
        elif i in type_def_lines:
            if i in modified_type_lines:
                replacement = modified_type_lines[i]
                if replacement:  # empty string = suppressed continuation line
                    types_out.append(replacement)
            else:
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

    # A comment-only runtime block is syntactically empty — `try:` with nothing
    # but comments raises IndentationError. Check for at least one real statement.
    has_code = any(
        l.strip() and not l.strip().startswith('#')
        for l in runtime_code.split('\n')
    )
    body = runtime_code if has_code else 'pass'

    # polyConfig is re-declared in every client function's try block within the same
    # __init__.py. Suppress the mypy no-redef error on that line in generated output.
    body = re.sub(r'^(\s*polyConfig\s*:.*)', r'\1  # type: ignore[no-redef]', body, flags=re.MULTILINE)

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
