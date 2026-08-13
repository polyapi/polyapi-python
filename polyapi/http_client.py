import asyncio
import logging
import os
import threading
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

# PID that owns the clients below; a fork resets it
_owner_pid: int = os.getpid()
_sync_client: httpx.Client | None = None
# Guard lazy creation of _sync_client
_sync_client_lock = threading.Lock()
# One async client per event loop.
_async_clients: "dict[asyncio.AbstractEventLoop, httpx.AsyncClient]" = {}
# In-flight request count per async client, so close_async can drain before aclose.
_async_inflight: "dict[httpx.AsyncClient, int]" = {}


def _reset_if_forked() -> None:
    """Drop clients inherited across os.fork() so childisolated
    Clear not close the inherited refs - child makes its own."""
    global _owner_pid, _sync_client
    current_pid = os.getpid()
    if current_pid != _owner_pid:
        _sync_client = None
        _async_clients.clear()
        _owner_pid = current_pid


def _get_sync_client() -> httpx.Client:
    global _sync_client
    _reset_if_forked()
    if _sync_client is None:
        # Double-checked lock
        with _sync_client_lock:
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


def _register_loop_close_hook(
    loop: asyncio.AbstractEventLoop, client: httpx.AsyncClient
) -> None:
    """aclose the client on loop right before loop torn down
    """
    original_close = loop.close

    def _close_with_cleanup(*args, **kwargs):
        cached = _async_clients.get(loop)
        if cached is not None and not loop.is_closed():
            try:
                loop.run_until_complete(cached.aclose())
            except Exception:
                logger.warning(
                    f"Failed to aclose async client id={id(cached)} pid={os.getpid()} "
                    f"loop={id(loop)} on teardown", exc_info=True)
        return original_close(*args, **kwargs)

    try:
        loop.close = _close_with_cleanup  # type: ignore[method-assign]
    except (AttributeError, TypeError):
        logger.debug(f"Could not hook loop.close pid={os.getpid()} loop={id(loop)}; relying on sweep")


def _get_async_client() -> httpx.AsyncClient:
    _reset_if_forked()
    current_loop = asyncio.get_running_loop()
    client = _async_clients.get(current_loop)
    if client is None:
        _sweep_dead_loops()
        client = httpx.AsyncClient(limits=DEFAULT_LIMITS, timeout=DEFAULT_TIMEOUT)
        _async_clients[current_loop] = client
        _register_loop_close_hook(current_loop, client)
        logger.debug(
            f"Created async client id={id(client)} pid={os.getpid()} loop={id(current_loop)} "
            f"max_connections={DEFAULT_LIMITS.max_connections} "
            f"max_keepalive={DEFAULT_LIMITS.max_keepalive_connections} "
            f"keepalive_expiry={DEFAULT_LIMITS.keepalive_expiry}"
        )
    return client


async def _dispatch_async(method_name: str, *args, **kwargs) -> httpx.Response:
    # Track in-flight requests per client so close_async can drain before aclose.
    client = _get_async_client()
    _async_inflight[client] = _async_inflight.get(client, 0) + 1
    try:
        return await getattr(client, method_name)(*args, **kwargs)
    finally:
        remaining = _async_inflight.get(client, 1) - 1
        if remaining <= 0:
            _async_inflight.pop(client, None)
        else:
            _async_inflight[client] = remaining


async def _drain_inflight(client: httpx.AsyncClient, timeout: float = 30.0) -> None:
    # Wait for in-flight requests on client to finish before closing it, so we don't
    # tear connections out from under active callers. Bounded.
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while _async_inflight.get(client, 0) > 0 and loop.time() < deadline:
        await asyncio.sleep(0.05)


def post(url, **kwargs) -> httpx.Response:
    return _get_sync_client().post(url, **kwargs)


async def async_post(url, **kwargs) -> httpx.Response:
    return await _dispatch_async("post", url, **kwargs)


def get(url, **kwargs) -> httpx.Response:
    return _get_sync_client().get(url, **kwargs)


async def async_get(url, **kwargs) -> httpx.Response:
    return await _dispatch_async("get", url, **kwargs)


def patch(url, **kwargs) -> httpx.Response:
    return _get_sync_client().patch(url, **kwargs)


async def async_patch(url, **kwargs) -> httpx.Response:
    return await _dispatch_async("patch", url, **kwargs)


def delete(url, **kwargs) -> httpx.Response:
    return _get_sync_client().delete(url, **kwargs)


async def async_delete(url, **kwargs) -> httpx.Response:
    return await _dispatch_async("delete", url, **kwargs)


def request(method, url, **kwargs) -> httpx.Response:
    return _get_sync_client().request(method, url, **kwargs)


async def async_request(method, url, **kwargs) -> httpx.Response:
    return await _dispatch_async("request", method, url, **kwargs)


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
        # Drain active requests first so aclose doesn't cause read errors.
        await _drain_inflight(client)
        await client.aclose()
    # Nuke clients left behind by dead loops
    _sweep_dead_loops()
