"""Unit tests for NCIEVSAdapter (NCI Thesaurus / Metathesaurus via the EVS REST API); no network.

``tests/fixtures/ncievs_responses.py`` holds real EVS answers (long lists trimmed, every
code-bearing synonym kept); hand-built payloads cover shapes the live API only produces for
other concepts (inactive concepts, odd relation types, oversized inverse lists).
"""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_lookup.adapters import ncievs_adapter
from knowledge_lookup.adapters.ncievs_adapter import NCIEVSAdapter
from knowledge_lookup.models import ConceptType, KnowledgeSource
from tests.fixtures.ncievs_responses import RECORDED, request_key

pytestmark = pytest.mark.unit

BASE = "https://api-evsrest.nci.nih.gov/api/v1"


class NotFound(Exception):
    status = 404


@pytest.fixture(autouse=True)
def no_spacing(monkeypatch):
    monkeypatch.setattr(ncievs_adapter, "_MIN_INTERVAL", 0.0)


@pytest.fixture
def adapter(lookup_config):
    return NCIEVSAdapter(lookup_config)


def replay(extra=None):
    """Fake ``_make_request`` answering from the recorded live responses."""
    extra = extra or {}

    async def fake(url, params=None, headers=None, json_data=None):
        key = request_key(url, params)
        if key in extra:
            value = extra[key]
            if isinstance(value, Exception):
                raise value
            return copy.deepcopy(value)
        if key not in RECORDED:
            raise AssertionError(f"unrecorded request: {key}")
        return copy.deepcopy(RECORDED[key])

    return fake


def concept_payload(code="C1", name="Thing", **extra):
    return {"code": code, "name": name, "terminology": "ncit", "active": True, **extra}


class TestBasics:
    def test_source_and_availability(self, adapter):
        assert adapter.get_source() == KnowledgeSource.NCIEVS
        assert adapter.is_available() is True
        assert adapter.default_terminology == "ncit"

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("ncit", "ncit"),
            ("NCIT", "ncit"),
            (" NCIM ", "ncim"),
            ("SNOMEDCT", "snomedct_us"),
            ("snomed", "snomedct_us"),
            ("LOINC", "lnc"),
            ("MedDRA", "mdr"),
            ("icd10cm", "icd10cm"),
            ("nci_thesaurus", "ncit"),
            ("bad name!", None),
            ("", None),
            (None, None),
            ("1abc", None),
        ],
    )
    def test_normalize_terminology(self, raw, expected):
        assert NCIEVSAdapter.normalize_terminology(raw) == expected

    @pytest.mark.parametrize(
        "raw,terminology,expected",
        [
            ("C3036", None, ("ncit", "C3036")),
            ("c3036", None, ("ncit", "C3036")),
            ("NCIT:C3036", None, ("ncit", "C3036")),
            ("ncit: c3036", None, ("ncit", "C3036")),
            ("NCIM:C0015672", None, ("ncim", "C0015672")),
            ("C0015672", None, ("ncim", "C0015672")),  # bare 7-digit CUI
            ("CL412928", None, ("ncim", "CL412928")),
            ("C0015672", "ncit", ("ncit", "C0015672")),  # explicit terminology wins
            ("C3036", "NCIM", ("ncim", "C3036")),
            ("SNOMEDCT:52702003", None, ("snomedct_us", "52702003")),
            ("snomedct_us:52702003", None, ("snomedct_us", "52702003")),
            ("icd10cm:G93.32", None, ("icd10cm", "G93.32")),
            ("52702003", "snomedct_us", ("snomedct_us", "52702003")),
        ],
    )
    def test_parse_id(self, adapter, raw, terminology, expected):
        assert adapter._parse_id(raw, terminology) == expected

    @pytest.mark.parametrize(
        "raw",
        ["", "   ", None, "ncit:", "bad id!", "a/b", "ncit:C3036/children", ":C3036", "x y:C1"],
    )
    def test_parse_id_rejects_garbage(self, adapter, raw):
        assert adapter._parse_id(raw) is None

    def test_default_terminology_can_be_changed(self, adapter):
        adapter.default_terminology = "ncim"
        assert adapter._parse_id("C3036") == ("ncim", "C3036")


