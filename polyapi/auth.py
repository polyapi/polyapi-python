from typing import List, Dict, Any, Tuple

from polyapi.typedefs import PropertySpecification
from polyapi.utils import parse_arguments, get_type_and_def


AUTH_DEFS_TEMPLATE = """
from typing import List, Dict, Any, TypedDict, Optional
{args_def}
{return_type_def}
"""

GET_TOKEN_TEMPLATE = """
from polyapi.config import get_api_key_and_url


def getToken(clientId: str, clientSecret: str, scopes: List[str], callback, options: Optional[Dict[str, Any]] = None):
    {description}
    # TODO timeout, autoCloseOnUrl, autoCloseOnToken
    options = options or {{}}
    url = "/auth-providers/{function_id}/execute"
    data = {{
        "clientId": clientId,
        "clientSecret": clientSecret,
        "scopes": scopes,
        "audience": options.get("audience"),
        "callbackUrl": options.get("callbackUrl"),
        "userId": options.get("userId"),
    }}
    resp = execute_post(url, data)
    data = resp.json()
    assert resp.status_code == 201, (resp.status_code, resp.content)

    token = data.get("token")
    url = data.get("url")
    error = data.get("error")
    if token:
        return callback(token, url, error)
    elif True or url and options.get("autoCloseOnUrl"):
        return callback(token, url, error)

    timeout = options.get("timeout", 120)
"""

SOCKETIO_STUFF = """
    except TimeoutError:
        print('timed out waiting for event')

    _, url = get_api_key_and_url()
    events_url = f"{{url}}/events"
    socketio.AsyncSimpleClient() as sio:
    print(f"Connecting to {{events_url}}")
    await sio.connect(events_url, transports=['websocket'])
    print('my sid is', sio.sid)
    print("my transport is", sio.transport)
    await sio.receive(timeout=timeout)

    const closeEventHandler = () => {
        if (!socket) {
        return;
        }
        socket.off(`handleAuthFunctionEvent:{{id}}`);
        socket.emit('unregisterAuthFunctionEventHandler', {
        clientID: eventsClientId,
        functionId: '{{id}}',
        apiKey: getApiKey()
        });
        socket.close();
        socket = null;
        if (timeoutID) {
        clearTimeout(timeoutID);
        }
    };
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