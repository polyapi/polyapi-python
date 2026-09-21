"""Manual launcher for the tracked HTTP client lifecycle contract.

The authoritative assertions live in ``tests/test_async_proof.py``. This
launcher loads that contract from the selected checkout without copying or
weakening it.
"""

import importlib.util
import io
import os
from pathlib import Path
import sys
from typing import Literal, Mapping, TypedDict, cast
import unittest


_Outcome = Literal["pass", "fail", "skip"]
_Status = Literal["PASS", "FAIL", "SKIP"]
_Color = Literal["green", "red", "yellow"]
_TestOutcome = tuple[str, _Outcome]
_TableRow = tuple[str, str, str, str, _Status]


class _SummaryRow(TypedDict):
    passed: int
    failed: int
    skipped: int
    status: _Status


_CATEGORY_TESTS: dict[str, tuple[str, ...]] = {
    "Fork reset": (
        "test_after_fork_in_child_resets_lock_and_state",
        "test_fork_child_reset_cannot_deadlock_with_parent_lock_held",
        "test_fork_clears_inherited_async_entry_before_creating_child_client",
        "test_reset_if_forked_drops_inherited_clients_without_closing",
    ),
    "Sync lifecycle": (
        "test_close_waits_for_active_sync_request",
        "test_sync_client_reuse_and_shutdown_replace_closed_client",
    ),
    "Async shutdown and ownership": (
        "test_cancelled_close_keeps_waiter_until_shared_cleanup_finishes",
        "test_close_async_blocks_new_requests_until_close_finishes",
        "test_close_async_drains_inflight_before_closing",
        "test_close_async_finishes_aclose_before_propagating_cancellation",
        "test_close_async_keeps_event_loop_responsive_during_sync_drain",
        "test_failed_aclose_retires_closed_client_and_propagates_error",
    ),
    "Event-loop lifecycle": (
        "test_client_aclosed_on_loop_teardown",
        "test_concurrent_loops_in_threads_get_isolated_clients",
        "test_loop_close_hook_not_stacked_on_client_recreation",
        "test_unhookable_loop_warns_that_explicit_shutdown_is_required",
    ),
    "Timeout and configuration compatibility": (
        "test_default_timeout_is_unbounded_and_env_configurable",
        "test_unbounded_timeout_contract_rejects_bounded_values",
    ),
    "Client request behavior": (
        "test_async_client_preserves_environment_proxy_support",
    ),
    "Real-resource soak": (
        "test_real_async_lifecycle_resource_soak",
    ),
}
_TEST_CATEGORIES = {
    test_name: category
    for category, test_names in _CATEGORY_TESTS.items()
    for test_name in test_names
}
_STATUS_COLORS: dict[_Status, _Color] = {
    "PASS": "green",
    "FAIL": "red",
    "SKIP": "yellow",
}


def _resolve_target_root():
    configured = os.environ.get("POLYAPI_SDK_TARGET")
    candidates: tuple[Path, ...]
    if configured:
        candidates = (Path(configured),)
    else:
        candidates = (Path(__file__).resolve().parents[1], Path.cwd())

    for candidate in candidates:
        target_root = candidate.resolve()
        contract = target_root / "tests" / "test_async_proof.py"
        if contract.is_file():
            return target_root, contract
    raise RuntimeError("selected checkout has no tracked lifecycle contract")


_TARGET_ROOT, _CONTRACT_PATH = _resolve_target_root()
sys.path.insert(0, str(_TARGET_ROOT))
_SPEC = importlib.util.spec_from_file_location(
    "_tracked_http_client_lifecycle",
    _CONTRACT_PATH,
)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("tracked lifecycle contract could not be loaded")
_CONTRACT = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _CONTRACT
_SPEC.loader.exec_module(_CONTRACT)


def _test_name(test: unittest.TestCase) -> str:
    return test.id().rsplit(".", 1)[-1]


def _validate_category_mapping() -> None:
    loader = unittest.TestLoader()
    contract_test_names = set(loader.getTestCaseNames(_CONTRACT.TestHttpClientLifecycle))
    mapped_test_names = set(_TEST_CATEGORIES)
    unmapped = sorted(contract_test_names - mapped_test_names)
    obsolete = sorted(mapped_test_names - contract_test_names)
    duplicate = len(_TEST_CATEGORIES) != sum(
        len(test_names) for test_names in _CATEGORY_TESTS.values()
    )
    if unmapped or obsolete or duplicate:
        details = []
        if unmapped:
            details.append("unmapped=" + ", ".join(unmapped))
        if obsolete:
            details.append("obsolete=" + ", ".join(obsolete))
        if duplicate:
            details.append("duplicate category mappings")
        raise RuntimeError("lifecycle category mapping is invalid: " + "; ".join(details))


def _summary_rows(
    outcomes: list[_TestOutcome],
) -> tuple[dict[str, _SummaryRow], list[str]]:
    rows: dict[str, _SummaryRow] = {
        category: {"passed": 0, "failed": 0, "skipped": 0, "status": "SKIP"}
        for category in _CATEGORY_TESTS
    }
    unmapped: list[str] = []
    for test_name, outcome in outcomes:
        category = _TEST_CATEGORIES.get(test_name)
        if category is None:
            unmapped.append(test_name)
            continue
        if outcome == "pass":
            rows[category]["passed"] += 1
        elif outcome == "fail":
            rows[category]["failed"] += 1
        else:
            rows[category]["skipped"] += 1

    for row in rows.values():
        row["status"] = (
            "FAIL" if row["failed"] else "PASS" if row["passed"] else "SKIP"
        )
    return rows, sorted(unmapped)