class TestSearch:
    @pytest.mark.asyncio
    async def test_ncit_search(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())) as req:
            results = await adapter.search_concepts("fatigue", limit=3)
        url, params = req.call_args.args
        assert url == f"{BASE}/concept/ncit/search"
        assert params == {
            "term": "fatigue",
            "pageSize": 3,
            "include": "summary",
            "type": "contains",
        }
        assert [c.primary_id for c in results] == ["NCIT:C3036", "NCIT:C146753", "NCIT:C122347"]
        fatigue = results[0]
        assert fatigue.primary_label == "Fatigue"
        assert fatigue.concept_type == ConceptType.SYMPTOM
        assert fatigue.semantic_types == ["Sign or Symptom"]
        assert "Fatigue (lassitude)" in fatigue.synonyms and "Fatigue" not in fatigue.synonyms
        assert fatigue.definitions[0] == "Overall tiredness and lack of energy."
        assert fatigue.categories == ["ncit"]
        assert fatigue.confidence_score == 0.9
        assert ("UMLS", "C0015672") in {(str(i.source), i.identifier) for i in fatigue.identifiers}
        data = fatigue.source_data[KnowledgeSource.NCIEVS]
        assert data["terminology"] == "ncit" and data["code"] == "C3036"
        assert data["version"] == "26.09d"
        assert results[1].concept_type == ConceptType.OBSERVATION  # semantic type "Finding"
        assert results[2].concept_type == ConceptType.UNKNOWN  # "Functional Concept"

    @pytest.mark.asyncio
    async def test_ncim_search_by_argument(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())) as req:
            results = await adapter.search_concepts("fatigue", limit=3, terminology="NCIM")
        assert req.call_args.args[0] == f"{BASE}/concept/ncim/search"
        assert [c.primary_id for c in results] == [
            "NCIM:C0015672",
            "NCIM:CL412928",
            "NCIM:CL550640",
        ]
        fatigue = results[0]
        identifiers = {(str(i.source), i.identifier) for i in fatigue.identifiers}
        # code-bearing NCIM synonyms become cross-reference identifiers
        assert ("HPO", "HP:0012378") in identifiers
        assert ("MEDLINEPLUS", "5324") in identifiers
        assert ("MESH", "D005221") in identifiers
        assert ("LOINC", "LA7542-9") in identifiers
        assert not any(i.startswith("MTHU") for _, i in identifiers)
        # the NCIM definition is a whole MedlinePlus page; HTML is turned into text
        assert (
            "<h3>" not in fatigue.definitions[0] and "What is fatigue?" in fatigue.definitions[0]
        )

    @pytest.mark.asyncio
    async def test_no_hits(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            assert await adapter.search_concepts("zzzzqqqq", limit=3) == []

    @pytest.mark.asyncio
    async def test_limit_page_size_and_search_type(self, adapter):
        body = {"total": 3, "concepts": [concept_payload(f"C{i}", f"N{i}") for i in range(1, 4)]}
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)) as req:
            two = await adapter.search_concepts("x", limit=2)
            await adapter.search_concepts("x", limit=5000, search_type="match")
            await adapter.search_concepts("x", search_type="bogus")
        assert len(two) == 2
        assert req.call_args_list[0].args[1]["pageSize"] == 2
        assert req.call_args_list[1].args[1]["pageSize"] == ncievs_adapter.MAX_PAGE
        assert req.call_args_list[1].args[1]["type"] == "match"
        assert req.call_args_list[2].args[1]["type"] == "contains"

    @pytest.mark.asyncio
    async def test_duplicates_and_nameless_entries_are_dropped(self, adapter):
        body = {
            "concepts": [
                concept_payload("C1", "One"),
                concept_payload("C1", "One again"),
                {"code": "C2"},
                "junk",
                concept_payload("C3", "Three"),
            ]
        }
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)):
            results = await adapter.search_concepts("x")
        assert [c.primary_id for c in results] == ["NCIT:C1", "NCIT:C3"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query,limit,terminology",
        [("", 5, None), ("  ", 5, None), (None, 5, None), ("x", 0, None), ("x", 5, "bad name!")],
    )
    async def test_invalid_input_makes_no_request(self, adapter, query, limit, terminology):
        with patch.object(adapter, "_make_request", AsyncMock()) as req:
            assert await adapter.search_concepts(query, limit, terminology=terminology) == []
        req.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("body", [None, [], {}, {"concepts": None}, "text"])
    async def test_unexpected_bodies(self, adapter, body):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)):
            assert await adapter.search_concepts("x") == []

    @pytest.mark.asyncio
    async def test_http_error(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("503"))):
            assert await adapter.search_concepts("x") == []


