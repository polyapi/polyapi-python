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


def _build_retries() -> int:
    # Retry connection-establishment failures.
    return _env_opt_int("POLY_HTTP_RETRIES", 1) or 0


# Import-time snapshot for reference/config surface. Clients re-read env at creation
DEFAULT_LIMITS = _build_limits()
DEFAULT_TIMEOUT = _build_timeout()
DEFAULT_RETRIES = _build_retries()
# PID that owns the clients below; a fork resets it
_owner_pid: int = os.getpid()
_sync_client: httpx.Client | None = None
# Guard lazy creation of _sync_client
_sync_client_lock = threading.Lock()
# One async client per event loop.
_async_clients: "dict[asyncio.AbstractEventLoop, httpx.AsyncClient]" = {}
# In-flight request count per async client, so close_async can drain before aclose.
_async_inflight: "dict[httpx.AsyncClient, int]" = {}
# Event loops whose close() already wrapped
_hooked_loops: "set[asyncio.AbstractEventLoop]" = set()
# Loops whose client is being closed by close_async; new requests wait on the Event so
# they don't race a replacement client into the pool mid-close.
_closing_loops: "dict[asyncio.AbstractEventLoop, asyncio.Event]" = {}


def _after_fork_in_child() -> None:
    """Reset all shared client state in a forked child
    """
    global _owner_pid, _sync_client, _sync_client_lock
    _sync_client_lock = threading.Lock()
    _sync_client = None
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
    global _owner_pid, _sync_client
    current_pid = os.getpid()
    if current_pid != _owner_pid:
        _sync_client = None
        _async_clients.clear()
        _async_inflight.clear()
        _hooked_loops.clear()
        _closing_loops.clear()
        _owner_pid = current_pid


def _get_sync_client() -> httpx.Client:
    global _sync_client
    _reset_if_forked()
    if _sync_client is None:
        # Double-checked lock
        with _sync_client_lock:
            if _sync_client is None:
                _sync_client = httpx.Client(limits=_build_limits(), timeout=_build_timeout())
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
        logger.debug(f"Could not hook loop.close pid={os.getpid()} loop={id(loop)}; relying on sweep")


def _get_async_client() -> httpx.AsyncClient:
    _reset_if_forked()
    current_loop = asyncio.get_running_loop()
    client = _async_clients.get(current_loop)
    if client is None:
        _sweep_dead_loops()
        limits = _build_limits()
        transport = httpx.AsyncHTTPTransport(limits=limits, retries=_build_retries())
        client = httpx.AsyncClient(transport=transport, timeout=_build_timeout())
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
    # If a shutdown is closing this loop's client, wait !
    # don't race a replacement into the pool mid-close.
    closing = _closing_loops.get(asyncio.get_running_loop())
    if closing is not None:
        await closing.wait()
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

    # If a close is already in progress for this loop, just wait for it.
    existing = _closing_loops.get(current_loop)
    if existing is not None:
        await existing.wait()
        return

    client = _async_clients.get(current_loop)
    if client is None:
        _sweep_dead_loops()
        return

    # Mark the loop as closing BEFORE draining so new requests block 
    done = asyncio.Event()
    _closing_loops[current_loop] = done
    try:
        await _drain_inflight(client)
        _async_clients.pop(current_loop, None)
        await client.aclose()
    finally:
        _closing_loops.pop(current_loop, None)
        done.set()  # release any requests that arrived during the close
    # Nuke clients left behind by dead loops
    _sweep_dead_loops()
