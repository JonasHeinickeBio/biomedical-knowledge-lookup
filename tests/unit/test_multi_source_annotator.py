import unittest
from unittest.mock import MagicMock, patch

from knowledge_lookup.src import multi_source_annotator


class TestMultiSourceAnnotator(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock()
        self.annotator = multi_source_annotator.MultiSourceAnnotator(self.config)

    @patch("knowledge_lookup.src.multi_source_annotator.MultiSourceAnnotator.annotate")
    def test_annotate(self, mock_annotate):
        mock_annotate.return_value = ["annotation1", "annotation2"]
        result = self.annotator.annotate("test")
        self.assertEqual(result, ["annotation1", "annotation2"])


if __name__ == "__main__":
    unittest.main()
