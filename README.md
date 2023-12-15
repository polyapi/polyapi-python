# PolyAPI Python Library

The PolyAPI Python Library lets you use and define PolyAPI functions using Python.

## PolyAPI Quickstart

### 1. Install Libraries

First install the client:

```bash
pip install git+https://github.com/polyapi/polyapi-python.git
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

```
python -m polyapi --context mycontext --description mydesc --server function add <function_name> foo.py
```

The code in `foo.py` should contain a single defined function named the same as your `<function_name>` variable.

So for example, if you want to add a function named `bar`, your file `foo.py` would look like this:

```
def bar():
    return "Hello World"
```

Pro-tip: after adding your function, be sure to re-run:

```
python -m polyapi generate
```

So that you can see your new function in your library!


## Upgrade

To upgrade your library to the latest version, pass the upgrade flag.:

```bash
pip install git+https://github.com/polyapi/polyapi-python.git --upgrade
```

## Unit Tests

To run this library's unit tests, please clone the repo then run:

```
python -m unittest discover
```