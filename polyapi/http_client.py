import asyncio
import logging
import os
import httpx

logger = logging.getLogger("poly")

# Connx pool + timeout defaults for the shared clients.

# Plz bump lims below if evictions like connect_tcp.started ->> ReadError ClosedResourceError

DEFAULT_LIMITS = httpx.Limits(
    max_connections=200,
    max_keepalive_connections=64,
    keepalive_expiry=30.0,
)
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=None, write=30.0, pool=15.0)

_sync_client: httpx.Client | None = None
# One async client per event loop. 
_async_clients: "dict[asyncio.AbstractEventLoop, httpx.AsyncClient]" = {}


def _get_sync_client() -> httpx.Client:
    global _sync_client
    if _sync_client is None:
        _sync_client = httpx.Client(limits=DEFAULT_LIMITS, timeout=DEFAULT_TIMEOUT)
    return _sync_client


def _retire_async_client(
    client: httpx.AsyncClient | None,
    loop: asyncio.AbstractEventLoop | None,
) -> None:
    """Best-effort close of an async client whose event loop is being dumped.
    """
    if client is None:
        return
    try:
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(lambda: loop.create_task(client.aclose()))
            logger.debug(f"Scheduled aclose of async client id={id(client)} pid={os.getpid()} loop={id(loop)}")
        else:
            loop_closed = None if loop is None else loop.is_closed()
            logger.debug(f"Dropping async client id={id(client)} pid={os.getpid()} loop={id(loop)} loop_closed={loop_closed}")
    except Exception:
        logger.warning(f"Failed to retire async client id={id(client)} pid={os.getpid()} loop={id(loop)}", exc_info=True)


def _sweep_dead_loops() -> None:
    """Wipe clients whose event loop has been closed.
    """
    for loop in list(_async_clients):
        if loop.is_closed():
            _retire_async_client(_async_clients.pop(loop, None), loop)


def _get_async_client() -> httpx.AsyncClient:
    current_loop = asyncio.get_running_loop()
    client = _async_clients.get(current_loop)
    if client is None:
        _sweep_dead_loops()
        client = httpx.AsyncClient(limits=DEFAULT_LIMITS, timeout=DEFAULT_TIMEOUT)
        _async_clients[current_loop] = client
        logger.debug(
            f"Created async client id={id(client)} pid={os.getpid()} loop={id(current_loop)} "
            f"max_connections={DEFAULT_LIMITS.max_connections} "
            f"max_keepalive={DEFAULT_LIMITS.max_keepalive_connections} "
            f"keepalive_expiry={DEFAULT_LIMITS.keepalive_expiry}"
        )
    return client


def post(url, **kwargs) -> httpx.Response:
    return _get_sync_client().post(url, **kwargs)


async def async_post(url, **kwargs) -> httpx.Response:
    return await _get_async_client().post(url, **kwargs)


def get(url, **kwargs) -> httpx.Response:
    return _get_sync_client().get(url, **kwargs)


async def async_get(url, **kwargs) -> httpx.Response:
    return await _get_async_client().get(url, **kwargs)


def patch(url, **kwargs) -> httpx.Response:
    return _get_sync_client().patch(url, **kwargs)


async def async_patch(url, **kwargs) -> httpx.Response:
    return await _get_async_client().patch(url, **kwargs)


def delete(url, **kwargs) -> httpx.Response:
    return _get_sync_client().delete(url, **kwargs)


async def async_delete(url, **kwargs) -> httpx.Response:
    return await _get_async_client().delete(url, **kwargs)


def request(method, url, **kwargs) -> httpx.Response:
    return _get_sync_client().request(method, url, **kwargs)


async def async_request(method, url, **kwargs) -> httpx.Response:
    return await _get_async_client().request(method, url, **kwargs)


def close():
    global _sync_client
    if _sync_client is not None:
        _sync_client.close()
        _sync_client = None

async def close_async():
    close()
    current_loop = asyncio.get_running_loop()
    client = _async_clients.pop(current_loop, None)
    if client is not None:
        await client.aclose()
    # Nuke clients left behind by dead loops
    _sweep_dead_loops()