class TestDetails:
    @pytest.mark.asyncio
    async def test_ncit_details(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())) as req:
            fatigue = await adapter.get_concept_details("NCIT:C3036")
            bare = await adapter.get_concept_details("c3036")
        assert req.call_args_list[0].args[0] == f"{BASE}/concept/ncit/C3036"
        assert req.call_args_list[0].args[1] == {"include": "summary,parents,children"}
        assert fatigue.primary_id == bare.primary_id == "NCIT:C3036"
        assert fatigue.parents == ["NCIT:C3858"]
        assert "NCIT:C180621" in fatigue.children and len(fatigue.children) == 5

    @pytest.mark.asyncio
    async def test_disease_details(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            cfs = await adapter.get_concept_details("NCIT:C3037")
        assert cfs.primary_label == "Chronic Fatigue Syndrome"
        assert cfs.concept_type == ConceptType.DISEASE
        assert cfs.parents == ["NCIT:C3131"]
        assert any(i.identifier == "C0015674" for i in cfs.identifiers)

    @pytest.mark.asyncio
    async def test_ncim_details_with_bare_cui(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())) as req:
            concept = await adapter.get_concept_details("C0015672")
        assert req.call_args.args[0] == f"{BASE}/concept/ncim/C0015672"
        assert concept.primary_id == "NCIM:C0015672"
        assert concept.parents[0] == "NCIM:C0004093"
        assert concept.categories == ["ncim"]

    @pytest.mark.asyncio
    async def test_terminology_argument_and_other_terminologies(self, adapter):
        body = concept_payload("G93.32", "ME/CFS", terminology="icd10cm", version="2026")
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)) as req:
            concept = await adapter.get_concept_details("G93.32", terminology="icd10cm")
        assert req.call_args.args[0] == f"{BASE}/concept/icd10cm/G93.32"
        assert concept.primary_id == "ICD10CM:G93.32"

    @pytest.mark.asyncio
    async def test_not_found_and_invalid(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=NotFound())):
            assert await adapter.get_concept_details("NCIT:C0000000000") is None
        with patch.object(adapter, "_make_request", AsyncMock()) as req:
            assert await adapter.get_concept_details("bad id!") is None
            assert await adapter.get_concept_details("") is None
        req.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("body", [None, [], {}, {"message": "x"}, {"code": "C1"}])
    async def test_unexpected_bodies(self, adapter, body):
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)):
            assert await adapter.get_concept_details("NCIT:C1") is None

    @pytest.mark.asyncio
    async def test_http_error(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("503"))):
            assert await adapter.get_concept_details("NCIT:C1") is None

    def test_inactive_concept_has_low_confidence(self, adapter):
        concept = adapter._to_concept(concept_payload(active=False), "ncit")
        assert concept.confidence_score == 0.3

    @pytest.mark.parametrize(
        "semantic_type,expected",
        [
            ("Disease or Syndrome", ConceptType.DISEASE),
            ("Neoplastic Process", ConceptType.DISEASE),
            ("Gene or Genome", ConceptType.GENE),
            ("Pharmacologic Substance", ConceptType.DRUG),
            ("Therapeutic or Preventive Procedure", ConceptType.PROCEDURE),
            ("Laboratory Procedure", ConceptType.ASSAY),
            ("Cell", ConceptType.CELL_TYPE),
            ("Never heard of it", ConceptType.UNKNOWN),
        ],
    )
    def test_concept_type_from_semantic_type(self, adapter, semantic_type, expected):
        data = concept_payload(properties=[{"type": "Semantic_Type", "value": semantic_type}])
        assert adapter._to_concept(data, "ncit").concept_type == expected

    def test_first_known_semantic_type_wins(self, adapter):
        props = [
            {"type": "Semantic_Type", "value": "Funny"},
            {"type": "Semantic_Type", "value": "Cell"},
            {"type": "Semantic_Type", "value": "Tissue"},
        ]
        concept = adapter._to_concept(concept_payload(properties=props), "ncit")
        assert concept.concept_type == ConceptType.CELL_TYPE
        assert concept.semantic_types == ["Funny", "Cell", "Tissue"]

    def test_main_definition_comes_first_and_html_is_text(self, adapter):
        data = concept_payload(
            definitions=[
                {"definition": "alt <b>one</b>", "type": "ALT_DEFINITION"},
                {"definition": "main", "type": "DEFINITION"},
                {"definition": "main", "type": "ALT_DEFINITION"},
                {"definition": "", "type": "ALT_DEFINITION"},
            ]
        )
        assert adapter._to_concept(data, "ncit").definitions == ["main", "alt one"]


