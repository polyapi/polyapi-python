from typing import List, Dict, Any, Tuple

from polyapi.typedefs import PropertySpecification
from polyapi.utils import parse_arguments, get_type_and_def


AUTH_DEFS_TEMPLATE = """
from typing import List, Dict, Any, TypedDict
{args_def}
{return_type_def}
"""

GET_TOKEN_TEMPLATE = """
def getToken(clientId: str, clientSecret: str, scopes: List[str], callback, options: Dict[str, Any] = None):
    {description}
    options = options or {{}}
    url = "/auth-providers/{function_id}/execute"
    resp = execute_post(url, {{
        "clientId": clientId,
        "clientSecret": clientSecret,
        "scopes": scopes,
        "userId": options.get("userId"),
    }})
    data = resp.json()
    assert resp.status_code == 201, (resp.status_code, resp.content)
    return callback(data.get("token"), data.get("url"), data.get("error"))
"""

REFRESH_TOKEN_TEMPLATE = """
def refreshToken(token: str) -> str:
    {description}
    url = "/auth-providers/{function_id}/refresh"
    resp = execute_post(url, {{"token": token}})
    assert resp.status_code == 201, (resp.status_code, resp.content)
    return resp.text
"""

REVOKE_TOKEN_TEMPLATE = """
def revokeToken(token: str) -> None:
    {description}
    url = "/auth-providers/{function_id}/revoke"
    resp = execute_post(url, {{"token": token}})
    assert resp.status_code == 201, (resp.status_code, resp.content)
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

    if function_description:
        function_description = f'"""{function_description}"""'

    if function_name == "getToken":
        func_str = GET_TOKEN_TEMPLATE.format(function_id=function_id, description=function_description)
    elif function_name == "refreshToken":
        func_str = REFRESH_TOKEN_TEMPLATE.format(function_id=function_id, description=function_description)
    elif function_name == "revokeToken":
        func_str = REVOKE_TOKEN_TEMPLATE.format(function_id=function_id, description=function_description)

    return func_str, func_type_defs