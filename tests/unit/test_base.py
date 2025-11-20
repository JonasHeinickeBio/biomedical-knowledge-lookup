import unittest
from unittest.mock import MagicMock, patch

from knowledge_lookup.src import base


class TestKnowledgeSourceAdapter(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock()
        # Use MagicMock for abstract base class
        self.adapter = MagicMock(spec=base.KnowledgeSourceAdapter)

    def test_get_source_abstract(self):
        with self.assertRaises(NotImplementedError):
            base.KnowledgeSourceAdapter.get_source(self.adapter)

    @patch("knowledge_lookup.src.base.KnowledgeSourceAdapter.search_concepts")
    def test_search_concepts_abstract(self, mock_search):
        mock_search.side_effect = NotImplementedError
        with self.assertRaises(NotImplementedError):
            self.adapter.search_concepts("test")


if __name__ == "__main__":
    unittest.main()