class TestRelationships:
    @pytest.mark.asyncio
    async def test_ncit_relationships(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())) as req:
            rels = await adapter.get_relationships("NCIT:C3036")
        assert req.call_args.args[1]["include"] == (
            "parents,children,roles,inverseRoles,associations,inverseAssociations"
        )
        assert rels[0] == {
            "relation_label": "is_a",
            "related_id": "NCIT:C3858",
            "related_name": "Mental and Behavioral Signs and Symptoms",
            "source": "NCIEVS",
            "direction": "outgoing",
        }
        labels = {r["relation_label"] for r in rels}
        assert {"is_a", "has_subclass", "Concept_In_Subset", "Disease_May_Have_Finding"} <= labels
        sub = next(r for r in rels if r["relation_label"] == "has_subclass")
        assert sub["direction"] == "incoming" and sub["related_id"].startswith("NCIT:C")
        finding = next(r for r in rels if r["relation_label"] == "Disease_May_Have_Finding")
        assert finding["direction"] == "incoming"
        for r in rels:
            assert {"relation_label", "related_id", "related_name", "source"} <= set(r)

    @pytest.mark.asyncio
    async def test_roles_are_typed(self, adapter):
        body = concept_payload(
            roles=[
                {
                    "code": "R101",
                    "type": "Disease_Has_Primary_Anatomic_Site",
                    "relatedCode": "C12735",
                    "relatedName": "Immune System",
                },
                {  # exact duplicate is dropped
                    "code": "R101",
                    "type": "Disease_Has_Primary_Anatomic_Site",
                    "relatedCode": "C12735",
                    "relatedName": "Immune System",
                },
                {"type": "no related code"},
            ]
        )
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)):
            rels = await adapter.get_relationships("NCIT:C1")
        assert rels == [
            {
                "relation_label": "Disease_Has_Primary_Anatomic_Site",
                "related_id": "NCIT:C12735",
                "related_name": "Immune System",
                "source": "NCIEVS",
                "direction": "outgoing",
            }
        ]

    @pytest.mark.asyncio
    async def test_ncim_relationships_use_rela_labels(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())):
            rels = await adapter.get_relationships("NCIM:C0015672")
        parent = rels[0]
        assert parent["relation_label"] == "is_a" and parent["related_id"] == "NCIM:C0004093"
        assert parent["asserted_by"] == "MDR"
        assert any(r["relation_label"] == "Concept_In_Subset" for r in rels)

    @pytest.mark.asyncio
    async def test_incoming_lists_are_capped(self, adapter):
        many = [
            {"type": "Disease_May_Have_Finding", "relatedCode": f"C{i}", "relatedName": f"D{i}"}
            for i in range(1, 251)
        ]
        body = concept_payload(inverseRoles=many, inverseAssociations=many[:3])
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)):
            rels = await adapter.get_relationships("NCIT:C1")
        assert len(rels) == ncievs_adapter.MAX_INVERSE

    @pytest.mark.parametrize(
        "item,label",
        [
            ({"type": "RO", "qualifiers": [{"type": "RELA", "value": "measures"}]}, "measures"),
            ({"type": "RO"}, "related_to"),
            ({"type": "RQ"}, "possibly_related_to"),
            ({"type": "RB"}, "broader_than"),
            ({"type": "RN", "qualifiers": [{"type": "OTHER", "value": "x"}]}, "narrower_than"),
            ({"type": "RO", "qualifiers": [{"type": "RELA", "value": ""}]}, "related_to"),
            ({"type": "Concept_In_Subset"}, "Concept_In_Subset"),
            ({}, "related_to"),
        ],
    )
    def test_relation_label(self, item, label):
        assert NCIEVSAdapter._relation_label(item) == label

    @pytest.mark.asyncio
    async def test_failures_give_nothing(self, adapter):
        assert await adapter.get_relationships("bad id!") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=NotFound())):
            assert await adapter.get_relationships("NCIT:C0") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_relationships("NCIT:C1") == []


