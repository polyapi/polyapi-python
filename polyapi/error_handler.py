import asyncio
import copy
import socketio  # type: ignore
from typing import Any, Callable, Dict, Optional

from polyapi.config import get_api_key_and_url


local_error_handlers: Dict[str, Any] = {}


def on(path: str, callback: Callable, options: Optional[Dict[str, Any]] = None) -> Callable:
    assert not local_error_handlers
    socket = socketio.AsyncClient()
    api_key, base_url = get_api_key_and_url()

    async def _inner():
        await socket.connect(base_url, transports=["websocket"], namespaces=["/events"])

        handler_id = None
        data = copy.deepcopy(options or {})
        data["path"] = path
        data["apiKey"] = api_key

        def registerCallback(id: int):
            nonlocal handler_id, socket
            handler_id = id
            socket.on(f"handleError:{handler_id}", callback, namespace="/events")

        await socket.emit("registerErrorHandler", data, "/events", registerCallback)
        if local_error_handlers.get(path):
            local_error_handlers[path].append(callback)
        else:
            local_error_handlers[path] = [callback]

        async def unregister():
            nonlocal handler_id, socket
            if handler_id and socket:
                await socket.emit(
                    "unregisterErrorHandler",
                    {"id": handler_id, "path": path, "apiKey": api_key},
                    namespace="/events",
                )

            if local_error_handlers.get(path):
                local_error_handlers[path].remove(callback)

        await socket.wait()

        return unregister

    return asyncio.run(_inner())