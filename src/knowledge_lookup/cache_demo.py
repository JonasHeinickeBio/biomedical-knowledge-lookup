"""
Cache Usage Examples for Knowledge Lookup Adapters

This module demonstrates how to use the professional caching system
in knowledge lookup adapters for improved performance.
"""

import asyncio
import time
from pathlib import Path

from knowledge_lookup import init_cache
from knowledge_lookup.adapters.unichem_adapter import UniChemAdapter
from knowledge_lookup.models import LookupConfig


async def demonstrate_caching():
    """Demonstrate the caching system with UniChem adapter."""

    print("🚀 UniChem Adapter Caching Demonstration")
    print("=" * 50)

    # Initialize cache with disk persistence
    cache_dir = Path("./demo_cache")
    init_cache(
        memory_max_size=500,  # Smaller for demo
        disk_cache_dir=cache_dir,
        disk_max_size=2000,
        default_ttl=1800,  # 30 minutes
        cleanup_interval=60,  # Cleanup every minute
    )

    # Initialize adapter
    config = LookupConfig()
    adapter = UniChemAdapter(config)

    print(f"✅ Adapter available: {adapter.is_available()}")
    print(f"✅ Cache directory: {cache_dir.absolute()}")

    # Show initial cache stats
    print("\n📊 Initial Cache Statistics:")
    stats = adapter.get_cache_stats()
    print(f"   Memory: {stats['sizes']['memory']} entries")
    print(f"   Disk: {stats['sizes']['disk']} entries")
    print(".2f")

    # Test 1: Source information caching
    print("\n🔍 Test 1: Source Information Caching")
    print("-" * 40)

    # First call (cache miss)
    start_time = time.time()
    sources1 = await adapter.get_sources()
    time.time() - start_time

    # Second call (cache hit)
    start_time = time.time()
    await adapter.get_sources()
    time.time() - start_time

    print(".3f")
    print(".3f")
    print(".1f")
    print(f"   Sources found: {len(sources1) if sources1 else 0}")

    # Test 2: Compound search caching
    print("\n🔍 Test 2: Compound Search Caching")
    print("-" * 40)

    compound_id = "CHEMBL25"  # Aspirin

    # First search (cache miss)
    start_time = time.time()
    results1 = await adapter.search_concepts(compound_id, limit=5)
    time.time() - start_time

    # Second search (cache hit)
    start_time = time.time()
    await adapter.search_concepts(compound_id, limit=5)
    time.time() - start_time

    print(".3f")
    print(".3f")
    print(".1f")
    print(f"   Results found: {len(results1)}")

    # Test 3: Cross-references caching
    print("\n🔍 Test 3: Cross-references Caching")
    print("-" * 40)

    # First call
    start_time = time.time()
    xrefs1 = await adapter.get_cross_references(compound_id)
    time.time() - start_time

    # Second call
    start_time = time.time()
    await adapter.get_cross_references(compound_id)
    time.time() - start_time

    print(".3f")
    print(".3f")
    print(".1f")
    print(f"   Cross-references found: {len(xrefs1)} sources")

    # Show final cache stats
    print("\n📊 Final Cache Statistics:")
    stats = adapter.get_cache_stats()
    print(f"   Memory cache: {stats['sizes']['memory']} entries")
    print(f"   Disk cache: {stats['sizes']['disk']} entries")
    print(".2f")
    print(f"   Memory hit rate: {stats['memory']['hit_rate']:.1%}")
    print(f"   Disk hit rate: {stats['disk']['hit_rate']:.1%}")

    # Demonstrate cache cleanup
    print("\n🧹 Cache Cleanup:")
    cleanup_stats = adapter._cache.cleanup()
    print(f"   Expired entries removed: {cleanup_stats['total_evicted']}")

    print("\n✅ Caching demonstration complete!")
    print("💡 The cache will persist between runs and automatically clean up expired entries.")


async def adapter_integration_example():
    """
    Example of how to integrate caching into a new adapter.

    This shows the pattern that other adapters should follow.
    """

    print("\n🔧 Adapter Integration Pattern:")
    print("=" * 40)

    code_example = '''
# In your adapter's __init__ method:
from ..cache import get_cache

def __init__(self, config):
    super().__init__(config)
    # ... other initialization ...
    self._cache = get_cache()  # Get global cache instance

# In expensive methods, add caching:
async def get_expensive_data(self, param: str) -> Optional[Dict]:
    """Get expensive data with caching."""

    # Create unique cache key
    cache_key = f"expensive_data_{param}"

    # Try cache first
    cached_data = self._cache.get(cache_key, namespace="your_adapter")
    if cached_data is not None:
        return cached_data

    # Fetch from API
    data = await self._fetch_from_api(param)

    # Cache result (with appropriate TTL)
    if data:
        self._cache.set(cache_key, data, ttl=3600, namespace="your_adapter")

    return data
'''

    print(code_example)

    print("📝 Key Integration Points:")
    print("   1. Import get_cache in adapter __init__")
    print("   2. Create descriptive cache keys")
    print("   3. Use appropriate TTL values (seconds)")
    print("   4. Use namespaces to avoid key collisions")
    print("   5. Handle cache misses gracefully")


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(demonstrate_caching())
    asyncio.run(adapter_integration_example())