class TestMappings:
    @pytest.mark.asyncio
    async def test_ncit_mappings_follow_the_cui_into_ncim(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())) as req:
            maps = await adapter.get_mappings("NCIT:C3037")
        urls = [c.args[0] for c in req.call_args_list]
        assert urls == [f"{BASE}/concept/ncit/C3037", f"{BASE}/concept/ncim/C0015674"]
        assert req.call_args_list[0].args[1] == {"include": "synonyms,maps,properties"}
        assert req.call_args_list[1].args[1] == {"include": "synonyms,maps"}
        by_target = {(m["toSource"], m["toId"]): m for m in maps}
        # from NCIt itself
        assert by_target[("UMLS", "C0015674")]["mappingType"] == "xref"
        assert by_target[("GDC", "comorbidities")]["mappingType"] == "Has Synonym"
        assert "via" not in by_target[("UMLS", "C0015674")]
        # from the Metathesaurus record of the CUI
        for key in [
            ("MESH", "D015673"),
            ("SNOMEDCT", "52702003"),
            ("ICD10CM", "G93.32"),
            ("ICD10CM", "R53.82"),
            ("MEDDRA", "10008874"),
            ("MEDLINEPLUS", "89"),
        ]:
            assert by_target[key]["via"] == "NCIM:C0015674", key
        for m in maps:
            if m["mappingType"] == "xref":
                assert m["fromId"] == "NCIT:C3037"
        # the CUI / NCIt code bridge is not repeated as a "via" mapping
        assert not [m for m in maps if m.get("via") and m["toSource"] in ("UMLS", "NCIT")]
        # SNOMED CT -> ICD-10-CM rule maps keep their rank and mapset
        rule = next(
            m for m in maps if m["fromId"] == "SNOMEDCT_US:52702003" and m["toId"] == "R53.82"
        )
        assert rule["toSource"] == "ICD10CM" and rule["rank"] == "1" and rule["confidence"] == 0.8
        assert rule["mapset"].startswith("SNOMEDCT_US_2026")
        for m in maps:
            assert {
                "fromId",
                "toId",
                "fromSource",
                "toSource",
                "mappingType",
                "confidence",
            } <= set(m)

    @pytest.mark.asyncio
    async def test_ncim_mappings(self, adapter):
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replay())) as req:
            maps = await adapter.get_mappings("C0015672")
        assert req.call_count == 1  # an NCIM concept needs no further hop
        by_target = {(m["toSource"], m["toId"]): m for m in maps}
        assert ("HPO", "HP:0012378") in by_target
        assert ("MESH", "D005221") in by_target
        assert ("NCIT", "C3036") in by_target and ("ICD10CM", "R53.83") in by_target
        assert ("LOINC", "LA7542-9") in by_target
        # Metathesaurus-generated placeholders are not real source codes
        assert not [m for m in maps if m["toId"].startswith("MTHU")]
        lower_rank = next(
            m for m in maps if m["toId"] == "R53.83" and m["fromId"] == "SNOMEDCT_US:248274002"
        )
        assert lower_rank["confidence"] == 0.6 and lower_rank["rank"] == "2"
        assert all("via" not in m for m in maps)

    @pytest.mark.asyncio
    async def test_property_xrefs_and_unknown_map_types(self, adapter):
        body = concept_payload(
            properties=[
                {"type": "UMLS_CUI", "value": "C1"},
                {"type": "OMIM_Number", "value": "123456"},
                {"type": "CAS_Registry", "value": "50-00-0"},
                {"type": "xRef", "value": "MESH:D1"},
                {"type": "xRef", "value": "noprefix"},
                {"type": "Semantic_Type", "value": "ignored"},
                {"type": "OMIM_Number", "value": ""},
            ],
            maps=[
                {"type": "Related To", "targetCode": "X1", "targetTerminology": "MedDRA"},
                {"type": "Has Synonym", "targetCode": "", "targetTerminology": "MedDRA"},
                "junk",
                {"targetCode": "Y2", "target": "icd10"},
            ],
        )
        ncim = concept_payload("C1", "Thing", terminology="ncim")
        replies = [body, ncim]
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=replies)):
            maps = await adapter.get_mappings("NCIT:C99")
        got = {(m["toSource"], m["toId"], m["mappingType"], m["confidence"]) for m in maps}
        assert ("UMLS", "C1", "xref", 0.9) in got
        assert ("OMIM", "123456", "xref", 0.9) in got
        assert ("CAS", "50-00-0", "xref", 0.9) in got
        assert ("MESH", "D1", "xref", 0.9) in got
        assert ("MEDDRA", "X1", "Related To", 0.6) in got
        assert ("ICD10", "Y2", "map", 0.6) in got
        assert not [m for m in maps if m["toId"] in ("noprefix", "ignored", "")]

    @pytest.mark.asyncio
    async def test_failed_ncim_hop_keeps_the_ncit_mappings(self, adapter):
        key_ncit = request_key(
            f"{BASE}/concept/ncit/C3037", {"include": "synonyms,maps,properties"}
        )
        key_ncim = request_key(f"{BASE}/concept/ncim/C0015674", {"include": "synonyms,maps"})
        fake = replay({key_ncit: RECORDED_NCIT_C3037, key_ncim: RuntimeError("down")})
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=fake)):
            maps = await adapter.get_mappings("NCIT:C3037")
        assert {m["toSource"] for m in maps} == {"UMLS", "GDC"}

    @pytest.mark.asyncio
    async def test_duplicates_are_removed(self, adapter):
        body = concept_payload(
            terminology="ncim",
            synonyms=[
                {"name": "a", "source": "MSH", "code": "D1"},
                {"name": "b", "source": "MSH", "code": "D1"},
                {"name": "c", "source": "MSH"},  # no code
                {"name": "d", "source": "AOD", "code": "9"},  # source not whitelisted
                {"name": "e", "source": "MTH", "code": "9"},
            ],
        )
        with patch.object(adapter, "_make_request", AsyncMock(return_value=body)):
            maps = await adapter.get_mappings("NCIM:C1")
        assert [(m["toSource"], m["toId"]) for m in maps] == [("MESH", "D1")]

    def test_own_terminology_codes_are_not_reported_as_cross_references(self, adapter):
        data = concept_payload(
            synonyms=[
                {"name": "a", "source": "NCI", "code": "C1"},
                {"name": "b", "source": "MSH", "code": "MTHU0001"},
                {"name": "c", "source": "MSH", "code": "D2"},
            ]
        )
        assert adapter._xref_pairs(data, "ncit") == [("MESH", "D2", "c")]

    @pytest.mark.asyncio
    async def test_failures_give_nothing(self, adapter):
        assert await adapter.get_mappings("bad id!") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=NotFound())):
            assert await adapter.get_mappings("NCIT:C0") == []
        with patch.object(adapter, "_make_request", AsyncMock(side_effect=RuntimeError("x"))):
            assert await adapter.get_mappings("NCIT:C1") == []


class TestSpacing:
    @pytest.mark.asyncio
    async def test_requests_are_spaced(self, adapter, monkeypatch):
        from knowledge_lookup.adapters import _vocab_common

        adapter._spacer.interval = 0.05
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(_vocab_common.asyncio, "sleep", fake_sleep)
        with patch.object(adapter, "_make_request", AsyncMock(return_value={"concepts": []})):
            await adapter.search_concepts("x")
            await adapter.search_concepts("x")
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.05 + 1e-6


RECORDED_NCIT_C3037 = next(v for k, v in RECORDED.items() if "ncit/C3037?include=synonyms" in k)
