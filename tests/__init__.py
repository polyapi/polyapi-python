"""Shared test bootstrap for unittest discovery."""

from pathlib import Path


# Some imports in `polyapi` expect the generated package directory to exist.
Path(__file__).resolve().parents[1].joinpath("polyapi", "poly").mkdir(parents=True, exist_ok=True)
