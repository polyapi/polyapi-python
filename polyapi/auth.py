from typing import List, Dict, Any, Tuple

from polyapi.typedefs import PropertySpecification


def render_auth_function(
    function_type: str,
    function_name: str,
    function_id: str,
    function_description: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
) -> Tuple[str, str]:
    print(f"TODO add auth function {function_name}!")
    func_str = ""
    func_type_defs = ""
    return func_str, func_type_defs