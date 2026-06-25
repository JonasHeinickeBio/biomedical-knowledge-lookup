"""
API Response Validator for real-world API testing.

This module provides tools to validate API responses and detect changes
in API response structures that could break adapter code.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

FIXTURE_DIR = Path(__file__).parent / "api_fixtures"
FIXTURE_DIR.mkdir(exist_ok=True)


class APIResponseValidator:
    """
    Validates API responses and detects structural changes.

    This validator helps ensure that adapter code continues to work
    with actual API responses and warns about breaking changes.
    """

    def __init__(self, source_name: str):
        self.source_name = source_name
        self.fixture_path = FIXTURE_DIR / f"{source_name}_responses.json"
        self.previous_responses = self._load_previous_responses()
        self.current_changes = []

    def _load_previous_responses(self) -> dict:
        """Load previously recorded API responses."""
        if self.fixture_path.exists():
            try:
                with open(self.fixture_path) as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                return {}
        return {}

    def _save_current_responses(self):
        """Save current responses to fixture file."""
        # This is handled externally by the fixture
        pass

    def generate_hash(self, data: Any) -> str:
        """Generate a hash for response data to detect changes."""

        def convert_for_json(obj: Any) -> Any:
            """Recursively convert objects to JSON-serializable format."""
            if isinstance(obj, dict):
                return {str(k): convert_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_for_json(item) for item in obj]
            elif hasattr(obj, "__dict__"):
                return convert_for_json(obj.__dict__)
            else:
                return obj

        converted = convert_for_json(data)
        response_str = json.dumps(converted, sort_keys=True, default=str)
        return hashlib.md5(response_str.encode()).hexdigest()

    def extract_keys(self, data: Any, path: str = "", max_depth: int = 10) -> set:
        """Extract all keys from nested dictionaries."""
        keys = set()
        if max_depth <= 0 or not isinstance(data, dict):
            return keys

        for key, value in data.items():
            keys.add(f"{path}.{key}" if path else key)
            if isinstance(value, dict):
                keys.update(
                    self.extract_keys(value, f"{path}.{key}" if path else key, max_depth - 1)
                )
            elif isinstance(value, list) and len(value) > 0:
                if isinstance(value[0], dict):
                    keys.update(
                        self.extract_keys(
                            value[0], f"{path}.{key}[0]" if path else key, max_depth - 1
                        )
                    )

        return keys

    def extract_types(self, data: Any, path: str = "", max_depth: int = 10) -> dict:
        """Extract types for all values in response."""
        types = {}
        if max_depth <= 0:
            types[path] = type(data).__name__
            return types

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                types[current_path] = type(value).__name__
                if isinstance(value, dict):
                    types.update(self.extract_types(value, current_path, max_depth - 1))
                elif isinstance(value, list) and len(value) > 0:
                    if isinstance(value[0], dict):
                        types.update(
                            self.extract_types(value[0], f"{current_path}[0]", max_depth - 1)
                        )
                    else:
                        types[current_path] = f"list[{type(value[0]).__name__}]"
        elif isinstance(data, list) and len(data) > 0:
            types[path] = f"list[{type(data[0]).__name__}]"
        else:
            types[path] = type(data).__name__

        return types

    def validate_response(
        self, cache_key: str, response_data: dict[str, Any], compare_with_previous: bool = True
    ) -> list[dict]:
        """
        Validate an API response against previous recordings.

        Args:
            cache_key: Unique identifier for this API call
            response_data: The response data to validate
            compare_with_previous: Whether to compare with previous responses

        Returns:
            List of change notifications
        """
        changes = []

        if compare_with_previous and cache_key in self.previous_responses:
            previous = self.previous_responses[cache_key]

            # Compare keys
            previous_keys = self.extract_keys(previous)
            current_keys = self.extract_keys(response_data)

            removed_keys = previous_keys - current_keys
            added_keys = current_keys - previous_keys

            if removed_keys:
                changes.append(
                    {"type": "keys_removed", "path": cache_key, "keys": list(removed_keys)}
                )

            if added_keys:
                changes.append({"type": "keys_added", "path": cache_key, "keys": list(added_keys)})

            # Compare types
            previous_types = self.extract_types(previous)
            current_types = self.extract_types(response_data)

            for key in previous_types:
                if key in current_types and previous_types[key] != current_types[key]:
                    changes.append(
                        {
                            "type": "type_changed",
                            "path": cache_key,
                            "field": key,
                            "old_type": previous_types[key],
                            "new_type": current_types[key],
                        }
                    )

        # Update current response
        if cache_key not in self.previous_responses:
            self.previous_responses[cache_key] = response_data
            changes.append(
                {
                    "type": "new_response",
                    "path": cache_key,
                    "hash": self.generate_hash(response_data),
                }
            )

        self.current_changes.extend(changes)
        return changes

    def print_changes(self, changes: list[dict] = None):
        """Print detected changes."""
        if changes is None:
            changes = self.current_changes

        if not changes:
            print("No changes detected.")
            return

        print(f"\n{'=' * 70}")
        print(f"API RESPONSE CHANGES ({len(changes)} detected)")
        print(f"Source: {self.source_name}")
        print(f"{'=' * 70}\n")

        for change in changes:
            print(f"Type: {change['type']}")
            print(f"  Path: {change['path']}")

            if change["type"] == "keys_removed":
                print(f"  Removed keys: {', '.join(change['keys'][:5])}")
                if len(change["keys"]) > 5:
                    print(f"  ... and {len(change['keys']) - 5} more")
            elif change["type"] == "keys_added":
                print(f"  Added keys: {', '.join(change['keys'][:5])}")
                if len(change["keys"]) > 5:
                    print(f"  ... and {len(change['keys']) - 5} more")
            elif change["type"] == "type_changed":
                print(f"  Field: {change['field']}")
                print(f"  Old type: {change['old_type']}")
                print(f"  New type: {change['new_type']}")
            elif change["type"] == "new_response":
                print(f"  Hash: {change['hash']}")

            print()

        print(f"{'=' * 70}\n")


# Global validator instances for each source
_validators = {}


def get_validator(source_name: str) -> APIResponseValidator:
    """Get or create a validator for a source."""
    if source_name not in _validators:
        _validators[source_name] = APIResponseValidator(source_name)
    return _validators[source_name]


def validate_adapter_response(
    source: str, cache_key: str, response_data: dict[str, Any]
) -> list[dict]:
    """
    Convenience function to validate an adapter response.

    Args:
        source: Source name (e.g., 'uniprot', 'ols')
        cache_key: Unique identifier for this API call
        response_data: The response data to validate

    Returns:
        List of detected changes
    """
    validator = get_validator(source)
    return validator.validate_response(cache_key, response_data)


def print_changes(source: str):
    """Print changes for a source."""
    validator = get_validator(source)
    validator.print_changes()


def save_fixtures():
    """Save all fixture data to files."""
    for source_name, validator in _validators.items():
        if validator.previous_responses:
            validator.fixture_path.parent.mkdir(parents=True, exist_ok=True)
            with open(validator.fixture_path, "w") as f:
                json.dump(validator.previous_responses, f, indent=2)
