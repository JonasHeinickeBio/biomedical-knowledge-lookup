"""Unit tests for knowledge_lookup.utils.redaction."""

import pytest

from knowledge_lookup.utils.redaction import MASK, redact

pytestmark = pytest.mark.unit


def test_masks_explicit_secret_values_anywhere():
    assert redact("failed with key s3cr3t-value in body", "s3cr3t-value") == (
        f"failed with key {MASK} in body"
    )


@pytest.mark.parametrize(
    "message",
    [
        "404, message='Not Found', url='https://data.bioontology.org/x?apikey=abc123&format=json'",
        "Client error for url 'https://uts-ws.nlm.nih.gov/rest/search?string=a&apiKey=abc123'",
        "https://api.omim.org/api/entry?mimNumber=1&api_key=abc123",
        "https://example.org/?access_token=abc123",
    ],
)
def test_masks_key_like_query_parameters(message):
    redacted = redact(message)
    assert "abc123" not in redacted
    assert MASK in redacted


@pytest.mark.parametrize(
    "message",
    [
        "headers={'Authorization': 'apikey token=abc123'}",
        "Authorization: Bearer abc123",
        "Authorization: Basic abc123",
    ],
)
def test_masks_authorization_header_values(message):
    assert "abc123" not in redact(message)


def test_leaves_ordinary_messages_untouched():
    message = "BioPortal search for 'type 2 diabetes' returned 0 concepts (cache key=search:1)"
    assert redact(message) == message


def test_accepts_exceptions_and_none_secrets():
    assert redact(ValueError("bad apikey=zzz"), None, "") == f"bad apikey={MASK}"