def _should_color(stream: object, environment: Mapping[str, str] | None = None) -> bool:
    active_environment: Mapping[str, str] = os.environ if environment is None else environment
    return bool(getattr(stream, "isatty", lambda: False)()) and "NO_COLOR" not in active_environment


def _color(text: str, color_name: _Color, enabled: bool) -> str:
    if not enabled:
        return text
    codes = {"green": "32", "red": "31", "yellow": "33"}
    return "\033[" + codes[color_name] + "m" + text + "\033[0m"


def _format_summary(outcomes: list[_TestOutcome], color: bool = False) -> str:
    rows, unmapped = _summary_rows(outcomes)
    lines = ["HTTP client lifecycle harness summary"]
    header = ("Category", "PASS", "FAIL", "SKIP", "Result")
    table_rows: list[_TableRow] = [
        (
            category,
            str(row["passed"]),
            str(row["failed"]),
            str(row["skipped"]),
            row["status"],
        )
        for category, row in rows.items()
    ]
    widths = [
        max(len(row[index]) for row in [header, *table_rows])
        for index in range(len(header))
    ]
    separator = "  ".join("-" * width for width in widths)
    lines.extend(
        (
            "  ".join(value.ljust(widths[index]) for index, value in enumerate(header)),
            separator,
        )
    )
    for row in table_rows:
        status = _color(
            row[4],
            _STATUS_COLORS[row[4]],
            color,
        )
        lines.append(
            "  ".join(
                [
                    row[0].ljust(widths[0]),
                    row[1].rjust(widths[1]),
                    row[2].rjust(widths[2]),
                    row[3].rjust(widths[3]),
                    status,
                ]
            )
        )

    passed = sum(outcome == "pass" for _test_name, outcome in outcomes)
    failed = sum(outcome == "fail" for _test_name, outcome in outcomes)
    skipped = sum(outcome == "skip" for _test_name, outcome in outcomes)
    overall = "PASS" if not failed and not unmapped else "FAIL"
    lines.append("")
    lines.append(
        "Overall {}: executed={} passed={} failed={} skipped={}".format(
            _color(overall, "green" if overall == "PASS" else "red", color),
            len(outcomes),
            passed,
            failed,
            skipped,
        )
    )
    if unmapped:
        lines.append("Unmapped lifecycle tests: " + ", ".join(unmapped))
    return "\n".join(lines)


class _LifecycleResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes: list[_TestOutcome] = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes.append((_test_name(test), "pass"))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes.append((_test_name(test), "fail"))

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes.append((_test_name(test), "fail"))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes.append((_test_name(test), "skip"))

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.outcomes.append((_test_name(test), "skip"))

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.outcomes.append((_test_name(test), "fail"))

    def wasSuccessful(self):
        _rows, unmapped = _summary_rows(self.outcomes)
        return super().wasSuccessful() and not unmapped


class _LifecycleRunner(unittest.TextTestRunner):
    resultclass = _LifecycleResult

    def run(self, test):
        result = cast(_LifecycleResult, super().run(test))
        self.stream.writeln(_format_summary(result.outcomes, _should_color(self.stream)))
        return result


def load_tests(loader, _tests, _pattern):
    _validate_category_mapping()
    return loader.loadTestsFromTestCase(_CONTRACT.TestHttpClientLifecycle)


def _run_self_checks():
    _validate_category_mapping()
    outcomes: list[_TestOutcome] = [
        ("test_after_fork_in_child_resets_lock_and_state", "pass"),
        ("test_close_waits_for_active_sync_request", "fail"),
        ("test_real_async_lifecycle_resource_soak", "skip"),
        ("unknown_lifecycle_test", "pass"),
    ]
    rows, unmapped = _summary_rows(outcomes)
    expected_fork_reset: _SummaryRow = {
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "status": "PASS",
    }
    if not all(
        (
            rows["Fork reset"] == expected_fork_reset,
            rows["Sync lifecycle"]["status"] == "FAIL",
            rows["Real-resource soak"]["status"] == "SKIP",
            unmapped == ["unknown_lifecycle_test"],
        )
    ):
        raise AssertionError("lifecycle summary status accounting failed")
    plain = _format_summary(outcomes, color=False)
    colored = _format_summary(outcomes, color=True)
    color_mode_ok = "\033[" not in plain and "\033[" in colored
    count_mode_ok = "Overall FAIL: executed=4 passed=2 failed=1 skipped=1" in plain
    if not color_mode_ok or not count_mode_ok:
        raise AssertionError("lifecycle summary color mode failed")

    class _Stream:
        def __init__(self, tty):
            self.tty = tty

        def isatty(self):
            return self.tty

    if not _should_color(_Stream(True), {}) or _should_color(_Stream(True), {"NO_COLOR": "1"}):
        raise AssertionError("lifecycle summary TTY color selection failed")
    if _should_color(_Stream(False), {}):
        raise AssertionError("lifecycle summary non-TTY color selection failed")
    result = _LifecycleResult(io.StringIO(), descriptions=True, verbosity=1)
    result.outcomes.append(("unknown_lifecycle_test", "pass"))
    if result.wasSuccessful():
        raise AssertionError("unmapped lifecycle tests must fail the harness")
    print("Lifecycle harness summary self-check: PASS")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.argv.remove("--self-check")
        _run_self_checks()
    else:
        unittest.main(testRunner=_LifecycleRunner)
