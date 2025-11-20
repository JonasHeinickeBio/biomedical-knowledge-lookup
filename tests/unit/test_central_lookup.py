import unittest
from unittest.mock import MagicMock, patch

from knowledge_lookup.src import central_lookup


class TestCentralKnowledgeLookup(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock()
        self.lookup = central_lookup.CentralKnowledgeLookup(self.config)

    @patch("knowledge_lookup.src.central_lookup.CentralKnowledgeLookup.search_concepts")
    def test_search_concepts(self, mock_search):
        mock_search.return_value = ["concept1", "concept2"]
        result = self.lookup.search_concepts("test")
        self.assertEqual(result, ["concept1", "concept2"])

    @patch("knowledge_lookup.src.central_lookup.CentralKnowledgeLookup.get_concept_details")
    def test_get_concept_details(self, mock_details):
        mock_details.return_value = {"id": "C123", "label": "Test"}
        result = self.lookup.get_concept_details("C123")
        self.assertEqual(result, {"id": "C123", "label": "Test"})


if __name__ == "__main__":
    unittest.main()
