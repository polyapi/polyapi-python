import asyncio
import importlib
import sys
from concurrent.futures import ThreadPoolExecutor


def _reload_polyapi():
    sys.modules.pop("polyapi", None)
    sys.modules.pop("polyapi.cli", None)
    polyapi = importlib.import_module("polyapi")

    for module_name, module in list(sys.modules.items()):
        if not module_name.startswith("polyapi.") or module_name == "polyapi.cli":
            continue
        submodule_name = module_name.removeprefix("polyapi.")
        if "." not in submodule_name:
            setattr(polyapi, submodule_name, module)

    return polyapi


def test_import_polyapi_does_not_import_cli():
    polyapi = _reload_polyapi()

    assert polyapi is not None
    assert "polyapi.cli" not in sys.modules


def test_cli_constants_shared_between_runtime_and_cli():
    cli_constants = importlib.import_module("polyapi.cli_constants")
    cli_module = importlib.import_module("polyapi.cli")

    assert tuple(cli_module.CLI_COMMANDS) == cli_constants.CLI_COMMANDS


def test_reload_preserves_existing_submodule_bindings():
    rendered_spec = importlib.import_module("polyapi.rendered_spec")

    polyapi = _reload_polyapi()

    assert polyapi.rendered_spec is rendered_spec


def test_poly_custom_nested_scopes_restore_previous_state():
    polyapi = _reload_polyapi()
    poly_custom = polyapi.polyCustom

    outer_token = poly_custom.push_scope(
        {
            "executionId": "outer",
            "responseHeaders": {"x-scope": "outer"},
            "responseStatusCode": None,
        }
    )
    try:
        assert poly_custom["executionId"] == "outer"

        inner_token = poly_custom.push_scope(
            {
                "executionId": "inner",
                "responseHeaders": {"x-scope": "inner"},
                "responseStatusCode": 202,
            }
        )
        try:
            assert poly_custom["executionId"] == "inner"
            assert poly_custom["responseHeaders"] == {"x-scope": "inner"}
            assert poly_custom.responseStatusCode == 202

            poly_custom["executionId"] = "should-not-overwrite"
            assert poly_custom["executionId"] == "inner"

            poly_custom.unlock_execution_id()
            poly_custom["executionId"] = "inner-updated"
            assert poly_custom["executionId"] == "inner-updated"
        finally:
            poly_custom.pop_scope(inner_token)

        assert poly_custom["executionId"] == "outer"
        assert poly_custom["responseHeaders"] == {"x-scope": "outer"}
        assert poly_custom["responseStatusCode"] is None
    finally:
        poly_custom.pop_scope(outer_token)

    assert poly_custom["executionId"] is None
    assert poly_custom["responseHeaders"] == {}
    assert poly_custom["responseStatusCode"] == 200


def test_poly_custom_isolated_across_async_tasks():
    polyapi = _reload_polyapi()
    poly_custom = polyapi.polyCustom

    async def worker(execution_id: str) -> tuple[str, str]:
        token = poly_custom.push_scope(
            {
                "executionId": execution_id,
                "responseHeaders": {"worker": execution_id},
                "responseStatusCode": None,
            }
        )
        try:
            await asyncio.sleep(0)
            poly_custom["responseHeaders"]["seen"] = execution_id
            await asyncio.sleep(0)
            return poly_custom["executionId"], poly_custom["responseHeaders"]["seen"]
        finally:
            poly_custom.pop_scope(token)

    async def run_workers() -> tuple[tuple[str, str], tuple[str, str]]:
        first_result, second_result = await asyncio.gather(worker("async-a"), worker("async-b"))
        return first_result, second_result

    first, second = asyncio.run(run_workers())

    assert first == ("async-a", "async-a")
    assert second == ("async-b", "async-b")
    assert poly_custom["executionId"] is None
    assert poly_custom["responseHeaders"] == {}


def test_poly_custom_isolated_across_threads():
    polyapi = _reload_polyapi()
    poly_custom = polyapi.polyCustom

    def worker(execution_id: str) -> tuple[str, str]:
        token = poly_custom.push_scope(
            {
                "executionId": execution_id,
                "responseHeaders": {"worker": execution_id},
                "responseStatusCode": None,
            }
        )
        try:
            poly_custom["responseHeaders"]["seen"] = execution_id
            return poly_custom["executionId"], poly_custom["responseHeaders"]["seen"]
        finally:
            poly_custom.pop_scope(token)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(worker, "thread-a").result()
        second = executor.submit(worker, "thread-b").result()

    assert first == ("thread-a", "thread-a")
    assert second == ("thread-b", "thread-b")
    assert poly_custom["executionId"] is None
    assert poly_custom["responseHeaders"] == {}
