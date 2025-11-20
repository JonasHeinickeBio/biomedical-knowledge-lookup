import unittest
from aid_pais_knowledgegraph.knowledge_lookup.central_lookup import CentralLookup

class TestAdapterSessionSingleton(unittest.TestCase):
    def test_singleton_session(self):
        # Create two CentralLookup instances
        lookup1 = CentralLookup()
        lookup2 = CentralLookup()
        # Their sessions should be the same object
        self.assertIs(lookup1.session, lookup2.session)
        # Adapters should be initialized only once
        self.assertIs(lookup1.adapters, lookup2.adapters)

if __name__ == "__main__":
    unittest.main()
