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

### 3. Test

That's it! Now open up a test file and you can run some code like so:

```python
from polyapi import poly
print(poly.polyapi.function.api.list(my_server, my_api_key))
```


## Add New Server Functions

To add a new server function, please follow the quickstart. Then you can add a server function like so:

```bash
python -m polyapi --context mycontext --description mydesc --server function add <function_name> foo.py
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

## Support

If you run into any issues or want help getting started with this project, please contact support@polyapi.io