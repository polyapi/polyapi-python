import ast
import json
import types
import sys
import re
from typing import Dict, List, Mapping, Optional, Tuple, Any
from typing import _TypedDictMeta as BaseTypedDict  # type: ignore
from typing_extensions import _TypedDictMeta, cast  # type: ignore
from stdlib_list import stdlib_list
from pydantic import TypeAdapter
from importlib.metadata import packages_distributions
from polyapi import schema
from polyapi.constants import PYTHON_TO_JSONSCHEMA_TYPE_MAP
from polyapi.generate import build_poly_schema_index, get_poly_schemas
from polyapi.utils import print_red
from polyapi.deployables import (
    DeployableFunctionTypes,
    Deployment,
    DeployableRecord,
    get_deployable_file_revision,
)


# these libraries are already installed in the base docker image
# and shouldnt be included in additional requirements
BASE_REQUIREMENTS = {
    "polyapi",
    "requests",
    "typing_extensions",
    "jsonschema-gentypes",
    "pydantic",
    "cloudevents",
}
all_stdlib_symbols = stdlib_list(".".join([str(v) for v in sys.version_info[0:2]]))
BASE_REQUIREMENTS.update(
    all_stdlib_symbols
)  # dont need to pip install stuff in the python standard library


def _parse_google_docstring(docstring: str) -> Dict[str, Any]:
    import re

    lines = docstring.split("\n")
    mode = None
    params = {}
    parsed = {
        "description": [],
        "params": [],
        "returns": {"description": []},
        "raises": {},
    }
    current_key = None

    # Regex to capture the parts of the parameter and the start of type/exception sections
    arg_pattern = re.compile(r"^\s*(\w+)\s*(\(.*?\))?:(.*)")
    section_pattern = re.compile(r"^\s*(Args|Returns|Raises):")

    for line in lines:
        line = line.rstrip()
        section_match = section_pattern.match(line)

        if section_match:
            mode = section_match.group(1).lower()
            continue

        if mode == "args":
            arg_match = arg_pattern.match(line)
            if arg_match:
                current_key = arg_match.group(1)
                type_desc = arg_match.group(2) if arg_match.group(2) else ""
                description = arg_match.group(3).strip()
                params[current_key] = {
                    "name": current_key,
                    "type": type_desc.strip("() "),
                    "description": [description],
                }
            elif current_key:
                params[current_key]["description"].append(line.strip())  # type: ignore

        elif mode == "returns":
            if not parsed["returns"]["description"]:  # type: ignore
                ret_type, _, desc = line.partition(":")
                parsed["returns"]["type"] = ret_type.strip()  # type: ignore
                parsed["returns"]["description"].append(desc.strip())  # type: ignore
            else:
                parsed["returns"]["description"].append(line.strip())  # type: ignore

        elif mode == "raises":
            if ":" in line:
                exc_type, desc = line.split(":", 1)
                parsed["raises"][exc_type.strip()] = desc.strip()  # type: ignore
            elif current_key:
                parsed["raises"][current_key] += " " + line.strip()  # type: ignore

        elif mode is None:
            parsed["description"].append(line.strip())  # type: ignore

    # Consolidate descriptions
    parsed["description"] = " ".join(parsed["description"]).strip()
    parsed["returns"]["description"] = " ".join(  # type: ignore
        parsed["returns"]["description"]  # type: ignore
    ).strip()
    parsed["params"] = [
        {**v, "description": " ".join(v["description"]).strip()}  # type: ignore
        for v in params.values()
    ]

    return parsed


def _get_typed_dict_schemas(code: str) -> Dict[str, Dict]:
    schemas = {}
    user_code = types.SimpleNamespace()
    exec(code, user_code.__dict__)
    for name, obj in user_code.__dict__.items():
        if isinstance(obj, BaseTypedDict):
            print_red("ERROR")
            print_red("\nERROR DETAILS: ")
            print(
                "It looks like you have used TypedDict in a custom function. Please use `from typing_extensions import TypedDict` instead. The `typing_extensions` version is more powerful and better allows us to provide rich types for your function."
            )
            sys.exit(1)
        elif (
            isinstance(obj, type)
            and isinstance(obj, _TypedDictMeta)
            and name != "TypedDict"
        ):
            schemas[name] = TypeAdapter(obj).json_schema()

    return schemas


