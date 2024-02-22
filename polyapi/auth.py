from typing import List, Dict, Any, Tuple
import uuid

from polyapi.typedefs import PropertySpecification
from polyapi.utils import parse_arguments, get_type_and_def


AUTH_DEFS_TEMPLATE = """
from typing import List, Dict, Any, TypedDict, Optional
{args_def}
{return_type_def}
"""

GET_TOKEN_TEMPLATE = """
import asyncio


async def getToken(clientId: str, clientSecret: str, scopes: List[str], callback, options: Optional[Dict[str, Any]] = None):
    \"""{description}

    Function ID: {function_id}
    \"""
    eventsClientId = "{client_id}"
    function_id = "{function_id}"

    options = options or {{}}
    path = "/auth-providers/{function_id}/execute"
    data = {{
        "clientId": clientId,
        "clientSecret": clientSecret,
        "scopes": scopes,
        "audience": options.get("audience"),
        "callbackUrl": options.get("callbackUrl"),
        "userId": options.get("userId"),
    }}
    resp = execute_post(path, data)
    data = resp.json()
    assert resp.status_code == 201, (resp.status_code, resp.content)

    token = data.get("token")
    url = data.get("url")
    error = data.get("error")
    if token:
        return callback(token, url, error)
    elif url and options.get("autoCloseOnUrl"):
        return callback(token, url, error)

    timeout = options.get("timeout", 120)

    api_key, base_url = get_api_key_and_url()
    socket = socketio.AsyncClient()
    await socket.connect(base_url, transports=['websocket'], namespaces=['/events'])

    async def closeEventHandler():
        nonlocal socket
        if not socket:
            return

        del socket.handlers['/events']['handleAuthFunctionEvent:{function_id}']
        await socket.emit('unregisterAuthFunctionEventHandler', {{
            "clientID": eventsClientId,
            "functionId": function_id,
            "apiKey": api_key
        }}, namespace="/events")
        await socket.disconnect()
        socket = None


    async def waitUntilTimeout(timeout):
        await asyncio.sleep(timeout)
        await closeEventHandler()


    async def handleEvent(data):
        nonlocal options
        callback(data.get('token'), data.get('url'), data.get('error'))
        if data.get('token') and options.get("autoCloseOnToken", True):
            await closeEventHandler()


    def registerCallback(registered: bool):
        nonlocal socket
        if registered:
            socket.on('handleAuthFunctionEvent:{function_id}', handleEvent, namespace="/events")
            callback(data.get('token'), data.get('url'), data.get('error'))

    data2 = {{
        "clientID": eventsClientId,
        "functionId": function_id,
        "apiKey": api_key
    }}
    await socket.emit('registerAuthFunctionEventHandler', data2, namespace="/events", callback=registerCallback)

    # run timeout task in background
    timeout = options.get("timeout", 120)
    timeout_task = asyncio.create_task(waitUntilTimeout(timeout))

    # cancel timeout task if socket.wait finishes before timeout up
    await socket.wait()
    timeout_task.cancel()

    return {{"close": closeEventHandler}}
"""

REFRESH_TOKEN_TEMPLATE = """
def refreshToken(token: str) -> str:
    \"""{description}

    Function ID: {function_id}
    \"""
    url = "/auth-providers/{function_id}/refresh"
    resp = execute_post(url, {{"token": token}})
    assert resp.status_code == 201, (resp.status_code, resp.content)
    return resp.text
"""

REVOKE_TOKEN_TEMPLATE = """
def revokeToken(token: str) -> None:
    \"""{description}

    Function ID: {function_id}
    \"""
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

    if function_name == "getToken":
        func_str = GET_TOKEN_TEMPLATE.format(function_id=function_id, description=function_description, client_id=uuid.uuid4().hex)
    elif function_name == "refreshToken":
        func_str = REFRESH_TOKEN_TEMPLATE.format(function_id=function_id, description=function_description)
    elif function_name == "revokeToken":
        func_str = REVOKE_TOKEN_TEMPLATE.format(function_id=function_id, description=function_description)

    return func_str, func_type_defs