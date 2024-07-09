import unittest
from mock import patch, Mock

from polyapi.rendered_spec import get_and_update_rendered_spec

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
    @patch("polyapi.rendered_spec._get_spec")
    def test_get_and_update_rendered_spec_fail(self, _get_spec):
        """ pass in a bad id to update and make sure it returns False
        """
        _get_spec.return_value = None
        updated = get_and_update_rendered_spec("123")
        self.assertEqual(_get_spec.call_count, 1)
        self.assertFalse(updated)

    @patch("polyapi.rendered_spec.requests.post")
    @patch("polyapi.rendered_spec._get_spec")
    def test_get_and_update_rendered_spec_success(self, _get_spec, post):
        """ pass in a bad id to update and make sure it returns False
        """
        _get_spec.return_value = GET_PRODUCTS_COUNT
        post.return_value = Mock(status_code=201, text="Created")
        updated = get_and_update_rendered_spec("123")
        self.assertEqual(_get_spec.call_count, 1)
        self.assertTrue(updated)