def get_jsonschema_type(python_type: str):
    if python_type == "Any":
        return "any"

    if python_type == "List":
        return "array"

    if python_type.startswith("List["):
        # the actual type will be returned as return_type_schema
        subtype = python_type[5:-1]
        if subtype == "Any":
            return "any[]"
        elif subtype in ["int", "float", "str", "bool"]:
            jsonschema_type = PYTHON_TO_JSONSCHEMA_TYPE_MAP.get(subtype)
            return f"{jsonschema_type}[]"
        else:
            # the schema will handle it!
            return "object"

    if python_type.startswith("Dict"):
        # schemas logic will handle deeper object type
        return "object"

    if python_type.startswith("schemas."):
        # this is a polyapi schema
        return "object"

    rv = PYTHON_TO_JSONSCHEMA_TYPE_MAP.get(python_type)
    if rv:
        return rv

    # should be custom type
    return python_type


def get_python_type_from_ast(expr: ast.expr) -> str:
    if isinstance(expr, ast.Name):
        return str(expr.id)
    elif isinstance(expr, ast.Subscript):
        assert isinstance(expr, ast.Subscript)
        name = getattr(expr.value, "id", "")
        if name == "List":
            slice = getattr(expr.slice, "id", "Any")
            return f"List[{slice}]"
        elif name == "Dict":
            if expr.slice and isinstance(expr.slice, ast.Tuple):
                key = get_python_type_from_ast(expr.slice.dims[0])
                value = get_python_type_from_ast(expr.slice.dims[1])
                return f"Dict[{key}, {value}]"
            else:
                return "Dict"
        return "Any"
    elif isinstance(expr, ast.Attribute):
        # python does a series of attributes from the bottom to the top
        # e.g. schemas.petStore.Pet becomes:
        # Pet is an Attribute of petStore which is then an Attribute of schemas which is a Name
        # this recursively unwraps the structure to like it appears in code: schemas.petStore.Pet
        val = expr.value
        output = get_python_type_from_ast(val)
        return output + "." + expr.attr
    else:
        return "Any"


def _get_type_schema(json_type: str, python_type: str, schemas: Dict[str, Dict]):
    if python_type.startswith("schemas."):
        schema_context_name = python_type[8:]
        title = schema_context_name.rsplit(".", 1)[-1]
        return {
            "title": title,
            "$schema": "http://json-schema.org/draft-06/schema#",
            "allOf": [
                {
                    "x-poly-ref": {
                        "path": schema_context_name,
                    }
                }
            ],
        }

    if python_type.startswith("List["):
        subtype = python_type[5:-1]
        schema = schemas.get(subtype, "Any")
        if schema:
            return {"type": "array", "items": schema}
        else:
            return {"type": "array"}
    elif python_type.startswith("Dict"):
        return {"type": "object"}
    else:
        return schemas.get(json_type)


def _get_type(expr: ast.expr | None, schemas: Dict[str, Dict]) -> Tuple[Any, Any, Any]:
    if not expr:
        return "any", "Any", None
    python_type = get_python_type_from_ast(expr)
    json_type = get_jsonschema_type(python_type)
    schema = _get_type_schema(json_type, python_type, schemas)
    return json_type, python_type, schema


def _get_req_name_if_not_in_base(
    n: Optional[str], pip_name_lookup: Mapping[str, List[str]]
) -> Optional[str]:
    if not n:
        return None

    if "." in n:
        n = n.split(".")[0]

    if n in BASE_REQUIREMENTS:
        return None
    else:
        return pip_name_lookup[n][0]


def _parse_deploy_comment(comment: str) -> Optional[Deployment]:
    # Poly deployed @ 2024-08-29T22:46:46.791Z - test.weeklyReport - https://develop-k8s.polyapi.io/canopy/polyui/collections/server-functions/f0630f95-eac8-4c7d-9d23-639d39034bb6 - e3b0c44
    pattern = r"^\s*(?:#\s*)*Poly deployed @ (\S+) - (\S+)\.([^.]+) - (https?:\/\/[^\/]+)\/\S+\/(\S+)s\/(\S+) - (\S+)$"
    match = re.match(pattern, comment)
    if not match:
        return None

    deployed, context, name, instance, deploy_type, id, file_revision = match.groups()

    # Local development puts canopy on a different port than the poly-server
    if instance.endswith("localhost:3000"):
        instance = instance.replace(":3000", ":8000")

    return {
        "name": name,
        "context": context,
        "type": deploy_type,  # type: ignore
        "id": id,
        "deployed": deployed,
        "fileRevision": file_revision,
        "instance": instance,
    }


