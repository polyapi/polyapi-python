from os import read
import unittest
from mock import patch

from polyapi.rendered_spec import get_and_update_rendered_spec


class T(unittest.TestCase):
    def test_get_and_update_rendered_spec_fail(self):
        """ pass in a bad id to update and make sure it returns False
        """
        updated = get_and_update_rendered_spec("123")
        self.assertFalse(updated)

    @patch("polyapi.rendered_spec.read_cached_specs")
    def test_get_and_update_rendered_spec_success(self, read_cached_specs):
        """ pass in a bad id to update and make sure it returns False
        """
        read_cached_specs.return_value = [{"id": "123"}]
        updated = get_and_update_rendered_spec("123")
        self.assertEqual(read_cached_specs.call_count, 1)
        self.assertTrue(updated)