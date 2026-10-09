"""Unit tests for the helpers shared by the OmicsDI / BioStudies / PRIDE adapters."""

import asyncio
from unittest.mock import patch

import pytest

from knowledge_lookup.adapters import _omics_common as common

pytestmark = pytest.mark.unit


class TestStripHtml:
    def test_removes_tags_and_collapses_space(self):
        assert common.strip_html("A<br>B  <em>C</em>\n D") == "A B C D"

    @pytest.mark.parametrize("value", [None, 5, ["x"], ""])
    def test_non_text_gives_empty(self, value):
        assert common.strip_html(value) == ""


class TestIsoDate:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("20150608", "2015-06-08"),
            ("2015-06-08", "2015-06-08"),
            ("2009/05/12", "2009-05-12"),
            ("2025-02-24T00:00:00Z", "2025-02-24"),
            ("2023-08-05 15:51:05", "2023-08-05"),
            ("Wed Nov 09 17:18:00 GMT 2022", "2022-11-09"),
            (1242086400000, "2009-05-12"),
            (1242086400000.0, "2009-05-12"),
            ("", None),
            (None, None),
            (False, None),
            ("not a date", None),
            (10**30, None),
        ],
    )
    def test_formats(self, raw, expected):
        assert common.iso_date(raw) == expected


class TestTaxonId:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("9606", "9606"),
            ("Homo Sapiens (ncbitaxon:9606)", "9606"),
            ("NEWT:10090", "10090"),
            ("taxid: 562", "562"),
            ("Homo sapiens (Human)", "9606"),
            ("Mus musculus", "10090"),
            ("Unknown species", None),
            (None, None),
        ],
    )
    def test_extraction(self, raw, expected):
        assert common.taxon_id(raw) == expected


def test_dedupe_keeps_order_and_drops_empty():
    assert common.dedupe(["b", "a", "b", "", "a", "c"]) == ["b", "a", "c"]


def test_relationship_drops_none_extras():
    item = common.relationship("has_x", "X:1", "x", "SRC", score=None, doi="10.1/x")
    assert item == {
        "relation_label": "has_x",
        "related_id": "X:1",
        "related_name": "x",
        "source": "SRC",
        "doi": "10.1/x",
    }


def test_mapping_has_contract_keys():
    item = common.mapping("A", "B", "SRC", "DST", "related", 0.5)
    assert set(item) == {"fromId", "toId", "fromSource", "toSource", "mappingType", "confidence"}
    assert item["mappingType"] == "related" and item["confidence"] == 0.5


class TestRequestThrottle:
    def test_sleeps_for_remaining_interval_only(self):
        """Patched clock and sleep: no wall-clock dependence, ordering asserted."""
        clock = {"now": 100.0}
        sleeps: list[float] = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            clock["now"] += seconds

        throttle = common.RequestThrottle(interval=0.5)

        async def run():
            await throttle.wait()  # first call never sleeps
            clock["now"] += 0.2  # 0.2 s of other work
            await throttle.wait()  # must wait the remaining 0.3 s
            clock["now"] += 1.0  # longer than the interval
            await throttle.wait()  # no sleep needed

        with (
            patch.object(common.time, "monotonic", side_effect=lambda: clock["now"]),
            patch.object(common.asyncio, "sleep", side_effect=fake_sleep),
        ):
            asyncio.run(run())
        assert len(sleeps) == 1
        assert sleeps[0] == pytest.approx(0.3, abs=1e-6)

    def test_zero_interval_never_sleeps(self):
        throttle = common.RequestThrottle(interval=0)
        with patch.object(common.asyncio, "sleep") as fake_sleep:

            async def run():
                for _ in range(3):
                    await throttle.wait()

            asyncio.run(run())
        fake_sleep.assert_not_called()
