"""
MedlinePlus adapter (consumer health information from the U.S. National Library of Medicine).

Two keyless NLM services are combined:

- **Health-topic web service** (``https://wsearch.nlm.nih.gov/ws/query?db=healthTopics``):
  text search over the English health topics. With ``rettype=topic`` every hit is the full
  topic record (title, URL, numeric topic id, "also called" terms, plain-language summary,
  topic groups, MeSH descriptors, related topics, Spanish equivalent, primary NIH institute,
  external links). Queries accept field limiters (``title:``, ``alt-title:``, ``mesh:``,
  ``full-summary:``, ``group:``).
- **MedlinePlus Connect** (``https://connect.medlineplus.gov/service``, HL7 Infobutton
  request/response): maps a *code* to the MedlinePlus page(s) for it. Supported code systems
  (OIDs verified live): ICD-10-CM ``2.16.840.1.113883.6.90``, ICD-9-CM ``...6.103``, SNOMED CT
  ``...6.96`` (problem list core subset and descendants), LOINC ``...6.1`` (lab-test pages),
  RxNorm ``...6.88`` and NDC ``...6.69`` (drug pages). An unknown OID is silently treated as
  ICD-9-CM by the service, so the adapter only ever sends the OIDs above.

Concept ids: ``MEDLINEPLUS:<url slug>``, for example
``MEDLINEPLUS:myalgicencephalomyelitischronicfatiguesyndrome`` (Spanish pages:
``MEDLINEPLUS:spanish/<slug>``); the numeric topic id (``89``) is kept as a second
identifier and in ``source_data``. The web service cannot search by numeric id, so only the
slug / URL resolves a topic. Code lookups use ``ICD10CM:G93.32``, ``SNOMEDCT:52702003``,
``ICD9CM:780.71``, ``LOINC:2951-2``, ``RXNORM:861004`` or ``NDC:<code>`` (bare ICD-10-CM and
LOINC codes are recognised too); the answer is the first matching page (all of them via
:meth:`concepts_for_code`). Lab-test and drug pages from Connect are returned as concepts but
cannot be re-fetched by slug afterwards.

The summaries are written for patients (roughly 8th-grade reading level) and are not clinical
terminology: use them as plain-language explanations next to the coded concepts. The
``ConceptType`` is a coarse heuristic (the "Symptoms" topic group -> SYMPTOM, therapy groups
-> TREATMENT, "Diagnostic Tests" -> PROCEDURE, otherwise DISEASE).

Usage terms (https://medlineplus.gov/about/using/usingcontent/ and the web-service pages):
free, no key; topic summaries, medical-test pages and the other items listed there are public
domain, but A.D.A.M. encyclopedia articles and ASHP drug monographs (reached through Connect
for drug codes) are copyrighted and may not be ingested or re-branded. Acknowledge the source
("Courtesy of MedlinePlus from the National Library of Medicine"), do not use the MedlinePlus
logo or imply endorsement. Limits: 85 requests/minute (web service) and 100/minute (Connect)
per IP address; Connect blocks an exceeding IP for 300 s. NLM recommends caching results for
12-24 hours (data refreshes Tuesday-Saturday). Requests are spaced by 0.8 s; the optional
``MEDLINEPLUS_EMAIL`` environment variable is sent as the web service's ``email`` parameter
(NLM uses it only to contact heavy users); nothing identifying is sent otherwise.
"""

import logging
import os
import re
from typing import Any
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from ..base import KnowledgeSourceAdapter
from ..models import ConceptType, KnowledgeSource, LookupConfig, UnifiedConcept
from ._vocab_common import Spacer, html_to_text

logger = logging.getLogger(__name__)

WS_URL = "https://wsearch.nlm.nih.gov/ws/query"
CONNECT_URL = "https://connect.medlineplus.gov/service"
TOOL_NAME = "biomedical-knowledge-lookup"
EMAIL_ENV = "MEDLINEPLUS_EMAIL"
MAX_RESULTS = 50  # topic records are ~15-40 kB each; keep one response reasonable
_LOOKUP_RESULTS = 10  # hits requested when resolving a slug
_MIN_INTERVAL = 0.8  # 75 requests/minute, under the 85 (web service) / 100 (Connect) limits
SPANISH_PREFIX = "spanish/"

