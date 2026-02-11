"""Tests proving the sync/async dual-mode pattern works correctly.

These tests mock HTTP calls so no live server is needed. They verify that:
1. is_async() correctly detects sync vs async context
2. http_client uses sync Client in sync context, AsyncClient in async context
3. execute(), direct_execute(), execute_post(), variable_get(), variable_update()
   all return the right type based on calling context
4. Parallel async execution with asyncio.gather works
"""

import asyncio
import inspect
from collections.abc import Coroutine
from unittest.mock import patch, MagicMock, AsyncMock

import httpx
import pytest

from polyapi import http_client
from polyapi.execute import (
    execute,
    direct_execute,
    execute_post,
    variable_get,
    variable_update,
    _build_direct_execute_params,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_response(status_code=200, json_data=None, text="ok"):
    """Build a fake httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    resp.content = text.encode()
    resp.json.return_value = json_data or {}
    return resp


# 1. is_async() detection

class TestIsAsync:
    def test_sync_context_returns_false(self):
        assert http_client.is_async() is False

    def test_async_context_returns_true(self):
        async def _check():
            return http_client.is_async()

        result = asyncio.run(_check())
        assert result is True

    def test_nested_sync_inside_async_still_true(self):
        """A plain (non-async) helper called from within an event loop
        should still report True because the loop is running."""

        def sync_helper():
            return http_client.is_async()

        async def _check():
            return sync_helper()

        assert asyncio.run(_check()) is True


# 2. http_client sync / async client pairing

class TestHttpClientPairing:
    """Verify that the sync helpers call httpx.Client and the async helpers
    call httpx.AsyncClient."""

    def setup_method(self):
        # Reset singletons so each test starts fresh
        http_client._sync_client = None
        http_client._async_client = None

    def teardown_method(self):
        http_client._sync_client = None
        http_client._async_client = None

    @patch.object(httpx.Client, "post", return_value=_fake_response())
    def test_sync_post_uses_sync_client(self, mock_post):
        resp = http_client.post("https://example.com", json={})
        mock_post.assert_called_once()
        assert resp.status_code == 200
        # The sync client should have been created
        assert http_client._sync_client is not None
        assert http_client._async_client is None

    @patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_fake_response())
    def test_async_post_uses_async_client(self, mock_post):
        async def _run():
            return await http_client.async_post("https://example.com", json={})

        resp = asyncio.run(_run())
        mock_post.assert_called_once()
        assert resp.status_code == 200
        assert http_client._async_client is not None

    @patch.object(httpx.Client, "get", return_value=_fake_response())
    def test_sync_get(self, mock_get):
        resp = http_client.get("https://example.com")
        mock_get.assert_called_once()
        assert resp.status_code == 200

    @patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=_fake_response())
    def test_async_get(self, mock_get):
        async def _run():
            return await http_client.async_get("https://example.com")

        resp = asyncio.run(_run())
        mock_get.assert_called_once()
        assert resp.status_code == 200

    @patch.object(httpx.Client, "patch", return_value=_fake_response())
    def test_sync_patch(self, mock_patch_method):
        resp = http_client.patch("https://example.com", data={"v": 1})
        mock_patch_method.assert_called_once()
        assert resp.status_code == 200

    @patch.object(httpx.AsyncClient, "patch", new_callable=AsyncMock, return_value=_fake_response())
    def test_async_patch(self, mock_patch_method):
        async def _run():
            return await http_client.async_patch("https://example.com", data={"v": 1})

        resp = asyncio.run(_run())
        mock_patch_method.assert_called_once()

    @patch.object(httpx.Client, "delete", return_value=_fake_response())
    def test_sync_delete(self, mock_delete):
        resp = http_client.delete("https://example.com")
        mock_delete.assert_called_once()

    @patch.object(httpx.AsyncClient, "delete", new_callable=AsyncMock, return_value=_fake_response())
    def test_async_delete(self, mock_delete):
        async def _run():
            return await http_client.async_delete("https://example.com")

        resp = asyncio.run(_run())
        mock_delete.assert_called_once()

    @patch.object(httpx.Client, "request", return_value=_fake_response())
    def test_sync_request(self, mock_request):
        resp = http_client.request("POST", "https://example.com")
        mock_request.assert_called_once()

    @patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=_fake_response())
    def test_async_request(self, mock_request):
        async def _run():
            return await http_client.async_request("POST", "https://example.com")

        resp = asyncio.run(_run())
        mock_request.assert_called_once()


# 3. execute() dual-mode

_CONFIG_PATCH = patch(
    "polyapi.execute.get_api_key_and_url",
    return_value=("fake-key", "https://api.example.com"),
)
_MTLS_PATCH = patch(
    "polyapi.execute.get_mtls_config",
    return_value=(False, None, None, None),
)


class TestExecuteDualMode:
    """execute() returns httpx.Response in sync context, coroutine in async."""

    @_CONFIG_PATCH
    @patch("polyapi.http_client.post", return_value=_fake_response(200, text='"hello"'))
    def test_sync_returns_response(self, mock_post, _mock_config):
        result = execute("server", "some-id", {})
        assert isinstance(result, MagicMock)  # our fake Response
        assert result.status_code == 200
        mock_post.assert_called_once()

    @_CONFIG_PATCH
    @patch("polyapi.http_client.async_post", new_callable=AsyncMock, return_value=_fake_response(200, text='"hello"'))
    def test_async_returns_coroutine_then_response(self, mock_post, _mock_config):
        async def _run():
            coro = execute("server", "some-id", {})
            # In async context, execute() returns a coroutine
            assert inspect.isawaitable(coro)
            return await coro

        result = asyncio.run(_run())
        assert result.status_code == 200
        mock_post.assert_called_once()

    @_CONFIG_PATCH
    @patch("polyapi.http_client.post", return_value=_fake_response(200, text='"hello"'))
    def test_sync_calls_correct_url(self, mock_post, _mock_config):
        execute("server", "abc-123", {"arg": 1})
        call_args = mock_post.call_args
        assert "/functions/server/abc-123/execute" in call_args[0][0]
        assert call_args[1]["json"] == {"arg": 1}
        assert "Bearer fake-key" in call_args[1]["headers"]["Authorization"]


# 4. direct_execute() dual-mode

class TestDirectExecuteDualMode:

    @_CONFIG_PATCH
    @_MTLS_PATCH
    @patch("polyapi.http_client.request", return_value=_fake_response(200, text='{"result": 1}'))
    @patch("polyapi.http_client.post", return_value=_fake_response(
        200, json_data={"url": "https://target.example.com", "method": "GET"},
    ))
    def test_sync_returns_response(self, mock_post, mock_request, _mtls, _config):
        result = direct_execute("server", "fn-id", {})
        assert result.status_code == 200
        # First call: POST to /direct-execute endpoint info
        assert "/direct-execute" in mock_post.call_args[0][0]
        # Second call: actual request to the target URL
        mock_request.assert_called_once()

    @_CONFIG_PATCH
    @_MTLS_PATCH
    @patch("polyapi.http_client.async_request", new_callable=AsyncMock, return_value=_fake_response(200))
    @patch("polyapi.http_client.async_post", new_callable=AsyncMock, return_value=_fake_response(
        200, json_data={"url": "https://target.example.com", "method": "GET"},
    ))
    def test_async_returns_coroutine(self, mock_post, mock_request, _mtls, _config):
        async def _run():
            coro = direct_execute("server", "fn-id", {})
            assert inspect.isawaitable(coro)
            return await coro

        result = asyncio.run(_run())
        assert result.status_code == 200


# 5. execute_post() dual-mode

class TestExecutePostDualMode:

    @_CONFIG_PATCH
    @patch("polyapi.http_client.post", return_value=_fake_response())
    def test_sync(self, mock_post, _config):
        result = execute_post("/some/path", {"data": 1})
        assert result.status_code == 200
        assert "https://api.example.com/some/path" == mock_post.call_args[0][0]

    @_CONFIG_PATCH
    @patch("polyapi.http_client.async_post", new_callable=AsyncMock, return_value=_fake_response())
    def test_async(self, mock_post, _config):
        async def _run():
            coro = execute_post("/some/path", {"data": 1})
            assert inspect.isawaitable(coro)
            return await coro

        result = asyncio.run(_run())
        assert result.status_code == 200


# 6. variable_get / variable_update dual-mode

class TestVariableGetDualMode:

    @_CONFIG_PATCH
    @patch("polyapi.http_client.get", return_value=_fake_response(200, text="42"))
    def test_sync(self, mock_get, _config):
        result = variable_get("var-123")
        assert result.status_code == 200
        assert "/variables/var-123/value" in mock_get.call_args[0][0]

    @_CONFIG_PATCH
    @patch("polyapi.http_client.async_get", new_callable=AsyncMock, return_value=_fake_response(200, text="42"))
    def test_async(self, mock_get, _config):
        async def _run():
            coro = variable_get("var-123")
            assert inspect.isawaitable(coro)
            return await coro

        result = asyncio.run(_run())
        assert result.status_code == 200


class TestVariableUpdateDualMode:

    @_CONFIG_PATCH
    @patch("polyapi.http_client.patch", return_value=_fake_response(200))
    def test_sync(self, mock_patch_call, _config):
        result = variable_update("var-123", "new-value")
        assert result.status_code == 200

    @_CONFIG_PATCH
    @patch("polyapi.http_client.async_patch", new_callable=AsyncMock, return_value=_fake_response(200))
    def test_async(self, mock_patch_call, _config):
        async def _run():
            coro = variable_update("var-123", "new-value")
            assert inspect.isawaitable(coro)
            return await coro

        result = asyncio.run(_run())
        assert result.status_code == 200


# 7. Parallel async execution with asyncio.gather

class TestAsyncParallelExecution:
    """Prove that multiple async execute() calls can be gathered in parallel."""

    @_CONFIG_PATCH
    @patch("polyapi.http_client.async_post", new_callable=AsyncMock)
    def test_gather_multiple_executes(self, mock_post, _config):
        # Each call returns a distinct response
        responses = [_fake_response(200, text=f'"result-{i}"') for i in range(5)]
        mock_post.side_effect = responses

        async def _run():
            coros = [execute("server", f"fn-{i}", {}) for i in range(5)]
            # All should be awaitables in async context
            for c in coros:
                assert inspect.isawaitable(c)
            return await asyncio.gather(*coros)

        results = asyncio.run(_run())
        assert len(results) == 5
        assert mock_post.call_count == 5
        # Verify each got a distinct response
        for i, r in enumerate(results):
            assert r.text == f'"result-{i}"'

    @_CONFIG_PATCH
    @patch("polyapi.http_client.async_post", new_callable=AsyncMock)
    def test_gather_is_faster_than_sequential(self, mock_post, _config):
        """Simulate latency: each call sleeps 0.1s. Gathering 5 should take
        ~0.1s total (parallel) rather than ~0.5s (sequential)."""
        import time

        async def _slow_post(*args, **kwargs):
            await asyncio.sleep(0.1)
            return _fake_response(200, text='"done"')

        mock_post.side_effect = _slow_post

        async def _run():
            start = time.monotonic()
            coros = [execute("server", f"fn-{i}", {}) for i in range(5)]
            results = await asyncio.gather(*coros)
            elapsed = time.monotonic() - start
            return results, elapsed

        results, elapsed = asyncio.run(_run())
        assert len(results) == 5
        # Parallel should finish well under 0.5s (sequential would be ~0.5s)
        assert elapsed < 0.3, f"Parallel gather took {elapsed:.2f}s — expected < 0.3s"


# 8. Helper: _build_direct_execute_params

class TestBuildDirectExecuteParams:
    def test_strips_url(self):
        params = _build_direct_execute_params({"url": "https://x.com", "method": "GET"})
        assert "url" not in params
        assert params["method"] == "GET"

    def test_converts_max_redirects_positive(self):
        params = _build_direct_execute_params({"url": "u", "maxRedirects": 5})
        assert "maxRedirects" not in params
        assert params["follow_redirects"] is True

    def test_converts_max_redirects_zero(self):
        params = _build_direct_execute_params({"url": "u", "maxRedirects": 0})
        assert params["follow_redirects"] is False

    def test_no_mutation_of_input(self):
        original = {"url": "u", "method": "POST", "maxRedirects": 3}
        _build_direct_execute_params(original)
        # Original dict should be unchanged
        assert "url" in original
        assert "maxRedirects" in original
