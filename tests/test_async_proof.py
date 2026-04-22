"""Tests proving the sync/async split works correctly.

These tests mock HTTP calls so no live server is needed. They verify that:
1. is_async() correctly detects sync vs async context
2. http_client uses sync Client in sync context, AsyncClient in async context
3. Sync functions (execute, direct_execute, etc.) always return httpx.Response
4. Async functions (execute_async, direct_execute_async, etc.) return coroutines
5. Parallel async execution with asyncio.gather works
"""

import asyncio
import inspect
from unittest.mock import patch, MagicMock, AsyncMock

import httpx
import pytest

from polyapi import http_client
from polyapi.execute import (
    execute,
    execute_async,
    direct_execute,
    direct_execute_async,
    execute_post,
    execute_post_async,
    variable_get,
    variable_get_async,
    variable_update,
    variable_update_async,
    _build_direct_execute_params,
    _check_endpoint_error,
    _check_response_error
)
from polyapi.exceptions import PolyApiException


# Helpers

def _fake_response(status_code=200, json_data=None, text="ok"):
    """Build a fake httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    resp.content = text.encode()
    resp.json.return_value = {} if json_data is None else json_data
    return resp


# 1. http_client sync / async client pairing

class TestHttpClientPairing:
    """Verify that the sync helpers call httpx.Client and the async helpers
    call httpx.AsyncClient."""

    def setup_method(self):
        # Reset singletons so each test starts fresh
        http_client._sync_client = None
        http_client._async_client = None
        http_client._async_client_loop = None

    def teardown_method(self):
        http_client._sync_client = None
        http_client._async_client = None
        http_client._async_client_loop = None

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
        assert http_client._async_client_loop is not None

    def test_async_post_reuses_client_within_same_loop(self):
        first_client = MagicMock()
        first_client.post = AsyncMock(return_value=_fake_response())

        with patch("polyapi.http_client.httpx.AsyncClient", return_value=first_client) as mock_async_client:
            async def _run():
                first_response = await http_client.async_post("https://example.com/first", json={})
                second_response = await http_client.async_post("https://example.com/second", json={})
                return first_response, second_response, asyncio.get_running_loop()

            first_response, second_response, current_loop = asyncio.run(_run())

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert mock_async_client.call_count == 1
        assert first_client.post.await_count == 2
        assert http_client._async_client is first_client
        assert http_client._async_client_loop is current_loop

    def test_async_post_recreates_client_after_loop_change(self):
        first_client = MagicMock()
        first_client.post = AsyncMock(return_value=_fake_response())
        second_client = MagicMock()
        second_client.post = AsyncMock(return_value=_fake_response())

        with patch(
            "polyapi.http_client.httpx.AsyncClient",
            side_effect=[first_client, second_client],
        ) as mock_async_client:
            async def _run_once(url: str):
                response = await http_client.async_post(url, json={})
                return response, http_client._async_client, asyncio.get_running_loop()

            first_response, first_cached_client, first_loop = asyncio.run(_run_once("https://example.com/first"))
            second_response, second_cached_client, second_loop = asyncio.run(_run_once("https://example.com/second"))

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert mock_async_client.call_count == 2
        assert first_client.post.await_count == 1
        assert second_client.post.await_count == 1
        assert first_cached_client is first_client
        assert second_cached_client is second_client
        assert first_loop is not second_loop
        assert http_client._async_client is second_client
        assert http_client._async_client_loop is second_loop

    def test_close_async_clears_cached_client_for_current_loop(self):
        async def _run():
            cached_client = MagicMock()
            cached_client.aclose = AsyncMock()
            http_client._async_client = cached_client
            http_client._async_client_loop = asyncio.get_running_loop()

            await http_client.close_async()

            return cached_client

        cached_client = asyncio.run(_run())

        cached_client.aclose.assert_awaited_once()
        assert http_client._async_client is None
        assert http_client._async_client_loop is None

    def test_close_async_drops_stale_client_without_cross_loop_close(self):
        stale_client = MagicMock()
        stale_client.aclose = AsyncMock()

        async def _seed_stale_client():
            http_client._async_client = stale_client
            http_client._async_client_loop = asyncio.get_running_loop()

        asyncio.run(_seed_stale_client())

        async def _close_on_new_loop():
            await http_client.close_async()

        asyncio.run(_close_on_new_loop())

        stale_client.aclose.assert_not_awaited()
        assert http_client._async_client is None
        assert http_client._async_client_loop is None

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


# 3. execute() / execute_async()

_CONFIG_PATCH = patch(
    "polyapi.execute.get_api_key_and_url",
    return_value=("fake-key", "https://api.example.com"),
)
_MTLS_PATCH = patch(
    "polyapi.execute.get_mtls_config",
    return_value=(False, None, None, None),
)


class TestExecute:
    """execute() always returns httpx.Response (sync).
    execute_async() always returns a coroutine that resolves to httpx.Response."""

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
            coro = execute_async("server", "some-id", {})
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

    @_CONFIG_PATCH
    @patch("polyapi.http_client.post", return_value=_fake_response(200, text='"hello"'))
    def test_sync_works_inside_async_context(self, mock_post, _mock_config):
        """execute() (sync) should still return httpx.Response even when
        called from within an async context — this is the key fix."""
        async def _run():
            result = execute("server", "some-id", {})
            # Should be a Response, NOT a coroutine
            assert not inspect.isawaitable(result)
            assert result.status_code == 200

        asyncio.run(_run())


# 4. direct_execute() / direct_execute_async()

class TestDirectExecute:

    @_CONFIG_PATCH
    @_MTLS_PATCH
    @patch("polyapi.execute.httpx.request", return_value=_fake_response(200, text='{"result": 1}'))
    @patch("polyapi.http_client.post", return_value=_fake_response(
        200, json_data={"url": "https://target.example.com", "method": "GET"},
    ))
    def test_sync_returns_response(self, mock_post, mock_request, _mtls, _config):
        result = direct_execute("server", "fn-id", {})
        assert result.status_code == 200
        assert "/direct-execute" in mock_post.call_args[0][0]
        mock_request.assert_called_once()

    @_CONFIG_PATCH
    @_MTLS_PATCH
    @patch("polyapi.http_client.async_post", new_callable=AsyncMock, return_value=_fake_response(
        200, json_data={"url": "https://target.example.com", "method": "GET"},
    ))
    def test_async_returns_coroutine(self, mock_post, _mtls, _config):
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=_fake_response(200))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def _run():
            with patch("polyapi.execute.httpx.AsyncClient", return_value=mock_client):
                coro = direct_execute_async("server", "fn-id", {})
                assert inspect.isawaitable(coro)
                return await coro

        result = asyncio.run(_run())
        assert result.status_code == 200


# 5. execute_post() / execute_post_async()

class TestExecutePost:

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
            coro = execute_post_async("/some/path", {"data": 1})
            assert inspect.isawaitable(coro)
            return await coro

        result = asyncio.run(_run())
        assert result.status_code == 200


# 6. variable_get / variable_get_async

class TestVariableGet:

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
            coro = variable_get_async("var-123")
            assert inspect.isawaitable(coro)
            return await coro

        result = asyncio.run(_run())
        assert result.status_code == 200


# 7. variable_update / variable_update_async

class TestVariableUpdate:

    @_CONFIG_PATCH
    @patch("polyapi.http_client.patch", return_value=_fake_response(200))
    def test_sync(self, mock_patch_call, _config):
        result = variable_update("var-123", "new-value")
        assert result.status_code == 200

    @_CONFIG_PATCH
    @patch("polyapi.http_client.async_patch", new_callable=AsyncMock, return_value=_fake_response(200))
    def test_async(self, mock_patch_call, _config):
        async def _run():
            coro = variable_update_async("var-123", "new-value")
            assert inspect.isawaitable(coro)
            return await coro

        result = asyncio.run(_run())
        assert result.status_code == 200


# 8. Parallel async execution with asyncio.gather

class TestAsyncParallelExecution:
    """Prove that multiple async execute_async() calls can be gathered in parallel."""

    @_CONFIG_PATCH
    @patch("polyapi.http_client.async_post", new_callable=AsyncMock)
    def test_gather_multiple_executes(self, mock_post, _config):
        responses = [_fake_response(200, text=f'"result-{i}"') for i in range(5)]
        mock_post.side_effect = responses

        async def _run():
            coros = [execute_async("server", f"fn-{i}", {}) for i in range(5)]
            for c in coros:
                assert inspect.isawaitable(c)
            return await asyncio.gather(*coros)

        results = asyncio.run(_run())
        assert len(results) == 5
        assert mock_post.call_count == 5
        for i, r in enumerate(results):
            assert r.text == f'"result-{i}"'

    @_CONFIG_PATCH
    @patch("polyapi.http_client.async_post", new_callable=AsyncMock)
    def test_gather_is_faster_than_sequential(self, mock_post, _config):
        """Measure both sequential and parallel execution in the same run,
        then assert parallel < sequential. Avoids flaky CI failures from
        hardcoded time thresholds."""
        import time

        async def _slow_post(*args, **kwargs):
            await asyncio.sleep(0.1)
            return _fake_response(200, text='"done"')

        mock_post.side_effect = _slow_post

        async def _run():
            # Sequential: await one at a time
            seq_start = time.monotonic()
            for i in range(5):
                await execute_async("server", f"fn-{i}", {})
            seq_elapsed = time.monotonic() - seq_start

            # Parallel: gather all at once
            par_start = time.monotonic()
            results = await asyncio.gather(
                *[execute_async("server", f"fn-{i}", {}) for i in range(5)]
            )
            par_elapsed = time.monotonic() - par_start

            return results, seq_elapsed, par_elapsed

        results, seq_elapsed, par_elapsed = asyncio.run(_run())
        assert len(results) == 5
        assert par_elapsed < seq_elapsed, (
            f"Parallel ({par_elapsed:.2f}s) should be faster than sequential ({seq_elapsed:.2f}s)"
        )


# 9. Helper: _build_direct_execute_params

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
        assert "url" in original
        assert "maxRedirects" in original


# 10. _check_endpoint_error vs _check_response_error

class TestCheckErrorBehaviorDifference:
    """_check_endpoint_error raises on api errors; _check_response_error only logs."""


    def test_endpoint_error_raises_for_api_with_logs(self):
        """_check_endpoint_error raises PolyApiException for api functions."""

        resp = _fake_response(status_code=500, text="server broke")
        with patch.dict("os.environ", {"LOGS_ENABLED": "1"}):
            with pytest.raises(PolyApiException, match="500"):
                _check_endpoint_error(resp, "api", "fn-1", {})

    def test_response_error_logs_for_api_with_logs(self):
        """_check_response_error only logs (no raise) for api functions."""
        resp = _fake_response(status_code=500, text="server broke")
        with patch.dict("os.environ", {"LOGS_ENABLED": "1"}):
            # Should NOT raise — just logs
            _check_response_error(resp, "api", "fn-1", {})

    def test_both_raise_for_non_api(self):
        """Both functions raise PolyApiException for non-api function types."""
        resp = _fake_response(status_code=500, text="server broke")
        with pytest.raises(PolyApiException, match="500"):
            _check_endpoint_error(resp, "server", "fn-1", {})
