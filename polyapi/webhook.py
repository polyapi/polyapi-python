import asyncio
import socketio  # type: ignore
from socketio.exceptions import ConnectionError  # type: ignore
import uuid
from typing import Any, Dict, List, Tuple

from polyapi.config import get_api_key_and_url
from polyapi.typedefs import PropertySpecification
from polyapi.utils import poly_full_path

# all active webhook handlers, used by unregister_all to cleanup
active_handlers: List[Dict[str, Any]] = []

# global client shared by all webhooks, will be initialized by webhook.start
client = None


WEBHOOK_TEMPLATE = """


async def {function_name}(callback, options=None):
    \"""{description}

    Function ID: {function_id}
    \"""
    from polyapi.webhook import client, active_handlers

    print("Starting webhook handler for {function_path}...")

    if not client:
        raise Exception("Client not initialized. Abort!")

    options = options or {{}}
    eventsClientId = "{client_id}"
    function_id = "{function_id}"

    api_key, base_url = get_api_key_and_url()

    def registerCallback(registered: bool):
        if registered:
            client.on('handleWebhookEvent:{function_id}', handleEvent, namespace="/events")
        else:
            print("Could not set register webhook event handler for {function_id}")

    async def handleEvent(data):
        nonlocal api_key
        nonlocal options
        polyCustom = {{}}
        resp = callback(data.get("body"), data.get("headers"), data.get("params"), polyCustom)
        if options.get("waitForResponse"):
            await client.emit('setWebhookListenerResponse', {{
                "webhookHandleID": function_id,
                "apiKey": api_key,
                "clientID": eventsClientId,
                "executionId": data.get("executionId"),
                "response": {{
                    "data": resp,
                    "statusCode": polyCustom.get("responseStatusCode", 200),
                    "contentType": polyCustom.get("responseContentType", None),
                }},
            }}, namespace="/events")

    data = {{
        "clientID": eventsClientId,
        "webhookHandleID": function_id,
        "apiKey": api_key,
        "waitForResponse": options.get("waitForResponse"),
    }}
    await client.emit('registerWebhookEventHandler', data, namespace="/events", callback=registerCallback)
    active_handlers.append({{"clientID": eventsClientId, "webhookHandleID": function_id, "apiKey": api_key, "path": "{function_path}"}})
"""


async def get_client_and_connect():
    _, base_url = get_api_key_and_url()
    global client
    client = socketio.AsyncClient()
    await client.connect(base_url, transports=["websocket"], namespaces=["/events"])


async def unregister(data: Dict[str, Any]):
    print(f"Stopping webhook handler for {data['path']}...")
    assert client
    await client.emit(
        "unregisterWebhookEventHandler",
        {
            "clientID": data["clientID"],
            "webhookHandleID": data["webhookHandleID"],
            "apiKey": data["apiKey"],
        },
        "/events",
    )


async def unregister_all():
    _, base_url = get_api_key_and_url()
    # maybe need to reconnect because maybe socketio client disconnected after Ctrl+C?
    # feels like Linux disconnects but Windows stays connected
    try:
        await client.connect(base_url, transports=["websocket"], namespaces=["/events"])
    except ConnectionError:
        pass
    await asyncio.gather(*[unregister(handler) for handler in active_handlers])


def render_webhook_handle(
    function_type: str,
    function_context: str,
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
        function_path=poly_full_path(function_context, function_name),
    )

    return func_str, ""


def start(*args):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_client_and_connect())
    asyncio.gather(*args)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(unregister_all())
        loop.stop()
