import sys
import unittest
from unittest.mock import mock_open, patch

from polyapi.cli import execute_from_cli
from polyapi.function_cli import function_add_or_update


class T(unittest.TestCase):
    @patch("polyapi.cli.initialize_config")
    @patch("polyapi.cli.function_add_or_update")
    def test_function_add_forwards_image(self, mock_add, _mock_initialize):
        with patch.object(
            sys,
            "argv",
            [
                "polyapi",
                "function",
                "add",
                "my_func",
                "foo.py",
                "--server",
                "--image",
                "python:3.12",
            ],
        ):
            execute_from_cli()

        kwargs = mock_add.call_args.kwargs
        self.assertEqual(kwargs["image"], "python:3.12")
        self.assertNotIn("skip_toolkit_build", kwargs)

    def test_function_add_skip_toolkit_build_removed(self):
        with patch.object(
            sys,
            "argv",
            [
                "polyapi",
                "function",
                "add",
                "my_func",
                "foo.py",
                "--server",
                "--skip-toolkit-build",
            ],
        ):
            with self.assertRaises(SystemExit) as cm:
                execute_from_cli()

        self.assertEqual(cm.exception.code, 2)

    @patch("polyapi.function_cli._func_already_exists", return_value=False)
    @patch("polyapi.function_cli.parse_function_code")
    @patch("polyapi.function_cli.get_jsonschema_type", side_effect=lambda type_name: type_name)
    @patch("polyapi.function_cli.get_api_key_and_url", return_value=("api-key", "https://api.example.com"))
    @patch("polyapi.function_cli.get_auth_headers", return_value={"Authorization": "Bearer api-key"})
    @patch("polyapi.function_cli.http_client.post")
    def test_function_add_includes_image_in_server_payload(
        self,
        mock_post,
        _mock_headers,
        _mock_api_config,
        _mock_jsonschema,
        mock_parse,
        _mock_exists,
    ):
        mock_parse.return_value = {
            "context": "demo",
            "types": {
                "description": "",
                "returns": {"type": "int"},
                "params": [{"name": "arg", "type": "str", "typeSchema": None, "description": ""}],
            },
            "config": {},
            "dependencies": [],
        }

        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"id": "fn-123"}

        with patch("builtins.open", mock_open(read_data="def my_func(arg: str) -> int:\n    return 1\n")):
            function_add_or_update(
                name="my_func",
                file="foo.py",
                context="demo",
                description="",
                client=False,
                server=True,
                logs_enabled=None,
                generate_contexts=None,
                visibility="ENVIRONMENT",
                image="python:3.12",
                generate=False,
                execution_api_key="",
            )

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["image"], "python:3.12")
        self.assertNotIn("skipToolkitBuild", payload)