# Code systems accepted by Connect: key -> (OID, display name).
CODE_SYSTEMS: dict[str, tuple[str, str]] = {
    "ICD10CM": ("2.16.840.1.113883.6.90", "ICD-10-CM"),
    "ICD9CM": ("2.16.840.1.113883.6.103", "ICD-9-CM"),
    "SNOMEDCT": ("2.16.840.1.113883.6.96", "SNOMED CT"),
    "LOINC": ("2.16.840.1.113883.6.1", "LOINC"),
    "RXNORM": ("2.16.840.1.113883.6.88", "RxNorm"),
    "NDC": ("2.16.840.1.113883.6.69", "NDC"),
}
_SYSTEM_ALIASES = {
    "ICD10": "ICD10CM",
    "ICD10CM": "ICD10CM",
    "ICD9": "ICD9CM",
    "ICD9CM": "ICD9CM",
    "SNOMED": "SNOMEDCT",
    "SNOMEDCT": "SNOMEDCT",
    "SNOMEDCTUS": "SNOMEDCT",
    "LOINC": "LOINC",
    "RXNORM": "RXNORM",
    "RXCUI": "RXNORM",
    "NDC": "NDC",
}
# Topic groups under "Diagnosis and Therapy" on https://medlineplus.gov/healthtopics.html
_TREATMENT_GROUPS = {
    "Complementary and Alternative Therapies",
    "Drug Therapy",
    "Surgery and Rehabilitation",
    "Transplantation and Donation",
}
_TEST_GROUPS = {"Diagnostic Tests"}
_SLUG_RE = re.compile(r"^(?:spanish/)?[a-z0-9][a-z0-9_\-]*$")
_ICD10CM_RE = re.compile(r"^[A-Z]\d[A-Z0-9](?:\.[A-Z0-9]{1,4})?$")
_LOINC_RE = re.compile(r"^\d{1,7}-\d$")
_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]*$")


def _clean(text: Any) -> str:
    return " ".join(str(text).split()) if text is not None else ""


