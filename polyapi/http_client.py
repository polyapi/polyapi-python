import asyncio
import httpx

_sync_client: httpx.Client | None = None
_async_client: httpx.AsyncClient | None = None
_async_client_loop: asyncio.AbstractEventLoop | None = None


def _get_sync_client() -> httpx.Client:
    global _sync_client
    if _sync_client is None:
        _sync_client = httpx.Client(timeout=None)
    return _sync_client


def _get_async_client() -> httpx.AsyncClient:
    global _async_client, _async_client_loop
    current_loop = asyncio.get_running_loop()
    if _async_client is None or _async_client_loop is not current_loop:
        _async_client = httpx.AsyncClient(timeout=None)
        _async_client_loop = current_loop
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
    global _sync_client, _async_client, _async_client_loop
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
