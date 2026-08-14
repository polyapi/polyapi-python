"""Tests proving the sync/async split works correctly.

These tests mock HTTP calls so no live server is needed. They verify that:
1. is_async() correctly detects sync vs async context
2. http_client uses sync Client in sync context, AsyncClient in async context
3. Sync functions (execute, direct_execute, etc.) always return httpx.Response
4. Async functions (execute_async, direct_execute_async, etc.) return coroutines
5. Parallel async execution with asyncio.gather works
"""

import asyncio
import gc
from http.server import BaseHTTPRequestHandler, HTTPServer
import inspect
import json
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import unittest
import warnings
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


_LIFECYCLE_TIMEOUT_SECONDS = 2
_REAL_RESOURCE_SOAK_CYCLES = 8
_REAL_RESOURCE_SOAK_TIMEOUT_SECONDS = 20


def _is_unbounded_timeout(value):
    if value is None:
        return True
    if not isinstance(value, httpx.Timeout):
        return False
    return all(
        getattr(value, component, object()) is None
        for component in ("connect", "read", "write", "pool")
    )


class _LifecycleLoopbackHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def log_message(self, _format, *_args):
        pass


class _LifecycleLoopbackServer(HTTPServer):
    def __init__(self, server_address):
        self._completed_condition = threading.Condition()
        self.completed_requests = 0
        super().__init__(server_address, _LifecycleLoopbackHandler)

    def shutdown_request(self, request):
        try:
            super().shutdown_request(request)
        finally:
            with self._completed_condition:
                self.completed_requests += 1
                self._completed_condition.notify_all()

    def wait_for_completed_requests(self, expected, timeout):
        with self._completed_condition:
            return self._completed_condition.wait_for(
                lambda: self.completed_requests >= expected,
                timeout=timeout,
            )


def _select_open_fd_directory():
    for candidate in ("/proc/self/fd", "/dev/fd"):
        try:
            entries = os.listdir(candidate)
        except OSError:
            continue
        if entries and all(entry.isdigit() for entry in entries):
            return candidate
    raise RuntimeError("open file descriptor measurement is unavailable")


def _count_open_fds(fd_directory):
    entries = os.listdir(fd_directory)
    if not entries or not all(entry.isdigit() for entry in entries):
        raise RuntimeError("open file descriptor measurement is malformed")
    return len(entries)


def _calibrate_open_fd_counter(fd_directory):
    before = _count_open_fds(fd_directory)
    read_fd = None
    write_fd = None
    try:
        read_fd, write_fd = os.pipe()
        during = _count_open_fds(fd_directory)
    finally:
        if read_fd is not None:
            os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)
    after = _count_open_fds(fd_directory)
    if during != before + 2 or after != before:
        raise RuntimeError("open file descriptor measurement is unstable")


def _run_real_async_cycle(url):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def exercise():
        try:
            response = await http_client.async_get(url)
            if response.status_code != 200 or response.text != "ok":
                raise AssertionError("loopback response contract failed")
        finally:
            await http_client.close_async()

    try:
        loop.run_until_complete(
            asyncio.wait_for(
                exercise(),
                timeout=_LIFECYCLE_TIMEOUT_SECONDS,
            )
        )
        return len(
            [task for task in asyncio.all_tasks(loop) if not task.done()]
        )
    finally:
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())
        loop.close()
        asyncio.set_event_loop(None)


def _lifecycle_resource_snapshot(fd_directory, pending_tasks):
    return {
        "open_fds": _count_open_fds(fd_directory),
        "live_threads": len(threading.enumerate()),
        "pending_tasks": pending_tasks,
        "retained_async_clients": len(http_client._async_clients),
        "retained_inflight_entries": len(http_client._async_inflight),
    }


