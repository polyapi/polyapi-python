import asyncio
import logging
import os
import threading
import httpx

logger = logging.getLogger("poly")

# Connx pool + timeout defaults for the shared clients.
# All overridable via POLY_HTTP_* env vars so operators can tune limits or
# opt into timeouts without editing callers. Empty / "none" parses to None (unbounded).


def _env_opt_int(name: str, default: "int | None") -> "int | None":
    raw = os.environ.get(name)
    if raw is None:
        return default
    raw = raw.strip()
    return None if raw == "" or raw.lower() in ("none", "null") else int(raw)


def _env_opt_float(name: str, default: "float | None") -> "float | None":
    raw = os.environ.get(name)
    if raw is None:
        return default
    raw = raw.strip()
    return None if raw == "" or raw.lower() in ("none", "null") else float(raw)


def _build_limits() -> httpx.Limits:
    return httpx.Limits(
        max_connections=_env_opt_int("POLY_HTTP_MAX_CONNECTIONS", 200),
        max_keepalive_connections=_env_opt_int("POLY_HTTP_MAX_KEEPALIVE_CONNECTIONS", None),
        keepalive_expiry=_env_opt_float("POLY_HTTP_KEEPALIVE_EXPIRY", 30.0),
    )


def _build_timeout() -> httpx.Timeout:
    # Default to the SDK's original unbounded timeout; bound per-phase only via env.
    return httpx.Timeout(
        connect=_env_opt_float("POLY_HTTP_CONNECT_TIMEOUT", None),
        read=_env_opt_float("POLY_HTTP_READ_TIMEOUT", None),
        write=_env_opt_float("POLY_HTTP_WRITE_TIMEOUT", None),
        pool=_env_opt_float("POLY_HTTP_POOL_TIMEOUT", None),
    )


# Import-time snapshot for reference/config surface. Clients re-read env at creation
DEFAULT_LIMITS = _build_limits()
DEFAULT_TIMEOUT = _build_timeout()
# PID that owns the clients below; a fork resets it
_owner_pid: int = os.getpid()
_sync_client: httpx.Client | None = None
# Coordinate lazy creation, active requests, and shutdown of _sync_client.
_sync_client_lock = threading.Lock()
_sync_client_condition = threading.Condition(_sync_client_lock)
_sync_inflight = 0
_sync_closing = False
# One async client per event loop.
_async_clients: "dict[asyncio.AbstractEventLoop, httpx.AsyncClient]" = {}
# In-flight request count per async client, so close_async can drain before aclose.
_async_inflight: "dict[httpx.AsyncClient, int]" = {}
# Event loops whose close() already wrapped
_hooked_loops: "set[asyncio.AbstractEventLoop]" = set()
# Shared close operation per event loop. New requests wait for it so they do not
# race a replacement client into the pool mid-close.
_closing_loops: "dict[asyncio.AbstractEventLoop, asyncio.Task[None]]" = {}


def _after_fork_in_child() -> None:
    """Reset all shared client state in a forked child
    """
    global _owner_pid, _sync_client, _sync_client_lock, _sync_client_condition
    global _sync_inflight, _sync_closing
    _sync_client_lock = threading.Lock()
    _sync_client_condition = threading.Condition(_sync_client_lock)
    _sync_client = None
    _sync_inflight = 0
    _sync_closing = False
    _async_clients.clear()
    _async_inflight.clear()
    _hooked_loops.clear()
    _closing_loops.clear()
    _owner_pid = os.getpid()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_after_fork_in_child)


def _reset_if_forked() -> None:
    """Drop clients inherited across os.fork() so childisolated
    Clear not close the inherited refs - child makes its own."""
    global _owner_pid, _sync_client, _sync_client_lock, _sync_client_condition
    global _sync_inflight, _sync_closing
    current_pid = os.getpid()
    if current_pid != _owner_pid:
        _sync_client_lock = threading.Lock()
        _sync_client_condition = threading.Condition(_sync_client_lock)
        _sync_client = None
        _sync_inflight = 0
        _sync_closing = False
        _async_clients.clear()
        _async_inflight.clear()
        _hooked_loops.clear()
        _closing_loops.clear()
        _owner_pid = current_pid


def _get_or_create_sync_client() -> httpx.Client:
    global _sync_client
    if _sync_client is None:
        _sync_client = httpx.Client(limits=_build_limits(), timeout=_build_timeout())
    return _sync_client


def _get_sync_client() -> httpx.Client:
    _reset_if_forked()
    with _sync_client_condition:
        while _sync_closing:
            _sync_client_condition.wait()
        return _get_or_create_sync_client()


def _dispatch_sync(method_name: str, *args, **kwargs) -> httpx.Response:
    global _sync_inflight
    _reset_if_forked()
    with _sync_client_condition:
        while _sync_closing:
            _sync_client_condition.wait()
        client = _get_or_create_sync_client()
        _sync_inflight += 1
    try:
        return getattr(client, method_name)(*args, **kwargs)
    finally:
        with _sync_client_condition:
            _sync_inflight -= 1
            if _sync_inflight == 0:
                _sync_client_condition.notify_all()


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


