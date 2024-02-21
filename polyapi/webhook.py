import uuid
from typing import Any, Dict, List, Tuple

from polyapi.typedefs import PropertySpecification

WEBHOOK_TEMPLATE = """
async def {function_name}(callback, options=None):
    "{description}"
    options = options or {{}}
    eventsClientId = "{client_id}"
    function_id = "{function_id}"

    api_key, base_url = get_api_key_and_url()
    socket = socketio.AsyncClient()
    await socket.connect(base_url, transports=['websocket'], namespaces=['/events'])

    def registerCallback(registered: bool):
        nonlocal socket
        if registered:
            socket.on('handleWebhookEvent:{function_id}', handleEvent, namespace="/events")
        else:
            print("Could not set register webhook event handler for {function_id}")

    def handleEvent(data):
        nonlocal options
        polyCustom = {{}}
        callback(data.get("body"), data.get("headers"), data.get("params"), polyCustom)

    data = {{
        "clientID": eventsClientId,
        "webhookHandleID": function_id,
        "apiKey": api_key
    }}
    await socket.emit('registerWebhookEventHandler', data, namespace="/events", callback=registerCallback)

    async def closeEventHandler():
        nonlocal socket
        if not socket:
            return

        await socket.emit('unregisterWebhookEventHandler', {{
            "clientID": eventsClientId,
            "webhookHandleID": function_id,
            "apiKey": api_key
        }}, namespace="/events")

    await socket.wait()

    return closeEventHandler
"""


def render_webhook_handle(
    function_type: str,
    function_name: str,
    function_id: str,
    function_description: str,
    arguments: List[PropertySpecification],
    return_type: Dict[str, Any],
) -> Tuple[str, str]:
    func_str = WEBHOOK_TEMPLATE.format(
        description=function_description,
        client_id=uuid.uuid4().hex,
        function_id=function_id,
        function_name=function_name,
    )

    return func_str, ""