# apps/shopper-domain/src/storage/deal_storage.py
import json
import logging
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

import redis.asyncio as redis

try:
    from src.storage.cycle_helper import get_circular_cycle_key, get_spanning_cycle_keys
except ImportError:
    from .cycle_helper import get_circular_cycle_key, get_spanning_cycle_keys

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = os.getenv(
    "DEAL_DATA_DIR",
    str(Path(__file__).resolve().parent.parent.parent / "data" / "deals"),
)

PRIMARY_CATEGORIES = {"meat", "seafood"}


def is_primary_deal(deal: dict[str, Any]) -> bool:
    category = (
        deal.get("normalized_category")
        or deal.get("category")
        or ""
    ).strip().lower()
    return category in PRIMARY_CATEGORIES


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
        # 1. Split deals into primary (meat/seafood) and secondary buckets
        primary_deals = [d for d in deals if is_primary_deal(d)]
        secondary_deals = [d for d in deals if not is_primary_deal(d)]

        buckets = {
            "primary": primary_deals,
            "secondary": secondary_deals,
        }

        # Calculate Redis TTL matching flyer expiry
        valid_to_utc = (
            valid_to.astimezone(timezone.utc)
            if valid_to.tzinfo
            else valid_to.replace(tzinfo=timezone.utc)
        )
        now_utc = datetime.now(timezone.utc)
        diff_seconds = int((valid_to_utc - now_utc).total_seconds())
        ttl_seconds = max(diff_seconds, 86400)

        cycles = get_spanning_cycle_keys(valid_from, valid_to)
        written_paths = []

        # 2. Persist both buckets to disk and Redis
        for bucket_name, bucket_deals in buckets.items():
            payload = {
                "store_id": store_id,
                "tier": bucket_name,
                "valid_from": valid_from.isoformat(),
                "valid_to": valid_to.isoformat(),
                "deals": bucket_deals,
            }
            serialized = json.dumps(payload, default=str)

            # Persist to disk partition for each active cycle
            for cycle_key in cycles:
                cycle_dir = os.path.join(self.base_storage_dir, cycle_key)
                os.makedirs(cycle_dir, exist_ok=True)
                file_path = os.path.join(cycle_dir, f"{store_id}-{bucket_name}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(serialized)
                written_paths.append(file_path)

            # Cache in Redis with tiered key
            cache_key = f"deals:store:{store_id}:{bucket_name}"
            await self.redis.set(cache_key, serialized, ex=ttl_seconds)

        return written_paths

    async def get_deals_for_stores(
        self,
        store_ids: list[str],
        tier: str = "primary",  # "primary", "secondary", or "all"
    ) -> dict[str, list[dict[str, Any]]]:
        current_cycle = get_circular_cycle_key()
        results: dict[str, list[dict[str, Any]]] = {sid: [] for sid in store_ids}

        tiers_to_load = ["primary", "secondary"] if tier == "all" else [tier]

        for current_tier in tiers_to_load:
            keys = [f"deals:store:{sid}:{current_tier}" for sid in store_ids]
            cached_payloads = await self.redis.mget(keys)
            missing_sids = []

            for sid, raw in zip(store_ids, cached_payloads):
                if raw:
                    data = json.loads(raw)
                    results[sid].extend(data.get("deals", []))
                else:
                    missing_sids.append(sid)

            # Disk fallback for cache miss
            for sid in missing_sids:
                file_path = os.path.join(
                    self.base_storage_dir, current_cycle, f"{sid}-{current_tier}.json"
                )
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    data = json.loads(content)
                    results[sid].extend(data.get("deals", []))
                    # Warm Redis cache
                    await self.redis.set(
                        f"deals:store:{sid}:{current_tier}", content, ex=86400
                    )

        return results