def _parse_dict(node):
    """Recursively parse an ast.Dict node into a Python dictionary."""
    result = {}
    for key, value in zip(node.keys, node.values):
        parsed_key = _parse_value(key)  # Keys can be other expressions too
        parsed_value = _parse_value(value)
        result[parsed_key] = parsed_value
    return result


def _parse_value(value):
    """Parse a value from different possible AST nodes to Python data."""
    if isinstance(value, ast.Constant):
        return value.value  # Handles str, int, float, NoneType, etc.
    elif isinstance(value, ast.Dict):
        return _parse_dict(value)
    elif isinstance(value, ast.List):
        return [_parse_value(item) for item in value.elts]
    elif isinstance(value, ast.Name):
        return value.id  # Could be a variable reference
    else:
        return None


def parse_function_code(  # noqa: C901
    code: str, name: Optional[str] = "", context: Optional[str] = ""
) -> DeployableRecord:
    poly_schemas = get_poly_schemas()
    schema_index = build_poly_schema_index(poly_schemas)
    schemas = _get_typed_dict_schemas(code)
    schema_index.update(schemas)

    # the pip name and the import name might be different
    # e.g. kube_hunter is the import name, but the pip name is kube-hunter
    # see https://stackoverflow.com/a/75144378
    pip_name_lookup = packages_distributions()

    deployable: DeployableRecord = {  # type: ignore
        "context": context,  # type: ignore
        "name": name,  # type: ignore
        "description": "",
        "config": {},
        "gitRevision": "",
        "fileRevision": "",
        "file": "",
        "types": {
            "description": "",
            "params": [],
            "returns": {
                "type": "",
                "typeSchema": None,
                "description": "",
            },
        },
        "typeSchemas": {},
        "dependencies": [],
        "deployments": [],
        "deploymentCommentRanges": [],
        "docStartIndex": -1,
        "docEndIndex": -1,
        "dirty": False,
    }

    class FunctionParserVisitor(ast.NodeVisitor):
        """
        Custom visitor so that we can keep track of the global offsets of text so we can easily generate replacements later
        """

        def __init__(self):
            self._name = name
            self._lines = code.splitlines(
                keepends=True
            )  # Keep line endings to maintain accurate indexing
            self._current_offset = 0
            self._line_offsets = [0]
            for i in range(1, len(self._lines)):
                self._line_offsets.append(
                    self._line_offsets[i - 1] + len(self._lines[i - 1])
                )

            self._extract_deploy_comments()

        def visit_AnnAssign(self, node):
            """Visit an assignment and check if it's defining a polyConfig."""
            self.generic_visit(node)  # Continue to visit children first

            if (
                isinstance(node.target, ast.Name)
                and node.target.id == "polyConfig"
                and isinstance(node.annotation, ast.Name)
            ):
                # We've found a polyConfig dictionary assignment
                if node.annotation.id == "PolyServerFunction":
                    deployable["type"] = "server-function"
                elif node.annotation.id == "PolyClientFunction":
                    deployable["type"] = "client-function"
                else:
                    print_red("ERROR")
                    print(f"Unsupported polyConfig type '${node.annotation.id}'")
                    sys.exit(1)
                deployable["config"] = _parse_dict(node.value)
                self._name = deployable["config"]["name"]

        def _extract_docstring_from_function(self, node: ast.FunctionDef):
            start_lineno = (node.body[0].lineno if node.body else node.lineno) - 1
            start_offset = self._line_offsets[start_lineno]
            end_offset = start_offset
            deployable["docStartIndex"] = start_offset
            deployable["docEndIndex"] = end_offset

            try:
                docstring = ast.get_docstring(node)
            finally:
                # Handle case where there is no doc string
                # Also handle case where docstring exists but is empty
                if type(docstring) is None or (
                    not docstring
                    and '"""' not in self._lines[start_lineno]
                    and "'''" not in self._lines[start_lineno]
                ):
                    return None

            docstring = cast(str, docstring)

            # Support both types of triple quotation marks
            pattern = '"""'
            str_offset = self._lines[start_lineno].find(pattern)
            if str_offset == -1:
                pattern = "'''"
                str_offset = self._lines[start_lineno].find(pattern)
            start_offset += str_offset
            # Determine end_offset for multiline or single line doc strings by searching until we hit the end of the opening pattern
            # We have to do this manually because the docstring we get from the ast excludes the quotation marks and whitespace
            if self._lines[start_lineno].find(pattern, str_offset + 3) == -1:
                end_offset = start_offset
                for i in range(start_lineno + 1, len(self._lines)):
                    end_offset = self._line_offsets[i]
                    str_offset = self._lines[i].find(pattern)
                    if str_offset >= 0:
                        end_offset += str_offset + 3
                        break
            else:
                end_offset += len(self._lines[start_lineno]) - 1

            deployable["docStartIndex"] = start_offset
            deployable["docEndIndex"] = end_offset

            # Check if the docstring is likely to be Google Docstring format https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html
            if "Args:" in docstring or "Returns:" in docstring:
                deployable["types"] = cast(
                    DeployableFunctionTypes, _parse_google_docstring(docstring)
                )
            else:
                deployable["types"]["description"] = docstring.strip()

        def _extract_deploy_comments(self):
            for i in range(len(self._lines)):
                line = self._lines[i]
                if line and not line.startswith("#"):
                    return
                deployment = _parse_deploy_comment(line.strip())
                if deployment:
                    start = self._line_offsets[i]
                    deployable["deployments"].append(deployment)
                    deployable["deploymentCommentRanges"].append(
                        [start, start + len(line)]
                    )

        def visit_Import(self, node: ast.Import):
            # TODO maybe handle `import foo.bar` case?
            for name in node.names:
                req = _get_req_name_if_not_in_base(name.name, pip_name_lookup)
                if req:
                    deployable["dependencies"].append(req)

        def visit_ImportFrom(self, node: ast.ImportFrom):
            if node.module:
                req = _get_req_name_if_not_in_base(node.module, pip_name_lookup)
                if req:
                    deployable["dependencies"].append(req)

        def visit_FunctionDef(self, node: ast.FunctionDef):
            if node.name == self._name:
                # Parse docstring which may contain param types and descriptions
                self._extract_docstring_from_function(node)
                function_args = [arg for arg in node.args.args]
                docstring_params = deployable["types"]["params"]
                parsed_params = []
                # parse params from actual function and merge in any data from the docstring
                for arg in function_args:
                    _, python_type, type_schema = _get_type(
                        arg.annotation, schema_index
                    )
                    json_arg = {
                        "name": arg.arg,
                        "type": python_type,
                        "description": "",
                    }
                    json_arg["typeSchema"] = (
                        json.dumps(type_schema) if type_schema else None
                    )

                    if docstring_params:
                        try:
                            type_index = next(
                                i
                                for i, d in enumerate(docstring_params)
                                if d["name"] == arg.arg
                            )
                            if type_index >= 0:
                                json_arg["description"] = docstring_params[type_index][
                                    "description"
                                ]
                                if docstring_params[type_index]["type"] != python_type:
                                    deployable["dirty"] = True
                        except:
                            pass
                    else:
                        deployable["dirty"] = True

                    parsed_params.append(json_arg)
                deployable["types"]["params"] = parsed_params  # type: ignore
                if node.returns:
                    _, python_type, return_type_schema = _get_type(
                        node.returns, schema_index
                    )
                    if deployable["types"]["returns"]["type"] != python_type:
                        deployable["dirty"] = True
                    deployable["types"]["returns"]["type"] = python_type
                    deployable["types"]["returns"]["typeSchema"] = return_type_schema
                else:
                    deployable["types"]["returns"]["type"] = "Any"

        def generic_visit(self, node):
            if hasattr(node, "lineno") and hasattr(node, "col_offset"):
                self._current_offset = (
                    self._line_offsets[node.lineno - 1] + node.col_offset
                )
            super().generic_visit(node)

    tree = ast.parse(code)
    visitor = FunctionParserVisitor()
    visitor.visit(tree)

    # Setting some top-level config values for convenience
    deployable["context"] = context or deployable["config"].get("context", "")
    deployable["name"] = name or deployable["config"].get("name", "")
    deployable["disableAi"] = deployable["config"].get("disableAi", False)
    deployable["description"] = deployable["types"].get("description", "")
    if not deployable["name"]:
        print_red("ERROR")
        print("Function config is missing a name.")
        sys.exit(1)

    deployable["fileRevision"] = get_deployable_file_revision(code)

    return deployable