class MedlinePlusAdapter(KnowledgeSourceAdapter):
    """MedlinePlus health topics (web service) and code-to-page mapping (Connect)."""

    def __init__(self, config: LookupConfig):
        super().__init__(config)
        self.ws_url = WS_URL
        self.connect_url = CONNECT_URL
        self._ws_spacer = Spacer(_MIN_INTERVAL)
        self._connect_spacer = Spacer(_MIN_INTERVAL)

    def get_source(self) -> KnowledgeSource:
        return KnowledgeSource.MEDLINEPLUS

    def is_available(self) -> bool:
        return True  # public, keyless

    # ------------------------------------------------------------------
    # id handling
    # ------------------------------------------------------------------

    @staticmethod
    def slug_from_url(url: str) -> str | None:
        """``https://medlineplus.gov/fatigue.html?utm_source=x`` -> ``fatigue``.

        Spanish pages keep their ``spanish/`` prefix; other paths (lab tests, drugs) keep
        their directory (``lab-tests/sodium-blood-test``). ``None`` if no path is left.
        """
        path = urlsplit(url if "//" in url else f"//{url}").path.strip("/")
        path = re.sub(r"\.html?$", "", path, flags=re.IGNORECASE)
        return path.lower() or None

    @staticmethod
    def _system_key(name: str) -> str | None:
        return _SYSTEM_ALIASES.get(re.sub(r"[^A-Z0-9]", "", name.upper()))

    def _parse_id(self, concept_id: str) -> tuple[str, ...] | None:
        """``("slug", slug)`` for a topic or ``("code", system_key, code)`` for Connect."""
        raw = (concept_id or "").strip()
        if not raw:
            return None
        if "/" in raw and ("." in raw.split("/", 1)[0] or raw.lower().startswith("http")):
            slug = self.slug_from_url(raw)  # a full URL
            return ("slug", slug) if slug and _SLUG_RE.match(slug) else None
        if ":" in raw:
            prefix, _, rest = raw.partition(":")
            rest = rest.strip()
            if prefix.strip().upper() == "MEDLINEPLUS":
                slug = rest.lower()
                return ("slug", slug) if _SLUG_RE.match(slug) and not slug.isdigit() else None
            system = self._system_key(prefix)
            if system and _CODE_RE.match(rest):
                return ("code", system, rest.upper() if system == "ICD10CM" else rest)
            return None
        upper = raw.upper()
        if _ICD10CM_RE.match(upper):
            return ("code", "ICD10CM", upper)
        if _LOINC_RE.match(raw):
            return ("code", "LOINC", raw)
        slug = raw.lower()
        if _SLUG_RE.match(slug) and not slug.isdigit():
            return ("slug", slug)
        return None

    # ------------------------------------------------------------------
    # HTTP + XML
    # ------------------------------------------------------------------

    async def _ws_query(self, params: dict[str, Any]) -> ET.Element | None:
        """One web-service call; the parsed root, or ``None`` for an unusable body."""
        await self._ws_spacer.wait()
        query = {"tool": TOOL_NAME, **params}
        email = os.getenv(EMAIL_ENV)
        if email:
            query["email"] = email
        text = await self._make_request_text(self.ws_url, query)
        if "<!DOCTYPE" in text or "<!ENTITY" in text:
            logger.warning("MedlinePlus: refusing an XML body with a DTD")
            return None
        try:
            return ET.fromstring(text)
        except ET.ParseError as e:
            logger.error(f"MedlinePlus: unparseable web service answer: {e}")
            return None

    async def _topics(self, term: str, limit: int, spanish: bool = False) -> list[dict[str, Any]]:
        params = {
            "db": "healthTopicsSpanish" if spanish else "healthTopics",
            "term": term,
            "retmax": min(limit, MAX_RESULTS),
            "rettype": "topic",
        }
        root = await self._ws_query(params)
        if root is None:
            return []
        topics: list[dict[str, Any]] = []
        for document in root.iter("document"):
            topic = self._parse_topic(document)
            if topic is not None:
                topics.append(topic)
        return topics

    @staticmethod
    def _parse_topic(document: ET.Element) -> dict[str, Any] | None:
        """One ``<document>`` of a ``rettype=topic`` answer as a plain dict."""
        node = document.find(".//health-topic")
        if node is None:
            return None
        url = node.get("url") or document.get("url") or ""
        slug = MedlinePlusAdapter.slug_from_url(url)
        title = _clean(node.get("title"))
        if not slug or not title:
            return None

        def refs(tag: str) -> list[dict[str, str]]:
            out = []
            for el in node.findall(tag):
                ref_url = el.get("url") or ""
                out.append(
                    {
                        "id": el.get("id") or "",
                        "url": ref_url,
                        "slug": MedlinePlusAdapter.slug_from_url(ref_url) or "",
                        "name": _clean(el.text),
                        "language": el.get("language") or "",
                    }
                )
            return out

        institute = node.find("primary-institute")
        return {
            "slug": slug,
            "topic_id": node.get("id") or "",
            "title": title,
            "url": url,
            "language": node.get("language") or "",
            "meta_description": _clean(node.get("meta-desc")),
            "also_called": [_clean(e.text) for e in node.findall("also-called") if _clean(e.text)],
            "see_references": [
                _clean(e.text) for e in node.findall("see-reference") if _clean(e.text)
            ],
            "summary": html_to_text(node.findtext("full-summary")),
            "groups": refs("group"),
            "related_topics": refs("related-topic"),
            "translations": refs("language-mapped-topic"),
            "mesh": [
                {"id": d.get("id") or "", "name": _clean(d.text)}
                for d in node.iter("descriptor")
                if d.get("id")
            ],
            "institute": (
                {"url": institute.get("url") or "", "name": _clean(institute.text)}
                if institute is not None and _clean(institute.text)
                else None
            ),
            "site_count": len(node.findall("site")),
        }

    async def _connect(self, system: str, code: str, language: str = "en") -> list[dict[str, str]]:
        """Connect entries ``[{"title", "url", "slug", "summary"}]`` for a code."""
        await self._connect_spacer.wait()
        params = {
            "mainSearchCriteria.v.cs": CODE_SYSTEMS[system][0],
            "mainSearchCriteria.v.c": code,
            "knowledgeResponseType": "application/json",
        }
        if language != "en":
            params["informationRecipient.languageCode.c"] = language
        data = await self._make_request(self.connect_url, params)
        feed = data.get("feed") if isinstance(data, dict) else None
        entries = feed.get("entry") if isinstance(feed, dict) else None
        out: list[dict[str, str]] = []
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            links = entry.get("link") or []
            href = str(links[0].get("href") or "") if links and isinstance(links[0], dict) else ""
            slug = self.slug_from_url(href)
            title = _clean((entry.get("title") or {}).get("_value"))
            if not slug or not title:
                continue
            summary = (entry.get("summary") or {}).get("_value")
            out.append(
                {
                    "title": title,
                    "url": href.split("?", 1)[0],
                    "slug": slug,
                    "summary": html_to_text(summary),
                }
            )
        return out

    # ------------------------------------------------------------------
    # unified model conversion
    # ------------------------------------------------------------------

    def _topic_concept(self, topic: dict[str, Any]) -> UnifiedConcept:
        group_names = [g["name"] for g in topic["groups"] if g["name"]]
        if "Symptoms" in group_names:
            concept_type = ConceptType.SYMPTOM
        elif _TREATMENT_GROUPS & set(group_names):
            concept_type = ConceptType.TREATMENT
        elif _TEST_GROUPS & set(group_names):
            concept_type = ConceptType.PROCEDURE
        else:
            concept_type = ConceptType.DISEASE
        concept = self._create_concept(
            f"MEDLINEPLUS:{topic['slug']}", topic["title"], concept_type
        )
        seen = {topic["title"].lower()}
        synonyms: list[str] = []
        for text in [*topic["also_called"], *topic["see_references"]]:
            if text.lower() not in seen:
                seen.add(text.lower())
                synonyms.append(text)
        concept.synonyms = synonyms
        concept.definitions = [topic["summary"]] if topic["summary"] else []
        concept.categories = group_names
        concept.related = [
            f"MEDLINEPLUS:{r['slug']}" for r in topic["related_topics"] if r["slug"]
        ]
        concept.confidence_score = 0.9
        if topic["topic_id"]:
            concept.add_identifier(
                "MEDLINEPLUS", topic["topic_id"], topic["title"], topic["url"] or None
            )
        for mesh in topic["mesh"]:
            concept.add_identifier("MESH", mesh["id"], mesh["name"] or topic["title"])
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.MEDLINEPLUS] = {
                "topic_id": topic["topic_id"],
                "url": topic["url"],
                "language": topic["language"],
                "meta_description": topic["meta_description"],
                "audience": "patients (plain-language consumer health information)",
                "groups": group_names,
                "mesh": topic["mesh"],
                "primary_institute": topic["institute"],
                "external_site_links": topic["site_count"],
                "attribution": "Courtesy of MedlinePlus from the National Library of Medicine",
            }
        return concept

    def _entry_concept(self, entry: dict[str, str], system: str, code: str) -> UnifiedConcept:
        """A Connect hit that is not (or not yet) a full health-topic record."""
        area = entry["slug"].split("/", 1)[0]
        concept_type = {"lab-tests": ConceptType.OBSERVATION, "druginfo": ConceptType.DRUG}.get(
            area, ConceptType.DISEASE
        )
        concept = self._create_concept(
            f"MEDLINEPLUS:{entry['slug']}", entry["title"], concept_type
        )
        concept.definitions = [entry["summary"]] if entry["summary"] else []
        concept.categories = [area] if "/" in entry["slug"] else []
        concept.confidence_score = 0.9
        if isinstance(concept.source_data, dict):
            concept.source_data[KnowledgeSource.MEDLINEPLUS] = {
                "url": entry["url"],
                "matched_code": f"{system}:{code}",
                "audience": "patients (plain-language consumer health information)",
                "attribution": "Courtesy of MedlinePlus from the National Library of Medicine",
            }
        return concept

    # ------------------------------------------------------------------
    # lookups shared by the public methods
    # ------------------------------------------------------------------

    async def _topic_by_slug(self, slug: str) -> dict[str, Any] | None:
        """The topic whose URL slug is exactly *slug*.

        The web service has no id lookup, but a query for the slug (or the quoted URL) ranks
        the topic with that URL first; the exact URL is then checked.
        """
        spanish = slug.startswith(SPANISH_PREFIX)
        bare = slug[len(SPANISH_PREFIX) :] if spanish else slug
        for term in (bare, f'"medlineplus.gov/{slug}.html"'):
            for topic in await self._topics(term, _LOOKUP_RESULTS, spanish):
                if topic["slug"] == slug:
                    return topic
        return None

    async def concepts_for_code(
        self, system: str, code: str, language: str = "en"
    ) -> list[UnifiedConcept]:
        """All MedlinePlus pages Connect returns for *code* (``system`` like ``ICD10CM``).

        Health-topic pages are upgraded to full topic records (one web-service call each);
        lab-test and drug pages stay as Connect entries. Never raises.
        """
        key = self._system_key(system)
        if key is None or not _CODE_RE.match(code or ""):
            return []
        try:
            entries = await self._connect(key, code, "es" if language.startswith("es") else "en")
        except Exception as e:
            logger.error(f"MedlinePlus Connect failed for {key}:{code}: {e}")
            return []
        concepts: list[UnifiedConcept] = []
        seen: set[str] = set()
        for entry in entries:
            if entry["slug"] in seen:
                continue
            seen.add(entry["slug"])
            topic = None
            if _SLUG_RE.match(entry["slug"]):
                try:
                    topic = await self._topic_by_slug(entry["slug"])
                except Exception as e:
                    logger.warning(f"MedlinePlus topic lookup failed for {entry['slug']}: {e}")
            if topic is not None:
                concept = self._topic_concept(topic)
                if isinstance(concept.source_data, dict):
                    concept.source_data[KnowledgeSource.MEDLINEPLUS]["matched_code"] = (
                        f"{key}:{code}"
                    )
            else:
                concept = self._entry_concept(entry, key, code)
            concepts.append(concept)
        return concepts

    async def _resolve(self, concept_id: str) -> tuple[dict[str, Any] | None, str | None]:
        """``(topic record, matched code id)`` for a slug / URL / code id; never raises."""
        parsed = self._parse_id(concept_id)
        if parsed is None:
            logger.warning(f"MedlinePlus: unrecognised id '{concept_id}'")
            return None, None
        try:
            if parsed[0] == "slug":
                return await self._topic_by_slug(parsed[1]), None
            _, system, code = parsed
            entries = await self._connect(system, code)
            for entry in entries:
                if _SLUG_RE.match(entry["slug"]):
                    topic = await self._topic_by_slug(entry["slug"])
                    if topic is not None:
                        return topic, f"{system}:{code}"
        except Exception as e:
            logger.error(f"MedlinePlus lookup failed for '{concept_id}': {e}")
        return None, None

    # ------------------------------------------------------------------
    # public interface
    # ------------------------------------------------------------------

    async def search_concepts(self, query: str, limit: int = 20) -> list[UnifiedConcept]:
        """Search English health topics by text (ranked by MedlinePlus).

        The query is passed through, so field limiters work (``title:asthma``,
        ``group:"Symptoms"``, ``mesh:...``); words are AND-ed, ``OR`` is supported.
        """
        text = (query or "").strip()
        if not text or limit < 1:
            return []
        try:
            topics = await self._topics(text, limit)
        except Exception as e:
            logger.error(f"MedlinePlus search failed for '{text}': {e}")
            return []
        concepts: list[UnifiedConcept] = []
        seen: set[str] = set()
        for topic in topics:
            if topic["slug"] not in seen:
                seen.add(topic["slug"])
                concepts.append(self._topic_concept(topic))
        logger.info(f"MedlinePlus search for '{text}' returned {len(concepts[:limit])} concepts")
        return concepts[:limit]

    async def get_concept_details(self, concept_id: str) -> UnifiedConcept | None:
        """A topic by slug / URL, or the first page MedlinePlus Connect gives for a code."""
        parsed = self._parse_id(concept_id)
        if parsed is None:
            logger.warning(f"MedlinePlus: unrecognised id '{concept_id}'")
            return None
        try:
            if parsed[0] == "code":
                concepts = await self.concepts_for_code(parsed[1], parsed[2])
                return concepts[0] if concepts else None
            topic = await self._topic_by_slug(parsed[1])
        except Exception as e:
            logger.error(f"MedlinePlus get_concept_details failed for '{concept_id}': {e}")
            return None
        return self._topic_concept(topic) if topic else None

    async def get_relationships(self, concept_id: str) -> list[dict[str, Any]]:
        """Typed links of a topic: ``related_topic``, ``member_of_group``,
        ``has_translation`` (Spanish page) and ``primary_institute`` (lead NIH institute).
        """
        topic, _ = await self._resolve(concept_id)
        if topic is None:
            return []
        out: list[dict[str, Any]] = []

        def add(label: str, related_id: str, name: str, **extra: Any) -> None:
            out.append(
                {
                    "relation_label": label,
                    "related_id": related_id,
                    "related_name": name,
                    "source": "MEDLINEPLUS",
                    **extra,
                }
            )

        for related in topic["related_topics"]:
            if related["slug"]:
                add("related_topic", f"MEDLINEPLUS:{related['slug']}", related["name"])
        for group in topic["groups"]:
            if group["id"]:
                add(
                    "member_of_group",
                    f"MEDLINEPLUS_GROUP:{group['id']}",
                    group["name"],
                    url=group["url"],
                )
        for translation in topic["translations"]:
            if translation["slug"]:
                add(
                    "has_translation",
                    f"MEDLINEPLUS:{translation['slug']}",
                    translation["name"],
                    language=translation["language"],
                )
        if topic["institute"]:
            add(
                "primary_institute",
                topic["institute"]["url"] or topic["institute"]["name"],
                topic["institute"]["name"],
            )
        return out

    async def get_mappings(self, concept_id: str) -> list[dict[str, Any]]:
        """Codes the topic is linked to.

        Always the topic's MeSH descriptors (``toSource="MESH"``, the only codes the topic
        record carries). When the id is a code (``ICD10CM:G93.32``) the Connect match
        ``code -> topic`` is returned as well. MedlinePlus cannot be asked in reverse
        ("which codes point to this topic"), so a slug id gives MeSH only.
        """
        topic, matched = await self._resolve(concept_id)
        if topic is None:
            return []
        topic_id = f"MEDLINEPLUS:{topic['slug']}"
        mappings: list[dict[str, Any]] = []
        if matched:
            system, _, code = matched.partition(":")
            mappings.append(
                {
                    "fromId": matched,
                    "toId": topic_id,
                    "fromSource": system,
                    "toSource": "MEDLINEPLUS",
                    "mappingType": "connect_match",
                    "confidence": 0.9,
                }
            )
        for mesh in topic["mesh"]:
            mappings.append(
                {
                    "fromId": topic_id,
                    "toId": mesh["id"],
                    "fromSource": "MEDLINEPLUS",
                    "toSource": "MESH",
                    "mappingType": "mesh_heading",
                    "confidence": 0.95,
                    "toName": mesh["name"],
                }
            )
        return mappings
