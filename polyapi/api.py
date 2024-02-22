from typing import Any, Dict, List, Tuple

from polyapi.typedefs import PropertySpecification
from polyapi.utils import add_type_import_path, camelCase, parse_arguments, get_type_and_def


API_DEFS_TEMPLATE = """
from typing import List, Dict, Any, TypedDict
{args_def}
{return_type_def}
class {api_response_type}(TypedDict):
    status: int
    headers: Dict
    data: {return_type_name}
"""

API_FUNCTION_TEMPLATE = """
def {function_name}(
{args}
) -> {api_response_type}:
    \"""{function_description}

    Function ID: {function_id}
    \"""
    resp = execute("{function_type}", "{function_id}", {data})
    return {api_response_type}(resp.json())  # type: ignore
"""


def render_api_function(
    function_type: str,
    function_name: str,
    function_id: str,
    function_description: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
) -> Tuple[str, str]:
    assert function_type == "apiFunction"
    arg_names = [a["name"] for a in arguments]
    args, args_def = parse_arguments(function_name, arguments)
    return_type_name, return_type_def = get_type_and_def(return_type)  # type: ignore
    data = "{" + ", ".join([f"'{arg}': {camelCase(arg)}" for arg in arg_names]) + "}"

    api_response_type = f"{function_name}Response"
    func_type_defs = API_DEFS_TEMPLATE.format(
        args_def=args_def,
        api_response_type=api_response_type,
        return_type_name=return_type_name,
        return_type_def=return_type_def,
    )
    func_str = API_FUNCTION_TEMPLATE.format(
        function_type="api",
        function_name=function_name,
        function_id=function_id,
        function_description=function_description.replace('"', "'"),
        args=args,
        data=data,
        api_response_type=add_type_import_path(function_name, api_response_type),
    )
    return func_str, func_type_defs