"""Unit tests for the helpers shared by the Clinical Tables / NCI EVS / MedlinePlus adapters."""

import pytest

from knowledge_lookup.adapters import _vocab_common
from knowledge_lookup.adapters._vocab_common import Spacer, html_to_text

pytestmark = pytest.mark.unit


class TestHtmlToText:
    @pytest.mark.parametrize("markup", [None, "", "   "])
    def test_empty(self, markup):
        assert html_to_text(markup) == ""

    def test_plain_text_is_unchanged(self):
        assert html_to_text("just  some\ttext") == "just some text"

    def test_blocks_become_lines_and_inline_tags_vanish(self):
        markup = (
            "<h3>What is fatigue?</h3>\n<p>Fatigue is a <a href='x'>feeling</a> of "
            "<b>tiredness</b>.</p><ul><li>Sleep</li><li>Food &amp; drink</li></ul>"
        )
        assert html_to_text(markup) == (
            "What is fatigue?\n\nFatigue is a feeling of tiredness.\n\nSleep\n\nFood & drink"
        )

    def test_entities_are_decoded_and_blank_runs_collapse(self):
        assert html_to_text("a&nbsp;b<br><br><br><br>c &lt;d&gt;") == "a b\n\nc <d>"

    def test_unclosed_and_junk_markup_does_not_raise(self):
        assert html_to_text("<p>open <b>bold") == "open bold"
        assert html_to_text("1 < 2 and 3 > 2") == "1 < 2 and 3 > 2"


class TestSpacer:
    @pytest.mark.asyncio
    async def test_first_call_does_not_wait_and_later_calls_do(self, monkeypatch):
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(_vocab_common.asyncio, "sleep", fake_sleep)
        spacer = Spacer(0.5)
        await spacer.wait()
        await spacer.wait()
        assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.5 + 1e-6

    @pytest.mark.asyncio
    async def test_zero_interval_never_sleeps(self, monkeypatch):
        async def fail_sleep(seconds):
            raise AssertionError("slept")

        monkeypatch.setattr(_vocab_common.asyncio, "sleep", fail_sleep)
        spacer = Spacer(0.0)
        for _ in range(3):
            await spacer.wait()

    @pytest.mark.asyncio
    async def test_waits_on_the_clock_between_requests(self, monkeypatch):
        now = [100.0]
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds

        monkeypatch.setattr(_vocab_common.time, "monotonic", lambda: now[0])
        monkeypatch.setattr(_vocab_common.asyncio, "sleep", fake_sleep)
        spacer = Spacer(1.0)
        await spacer.wait()
        now[0] += 0.4  # 0.4 s of "work" between the requests
        await spacer.wait()
        assert sleeps == [pytest.approx(0.6)]
        now[0] += 5.0  # long gap: no wait
        await spacer.wait()
        assert len(sleeps) == 1