def _run_real_resource_soak():
    fd_directory = _select_open_fd_directory()
    _calibrate_open_fd_counter(fd_directory)

    server = _LifecycleLoopbackServer(("127.0.0.1", 0))
    server_ready = threading.Event()
    server_stopped = threading.Event()
    server_errors = []

    def serve():
        server_ready.set()
        try:
            server.serve_forever(poll_interval=0.05)
        except BaseException as error:
            server_errors.append(type(error).__name__)
        finally:
            server_stopped.set()

    server_thread = threading.Thread(
        target=serve,
        name="pr131-loopback-server",
    )
    server_thread.start()
    baseline = None
    measurements = []

    try:
        if not server_ready.wait(_LIFECYCLE_TIMEOUT_SECONDS):
            raise TimeoutError("loopback server did not become ready")
        port = server.server_address[1]
        url = f"http://127.0.0.1:{port}/health"

        with patch.dict(http_client.os.environ, {}, clear=True):
            warm_pending = _run_real_async_cycle(url)
            if not server.wait_for_completed_requests(
                1,
                _LIFECYCLE_TIMEOUT_SECONDS,
            ):
                raise TimeoutError("loopback warmup did not complete")
            gc.collect()
            baseline = _lifecycle_resource_snapshot(
                fd_directory,
                warm_pending,
            )

            for cycle in range(_REAL_RESOURCE_SOAK_CYCLES):
                pending_tasks = _run_real_async_cycle(url)
                if not server.wait_for_completed_requests(
                    cycle + 2,
                    _LIFECYCLE_TIMEOUT_SECONDS,
                ):
                    raise TimeoutError("loopback cycle did not complete")
                gc.collect()
                measurements.append(
                    _lifecycle_resource_snapshot(
                        fd_directory,
                        pending_tasks,
                    )
                )
    finally:
        server.shutdown()
        server.server_close()
        if not server_stopped.wait(_LIFECYCLE_TIMEOUT_SECONDS):
            raise TimeoutError("loopback server did not stop")
        server_thread.join(_LIFECYCLE_TIMEOUT_SECONDS)
        if server_thread.is_alive():
            raise TimeoutError("loopback server thread did not stop")

    if server_errors:
        raise RuntimeError(f"loopback server failed: {server_errors[0]}")
    if baseline is None:
        raise RuntimeError("resource baseline was not recorded")
    clean_baseline = {
        "open_fds": baseline["open_fds"],
        "live_threads": baseline["live_threads"],
        "pending_tasks": 0,
        "retained_async_clients": 0,
        "retained_inflight_entries": 0,
    }
    if baseline != clean_baseline:
        raise AssertionError(f"warm resource baseline was not clean: {baseline}")
    if any(measurement != baseline for measurement in measurements):
        raise AssertionError(
            f"resource plateau changed: baseline={baseline} "
            f"measurements={measurements}"
        )

    gc.collect()
    if server.socket.fileno() != -1:
        raise AssertionError("loopback server socket was not closed")
    if _count_open_fds(fd_directory) != baseline["open_fds"] - 1:
        raise AssertionError("loopback server file descriptors were not released")
    if len(threading.enumerate()) != baseline["live_threads"] - 1:
        raise AssertionError("loopback server thread was not released")

    return {
        "cycles": _REAL_RESOURCE_SOAK_CYCLES,
        "open_fd_net_growth": (
            measurements[-1]["open_fds"] - baseline["open_fds"]
        ),
        "live_thread_net_growth": (
            measurements[-1]["live_threads"] - baseline["live_threads"]
        ),
        "max_pending_tasks": max(
            measurement["pending_tasks"] for measurement in measurements
        ),
        "max_retained_async_clients": max(
            measurement["retained_async_clients"]
            for measurement in measurements
        ),
        "max_retained_inflight_entries": max(
            measurement["retained_inflight_entries"]
            for measurement in measurements
        ),
        "server_requests": server.completed_requests,
        "server_stopped": not server_thread.is_alive(),
    }


# 1. http_client sync / async client pairing

