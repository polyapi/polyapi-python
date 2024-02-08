import unittest

from polyapi.auth import render_auth_function

GET_TOKEN = {
    "type": "authFunction",
    "id": "dummyid",
    "context": "auth0.authCodeFlow",
    "name": "getToken",
    "description": "This function obtains a token from authO using the OAuth 2.0 authorization code flow. It will return a login url if the user needs to log in, a token once they are logged in, and an error if the user fails to log in. It allows an optional callback url where the user is going to be redirected after log in. If the refresh token flow is enabled, the refresh token will be stored on the poly server.",
    "function": {
        "arguments": [
            {
                "name": "clientId",
                "required": True,
                "type": {"kind": "primitive", "type": "string"},
            },
            {
                "name": "clientSecret",
                "required": True,
                "type": {"kind": "primitive", "type": "string"},
            },
            {
                "name": "scopes",
                "required": True,
                "type": {
                    "kind": "array",
                    "items": {"kind": "primitive", "type": "string"},
                },
            },
            {
                "name": "callback",
                "required": True,
                "type": {
                    "kind": "function",
                    "name": "AuthFunctionCallback",
                    "spec": {
                        "arguments": [
                            {
                                "name": "token",
                                "required": False,
                                "nullable": True,
                                "type": {"kind": "primitive", "type": "string"},
                            },
                            {
                                "name": "url",
                                "required": False,
                                "type": {"kind": "primitive", "type": "string"},
                            },
                            {
                                "name": "error",
                                "required": False,
                                "nullable": True,
                                "type": {"kind": "primitive", "type": "object"},
                            },
                        ],
                        "returnType": {"kind": "void"},
                        "synchronous": True,
                    },
                },
            },
            {
                "name": "options",
                "required": False,
                "type": {
                    "kind": "object",
                    "properties": [
                        {
                            "name": "callbackUrl",
                            "required": False,
                            "type": {"kind": "primitive", "type": "string"},
                        },
                        {
                            "name": "timeout",
                            "required": False,
                            "type": {"kind": "primitive", "type": "number"},
                        },
                        {
                            "name": "audience",
                            "required": False,
                            "type": {"kind": "primitive", "type": "string"},
                        },
                        {
                            "name": "autoCloseOnToken",
                            "required": False,
                            "type": {"kind": "primitive", "type": "boolean"},
                        },
                        {
                            "name": "autoCloseOnUrl",
                            "required": False,
                            "type": {"kind": "primitive", "type": "boolean"},
                        },
                        {
                            "name": "userId",
                            "required": False,
                            "type": {"kind": "primitive", "type": "string"},
                        },
                    ],
                },
            },
        ],
        "returnType": {
            "kind": "object",
            "properties": [
                {
                    "name": "close",
                    "type": {
                        "kind": "function",
                        "spec": {
                            "arguments": [],
                            "returnType": {"kind": "void"},
                            "synchronous": True,
                        },
                    },
                    "required": True,
                }
            ],
        },
        "synchronous": True,
    },
    "visibilityMetadata": {"visibility": "ENVIRONMENT"},
}


class T(unittest.TestCase):
    def test_render_get_token(self):
        # same test but try it as a serverFunction rather than an apiFunction
        func_str, _ = render_auth_function(
            "atuhFunction",
            GET_TOKEN["name"],
            GET_TOKEN["id"],
            GET_TOKEN["description"],
            GET_TOKEN["function"]["arguments"],
            GET_TOKEN["function"]["returnType"],
        )
        self.assertIn(GET_TOKEN["id"], func_str)
        # self.assertIn("conversationSID: str", func_str)
        # self.assertIn("authToken: str", func_str)
        # self.assertIn(f"-> _{name}.ResponseType", func_str)
