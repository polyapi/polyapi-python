# PolyAPI Python Client

This is the PolyAPI Python client.

Please set the following environment variables:

## 1. Setup Env

```bash
POLY_API_KEY='your_key'
POLY_API_BASE_URL='your_server'  # e.g. na1.polyapi.io
```

## 2. Install Libraries

Then run the following

```bash
pip3 install git+https://github.com/polyapi/polyapi-python.git
```

## 3. Generate Your Functions

Now you can run the following to generate your library

```bash
python3 -m polyapi generate
```

## 4. Test

That's it! Now open up a test file and you can run some code like so:

```python
from polyapi import poly
print(poly.polyapi.function.api.list(my_server, my_api_key))
```

## Unit Tests

To run this library's unit tests, please clone the repo then run:

```
python3 -m unittest discover
```