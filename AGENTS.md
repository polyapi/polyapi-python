The PolyAPI Python SDK lets you use and define PolyAPI functions using Python.

# Commands:

* install local environment: pip install -r dev_requirements.txt
* tests: python -m unittest discover
* lint: flake8 --config=.flake8
* mypy: ./check_mypy.sh
* generate the `polyapi` library: python -m polyapi generate

tests+lint+mypy+generate should all pass after any change

# Notes for contributors

* Always run commands with the workspace venv executable path when possible (for example, .venv/bin/python -m unittest discover).
* If .venv does not exist, prompt user to create it via VSCode.

# Generated Directories

The following directories are generated. Do not change them directly, alter the code that generates them in `polyapi/generate.py`:

* polyapi/poly
* polyapi/schemas
* polyapi/tabi
* polyapi/vari