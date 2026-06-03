The PolyAPI Python SDK lets you use and define PolyAPI functions using Python.

# Commands:

Use venv in .venv for all commands! Python3.14+ preferred.

If .venv does not exist, prompt user to create it via VSCode.

* install local environment: pip install -r dev_requirements.txt
* tests: python -m unittest discover
* lint: flake8 --config=.flake8
* mypy: ./check_mypy.sh
* generate the `polyapi` library: python -m polyapi generate

tests+lint+mypy+generate should all pass after any change

# Notes for contributors

* Always run commands with the workspace venv executable path when possible (for example, .venv/bin/python -m unittest discover).
* Linting is scoped in .flake8 to exclude generated SDK trees and virtualenv directories.
* Type checking is intentionally scoped in check_mypy.sh to maintained core modules and uses --follow-imports=skip to avoid generated/transitive module noise.
* If you change no-types schema generation, update the template in polyapi/generate.py:create_empty_schemas_module (not only polyapi/schemas/__init__.py), then re-run tests.
