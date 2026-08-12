import asyncio
import logging
import os
import httpx

logger = logging.getLogger("polyapi.http_client")

# Connx pool + timeout defaults for the shared clients.

# Plz bump lims below if evictions like connect_tcp.started ->> ReadError ClosedResourceError

DEFAULT_LIMITS = httpx.Limits(
    max_connections=200,
    max_keepalive_connections=64,
    keepalive_expiry=30.0,
)
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=90.0, write=30.0, pool=15.0)

_sync_client: httpx.Client | None = None
_async_client: httpx.AsyncClient | None = None
_async_client_loop: asyncio.AbstractEventLoop | None = None


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
        if loop is not None and not loop.is_closed():
            if loop.is_running():
                # Schedule the close on the client's own loop (may be another thread).
                loop.call_soon_threadsafe(lambda: loop.create_task(client.aclose()))
                logger.info(
                    "retiring async client id=%s pid=%s loop=%s (scheduled aclose)",
                    id(client), os.getpid(), id(loop),
                )
                return
            loop.run_until_complete(client.aclose())
        logger.info(
            "retired async client id=%s pid=%s loop=%s",
            id(client), os.getpid(), id(loop),
        )
    except Exception:
        # Never let cleanup of a dead client break the caller's request.
        logger.warning(
            "failed to cleanly retire async client id=%s pid=%s loop=%s",
            id(client), os.getpid(), id(loop), exc_info=True,
        )


def _get_async_client() -> httpx.AsyncClient:
    global _async_client, _async_client_loop
    current_loop = asyncio.get_running_loop()
    if _async_client is None or _async_client_loop is not current_loop:
        _retire_async_client(_async_client, _async_client_loop)
        _async_client = httpx.AsyncClient(limits=DEFAULT_LIMITS, timeout=DEFAULT_TIMEOUT)
        _async_client_loop = current_loop
        logger.info(
            "created async client id=%s pid=%s loop=%s "
            "max_connections=%s max_keepalive=%s keepalive_expiry=%s",
            id(_async_client), os.getpid(), id(current_loop),
            DEFAULT_LIMITS.max_connections,
            DEFAULT_LIMITS.max_keepalive_connections,
            DEFAULT_LIMITS.keepalive_expiry,
        )
    return _async_client


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
    global _async_client, _async_client_loop
    close()
    client = _async_client
    client_loop = _async_client_loop
    _async_client = None
    _async_client_loop = None
    if client is None:
        return

    current_loop = asyncio.get_running_loop()
    if client_loop is current_loop:
        await client.aclose()
    else:
        _retire_async_client(client, client_loop)
