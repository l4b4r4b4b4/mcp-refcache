#!/usr/bin/env python3
"""Manual test for async timeout and polling functionality.

This script demonstrates:
1. A slow function that exceeds async_timeout
2. Polling for task status with RefCache.get()
3. Eventual completion and result retrieval
"""

import asyncio
import time

from mcp_refcache import RefCache
from mcp_refcache.backends.task_memory import MemoryTaskBackend
from mcp_refcache.models import AsyncTaskResponse, CacheResponse


async def main() -> None:
    """Test async timeout and polling."""
    print("=" * 60)
    print("Testing Async Timeout and Polling")
    print("=" * 60)

    # Create cache with task backend
    cache = RefCache(name="test-async", task_backend=MemoryTaskBackend(max_workers=2))

    # Define a slow function
    @cache.cached(async_timeout=0.2)
    async def slow_computation(n: int) -> dict:
        """Simulate a slow computation."""
        await asyncio.sleep(1.0)  # Takes 1 second
        return {"result": n * 2, "computed_at": time.time()}

    print("\n1. Starting slow computation (will timeout after 0.2s)...")
    result = await slow_computation(42)

    print(f"\n2. Initial response: {result}")
    ref_id = result["ref_id"]
    assert result["status"] == "processing"
    assert result["is_async"] is True

    print(f"\n3. Polling for task status with ref_id={ref_id}...")

    # Poll for completion
    max_polls = 15
    for poll_count in range(1, max_polls + 1):
        await asyncio.sleep(0.2)

        # Use cache.get() to poll
        response = cache.get(ref_id)

        if isinstance(response, AsyncTaskResponse):
            if response.eta_seconds:
                print(
                    f"   Poll #{poll_count}: Status={response.status.value}, "
                    f"ETA={response.eta_seconds:.1f}s"
                )
            else:
                print(f"   Poll #{poll_count}: Status={response.status.value}")

            if response.progress:
                print(
                    f"              Progress={response.progress.current}/{response.progress.total}"
                )
        elif isinstance(response, CacheResponse):
            print(f"   Poll #{poll_count}: Task complete! Got cached result.")
            print(f"\n4. Final result: {response.preview}")
            break
        else:
            print(f"   Poll #{poll_count}: Unexpected response type: {type(response)}")
            break
    else:
        print(f"\n   Timeout: Task didn't complete after {max_polls} polls")

    # Verify we can retrieve the cached result
    print("\n5. Retrieving full value with resolve()...")
    final_value = cache.resolve(ref_id)
    print(f"   Value: {final_value}")
    assert final_value["result"] == 84

    print("\n" + "=" * 60)
    print("✅ Async polling test successful!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
