import json
from datetime import datetime, timezone
import os
from typing import Any

import redis.asyncio as redis 
from src.storage.cycle_helper import get_circular_cycle_key, get_spanning_cycle_keys

from pathlib import Path

# Resolve to apps/shopper-domain/data/deals by default
DEFAULT_DATA_DIR = str(Path(__file__).resolve().parent.parent.parent / "data" / "deals")

class PartitionedDealStorage:
    def __init__(self, redis_client: redis.Redis, base_storage_dir: str | None = None):
        self.redis = redis_client
        self.base_storage_dir = base_storage_dir or DEFAULT_DATA_DIR

    async def save_deals(
        self,
        store_id: str,
        deals: list[dict[str, Any]],
        valid_from: datetime,
        valid_to: datetime,
    ) -> list[str]:
        payload = {
            "store_id": store_id,
            "valid_from": valid_from.isoformat(),
            "valid_to": valid_to.isoformat(),
            "deals": deals,
        }
        serialized = json.dumps(payload)

        # 1. Local partition store
        cycles = get_spanning_cycle_keys(valid_from, valid_to)
        written_paths = []
        for cycle_key in cycles:
            cycle_dir = os.path.join(self.base_storage_dir, cycle_key)
            os.makedirs(cycle_dir, exist_ok=True)
            file_path = os.path.join(cycle_dir, f"{store_id}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(serialized)
            written_paths.append(file_path)
            
        # 2. Redis active cache with TTL matching flyer expiry
        ttl_seconds = max(int((valid_to - datetime.now(timezone.utc)).total_seconds()), 3600)
        cache_key = f"deals:store:{store_id}"
        await self.redis.set(cache_key, serialized, ex=ttl_seconds)

        return written_paths

    async def get_deals_for_stores(self, store_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        current_cycle = get_circular_cycle_key()
        results: dict[str, list[dict[str, Any]]] = {}
        missing_store_ids = []

        # 1. Fast Redis query
        keys = [f"deals:store:{sid}" for sid in store_ids]
        cached_payloads = await self.redis.mget(keys)

        for sid, raw in zip(store_ids, cached_payloads):
            if raw:
                data = json.loads(raw)
                results[sid] = data.get("deals", [])
            else:
                missing_store_ids.append(sid)

        # 2. Blob / Local filesystem fallback
        for sid in missing_store_ids:
            file_path = os.path.join(self.base_storage_dir, current_cycle, f"{sid}.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                data = json.loads(content)
                results[sid] = data.get("deals", [])
                await self.redis.set(f"deals:store:{sid}", content, ex=86400)
            else:
                results[sid] = []

        return results