"""Regression tests for the optional tenant-generated ``poly`` package."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_without_generated_poly(source: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temporary_directory:
        checkout = Path(temporary_directory)
        shutil.copytree(
            REPO_ROOT / "polyapi",
            checkout / "polyapi",
            ignore=shutil.ignore_patterns("poly", "__pycache__"),
        )
        assert not (checkout / "polyapi" / "poly").exists()
        return subprocess.run(
            [sys.executable, "-c", source, "lifecycle-harness"],
            cwd=checkout,
            capture_output=True,
            check=False,
            text=True,
        )


class TestGeneratedPolyBoundary(unittest.TestCase):
    def test_core_http_client_import_does_not_require_generated_poly(self):
        result = _run_without_generated_poly(
            "import polyapi; import polyapi.http_client; "
            "assert 'poly' not in vars(polyapi)"
        )

        self.assertEqual(result.returncode, 0, result.stderr)


    def test_generated_poly_access_requires_generated_package(self):
        result = _run_without_generated_poly("from polyapi import poly")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No 'poly' found.", result.stderr)
        self.assertIn("python3 -m polyapi generate", result.stderr)