class TestHttpClientPairing:
    """Verify that the sync helpers call httpx.Client and the async helpers
    call httpx.AsyncClient."""

    def setup_method(self):
        # Reset singletons so each test starts fresh
        with http_client._sync_client_condition:
            http_client._sync_client = None
            http_client._sync_inflight = 0
            http_client._sync_closing = False
            http_client._sync_client_condition.notify_all()
        http_client._async_clients.clear()
        http_client._async_inflight.clear()
        http_client._hooked_loops.clear()
        http_client._closing_loops.clear()
        http_client._owner_pid = http_client.os.getpid()

    def teardown_method(self):
        with http_client._sync_client_condition:
            http_client._sync_client = None
            http_client._sync_inflight = 0
            http_client._sync_closing = False
            http_client._sync_client_condition.notify_all()
        http_client._async_clients.clear()
        http_client._async_inflight.clear()
        http_client._hooked_loops.clear()
        http_client._closing_loops.clear()
        http_client._owner_pid = http_client.os.getpid()

    @patch.object(httpx.Client, "post", return_value=_fake_response())
    def test_sync_post_uses_sync_client(self, mock_post):
        resp = http_client.post("https://example.com", json={})
        mock_post.assert_called_once()
        assert resp.status_code == 200
        # The sync client should have been created
        assert http_client._sync_client is not None
        assert not http_client._async_clients

    def test_sync_client_reuse_and_shutdown_replace_closed_client(self):
        clients = []

        def create_client(*args, **kwargs):
            client = MagicMock()
            client.post = MagicMock(return_value=f"sync-{len(clients)}")
            client.close = MagicMock()
            clients.append(client)
            return client

        with patch(
            "polyapi.http_client.httpx.Client",
            side_effect=create_client,
        ):
            assert http_client.post("https://example.com/first") == "sync-0"
            assert http_client.post("https://example.com/reused") == "sync-0"
            first_client = http_client._sync_client
            http_client.close()
            assert http_client.post("https://example.com/replacement") == "sync-1"
            replacement_client = http_client._sync_client
            http_client.close()
            http_client.close()

        assert first_client is not replacement_client
        assert [client.post.call_count for client in clients] == [2, 1]
        assert [client.close.call_count for client in clients] == [1, 1]
        assert http_client._sync_client is None

    @patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_fake_response())
    def test_async_post_uses_async_client(self, mock_post):
        async def _run():
            resp = await http_client.async_post("https://example.com", json={})
            # Inspect the registry while the loop is alive; teardown pops it.
            return resp, len(http_client._async_clients)

        resp, cached_count = asyncio.run(_run())
        mock_post.assert_called_once()
        assert resp.status_code == 200
        # A client was cached for the loop that ran the request.
        assert cached_count == 1

    def test_async_post_reuses_client_within_same_loop(self):
        first_client = MagicMock()
        first_client.post = AsyncMock(return_value=_fake_response())
        first_client.aclose = AsyncMock()

        with patch("polyapi.http_client.httpx.AsyncClient", return_value=first_client) as mock_async_client:
            async def _run():
                first_response = await http_client.async_post("https://example.com/first", json={})
                second_response = await http_client.async_post("https://example.com/second", json={})
                loop = asyncio.get_running_loop()
                # Capture the cached client while the loop is alive (teardown pops it).
                return first_response, second_response, http_client._async_clients.get(loop)

            first_response, second_response, cached = asyncio.run(_run())

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert mock_async_client.call_count == 1
        assert first_client.post.await_count == 2
        assert cached is first_client

    def test_async_post_recreates_client_after_loop_change(self):
        first_client = MagicMock()
        first_client.post = AsyncMock(return_value=_fake_response())
        first_client.aclose = AsyncMock()
        second_client = MagicMock()
        second_client.post = AsyncMock(return_value=_fake_response())
        second_client.aclose = AsyncMock()

        with patch(
            "polyapi.http_client.httpx.AsyncClient",
            side_effect=[first_client, second_client],
        ) as mock_async_client:
            async def _run_once(url: str):
                loop = asyncio.get_running_loop()
                response = await http_client.async_post(url, json={})
                # Capture the cached client while the loop is alive (teardown pops it).
                return response, http_client._async_clients.get(loop), loop

            first_response, first_cached_client, first_loop = asyncio.run(_run_once("https://example.com/first"))
            second_response, second_cached_client, second_loop = asyncio.run(_run_once("https://example.com/second"))

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert mock_async_client.call_count == 2
        assert first_client.post.await_count == 1
        assert second_client.post.await_count == 1
        # Each loop got its own client while it was alive.
        assert first_cached_client is first_client
        assert second_cached_client is second_client
        assert first_loop is not second_loop
        # Each loop's teardown hook popped its own client, so the registry is empty.
        assert http_client._async_clients == {}

    def test_client_aclosed_on_loop_teardown(self):
        """The loop-close hook must aclose the client while the loop is still alive,
        so the connection pool is released instead of leaking after the loop closes."""
        client = MagicMock()
        client.post = AsyncMock(return_value=_fake_response())
        client.aclose = AsyncMock()

        with patch("polyapi.http_client.httpx.AsyncClient", return_value=client):
            async def _run():
                await http_client.async_post("https://example.com", json={})

            asyncio.run(_run())  # loop teardown should trigger aclose

        client.aclose.assert_awaited_once()

    def test_loop_close_hook_not_stacked_on_client_recreation(self):
        """recreating clients on the same loop must install only one loop.close
        wrapper, so the final client is aclosed exactly once — not once per recreation."""
        clients = [MagicMock() for _ in range(4)]
        for c in clients:
            c.post = AsyncMock(return_value=_fake_response())
            c.aclose = AsyncMock()

        with patch("polyapi.http_client.httpx.AsyncClient", side_effect=clients):
            async def _run():
                loop = asyncio.get_running_loop()
                for i in range(4):
                    await http_client.async_post("https://example.com", json={})
                    if i < 3:
                        # simulate a close/recreate cycle on the SAME loop
                        http_client._async_clients.pop(loop, None)
                        http_client._async_inflight.clear()

            asyncio.run(_run())

        # Only the last client is live at teardown; the single hook aclos it once.
        assert clients[-1].aclose.await_count == 1
        # Earlier clients were popped without closing here (no stacked wrappers).
        assert all(c.aclose.await_count == 0 for c in clients[:-1])

    def test_unhookable_loop_warns_that_explicit_shutdown_is_required(self):
        class ReadOnlyCloseLoop:
            def close(self):
                pass

            def __setattr__(self, name, value):
                if name == "close":
                    raise AttributeError("close is read-only")
                object.__setattr__(self, name, value)

        loop = ReadOnlyCloseLoop()
        with self.assertLogs("poly", level=logging.WARNING) as captured:
            http_client._register_loop_close_hook(loop)

        assert loop not in http_client._hooked_loops
        assert any(
            "await close_async() before closing this event loop" in message
            for message in captured.output
        )

    def test_default_timeout_is_unbounded_and_env_configurable(self):
        """Default timeout is unbounded behavior; env vars override
        """
        # Default: every phase is None 
        assert http_client._env_opt_float("POLY_HTTP_READ_TIMEOUT", None) is None
        default_timeout = httpx.Timeout(
            connect=http_client._env_opt_float("POLY_HTTP_CONNECT_TIMEOUT", None),
            read=http_client._env_opt_float("POLY_HTTP_READ_TIMEOUT", None),
            write=http_client._env_opt_float("POLY_HTTP_WRITE_TIMEOUT", None),
            pool=http_client._env_opt_float("POLY_HTTP_POOL_TIMEOUT", None),
        )
        assert default_timeout == httpx.Timeout(None)

        # Env override is respected; "none" parses back to None.
        with patch.dict("os.environ", {"POLY_HTTP_READ_TIMEOUT": "90"}):
            assert http_client._env_opt_float("POLY_HTTP_READ_TIMEOUT", None) == 90.0
        with patch.dict("os.environ", {"POLY_HTTP_MAX_KEEPALIVE_CONNECTIONS": "none"}):
            assert http_client._env_opt_int("POLY_HTTP_MAX_KEEPALIVE_CONNECTIONS", 64) is None

    def test_unbounded_timeout_contract_rejects_bounded_values(self):
        assert _is_unbounded_timeout(None)
        assert _is_unbounded_timeout(httpx.Timeout(None))
        assert not _is_unbounded_timeout(httpx.Timeout(1.0))
        assert not _is_unbounded_timeout(
            httpx.Timeout(
                connect=None,
                read=1.0,
                write=None,
                pool=None,
            )
        )
        assert not _is_unbounded_timeout(object())

    @unittest.skipUnless(
        os.environ.get("POLYAPI_RUN_REAL_RESOURCE_SOAK") == "1",
        "manual real-resource soak",
    )
    def test_real_async_lifecycle_resource_soak(self):
        project_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.test_async_proof",
                "--resource-soak-probe",
            ],
            cwd=project_root,
            env={
                "PATH": os.defpath,
                "PYTHONPATH": str(project_root),
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            capture_output=True,
            text=True,
            timeout=_REAL_RESOURCE_SOAK_TIMEOUT_SECONDS,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        metrics = json.loads(result.stdout.strip())
        assert metrics == {
            "cycles": _REAL_RESOURCE_SOAK_CYCLES,
            "open_fd_net_growth": 0,
            "live_thread_net_growth": 0,
            "max_pending_tasks": 0,
            "max_retained_async_clients": 0,
            "max_retained_inflight_entries": 0,
            "server_requests": _REAL_RESOURCE_SOAK_CYCLES + 1,
            "server_stopped": True,
        }

    def test_async_client_preserves_environment_proxy_support(self):
        with patch.dict(
            http_client.os.environ,
            {"HTTPS_PROXY": "http://proxy.invalid:8080"},
            clear=True,
        ):
            async def _run():
                client = http_client._get_async_client()
                proxy_pools = [
                    type(transport._pool).__name__
                    for transport in client._mounts.values()
                    if transport is not None
                ]
                await http_client.close_async()
                return proxy_pools

            proxy_pools = asyncio.run(_run())

        assert "AsyncHTTPProxy" in proxy_pools

    def test_close_waits_for_active_sync_request(self):
        request_started = threading.Event()
        release_request = threading.Event()
        client_closed = threading.Event()
        errors = []
        client = MagicMock()

        def _post(*args, **kwargs):
            request_started.set()
            if not release_request.wait(1):
                raise AssertionError("request release timed out")
            return _fake_response()

        client.post = MagicMock(side_effect=_post)
        client.close = MagicMock(side_effect=client_closed.set)

        def _request():
            try:
                http_client.post("https://example.com")
            except Exception as exc:
                errors.append(exc)

        with patch("polyapi.http_client.httpx.Client", return_value=client):
            request_thread = threading.Thread(target=_request)
            request_thread.start()
            assert request_started.wait(1)

            close_thread = threading.Thread(target=http_client.close)
            close_thread.start()
            with http_client._sync_client_condition:
                assert http_client._sync_client_condition.wait_for(
                    lambda: http_client._sync_closing,
                    timeout=1,
                )
            assert not client_closed.is_set()

            release_request.set()
            request_thread.join(1)
            close_thread.join(1)

        assert not request_thread.is_alive()
        assert not close_thread.is_alive()
        assert errors == []
        client.close.assert_called_once()
        assert http_client._sync_client is None

    def test_close_async_keeps_event_loop_responsive_during_sync_drain(self):
        request_started = threading.Event()
        release_request = threading.Event()
        close_task_created = threading.Event()
        loop_progressed = threading.Event()
        loop_holder = {}
        errors = []
        client = MagicMock()

        def _post(*args, **kwargs):
            request_started.set()
            if not release_request.wait(2):
                raise AssertionError("request release timed out")
            return _fake_response()

        def _request():
            try:
                http_client.post("https://example.com")
            except Exception as exc:
                errors.append(exc)

        async def _run():
            loop_holder["loop"] = asyncio.get_running_loop()
            request_thread = threading.Thread(target=_request, daemon=True)
            request_thread.start()
            if not await asyncio.to_thread(request_started.wait, 1):
                raise AssertionError("sync request did not start")
            closer = asyncio.create_task(http_client.close_async())
            close_task_created.set()
            await closer
            request_thread.join(1)
            if request_thread.is_alive():
                raise AssertionError("sync request thread did not finish")

        def _run_loop():
            try:
                asyncio.run(_run())
            except Exception as exc:
                errors.append(exc)

        client.post = MagicMock(side_effect=_post)
        client.close = MagicMock()
        loop_thread = threading.Thread(target=_run_loop, daemon=True)
        loop_was_responsive = False

        with patch("polyapi.http_client.httpx.Client", return_value=client):
            loop_thread.start()
            try:
                assert close_task_created.wait(1)
                with http_client._sync_client_condition:
                    assert http_client._sync_client_condition.wait_for(
                        lambda: http_client._sync_closing,
                        timeout=1,
                    )
                loop_holder["loop"].call_soon_threadsafe(loop_progressed.set)
                loop_was_responsive = loop_progressed.wait(1)
            finally:
                release_request.set()
                loop_thread.join(2)

        assert loop_was_responsive
        assert not loop_thread.is_alive()
        assert errors == []
        client.close.assert_called_once()

    def test_close_async_drains_inflight_before_closing(self):
        """close_async must wait for in-flight requests to finish before
        aclose(), or connections get torn out mid-read."""
        order = []
        client = MagicMock()

        async def _slow_post(*a, **k):
            await asyncio.sleep(0.1)
            order.append("request_done")
            return _fake_response()

        async def _aclose():
            order.append("aclose")

        client.post = AsyncMock(side_effect=_slow_post)
        client.aclose = AsyncMock(side_effect=_aclose)

        with patch("polyapi.http_client.httpx.AsyncClient", return_value=client):
            async def _run():
                task = asyncio.create_task(
                    http_client.async_post("https://example.com", json={})
                )
                await asyncio.sleep(0.01)  # let the request start and register in-flight
                await http_client.close_async()
                await task

            asyncio.run(_run())

        # aclose ran only after the in-flight request completed.
        assert order == ["request_done", "aclose"]

    def test_close_async_blocks_new_requests_until_close_finishes(self):
        """a request arriving mid-close must NOT create a replacement
        client that shutdown never closes. It waits until aclose() finishes, then gets
        a fresh client."""
        order = []
        old_client = MagicMock()
        new_client = MagicMock()

        async def _slow_post(*a, **k):
            await asyncio.sleep(0.1)
            order.append("inflight_done")
            return _fake_response()

        async def _old_aclose():
            order.append("old_aclose")

        async def _new_post(*a, **k):
            order.append("new_post")
            return _fake_response()

        old_client.post = AsyncMock(side_effect=_slow_post)
        old_client.aclose = AsyncMock(side_effect=_old_aclose)
        new_client.post = AsyncMock(side_effect=_new_post)
        new_client.aclose = AsyncMock()

        with patch("polyapi.http_client.httpx.AsyncClient", side_effect=[old_client, new_client]):
            async def _run():
                inflight = asyncio.create_task(http_client.async_post("https://x/1", json={}))
                await asyncio.sleep(0.01)  # register in-flight on the old client
                closer = asyncio.create_task(http_client.close_async())
                await asyncio.sleep(0.01)  # let close mark the loop as closing
                new_req = asyncio.create_task(http_client.async_post("https://x/2", json={}))
                await asyncio.gather(inflight, closer, new_req)

            asyncio.run(_run())

        # In-flight drained, old client closed, THEN the new request ran on a fresh client.
        assert order == ["inflight_done", "old_aclose", "new_post"]
        assert new_client.post.await_count == 1

    def test_close_async_finishes_aclose_before_propagating_cancellation(self):
        client = MagicMock()

        async def _run():
            close_started = asyncio.Event()
            release_close = asyncio.Event()

            async def _aclose():
                close_started.set()
                await release_close.wait()

            client.aclose = AsyncMock(side_effect=_aclose)
            loop = asyncio.get_running_loop()
            http_client._async_clients[loop] = client

            closer = asyncio.create_task(http_client.close_async())
            await close_started.wait()
            closer.cancel()
            await asyncio.sleep(0)

            assert http_client._async_clients.get(loop) is client
            assert loop in http_client._closing_loops
            assert not closer.done()

            release_close.set()
            with pytest.raises(asyncio.CancelledError):
                await closer

            assert loop not in http_client._async_clients
            assert loop not in http_client._closing_loops

        asyncio.run(_run())
        client.aclose.assert_awaited_once()

    def test_cancelled_close_keeps_waiter_until_shared_cleanup_finishes(self):
        client = MagicMock()

        async def _run():
            request_started = asyncio.Event()
            release_request = asyncio.Event()
            close_started = asyncio.Event()
            release_close = asyncio.Event()

            async def _post(*args, **kwargs):
                request_started.set()
                await release_request.wait()
                return _fake_response()

            async def _aclose():
                close_started.set()
                await release_close.wait()

            client.post = AsyncMock(side_effect=_post)
            client.aclose = AsyncMock(side_effect=_aclose)
            loop = asyncio.get_running_loop()
            http_client._async_clients[loop] = client

            request = asyncio.create_task(
                http_client.async_post("https://example.com", json={})
            )
            await asyncio.wait_for(request_started.wait(), timeout=1)

            owner = asyncio.create_task(http_client.close_async())
            await asyncio.sleep(0)
            assert loop in http_client._closing_loops
            waiter = asyncio.create_task(http_client.close_async())
            await asyncio.sleep(0)

            assert owner.cancel()
            await asyncio.sleep(0)
            assert not owner.done()
            assert not waiter.done()
            assert client.aclose.await_count == 0

            release_request.set()
            await asyncio.wait_for(request, timeout=1)
            await asyncio.wait_for(close_started.wait(), timeout=1)
            assert not owner.done()
            assert not waiter.done()

            release_close.set()
            await asyncio.wait_for(waiter, timeout=1)
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(owner, timeout=1)

            assert loop not in http_client._async_clients
            assert loop not in http_client._closing_loops

        asyncio.run(_run())
        client.aclose.assert_awaited_once()

    def test_failed_aclose_retires_closed_client_and_propagates_error(self):
        failed_client = MagicMock()
        replacement_client = MagicMock()
        close_error = RuntimeError("synthetic close failure")

        async def _failed_aclose():
            failed_client.is_closed = True
            raise close_error

        failed_client.is_closed = False
        failed_client.get = AsyncMock(
            side_effect=AssertionError("closed client was reused")
        )
        failed_client.aclose = AsyncMock(side_effect=_failed_aclose)
        replacement_client.get = AsyncMock(return_value=_fake_response())
        replacement_client.aclose = AsyncMock()

        async def _run():
            loop = asyncio.get_running_loop()
            http_client._async_clients[loop] = failed_client

            with pytest.raises(RuntimeError) as captured:
                await http_client.close_async()
            assert captured.value is close_error
            assert failed_client.is_closed
            assert loop not in http_client._async_clients
            assert loop not in http_client._closing_loops

            response = await http_client.async_get("https://example.com")
            assert response.status_code == 200
            assert http_client._async_clients.get(loop) is replacement_client
            await http_client.close_async()

        with patch(
            "polyapi.http_client.httpx.AsyncClient",
            return_value=replacement_client,
        ) as create_client:
            asyncio.run(_run())

        failed_client.aclose.assert_awaited_once()
        failed_client.get.assert_not_awaited()
        create_client.assert_called_once()
        replacement_client.get.assert_awaited_once()
        replacement_client.aclose.assert_awaited_once()

    def test_fork_clears_inherited_async_entry_before_creating_child_client(self):
        """In forked child, _get_async_client must drop the inherited parent
        entry before creating the child's own."""
        parent_loop = MagicMock()
        parent_client = MagicMock()
        parent_client.aclose = AsyncMock()
        http_client._async_clients[parent_loop] = parent_client

        child_client = MagicMock()
        child_client.post = AsyncMock(return_value=_fake_response())
        child_client.aclose = AsyncMock()

        child_pid = http_client._owner_pid + 1
        with patch.object(http_client.os, "getpid", return_value=child_pid), \
                patch("polyapi.http_client.httpx.AsyncClient", return_value=child_client):
            async def _run():
                await http_client.async_post("https://example.com", json={})
                return dict(http_client._async_clients)

            entries = asyncio.run(_run())

        # Parent's inherited entry was dropped, and its sockets left untouched.
        assert parent_loop not in entries
        parent_client.aclose.assert_not_awaited()
        # Child created exactly one client for itself.
        assert list(entries.values()) == [child_client]

    def test_after_fork_in_child_resets_lock_and_state(self):
        """after-fork hook must recreate _sync_client_lock (a child could
        inherit it locked and deadlock) and clear all inherited client state."""
        old_lock = http_client._sync_client_lock
        old_condition = http_client._sync_client_condition
        http_client._sync_client = MagicMock()
        http_client._sync_inflight = 2
        http_client._sync_closing = True
        http_client._async_clients[MagicMock()] = MagicMock()
        http_client._async_inflight[MagicMock()] = 3

        http_client._after_fork_in_child()

        # Fresh, unlocked lock — not the (possibly held) inherited one.
        assert http_client._sync_client_lock is not old_lock
        assert http_client._sync_client_condition is not old_condition
        assert not http_client._sync_client_lock.locked()
        # All inherited state dropped (not closed).
        assert http_client._sync_client is None
        assert http_client._sync_inflight == 0
        assert not http_client._sync_closing
        assert http_client._async_clients == {}
        assert http_client._async_inflight == {}
        assert http_client._owner_pid == http_client.os.getpid()

    @unittest.skipUnless(
        hasattr(os, "fork") and hasattr(signal, "SIGALRM"),
        "requires fork and SIGALRM",
    )
    def test_fork_child_reset_cannot_deadlock_with_parent_lock_held(self):
        inherited_client = MagicMock()
        http_client._async_inflight[inherited_client] = 1
        lock_acquired = threading.Event()
        release_parent_lock = threading.Event()

        def hold_parent_lock():
            with http_client._sync_client_lock:
                lock_acquired.set()
                release_parent_lock.wait(_LIFECYCLE_TIMEOUT_SECONDS)

        holder = threading.Thread(target=hold_parent_lock)
        holder.start()
        assert lock_acquired.wait(_LIFECYCLE_TIMEOUT_SECONDS)

        read_fd, write_fd = os.pipe()
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="This process .* is multi-threaded, use of fork.*",
                category=DeprecationWarning,
            )
            child_pid = os.fork()
        if child_pid == 0:
            os.close(read_fd)

            def alarm_handler(_signum, _frame):
                raise TimeoutError("child lock acquisition timed out")

            signal.signal(signal.SIGALRM, alarm_handler)
            signal.alarm(_LIFECYCLE_TIMEOUT_SECONDS)
            child_completed = False
            try:
                with patch(
                    "polyapi.http_client.httpx.Client",
                    return_value=MagicMock(),
                ):
                    http_client._get_sync_client()
                child_completed = True
            except Exception:
                child_completed = False
            finally:
                signal.alarm(0)

            payload = (
                f"{int(child_completed)}:{len(http_client._async_inflight)}"
            ).encode("ascii")
            os.write(write_fd, payload)
            os.close(write_fd)
            os._exit(0)

        os.close(write_fd)
        release_parent_lock.set()
        holder.join(_LIFECYCLE_TIMEOUT_SECONDS)
        assert not holder.is_alive()

        deadline = time.monotonic() + _LIFECYCLE_TIMEOUT_SECONDS
        child_status = None
        while time.monotonic() < deadline:
            waited_pid, child_status = os.waitpid(child_pid, os.WNOHANG)
            if waited_pid == child_pid:
                break
            time.sleep(0.01)
        else:
            os.kill(child_pid, signal.SIGKILL)
            os.waitpid(child_pid, 0)

        payload = os.read(read_fd, 64)
        os.close(read_fd)
        assert child_status is not None
        assert os.waitstatus_to_exitcode(child_status) == 0
        assert payload == b"1:0"

    def test_reset_if_forked_drops_inherited_clients_without_closing(self):
        """After a fork (PID change), inherited clients must be dropped, not closed —
        their sockets belong to the parent process."""
        inherited_sync = MagicMock()
        inherited_sync.close = MagicMock()
        inherited_async = MagicMock()
        inherited_async.aclose = AsyncMock()
        fake_loop = MagicMock()

        http_client._sync_client = inherited_sync
        http_client._async_clients[fake_loop] = inherited_async

        # Simulate running in a forked child: getpid() now differs from _owner_pid.
        with patch.object(http_client.os, "getpid", return_value=http_client._owner_pid + 1):
            http_client._reset_if_forked()

        # Inherited references cleared
        assert http_client._sync_client is None
        assert http_client._async_clients == {}
        # never closed (that would tear down the parent's live sockets).
        inherited_sync.close.assert_not_called()
        inherited_async.aclose.assert_not_awaited()

    def test_close_async_clears_cached_client_for_current_loop(self):
        async def _run():
            cached_client = MagicMock()
            cached_client.aclose = AsyncMock()
            http_client._async_clients[asyncio.get_running_loop()] = cached_client

            await http_client.close_async()

            return cached_client

        cached_client = asyncio.run(_run())

        cached_client.aclose.assert_awaited_once()
        assert http_client._async_clients == {}

    def test_close_async_drops_stale_client_without_cross_loop_close(self):
        stale_client = MagicMock()
        stale_client.aclose = AsyncMock()

        async def _seed_stale_client():
            # Cache a client against this loop, which is closed once the run ends.
            http_client._async_clients[asyncio.get_running_loop()] = stale_client

        asyncio.run(_seed_stale_client())

        async def _close_on_new_loop():
            await http_client.close_async()

        asyncio.run(_close_on_new_loop())

        # The stale client's loop is closed, so it's dropped and not awaited across loops.
        stale_client.aclose.assert_not_awaited()
        assert http_client._async_clients == {}

    def test_concurrent_loops_in_threads_get_isolated_clients(self):
        """Two loops running at once (in separate threads) should get own client
        And not evict each other's"""
        import threading

        seen = {}
        barrier = threading.Barrier(2)

        def worker(name):
            async def _run():
                # Force both loops to overlap 
                loop = asyncio.get_running_loop()
                _ = http_client._get_async_client()
                barrier.wait()
                await asyncio.sleep(0.05)
                seen[name] = (loop, http_client._async_clients.get(loop))

            asyncio.run(_run())

        def create_client(*args, **kwargs):
            client = MagicMock()
            client.aclose = AsyncMock()
            return client

        with patch(
            "polyapi.http_client.httpx.AsyncClient",
            side_effect=create_client,
        ):
            t1 = threading.Thread(target=worker, args=("a",))
            t2 = threading.Thread(target=worker, args=("b",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        (loop_a, client_a), (loop_b, client_b) = seen["a"], seen["b"]
        assert loop_a is not loop_b
        # Each loop kept the client it created — no cross-loop eviction.
        assert client_a is not None and client_b is not None
        assert client_a is not client_b

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


class TestHttpClientLifecycle(unittest.TestCase):
    """The deterministic HTTP-client lifecycle contract run by the harness.

    The legacy pairing tests intentionally remain pytest-style and are not part
    of normal unittest discovery. Keep this class limited to lifecycle coverage
    introduced by the shared-client concurrency change.
    """

    __test__ = False

    setUp = TestHttpClientPairing.setup_method
    tearDown = TestHttpClientPairing.teardown_method
    test_sync_client_reuse_and_shutdown_replace_closed_client = (
        TestHttpClientPairing.test_sync_client_reuse_and_shutdown_replace_closed_client
    )
    test_client_aclosed_on_loop_teardown = (
        TestHttpClientPairing.test_client_aclosed_on_loop_teardown
    )
    test_loop_close_hook_not_stacked_on_client_recreation = (
        TestHttpClientPairing.test_loop_close_hook_not_stacked_on_client_recreation
    )
    test_unhookable_loop_warns_that_explicit_shutdown_is_required = (
        TestHttpClientPairing.test_unhookable_loop_warns_that_explicit_shutdown_is_required
    )
    test_default_timeout_is_unbounded_and_env_configurable = (
        TestHttpClientPairing.test_default_timeout_is_unbounded_and_env_configurable
    )
    test_unbounded_timeout_contract_rejects_bounded_values = (
        TestHttpClientPairing.test_unbounded_timeout_contract_rejects_bounded_values
    )
    test_real_async_lifecycle_resource_soak = (
        TestHttpClientPairing.test_real_async_lifecycle_resource_soak
    )
    test_async_client_preserves_environment_proxy_support = (
        TestHttpClientPairing.test_async_client_preserves_environment_proxy_support
    )
    test_close_waits_for_active_sync_request = (
        TestHttpClientPairing.test_close_waits_for_active_sync_request
    )
    test_close_async_keeps_event_loop_responsive_during_sync_drain = (
        TestHttpClientPairing.test_close_async_keeps_event_loop_responsive_during_sync_drain
    )
    test_close_async_drains_inflight_before_closing = (
        TestHttpClientPairing.test_close_async_drains_inflight_before_closing
    )
    test_close_async_blocks_new_requests_until_close_finishes = (
        TestHttpClientPairing.test_close_async_blocks_new_requests_until_close_finishes
    )
    test_close_async_finishes_aclose_before_propagating_cancellation = (
        TestHttpClientPairing.test_close_async_finishes_aclose_before_propagating_cancellation
    )
    test_cancelled_close_keeps_waiter_until_shared_cleanup_finishes = (
        TestHttpClientPairing.test_cancelled_close_keeps_waiter_until_shared_cleanup_finishes
    )
    test_failed_aclose_retires_closed_client_and_propagates_error = (
        TestHttpClientPairing.test_failed_aclose_retires_closed_client_and_propagates_error
    )
    test_fork_clears_inherited_async_entry_before_creating_child_client = (
        TestHttpClientPairing.test_fork_clears_inherited_async_entry_before_creating_child_client
    )
    test_after_fork_in_child_resets_lock_and_state = (
        TestHttpClientPairing.test_after_fork_in_child_resets_lock_and_state
    )
    test_fork_child_reset_cannot_deadlock_with_parent_lock_held = (
        TestHttpClientPairing.test_fork_child_reset_cannot_deadlock_with_parent_lock_held
    )
    test_reset_if_forked_drops_inherited_clients_without_closing = (
        TestHttpClientPairing.test_reset_if_forked_drops_inherited_clients_without_closing
    )
    test_concurrent_loops_in_threads_get_isolated_clients = (
        TestHttpClientPairing.test_concurrent_loops_in_threads_get_isolated_clients
    )


def load_tests(_loader, _tests, _pattern):
    """Keep lifecycle and legacy pairing coverage out of generic unittest CI."""
    return unittest.TestSuite()


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


if __name__ == "__main__":
    if sys.argv[1:] != ["--resource-soak-probe"]:
        raise SystemExit("unsupported lifecycle probe")
    print(json.dumps(_run_real_resource_soak(), sort_keys=True))
