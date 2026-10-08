# apps/shopper-domain/src/storage/deal_storage.py
import json
import logging
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Optional

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

PRIMARY_CATEGORIES = {
    "meat",
    "fresh meat",
    "poultry",
    "beef",
    "pork",
    "chicken",
    "meat & poultry",
    "meat and poultry",
    "seafood",
    "fresh seafood",
    "fish",
    "shellfish",
}


def normalize_category_key(category: str) -> str:
    """Normalizes category string to lowercase standard slug."""
    cat = category.strip().lower()
    if cat in {"meat", "meat & poultry", "meat and poultry", "poultry", "beef", "pork", "chicken"}:
        return "meat_and_poultry"
    if cat in {"seafood", "fish", "shellfish"}:
        return "seafood"
    if cat in {"produce", "fruits", "fruit", "vegetables", "vegetable"}:
        return "produce"
    if cat in {"dairy", "dairy & eggs", "dairy and eggs", "milk", "cheese", "eggs"}:
        return "dairy_and_eggs"
    if cat in {"bakery", "bread"}:
        return "bakery"
    if cat in {"frozen", "frozen foods"}:
        return "frozen"
    if cat in {"beverages", "drinks", "beverage", "soda"}:
        return "beverages"
    return "pantry"


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

    async def get_flyer_id_for_postal(
        self,
        postal_code: str,
        chain_id: str,
    ) -> Optional[str]:
        cache_key = f"deals:flyer:{postal_code}:{chain_id}"
        val = await self.redis.get(cache_key)
        return str(val) if val is not None else None

    async def set_flyer_id_for_postal(
        self,
        postal_code: str,
        chain_id: str,
        flyer_id: Any,
        ttl: Optional[int] = None,
    ) -> None:
        cache_key = f"deals:flyer:{postal_code}:{chain_id}"
        if ttl is not None:
            await self.redis.set(cache_key, str(flyer_id), ex=int(ttl))
        else:
            await self.redis.set(cache_key, str(flyer_id))

    async def save_deals(
        self,
        flyer_id: str | None = None,
        deals: list[dict[str, Any]] | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        *,
        store_id: str | None = None,
    ) -> list[str]:
        target_id = str(flyer_id if flyer_id is not None else store_id)
        if deals is None:
            deals = []
        if valid_from is None:
            valid_from = datetime.now(timezone.utc)
        if valid_to is None:
            valid_to = datetime.now(timezone.utc)

        # 1. Split deals into primary (meat/seafood) and secondary buckets
        primary_deals = [d for d in deals if is_primary_deal(d)]
        secondary_deals = [d for d in deals if not is_primary_deal(d)]

        logger.info("Deals found for flyer_id=%s: %d primary, %d secondary", target_id, len(primary_deals), len(secondary_deals))

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

        # 2. Persist both buckets to disk and Redis using flyer_id
        for bucket_name, bucket_deals in buckets.items():
            payload = {
                "flyer_id": target_id,
                "store_id": target_id,
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
                file_path = os.path.join(cycle_dir, f"{target_id}-{bucket_name}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(serialized)
                written_paths.append(file_path)

            # Cache in Redis with flyer-tiered key
            cache_key = f"deals:flyer:{target_id}:{bucket_name}"
            await self.redis.set(cache_key, serialized, ex=ttl_seconds)

        # 3. Index deals by category in Redis sorted sets and deal hashes
        # Hash mapping: deals:data:{deal_id} -> JSON string
        # Sorted set / Set indexing by store & category: deals:store:{store_id}:cat:{category_slug} -> deal_id (score = deal_price)
        # Store all deals index: deals:store:{store_id}:all -> deal_id (score = deal_price)
        for deal in deals:
            d_id = str(deal.get("deal_id") or "")
            s_id = str(deal.get("store_id") or target_id)
            if not d_id:
                continue

            deal_json = json.dumps(deal, default=str)
            deal_data_key = f"deals:data:{d_id}"
            await self.redis.set(deal_data_key, deal_json, ex=ttl_seconds)

            norm_cat = str(deal.get("normalized_category") or deal.get("category") or "Pantry")
            cat_slug = normalize_category_key(norm_cat)
            price = float(deal.get("deal_price") or 0.0)

            # Add to store-category sorted set
            store_cat_key = f"deals:store:{s_id}:cat:{cat_slug}"
            try:
                await self.redis.zadd(store_cat_key, {d_id: price})
                await self.redis.expire(store_cat_key, ttl_seconds)
            except Exception:
                pass

            # Add to store all deals sorted set
            store_all_key = f"deals:store:{s_id}:all"
            try:
                await self.redis.zadd(store_all_key, {d_id: price})
                await self.redis.expire(store_all_key, ttl_seconds)
            except Exception:
                pass

        return written_paths

    async def get_deals_by_category(
        self,
        store_id: str,
        category: str,
        min_price: float = 0.0,
        max_price: float = float("inf"),
    ) -> list[dict[str, Any]]:
        """
        Query deals for a store filtered by normalized category without cross-contamination.
        """
        cat_slug = normalize_category_key(category)
        store_cat_key = f"deals:store:{store_id}:cat:{cat_slug}"
        deal_ids = await self.redis.zrangebyscore(store_cat_key, min=min_price, max=max_price)

        if not deal_ids:
            return []

        # Convert byte responses if any
        decoded_ids = [did.decode("utf-8") if isinstance(did, bytes) else str(did) for did in deal_ids]
        data_keys = [f"deals:data:{did}" for did in decoded_ids]
        cached_deals = await self.redis.mget(data_keys)

        results: list[dict[str, Any]] = []
        for raw in cached_deals:
            if raw:
                try:
                    results.append(json.loads(raw))
                except Exception:
                    pass
        return results

    async def get_deals_by_flyer_id(
        self,
        flyer_id: str,
        tier: str = "primary",  # "primary", "secondary", or "all"
    ) -> list[dict[str, Any]]:
        results = await self.get_deals_for_flyers([str(flyer_id)], tier=tier)
        return results.get(str(flyer_id), [])

    async def get_deals_for_flyers(
        self,
        flyer_ids: list[str],
        tier: str = "primary",  # "primary", "secondary", or "all"
    ) -> dict[str, list[dict[str, Any]]]:
        current_cycle = get_circular_cycle_key()
        results: dict[str, list[dict[str, Any]]] = {fid: [] for fid in flyer_ids}

        tiers_to_load = ["primary", "secondary"] if tier == "all" else [tier]

        for current_tier in tiers_to_load:
            keys = [f"deals:flyer:{fid}:{current_tier}" for fid in flyer_ids]
            cached_payloads = await self.redis.mget(keys)
            missing_fids = []

            for fid, raw in zip(flyer_ids, cached_payloads):
                if raw:
                    data = json.loads(raw)
                    results[fid].extend(data.get("deals", []))
                else:
                    missing_fids.append(fid)

            # Disk fallback for cache miss
            for fid in missing_fids:
                file_path = os.path.join(
                    self.base_storage_dir, current_cycle, f"{fid}-{current_tier}.json"
                )
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    data = json.loads(content)
                    results[fid].extend(data.get("deals", []))
                    # Warm Redis cache
                    await self.redis.set(
                        f"deals:flyer:{fid}:{current_tier}", content, ex=86400
                    )

        return results

    async def get_deals_for_stores(
        self,
        store_ids: list[str],
        tier: str = "primary",  # "primary", "secondary", or "all"
    ) -> dict[str, list[dict[str, Any]]]:
        # First check flyer keys (where target_id was store_id or flyer_id)
        results = await self.get_deals_for_flyers(store_ids, tier)

        # Check for any remaining missing stores in store context mappings or legacy store keys or disk
        missing_sids = [sid for sid in store_ids if not results.get(sid)]
        if missing_sids:
            current_cycle = get_circular_cycle_key()
            tiers_to_load = ["primary", "secondary"] if tier == "all" else [tier]

            for sid in list(missing_sids):
                try:
                    ctx_raw = await self.redis.get(f"deals:store:{sid}:context")
                    if ctx_raw:
                        ctx = json.loads(ctx_raw)
                        fid = ctx.get("flyer_id")
                        if fid and fid != sid:
                            flyer_deals = await self.get_deals_by_flyer_id(fid, tier=tier)
                            if flyer_deals:
                                results[sid].extend(flyer_deals)
                                missing_sids.remove(sid)
                except Exception:
                    pass

            for current_tier in tiers_to_load:
                legacy_keys = [f"deals:store:{sid}:{current_tier}" for sid in missing_sids]
                cached_payloads = await self.redis.mget(legacy_keys)
                for sid, raw in zip(missing_sids, cached_payloads):
                    if raw:
                        data = json.loads(raw)
                        results[sid].extend(data.get("deals", []))
                    else:
                        file_path = os.path.join(
                            self.base_storage_dir, current_cycle, f"{sid}-{current_tier}.json"
                        )
                        if os.path.exists(file_path):
                            with open(file_path, "r", encoding="utf-8") as f:
                                content = f.read()
                            data = json.loads(content)
                            results[sid].extend(data.get("deals", []))
                            await self.redis.set(
                                f"deals:flyer:{sid}:{current_tier}", content, ex=86400
                            )

        return results