import asyncio
import copy
import socketio  # type: ignore
from socketio.exceptions import ConnectionError  # type: ignore
from typing import Any, Callable, Dict, List, Optional

from polyapi.config import get_api_key_and_url


# all active webhook handlers, used by unregister_all to cleanup
active_handlers: List[Dict[str, Any]] = []

# global client shared by all error handlers, will be initialized by webhook.start
client = None


def prepare():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_client_and_connect())
    print("Client initialized!")



async def get_client_and_connect():
    _, base_url = get_api_key_and_url()
    global client
    client = socketio.AsyncClient()
    await client.connect(base_url, transports=["websocket"], namespaces=["/events"])


async def unregister(data: Dict[str, Any]):
    print(f"Stopping error handler for {data['path']}...")
    assert client
    await client.emit(
        "unregisterErrorHandler",
        data,
        "/events",
    )


async def unregister_all():
    _, base_url = get_api_key_and_url()
    # need to reconnect because maybe socketio client disconnected after Ctrl+C?
    try:
        await client.connect(base_url, transports=["websocket"], namespaces=["/events"])
    except ConnectionError:
        pass
    await asyncio.gather(*[unregister(handler) for handler in active_handlers])


async def on(
    path: str, callback: Callable, options: Optional[Dict[str, Any]] = None
) -> None:
    print(f"Starting error handler for {path}...")

    if not client:
        raise Exception("Client not initialized. Abort!")

    api_key, _ = get_api_key_and_url()
    handler_id = None
    data = copy.deepcopy(options or {})
    data["path"] = path
    data["apiKey"] = api_key

    def registerCallback(id: int):
        nonlocal handler_id
        handler_id = id
        client.on(f"handleError:{handler_id}", callback, namespace="/events")
        active_handlers.append({"path": path, "id": handler_id, "apiKey": api_key})

    await client.emit("registerErrorHandler", data, "/events", registerCallback)


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