import unittest

from .test_api import TWILIO
from polyapi.server import render_server_function

GET_PRODUCTS_COUNT = {
    "id": "8f7d24b0-4a29-40c0-9091",
    "type": "serverFunction",
    "context": "test",
    "name": "getProductsCount111",
    "description": "An API call to retrieve the count of products in the product list.",
    "requirements": ["snabbdom"],
    "function": {
        "arguments": [
            {
                "name": "products",
                "required": False,
                "type": {
                    "kind": "array",
                    "items": {"kind": "primitive", "type": "string"},
                },
            }
        ],
        "returnType": {"kind": "plain", "value": "number"},
        "synchronous": True,
    },
    "code": "",
    "language": "javascript",
    "visibilityMetadata": {"visibility": "ENVIRONMENT"},
}


class T(unittest.TestCase):
    def test_render_function_twilio_server(self):
        # same test but try it as a serverFunction rather than an apiFunction
        name = TWILIO["name"]
        func_str, _ = render_server_function(
            "serverFunction",
            TWILIO["name"],
            TWILIO["id"],
            TWILIO["description"],
            TWILIO["function"]["arguments"],
            TWILIO["function"]["returnType"],
        )
        self.assertIn(TWILIO["id"], func_str)
        self.assertIn("conversationSID: str", func_str)
        self.assertIn("authToken: str", func_str)
        self.assertIn(f"-> _{name}.ResponseType", func_str)

    def test_render_function_get_products_count(self):
        return_type = GET_PRODUCTS_COUNT["function"]["returnType"]
        func_str, _ = render_server_function(
            GET_PRODUCTS_COUNT["type"],
            GET_PRODUCTS_COUNT["name"],
            GET_PRODUCTS_COUNT["id"],
            GET_PRODUCTS_COUNT["description"],
            GET_PRODUCTS_COUNT["function"]["arguments"],
            return_type,
        )
        self.assertIn(GET_PRODUCTS_COUNT["id"], func_str)
        self.assertIn("products: List[str]", func_str)
        self.assertIn("-> float", func_str)