def _register_loop_close_hook(loop: asyncio.AbstractEventLoop) -> None:
    """aclose the loop's async client right before the loop is torn down.
    """
    if loop in _hooked_loops:
        return
    original_close = loop.close

    def _close_with_cleanup(*args, **kwargs):
        _hooked_loops.discard(loop)
        cached = _async_clients.pop(loop, None)
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
        _hooked_loops.add(loop)
    except (AttributeError, TypeError):
        logger.warning(
            f"Could not hook loop.close pid={os.getpid()} loop={id(loop)}; "
            "await close_async() before closing this event loop"
        )


def _get_async_client() -> httpx.AsyncClient:
    _reset_if_forked()
    current_loop = asyncio.get_running_loop()
    client = _async_clients.get(current_loop)
    if client is None:
        _sweep_dead_loops()
        limits = _build_limits()
        client = httpx.AsyncClient(limits=limits, timeout=_build_timeout())
        _async_clients[current_loop] = client
        _register_loop_close_hook(current_loop)
        logger.debug(
            f"Created async client id={id(client)} pid={os.getpid()} loop={id(current_loop)} "
            f"max_connections={limits.max_connections} "
            f"max_keepalive={limits.max_keepalive_connections} "
            f"keepalive_expiry={limits.keepalive_expiry}"
        )
    return client


async def _dispatch_async(method_name: str, *args, **kwargs) -> httpx.Response:
    # If a shutdown is closing this loop's client, wait so a replacement is not
    # published mid-close. The shutdown caller owns any close error.
    closing = _closing_loops.get(asyncio.get_running_loop())
    if closing is not None:
        try:
            await asyncio.shield(closing)
        except Exception:
            pass
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


async def _drain_inflight(client: httpx.AsyncClient) -> None:
    # Preserve the SDK's unbounded request behavior during shutdown. The shared
    # close operation retains ownership until every active request finishes.
    while _async_inflight.get(client, 0) > 0:
        await asyncio.sleep(0.05)


async def _wait_for_close_task(close_task: "asyncio.Task[None]") -> None:
    """Wait for shared cleanup before propagating caller cancellation."""
    caller_cancelled = False
    while not close_task.done():
        try:
            await asyncio.shield(close_task)
        except asyncio.CancelledError:
            caller_cancelled = True
    close_task.result()
    if caller_cancelled:
        raise asyncio.CancelledError()


async def _close_clients_for_loop(
    current_loop: asyncio.AbstractEventLoop,
) -> None:
    """Close shared clients while retaining ownership through completion."""
    try:
        await asyncio.to_thread(close)
        client = _async_clients.get(current_loop)
        if client is None:
            return

        await _drain_inflight(client)
        try:
            await client.aclose()
        finally:
            if _async_clients.get(current_loop) is client:
                _async_clients.pop(current_loop, None)
            _async_inflight.pop(client, None)
    finally:
        if _closing_loops.get(current_loop) is asyncio.current_task():
            _closing_loops.pop(current_loop, None)
        _sweep_dead_loops()


def post(url, **kwargs) -> httpx.Response:
    return _dispatch_sync("post", url, **kwargs)


async def async_post(url, **kwargs) -> httpx.Response:
    return await _dispatch_async("post", url, **kwargs)


def get(url, **kwargs) -> httpx.Response:
    return _dispatch_sync("get", url, **kwargs)


async def async_get(url, **kwargs) -> httpx.Response:
    return await _dispatch_async("get", url, **kwargs)


def patch(url, **kwargs) -> httpx.Response:
    return _dispatch_sync("patch", url, **kwargs)


async def async_patch(url, **kwargs) -> httpx.Response:
    return await _dispatch_async("patch", url, **kwargs)


def delete(url, **kwargs) -> httpx.Response:
    return _dispatch_sync("delete", url, **kwargs)


async def async_delete(url, **kwargs) -> httpx.Response:
    return await _dispatch_async("delete", url, **kwargs)


def request(method, url, **kwargs) -> httpx.Response:
    return _dispatch_sync("request", method, url, **kwargs)


async def async_request(method, url, **kwargs) -> httpx.Response:
    return await _dispatch_async("request", method, url, **kwargs)


def close():
    global _sync_client, _sync_closing
    _reset_if_forked()
    with _sync_client_condition:
        while _sync_closing:
            _sync_client_condition.wait()
        if _sync_client is None:
            return
        _sync_closing = True
        while _sync_inflight > 0:
            _sync_client_condition.wait()
        client = _sync_client
    try:
        client.close()
    finally:
        with _sync_client_condition:
            if _sync_client is client:
                _sync_client = None
            _sync_closing = False
            _sync_client_condition.notify_all()


async def close_async():
    current_loop = asyncio.get_running_loop()
    close_task = _closing_loops.get(current_loop)
    if close_task is None:
        close_task = asyncio.create_task(_close_clients_for_loop(current_loop))
        _closing_loops[current_loop] = close_task
    await _wait_for_close_task(close_task)
