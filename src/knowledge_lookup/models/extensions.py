"""
Backward-compatible model extensions.

The generated ``biomedical_knowledge_models`` changed several field types
from the original hand-written models (e.g. ``errors`` from ``Dict`` to
``Optional[str]``).  The wrappers in this module restore the old API
while delegating storage to the generated models.

These are imported *after* the generated models are fully loaded to avoid
circular-import issues (adapters import from ``.models`` at module level).
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from .biomedical_knowledge_models import (
    ConceptIdentifier as _ConceptIdentifier,
)
from .biomedical_knowledge_models import (
    ConceptMapping as _ConceptMapping,
)
from .biomedical_knowledge_models import (
    KnowledgeSource as _KnowledgeSource,
)
from .biomedical_knowledge_models import (
    LookupConfig as _LookupConfig,
)
from .biomedical_knowledge_models import (
    LookupResult as _LookupResult,
)
from .biomedical_knowledge_models import (
    UnifiedConcept as _UnifiedConcept,
)


class _SourceList(list):
    """A list whose ``__contains__`` also matches ``KnowledgeSource`` enum values."""

    def __contains__(self, item: Any) -> bool:
        if isinstance(item, _KnowledgeSource):
            return super().__contains__(item.value)
        return super().__contains__(item)

    def count(self, item: Any) -> int:
        if isinstance(item, _KnowledgeSource):
            return super().count(item.value)
        return super().count(item)


class ConceptIdentifier(_ConceptIdentifier):
    """Backward-compatible wrapper with a human-friendly ``__str__``."""

    def __str__(self) -> str:
        src = self.source
        if isinstance(src, _KnowledgeSource):
            src_str = src.value.lower()
        elif isinstance(src, str):
            src_str = src.lower()
        else:
            src_str = str(src).lower()
        return f"{src_str}:{self.identifier}"


class ConceptMapping(_ConceptMapping):
    """Backward-compatible wrapper with sensible field defaults."""

    def __init__(self, /, **data: Any) -> None:
        if data.get("mapping_type") is None:
            data["mapping_type"] = "exact"
        if data.get("confidence") is None:
            data["confidence"] = 1.0
        super().__init__(**data)


class UnifiedConcept(_UnifiedConcept):
    """
    Backward-compatible wrapper around ``biomedical_knowledge_models.UnifiedConcept``.

    Accepts old-style field names (``label`` → ``primary_label``,
    ``source`` → ``sources``) and provides the ``add_identifier()``
    method used by all adapters.

    List fields (``definitions``, ``synonyms``, ``categories``,
    ``semantic_types``, ``parents``, ``children``, ``identifiers``)
    are initialized to ``[]`` instead of ``None`` so that ``.append()``
    works without explicit ``None`` guards.
    """

    LIST_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "definitions",
            "synonyms",
            "categories",
            "semantic_types",
            "parents",
            "children",
            "identifiers",
            "related",
            "mappings",
            "sources",
        }
    )

    def __init__(self, /, **data: Any) -> None:
        if "label" in data and "primary_label" not in data:
            data["primary_label"] = data.pop("label")
        if "source" in data and "sources" not in data:
            src = data.pop("source")
            data["sources"] = [src] if not isinstance(src, list) else src
        # Pop dict-backed fields before passing to pydantic (they're Optional[str] now)
        raw_sd = data.pop("source_data", None)
        raw_labels = data.pop("labels", None)
        # Ensure list fields default to [] instead of None
        for field in UnifiedConcept.LIST_FIELDS:
            if data.get(field) is None:
                data[field] = []
        if data.get("confidence_score") is None:
            data["confidence_score"] = 0.0
        super().__init__(**data)
        # Initialize source_data and labels dict backing stores
        object.__setattr__(self, "_source_data_dict", {})
        object.__setattr__(self, "_labels_dict", {})
        if isinstance(raw_sd, dict):
            object.__getattribute__(self, "_source_data_dict").update(raw_sd)
        if isinstance(raw_labels, dict):
            object.__getattribute__(self, "_labels_dict").update(raw_labels)
        # Remove base-model attributes so __getattr__ dispatches to our backing dicts
        try:
            del self.__dict__["source_data"]
        except (KeyError, AttributeError):
            pass
        try:
            del self.__dict__["labels"]
        except (KeyError, AttributeError):
            pass

    def __setattr__(self, name: str, value: Any) -> None:
        # Route labels/source_data assignments to their dict backing stores
        if name == "labels":
            target = object.__getattribute__(self, "_labels_dict")
            if isinstance(value, dict):
                target.clear()
                target.update(value)
            elif isinstance(value, str):
                # JSON string - parse and update
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        target.clear()
                        target.update(parsed)
                except (ValueError, TypeError):
                    target.clear()
            return
        if name == "source_data":
            target = object.__getattribute__(self, "_source_data_dict")
            if isinstance(value, dict):
                target.clear()
                target.update(value)
            elif isinstance(value, str):
                # JSON string - parse and update
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        target.clear()
                        target.update(parsed)
                except (ValueError, TypeError):
                    target.clear()
            return
        if name == "sources" and isinstance(value, set | frozenset):
            # Convert set of enums to list of strings
            value = [str(v.value) if isinstance(v, _KnowledgeSource) else str(v) for v in value]
        super().__setattr__(name, value)

    def __getattr__(self, name: str) -> Any:
        if name == "source_data":
            return object.__getattribute__(self, "_source_data_dict")
        if name == "labels":
            return object.__getattribute__(self, "_labels_dict")
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def add_identifier(
        self,
        source: _KnowledgeSource | str,
        identifier: str,
        label: str | None = None,
        url: str | None = None,
    ) -> None:
        """Append a ``ConceptIdentifier`` to the ``identifiers`` list."""
        from .models import ConceptIdentifier as CI

        if self.identifiers is None:
            self.identifiers = []
        if isinstance(source, str):
            source = _KnowledgeSource(source.upper())
        self.identifiers.append(
            CI(
                source=source,
                identifier=identifier,
                label=label or self.primary_label,
                url=url,
            )
        )

    def has_source(self, source: _KnowledgeSource) -> bool:
        """Check if this concept originated from *source*."""
        # Check sources list
        if self.sources:
            for s in self.sources:
                if (isinstance(s, str) and source.value == s) or s == source:
                    return True
        # Check identifiers
        for ident in self.identifiers or []:
            if ident.source == source:
                return True
        return False

    def add_mapping(
        self,
        target_source: _KnowledgeSource | str,
        target_id: str,
        target_label: str | None = None,
        mapping_type: str = "exact",
        confidence: float = 1.0,
        mapping_source: str | None = None,
    ) -> None:
        """Add a ConceptMapping to this concept."""
        from .models import ConceptIdentifier as CI
        from .models import ConceptMapping as CM

        if self.mappings is None:
            self.mappings = []
        from_source = self.sources[0] if self.sources else _KnowledgeSource.GO
        from_concept = CI(
            source=from_source,
            identifier=self.primary_id,
            label=self.primary_label,
        )
        to_concept = CI(
            source=target_source,
            identifier=target_id,
            label=target_label,
        )
        self.mappings.append(
            CM(
                from_concept=from_concept,
                to_concept=to_concept,
                mapping_type=mapping_type,
                confidence=confidence,
                source=mapping_source,
            )
        )

    def get_identifier(self, source: _KnowledgeSource) -> _ConceptIdentifier | None:
        """Return the ``ConceptIdentifier`` for *source*, or ``None``."""
        for ident in self.identifiers or []:
            if ident.source == source:
                return ident
        return None

    def merge_with(self, other: UnifiedConcept) -> UnifiedConcept:
        """Merge another concept into this one (backward-compat)."""
        # Pick the higher-confidence primary_label and concept_type
        merged = UnifiedConcept(
            primary_id=self.primary_id,
            primary_label=(
                self.primary_label
                if (self.confidence_score or 0) >= (other.confidence_score or 0)
                else other.primary_label
            ),
            concept_type=self.concept_type or other.concept_type,
            confidence_score=max(self.confidence_score or 0, other.confidence_score or 0),
        )
        # Merge list fields (dedup preserving order)
        for field in UnifiedConcept.LIST_FIELDS:
            ours = getattr(self, field, None) or []
            theirs = getattr(other, field, None) or []
            deduped = []
            for item in [*ours, *theirs]:
                if item not in deduped:
                    deduped.append(item)
            setattr(merged, field, deduped)
        # Merge labels
        self_labels: dict[str, str] = self.labels if isinstance(self.labels, dict) else {}
        other_labels: dict[str, str] = other.labels if isinstance(other.labels, dict) else {}
        merged_labels: dict[str, str] = {**self_labels, **other_labels}
        # Store as JSON string (the underlying field type)
        object.__setattr__(merged, "_labels_dict", merged_labels)
        merged.labels = json.dumps(merged_labels)
        # Merge source_data
        self_source: dict[str, str] = (
            self.source_data if isinstance(self.source_data, dict) else {}
        )
        other_source: dict[str, str] = (
            other.source_data if isinstance(other.source_data, dict) else {}
        )
        merged_source: dict[str, str] = {**self_source, **other_source}
        # Store as JSON string (the underlying field type)
        object.__setattr__(merged, "_source_data_dict", merged_source)
        merged.source_data = json.dumps(merged_source)
        return merged


class LookupConfig(_LookupConfig):
    """
    Backward-compatible wrapper that accepts ``api_keys`` as a dict.

    The regenerated schema changed ``api_keys`` from ``Dict[str, str]``
    to ``Optional[str]``.  This wrapper stores dict keys in a private
    ``_api_keys_dict`` so ``get_api_key()`` works for all adapters.
    """

    _api_keys_dict: dict[str, str] | None = None

    def __init__(self, /, **data: Any) -> None:
        raw_keys = data.pop("api_keys", None)
        # Set sensible defaults for regenerated model fields that lost them
        if data.get("max_results_per_source") is None:
            data["max_results_per_source"] = 20
        if data.get("timeout_per_source") is None:
            data["timeout_per_source"] = 30
        if data.get("parallel_queries") is None:
            data["parallel_queries"] = True
        if data.get("enable_deduplication") is None:
            data["enable_deduplication"] = True
        super().__init__(**data)
        # Always initialize _api_keys_dict
        object.__setattr__(self, "_api_keys_dict", {})
        if isinstance(raw_keys, dict):
            object.__getattribute__(self, "_api_keys_dict").update(raw_keys)

    def __getattribute__(self, name: str) -> Any:
        if name == "api_keys":
            keys_dict = object.__getattribute__(self, "_api_keys_dict")
            return keys_dict if keys_dict is not None else {}
        # Use parent's __getattribute__ (pydantic v2)
        return super().__getattribute__(name)

    def get_api_key(self, service: str) -> str | None:
        """Get API key: check dict-storage, then string field, then env vars."""
        if self._api_keys_dict:
            key = self._api_keys_dict.get(service)
            if key:
                return key
        raw_api_keys = object.__getattribute__(self, "api_keys")
        if raw_api_keys:
            return raw_api_keys
        try:
            import os

            from dotenv import load_dotenv

            load_dotenv()
            return os.getenv(f"{service.upper()}_API_KEY") or os.getenv(
                f"{service.lower()}_api_key"
            )
        except ImportError:
            return None

    def is_source_enabled(self, source: _KnowledgeSource) -> bool:
        """Check whether *source* is enabled (all enabled when no filter set)."""
        if self.enabled_sources is None:
            return True
        return source in self.enabled_sources

    @classmethod
    def with_all_sources(cls) -> LookupConfig:
        """Create a config with all available knowledge sources enabled."""
        return cls(enabled_sources=list(_KnowledgeSource))


class LookupResult(_LookupResult):
    """
    Backward-compatible wrapper that stores ``errors`` as a dict.

    The regenerated schema changed ``errors`` from ``Dict[str, list[str]]``
    to ``Optional[str]``.  This wrapper stores the dict in a private
    ``_errors_dict`` attribute and provides ``add_error()``.

    Accessing ``result.errors`` returns the internal dict (or ``{}``)
    so existing callers (``.items()``, ``len()``, ``add_error()``) work.
    """

    _errors_dict: dict[str, str] | None = None

    def __init__(self, /, **data: Any) -> None:
        # Backward-compat: default None fields to sensible defaults
        for field in ("total_found",):
            if data.get(field) is None:
                data[field] = 0
        for field in ("execution_time",):
            if data.get(field) is None:
                data[field] = 0.0
        for field in ("concepts", "sources_queried", "sources_succeeded", "sources_failed"):
            if data.get(field) is None:
                data[field] = []
        raw_errors = data.pop("errors", None)
        super().__init__(**data)
        if isinstance(raw_errors, dict):
            object.__setattr__(self, "_errors_dict", raw_errors)
        elif raw_errors is None:
            object.__setattr__(self, "_errors_dict", {})

    def __getattribute__(self, name: str) -> Any:
        if name == "errors":
            errors_dict = object.__getattribute__(self, "_errors_dict")
            return errors_dict or {}
        if name == "source_health":
            sh = object.__getattribute__(self, "source_health")
            return sh if sh is not None else {}
        if name in ("sources_succeeded", "sources_failed"):
            raw = object.__getattribute__(self, name)
            return _SourceList(raw) if raw is not None else _SourceList()
        return object.__getattribute__(self, name)

    def __getattr__(self, name: str) -> Any:
        if name == "source_health":
            return {}
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def add_error(self, source: str | _KnowledgeSource, message: str) -> None:
        """Add an error message for *source*."""
        if self._errors_dict is None:
            object.__setattr__(self, "_errors_dict", {})
        source_str = str(source.value) if isinstance(source, _KnowledgeSource) else str(source)
        assert self._errors_dict is not None
        self._errors_dict[source_str] = message
        # Track in sources_failed (bypass __getattribute__ wrapper)
        raw_failed = object.__getattribute__(self, "sources_failed")
        if raw_failed is None:
            raw_failed = []
            object.__setattr__(self, "sources_failed", raw_failed)
        if source_str not in raw_failed:
            raw_failed.append(source_str)

    def add_concepts(self, concepts: list, source: str | _KnowledgeSource) -> None:
        """Add concepts to the result (backward-compat)."""
        if self.concepts is None:
            self.concepts = []
        source_str = str(source.value) if isinstance(source, _KnowledgeSource) else str(source)
        for c in concepts:
            if hasattr(c, "sources") and not c.sources:
                c.sources = [source_str]
            self.concepts.append(c)
        self.total_found = len(self.concepts)
        # Track in sources_succeeded (use object.__getattribute__ to bypass wrapper)
        raw_succeeded = object.__getattribute__(self, "sources_succeeded")
        if raw_succeeded is None:
            raw_succeeded = []
            object.__setattr__(self, "sources_succeeded", raw_succeeded)
        if source_str not in raw_succeeded:
            raw_succeeded.append(source_str)

    def get_best_matches(self, n: int = 5) -> list:
        """Return the top *n* concepts by confidence score."""
        sorted_concepts = sorted(
            (c for c in (self.concepts or []) if c is not None),
            key=lambda c: c.confidence_score if c.confidence_score is not None else 0,
            reverse=True,
        )
        return sorted_concepts[:n]

    def group_by_source(self) -> dict:
        """Group concepts by their source(s)."""
        groups: dict[str, list] = {}
        for c in self.concepts or []:
            for src in c.sources or []:
                groups.setdefault(src, []).append(c)
        # Convert string keys back to KnowledgeSource where possible
        result: dict = {}
        for key, val in groups.items():
            try:
                result[_KnowledgeSource(key)] = val
            except (ValueError, KeyError):
                result[key] = val
        return result
