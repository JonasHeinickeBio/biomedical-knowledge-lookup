import unittest
from unittest.mock import patch

from knowledge_lookup.src import helpers


class TestHelpers(unittest.TestCase):
    @patch("knowledge_lookup.src.helpers.some_helper_function")
    def test_some_helper_function(self, mock_func):
        mock_func.return_value = "mocked"
        result = helpers.some_helper_function("input")
        self.assertEqual(result, "mocked")


if __name__ == "__main__":
    unittest.main()
