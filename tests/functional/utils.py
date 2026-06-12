"""
Functional test utilities for adapter validation.
"""

import warnings
from typing import Any, Callable

from knowledge_lookup.models import KnowledgeSource


class ResponseStructureValidator:
    """
    Validates API response structure and warns about changes.
    
    This class helps detect when API responses change structure,
    which could break downstream code.
    """
    
    def __init__(self, source: KnowledgeSource):
        self.source = source
        self.structures = {}  # cache_key -> structure info
    
    def extract_structure(self, data: Any, max_depth: int = 5) -> dict:
        """
        Extract the structure of a response for comparison.
        
        Args:
            data: The response data
            max_depth: Maximum recursion depth
            
        Returns:
            Dictionary describing the structure
        """
        if max_depth <= 0:
            return {"type": type(data).__name__}
        
        if isinstance(data, dict):
            return {
                "type": "dict",
                "keys": {k: self.extract_structure(v, max_depth - 1) for k, v in data.items()}
            }
        elif isinstance(data, list):
            if len(data) > 0:
                return {
                    "type": "list",
                    "length": len(data),
                    "item_structure": self.extract_structure(data[0], max_depth - 1)
                }
            return {"type": "list", "length": 0}
        else:
            return {"type": type(data).__name__, "value": str(data)[:100]}
    
    def validate(self, cache_key: str, data: Any) -> list[dict]:
        """
        Validate response structure against previous recordings.
        
        Args:
            cache_key: Unique identifier for this API call
            data: New response data
            
        Returns:
            List of warnings about changes
        """
        warnings_list = []
        new_structure = self.extract_structure(data)
        
        if cache_key in self.structures:
            old_structure = self.structures[cache_key]
            
            # Compare structures
            structure_warnings = self._compare_structures(
                old_structure, new_structure, path=""
            )
            warnings_list.extend(structure_warnings)
        
        # Store new structure
        self.structures[cache_key] = new_structure
        
        return warnings_list
    
    def _compare_structures(self, old: dict, new: dict, path: str) -> list[dict]:
        """Compare two structures and return differences."""
        warnings = []
        
        if old.get("type") != new.get("type"):
            warnings.append({
                "type": "type_change",
                "path": path or "root",
                "old_type": old.get("type"),
                "new_type": new.get("type")
            })
            return warnings
        
        if old["type"] == "dict":
            old_keys = set(old.get("keys", {}).keys())
            new_keys = set(new.get("keys", {}).keys())
            
            # Check for removed keys
            removed = old_keys - new_keys
            for key in removed:
                warnings.append({
                    "type": "key_removed",
                    "path": f"{path}.{key}" if path else key,
                    "key": key
                })
            
            # Check for added keys
            added = new_keys - old_keys
            for key in added:
                warnings.append({
                    "type": "key_added",
                    "path": f"{path}.{key}" if path else key,
                    "key": key
                })
            
            # Recurse into common keys
            for key in old_keys & new_keys:
                sub_warnings = self._compare_structures(
                    old["keys"][key],
                    new["keys"][key],
                    f"{path}.{key}" if path else key
                )
                warnings.extend(sub_warnings)
        
        elif old["type"] == "list":
            old_len = old.get("length", 0)
            new_len = new.get("length", 0)
            
            if old_len != new_len:
                warnings.append({
                    "type": "list_length_change",
                    "path": path,
                    "old_length": old_len,
                    "new_length": new_len
                })
            
            # Compare item structures if list is non-empty
            if "item_structure" in old and "item_structure" in new:
                sub_warnings = self._compare_structures(
                    old["item_structure"],
                    new["item_structure"],
                    f"{path}[item]"
                )
                warnings.extend(sub_warnings)
        
        return warnings
    
    def get_all_structures(self) -> dict:
        """Get all recorded structures."""
        return self.structures


class APIWarningManager:
    """
    Manages API response change warnings across test runs.
    
    This helps track when APIs change their response format,
    allowing for proactive updates to adapter code.
    """
    
    def __init__(self):
        self.warnings = []
        self.structures = {}
    
    def add_warning(self, source: KnowledgeSource, cache_key: str, warning: dict):
        """Record a warning about API change."""
        self.warnings.append({
            "source": source.value,
            "cache_key": cache_key,
            **warning
        })
    
    def check_structure(
        self, 
        source: KnowledgeSource, 
        cache_key: str, 
        data: Any
    ) -> list[dict]:
        """Check structure and return warnings."""
        validator = ResponseStructureValidator(source)
        return validator.validate(cache_key, data)
    
    def print_warnings(self):
        """Print all accumulated warnings."""
        if not self.warnings:
            return
        
        print("\n" + "=" * 70)
        print(f"API RESPONSE STRUCTURE WARNINGS ({len(self.warnings)} found)")
        print("=" * 70)
        
        for warning in self.warnings:
            print(f"\nSource: {warning['source']}")
            print(f"Cache Key: {warning['cache_key']}")
            print(f"Type: {warning['type']}")
            print(f"Path: {warning.get('path', 'N/A')}")
            
            if warning['type'] == 'key_removed':
                print(f"Removed key: {warning['key']}")
            elif warning['type'] == 'key_added':
                print(f"Added key: {warning['key']}")
            elif warning['type'] == 'type_change':
                print(f"Old type: {warning['old_type']}")
                print(f"New type: {warning['new_type']}")
            elif warning['type'] == 'list_length_change':
                print(f"Old length: {warning['old_length']}")
                print(f"New length: {warning['new_length']}")
        
        print("\n" + "=" * 70)
        print("These warnings indicate API changes. Update adapter code if needed.")
        print("=" * 70 + "\n")


def warn_about_response_changes(
    source: KnowledgeSource,
    cache_key: str,
    data: Any,
    manager: APIWarningManager = None
) -> APIWarningManager:
    """
    Convenience function to check for API response changes.
    
    Args:
        source: Knowledge source
        cache_key: Unique identifier for this call
        data: Response data
        manager: Optional manager instance
        
    Returns:
        Manager with any warnings added
    """
    if manager is None:
        manager = APIWarningManager()
    
    warnings = manager.check_structure(source, cache_key, data)
    
    for warning in warnings:
        manager.add_warning(source, cache_key, warning)
    
    return manager
