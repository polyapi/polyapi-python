from typing import Any, Dict, List, Tuple, cast

from polyapi.typedefs import PropertySpecification, PropertyType
from polyapi.utils import add_type_import_path, parse_arguments, get_type_and_def, return_type_already_defined_in_args, rewrite_arg_name

SERVER_DEFS_TEMPLATE = """
from typing import List, Dict, Any, TypedDict, Callable
{args_def}
{return_type_def}
"""

SERVER_FUNCTION_TEMPLATE = """
def {function_name}(
{args}
) -> {return_type_name}:
    \"""{function_description}

    Function ID: {function_id}
    \"""
    resp = execute("{function_type}", "{function_id}", {data})
    try:
        return {return_action}
    except:
        return resp.text  # type: ignore # fallback for debugging


"""


def render_server_function(
    function_type: str,
    function_name: str,
    function_id: str,
    function_description: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
) -> Tuple[str, str]:
    arg_names = [a["name"] for a in arguments]
    args, args_def = parse_arguments(function_name, arguments)
    return_type_name, return_type_def = get_type_and_def(cast(PropertyType, return_type), "ReturnType")

    if return_type_def and return_type_already_defined_in_args(return_type_name, args_def):
        return_type_def = ""

    data = "{" + ", ".join([f"'{arg}': {rewrite_arg_name(arg)}" for arg in arg_names]) + "}"
    func_type_defs = SERVER_DEFS_TEMPLATE.format(
        args_def=args_def,
        return_type_def=return_type_def,
    )
    func_str = SERVER_FUNCTION_TEMPLATE.format(
        return_type_name=add_type_import_path(function_name, return_type_name),
        function_type="server",
        function_name=function_name,
        function_id=function_id,
        function_description=function_description.replace('"', "'"),
        args=args,
        return_action=_get_server_return_action(return_type_name),
        data=data,
    )
    return func_str, func_type_defs


def _get_server_return_action(return_type_name: str) -> str:
    if return_type_name == "str":
        return_action = "resp.text"
    else:
        return_action = "resp.json()"
    return return_action