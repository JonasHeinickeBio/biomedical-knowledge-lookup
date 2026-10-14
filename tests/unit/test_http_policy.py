"""Tests for the request policy: Retry-After, retry strategies, concurrency, headers.

These follow the documented rules of the public Wikidata and DBpedia endpoints.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from knowledge_lookup import base
from knowledge_lookup.adapters.dbpedia_adapter import DBpediaAdapter
from knowledge_lookup.adapters.wikidata_adapter import WikidataAdapter
from knowledge_lookup.base import (
    MAX_RETRY_AFTER,
    KnowledgeSourceAdapter,
    default_user_agent,
    retry_after_seconds,
)
from knowledge_lookup.models import KnowledgeSource, LookupConfig
from knowledge_lookup.utils.retry_utils import DEFAULT_RETRY_STRATEGIES, ErrorCategory

pytestmark = pytest.mark.unit


def _http_error(status, headers=None):
    return aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=status, message="x", headers=headers
    )


class _Adapter(KnowledgeSourceAdapter):
    def get_source(self):
        return KnowledgeSource.BIOPORTAL

    async def search_concepts(self, query, limit=20):
        return []

    async def get_concept_details(self, concept_id):
        return None


@pytest.fixture
def adapter():
    return _Adapter(LookupConfig())


@pytest.fixture
def real_sleeps(monkeypatch):
    """Let the retry loop sleep (it is skipped under pytest) but record, not wait."""
    monkeypatch.setenv("BKL_RETRY_SLEEP", "1")
    sleep = AsyncMock()
    monkeypatch.setattr(base.asyncio, "sleep", sleep)
    return sleep


class TestRetryAfterParsing:
    def test_seconds(self):
        assert retry_after_seconds(_http_error(429, {"Retry-After": "7"})) == 7.0

    def test_http_date(self):
        when = datetime.now(UTC) + timedelta(seconds=30)
        exc = _http_error(429, {"Retry-After": format_datetime(when, usegmt=True)})
        assert 25 <= retry_after_seconds(exc) <= 31

    def test_past_date_is_zero(self):
        when = datetime.now(UTC) - timedelta(seconds=30)
        exc = _http_error(429, {"Retry-After": format_datetime(when, usegmt=True)})
        assert retry_after_seconds(exc) == 0.0

    @pytest.mark.parametrize("headers", [None, {}, {"Retry-After": ""}, {"Retry-After": "soon"}])
    def test_missing_or_unusable(self, headers):
        assert retry_after_seconds(_http_error(429, headers)) is None

    def test_exception_without_headers(self):
        assert retry_after_seconds(RuntimeError("boom")) is None


class TestRetryAfterIsHonoured:
    @pytest.mark.asyncio
    async def test_waits_at_least_as_long_as_the_server_asks(self, adapter, real_sleeps):
        calls = []

        async def op():
            calls.append(1)
            if len(calls) == 1:
                raise _http_error(429, {"Retry-After": "17"})
            return "ok"

        assert await adapter._call_with_retry("t", op) == "ok"
        # the default RATE_LIMITED backoff for a first retry is 2 s: 17 s wins
        real_sleeps.assert_awaited_once_with(17.0)

    @pytest.mark.asyncio
    async def test_backoff_wins_when_it_is_longer(self, adapter, real_sleeps):
        calls = []

        async def op():
            calls.append(1)
            if len(calls) == 1:
                raise _http_error(429, {"Retry-After": "0"})
            return "ok"

        await adapter._call_with_retry("t", op)
        real_sleeps.assert_awaited_once_with(2.0)

    @pytest.mark.asyncio
    async def test_is_capped(self, adapter, real_sleeps):
        calls = []

        async def op():
            calls.append(1)
            if len(calls) == 1:
                raise _http_error(429, {"Retry-After": "86400"})
            return "ok"

        await adapter._call_with_retry("t", op)
        real_sleeps.assert_awaited_once_with(MAX_RETRY_AFTER)

    @pytest.mark.asyncio
    async def test_applies_to_503(self, adapter, real_sleeps):
        calls = []

        async def op():
            calls.append(1)
            if len(calls) == 1:
                raise _http_error(503, {"Retry-After": "11"})
            return "ok"

        await adapter._call_with_retry("t", op)
        real_sleeps.assert_awaited_once_with(11.0)

    @pytest.mark.asyncio
    async def test_not_used_for_errors_that_are_not_retried(self, adapter, real_sleeps):
        async def op():
            raise _http_error(400, {"Retry-After": "5"})

        with pytest.raises(aiohttp.ClientResponseError):
            await adapter._call_with_retry("t", op)
        real_sleeps.assert_not_awaited()


class TestRetryStrategiesOverride:
    @pytest.mark.asyncio
    async def test_adapter_strategies_are_used_by_make_request(self, adapter):
        adapter.retry_strategies = {
            **DEFAULT_RETRY_STRATEGIES,
            ErrorCategory.SERVER_ERROR: (1, 0.0, 0.0),
        }
        attempts = []

        class _Resp:
            headers: dict = {}

            def raise_for_status(self):
                attempts.append(1)
                raise _http_error(500)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        session = MagicMock(closed=False)
        session.get = MagicMock(return_value=_Resp())
        adapter.session = session
        with pytest.raises(aiohttp.ClientResponseError):
            await adapter._make_request("http://x")
        assert len(attempts) == 1  # the default would be 4


class TestConcurrencyGate:
    @pytest.mark.asyncio
    async def test_limits_simultaneous_requests(self, adapter):
        adapter.max_concurrent_requests = 2
        active = peak = 0

        class _Resp:
            headers: dict = {}

            def raise_for_status(self):
                pass

            async def json(self):
                nonlocal active, peak
                active += 1
                peak = max(peak, active)
                await asyncio.sleep(0.01)
                active -= 1
                return {}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        session = MagicMock(closed=False)
        session.get = MagicMock(side_effect=lambda *a, **k: _Resp())
        adapter.session = session

        await asyncio.gather(*(adapter._make_request(f"http://x/{i}") for i in range(8)))
        assert peak == 2

    @pytest.mark.asyncio
    async def test_unlimited_by_default(self, adapter):
        assert adapter.max_concurrent_requests is None
        assert adapter._gate() is None

    def test_gate_is_recreated_for_a_new_event_loop(self, adapter):
        adapter.max_concurrent_requests = 1

        async def gate():
            return adapter._gate()

        first = asyncio.run(gate())
        second = asyncio.run(gate())
        assert first is not second


class TestResponseHook:
    @pytest.mark.asyncio
    async def test_hook_sees_every_successful_response(self, adapter):
        seen = []
        adapter._inspect_response = seen.append  # type: ignore[method-assign]

        class _Resp:
            headers = {"X-Test": "1"}

            def raise_for_status(self):
                pass

            async def json(self):
                return {"ok": True}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        session = MagicMock(closed=False)
        session.get = MagicMock(return_value=_Resp())
        adapter.session = session
        assert await adapter._make_request("http://x") == {"ok": True}
        assert len(seen) == 1 and seen[0].headers == {"X-Test": "1"}


class TestUserAgent:
    def test_names_the_client_and_gives_a_contact_url(self):
        agent = default_user_agent()
        assert agent.startswith("AID-PAIS-Knowledge-Lookup/")
        assert "(+https://github.com/JonasHeinickeBio/biomedical-knowledge-lookup)" in agent

    @pytest.mark.asyncio
    async def test_wikidata_sends_it(self):
        adapter = WikidataAdapter(LookupConfig())
        with patch.object(
            adapter, "_make_request", new_callable=AsyncMock, return_value={}
        ) as mock_req:
            await adapter.get_concept_details("Q1472")
            await adapter.search_concepts("crohn")
        agents = {c.kwargs["headers"]["User-Agent"] for c in mock_req.call_args_list}
        assert agents == {default_user_agent()}


class TestEndpointPolicies:
    def test_wikidata_matches_the_documented_limits(self):
        adapter = WikidataAdapter(LookupConfig())
        assert adapter.min_request_timeout > 60  # the Query Service deadline
        assert adapter.max_concurrent_requests <= 5  # parallel queries per IP
        strategies = adapter.retry_strategies
        # no immediate double retry: failed and slow queries count against the quota
        assert strategies[ErrorCategory.NETWORK_ERROR][1] > 0
        assert strategies[ErrorCategory.SERVER_ERROR][0] <= 2
        # unchanged categories keep the shared defaults
        assert (
            strategies[ErrorCategory.RATE_LIMITED]
            == DEFAULT_RETRY_STRATEGIES[ErrorCategory.RATE_LIMITED]
        )

    def test_dbpedia_matches_the_documented_limits(self):
        adapter = DBpediaAdapter(LookupConfig())
        assert adapter.min_request_timeout > 120  # MaxQueryExecutionTime
        assert adapter.max_concurrent_requests <= 50
        assert adapter.retry_strategies[ErrorCategory.NETWORK_ERROR][1] > 0

    @pytest.mark.asyncio
    async def test_session_timeout_covers_the_server_deadline(self):
        config = LookupConfig()
        config.timeout_per_source = 30.0
        for cls, deadline in ((WikidataAdapter, 60), (DBpediaAdapter, 120)):
            adapter = cls(config)
            try:
                assert (await adapter._get_session()).timeout.total > deadline
            finally:
                await adapter.close()


class TestDBpediaPartialResults:
    @pytest.fixture
    def adapter(self):
        return DBpediaAdapter(LookupConfig())

    def _response(self, **headers):
        return MagicMock(headers=headers)

    def test_anytime_query_is_reported(self, adapter, caplog):
        with caplog.at_level(logging.WARNING):
            adapter._inspect_response(
                self._response(
                    **{"X-SQL-State": "S1TAT", "X-SQL-Message": "Returning incomplete results"}
                )
            )
        assert "partial results" in caplog.text
        assert "S1TAT" in caplog.text

    def test_row_cap_is_reported(self, adapter, caplog):
        with caplog.at_level(logging.WARNING):
            adapter._inspect_response(self._response(**{"X-SPARQL-MaxRows": "10000"}))
        assert "partial results" in caplog.text

    def test_complete_results_are_silent(self, adapter, caplog):
        with caplog.at_level(logging.WARNING):
            adapter._inspect_response(self._response(**{"X-Exec-Milliseconds": "12"}))
        assert caplog.text == ""

    def test_odd_responses_do_not_raise(self, adapter):
        adapter._inspect_response(object())
        adapter._inspect_response(MagicMock(headers=None))
