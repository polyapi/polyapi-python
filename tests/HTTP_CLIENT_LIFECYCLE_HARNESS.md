# HTTP client lifecycle harness

This launcher runs the 20-test lifecycle contract in
[`test_async_proof.py`](test_async_proof.py). It does not copy assertions and
runs with the bounded loopback-only resource soak on every pull request and
push to `develop`.

The 14 pre-existing `TestHttpClientPairing` methods remain pytest-style and
out of normal PR `unittest` collection. The `TestHttpClientLifecycle` contract
contains only coverage added for shared-client concurrency and is collected
once through this launcher.

Run from the selected SDK checkout with its virtual environment:

```fish
set -lx POLYAPI_SDK_TARGET /Users/eric/dev/poly/polyapi-python
set -l qa_python $POLYAPI_SDK_TARGET/.venv/bin/python

# Fast lifecycle contract. The manual resource soak is skipped.
$qa_python tests/run_http_client_lifecycle_harness.py -v

# Full lifecycle contract with the bounded loopback-only resource soak.
set -lx POLYAPI_RUN_REAL_RESOURCE_SOAK 1
$qa_python tests/run_http_client_lifecycle_harness.py -v
```

`POLYAPI_SDK_TARGET` is optional when running the launcher from the target
checkout. Set it to run the same contract against another local checkout.

The launcher prints the usual `unittest` failures first, followed by a stable
summary. The fast command reports `Real-resource soak` as `SKIP`; the full
command reports it as `PASS` when it succeeds.

```text
HTTP client lifecycle harness summary
Category                                PASS  FAIL  SKIP  Result
--------------------------------------  ----  ----  ----  ------
Fork reset                                 4     0     0  PASS
Sync lifecycle                             2     0     0  PASS
Async shutdown and ownership               6     0     0  PASS
Event-loop lifecycle                       4     0     0  PASS
Timeout and configuration compatibility    2     0     0  PASS
Client request behavior                    1     0     0  PASS
Real-resource soak                         0     0     1  SKIP

Overall PASS: executed=20 passed=19 failed=0 skipped=1
```

When output is a terminal, `PASS`, `FAIL`, and `SKIP` are green, red, and
yellow. Redirected output and environments with `NO_COLOR` set use the same
plain-text table.

CI runs the lifecycle contract through this launcher exactly once. Generic
`unittest` discovery keeps `tests.test_async_proof` out of its suite, matching
the legacy collection boundary while retaining all other discovered tests.

To run the remaining unit tests locally:

```fish
cd $POLYAPI_SDK_TARGET
$qa_python -m unittest discover -s tests -t . -v
```
