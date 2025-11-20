import unittest
from unittest.mock import MagicMock, patch

from knowledge_lookup.src import factory


class TestFactory(unittest.TestCase):
    @patch("knowledge_lookup.src.factory.create_adapter")
    def test_create_adapter(self, mock_create):
        mock_create.return_value = MagicMock()
        adapter = factory.create_adapter("dbpedia", MagicMock())
        self.assertIsNotNone(adapter)


if __name__ == "__main__":
    unittest.main()
