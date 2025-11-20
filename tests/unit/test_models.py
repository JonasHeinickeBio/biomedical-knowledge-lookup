import unittest

from knowledge_lookup.src import models


class TestKnowledgeSourceEnum(unittest.TestCase):
    def test_enum_members(self):
        sources = [s.value for s in models.KnowledgeSource]
        self.assertIn("umls", sources)
        self.assertIn("ols", sources)
        self.assertIn("bioportal", sources)
        self.assertIn("ensembl", sources)


class TestUnifiedConcept(unittest.TestCase):
    def test_unified_concept_creation(self):
        concept = models.UnifiedConcept(
            primary_id="C123", primary_label="Test", concept_type=models.ConceptType.UNKNOWN
        )
        self.assertEqual(concept.primary_id, "C123")
        self.assertEqual(concept.primary_label, "Test")
        self.assertEqual(concept.concept_type, models.ConceptType.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
