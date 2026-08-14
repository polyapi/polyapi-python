# PolyAPI Python Library

The PolyAPI Python Library lets you use and define PolyAPI functions using Python.

## PolyAPI Quickstart

### 1. Install Libraries

First install the client.

We recommend the use of venv so you can have multiple projects each with separate credentials:

```bash
python -m venv myvenv
source myvenv/bin/activate
pip install polyapi-python
```

Replace `myvenv` with whatever you'd like your venv to be named!

For more on Python virtual environments, we recommend this [venv primer](https://realpython.com/python-virtual-environments-a-primer/).

However, if you only need to use polyapi with a single project, you can do a basic install:

```bash
pip install polyapi-python
```

### 2. Generate Your Functions

Now you can run the following to generate your library

```bash
python -m polyapi generate
```

You will be prompted to enter the Poly server url you use and your Poly API key.

You can also provide the key and url as environment variables (useful for deployment):

```
POLY_API_KEY='your_key'
POLY_API_BASE_URL='your_server'  # e.g. na1.polyapi.io
```

### HTTP Client Configuration

The SDK reuses one synchronous HTTP client per process and one asynchronous
client per event loop. New clients read these optional environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `POLY_HTTP_MAX_CONNECTIONS` | `200` | Maximum connections per client |
| `POLY_HTTP_MAX_KEEPALIVE_CONNECTIONS` | `none` | Maximum idle keep-alive connections per client |
| `POLY_HTTP_KEEPALIVE_EXPIRY` | `30` | Idle keep-alive expiry in seconds |
| `POLY_HTTP_CONNECT_TIMEOUT` | `none` | Connection timeout in seconds |
| `POLY_HTTP_READ_TIMEOUT` | `none` | Read timeout in seconds |
| `POLY_HTTP_WRITE_TIMEOUT` | `none` | Write timeout in seconds |
| `POLY_HTTP_POOL_TIMEOUT` | `none` | Connection-pool timeout in seconds |

An empty value, `none`, or `null` means unbounded. Limits are per client, so
processes with multiple event loops can create one configured pool per loop.

Call `polyapi.http_client.close()` during synchronous shutdown or await
`polyapi.http_client.close_async()` on each owning event loop during
asynchronous shutdown. The shutdown functions wait for active SDK requests
before closing their client. Clients on standard asyncio loops are closed
automatically when the loop closes. If a custom event-loop implementation
reports that its close hook could not be installed, explicitly await
`close_async()` before closing that loop.

### 3. Test

That's it! Now open up a test file and you can run some code like so:

```python
from polyapi import poly
print(poly.polyapi.function.api.list(my_server, my_api_key))
```


## Add New Server Functions

To add a new server function, please follow the quickstart. Then you can add a server function like so:

```bash
python -m polyapi function add <function_name> foo.py --server --context mycontext --description mydesc
```

The code in `foo.py` should contain a single defined function named the same as your `<function_name>` variable.

So for example, if you want to add a function named `bar`, your file `foo.py` would look like this:

```python
def bar():
    return "Hello World"
```

## Complex Types In Server Functions

You can define arbitrarily complex argument and return types using TypedDicts.

NOTE: you must use `TypedDict` from `typing_extensions`, not from the base `typing` module.

```python
from typing_extensions import TypedDict


class Foobar(TypedDict):
    count: int


def bar(n: int) -> Foobar:
    return Foobar(count=n)
```

## Pypi

This library is hosted on Pypi. You can find the latest version on the [pypi polyapi-python](https://pypi.org/project/polyapi-python/) project.


## Upgrade

To upgrade your library to the latest version, pass the upgrade flag.

```bash
pip install polyapi-python --upgrade
```

## Pre-Release

To upgrade your library to the latest dev version, pass the `--pre` flag.

```bash
pip install polyapi-python --pre --upgrade
```

## Change Your API Key

If you need to change your API key or what server you are pointing to, you can run:

```bash
python -m polyapi setup
```

## Unit Tests

To run this library's unit tests, please clone the repo then run:

```bash
python -m unittest discover
```

## Linting

The flake8 config is at the root of this repo at `.flake8`.

When hacking on this library, please enable flake8 and add this line to your flake8 args (e.g., in your VSCode Workspace Settings):

```
--config=.flake8
```

## Mypy Type Improvements

This script is handy for checking for any mypy types:

```bash
./check_mypy.sh
```

Please ignore \[name-defined\] errors for now. This is a known bug we are working to fix!

## Strategies for QA'ing Changes To Generate Or Other Core Functionality

Our https://na1.polyapi.io has a large OOB catalog (as does eu1/na2). We also have several big internal PolyAPI projects with Python (message @eupharis if you need a pointer to which ones).

Running `python -m polyapi generate` in all these projects and then checking the flake8 and check_mypy steps above is a great way to build confidence that the `generate` changes has no gotchas.

Of course all this is in addition to the changes passing through normal unittests and integration tests!

## Support

If you run into any issues or want help getting started with this project, please contact support@polyapi.io
.
