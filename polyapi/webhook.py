import asyncio
import socketio  # type: ignore
import uuid
from typing import Any, Dict, List, Tuple

from polyapi.config import get_api_key_and_url
from polyapi.typedefs import PropertySpecification


WEBHOOK_TEMPLATE = """
from polyapi.webhook import client


async def {function_name}(callback, options=None):
    \"""{description}

    Function ID: {function_id}
    \"""
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
        resp = await callback(data.get("body"), data.get("headers"), data.get("params"), polyCustom)
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
"""

client = None


async def get_client_and_connect():
    _, base_url = get_api_key_and_url()
    global client
    client = socketio.AsyncClient()
    await client.connect(base_url, transports=["websocket"], namespaces=["/events"])


def unregister_all():
    print("TODO unregister all webhooks")


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