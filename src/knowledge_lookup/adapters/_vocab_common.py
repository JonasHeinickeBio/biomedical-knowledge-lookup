"""
Small helpers shared by the NLM / NCI vocabulary adapters (Clinical Tables, NCI EVS,
MedlinePlus): request spacing and HTML-to-text conversion.
"""

import asyncio
import re
import time
from html.parser import HTMLParser

_BLOCK_TAGS = {
    "p",
    "div",
    "li",
    "ul",
    "ol",
    "br",
    "tr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "section",
}
_BLANK_LINES_RE = re.compile(r"\n\s*\n+")


class Spacer:
    """Keeps at least ``interval`` seconds between the starts of consecutive requests.

    The upstream services publish soft rate limits (Clinical Tables 25 req/s, MedlinePlus
    85-100 req/min); spacing requests keeps parallel fan-out (several tables, several
    related lookups) polite without a global scheduler. ``interval`` is a plain attribute so
    tests can set it to ``0``.
    """

    def __init__(self, interval: float):
        self.interval = interval
        self._lock = asyncio.Lock()
        self._last = float("-inf")  # the first request never waits

    async def wait(self) -> None:
        async with self._lock:
            delay = self.interval - (time.monotonic() - self._last)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = time.monotonic()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(markup: str | None) -> str:
    """Plain text from an HTML fragment: block tags become line breaks, entities decoded.

    MedlinePlus and NCI Metathesaurus definitions are HTML (``<h3>``, ``<p>``, ``<ul>``);
    consumers of :class:`UnifiedConcept` expect text.
    """
    if not markup:
        return ""
    parser = _TextExtractor()
    parser.feed(markup)
    parser.close()
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return _BLANK_LINES_RE.sub("\n\n", "\n".join(lines)).strip()
