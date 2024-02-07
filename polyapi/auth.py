from typing import List, Dict, Any, Tuple

from polyapi.typedefs import PropertySpecification
from polyapi.utils import parse_arguments, get_type_and_def


AUTH_DEFS_TEMPLATE = """
from typing import List, Dict, Any, TypedDict
{args_def}
{return_type_def}
"""

GET_TOKEN_TEMPLATE = """
def getToken(clientId, clientSecret, scopes, callback, userId) -> Dict:
    url = "/auth-providers/{function_id}/execute"
    resp = execute_post(url, {{
        "clientId": clientId,
        "clientSecret": clientSecret,
        "scopes": scopes,
        "userId": userId,
    }})
    data = resp.json()
    return callback(data.get("token"), data.get("url"), data.get("error"))
"""


def render_auth_function(
    function_type: str,
    function_name: str,
    function_id: str,
    function_description: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
) -> Tuple[str, str]:
    """ renders getToken, revokeToken, refreshToken as appropriate
    """
    args, args_def = parse_arguments(function_name, arguments)
    return_type_name, return_type_def = get_type_and_def(return_type)  # type: ignore
    func_type_defs = AUTH_DEFS_TEMPLATE.format(
        args_def=args_def,
        return_type_def=return_type_def,
    )

    func_str = ""

    if function_name == "getToken":
        func_str = GET_TOKEN_TEMPLATE.format(function_id=function_id)

    return func_str, func_type_defs