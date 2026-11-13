import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any

from src.ingestion.factory import DealAdapterFactory
from src.services.categories import is_primary_deal
from src.storage.deal_storage import PartitionedDealStorage

logger = logging.getLogger(__name__)


def _filter_deals_by_tier(deals: list[dict[str, Any]], tier: str) -> list[dict[str, Any]]:
    normalized_tier = (tier or "primary").strip().lower()
    if normalized_tier == "primary":
        return [d for d in deals if is_primary_deal(d)]
    if normalized_tier == "secondary":
        return [d for d in deals if not is_primary_deal(d)]
    return deals


async def _find_cached_deals(
    storage: PartitionedDealStorage,
    postal_code: str,
    chain: str,
    store_id: str,
    tier: str,
    strict: bool = False,
) -> list[dict[str, Any]] | None:
    flyer_id = await storage.get_flyer_id_for_postal(postal_code, chain)
    target_ids: list[str] = []
    if flyer_id:
        target_ids.append(flyer_id)
    if store_id and (not strict or not flyer_id):
        target_ids.append(store_id)
    for fid in target_ids:
        deals = (
            await storage.get_complete_primary_deals(fid)
            if strict else await storage.get_deals_by_flyer_id(fid, tier)
        )
        if deals is not None and (strict or deals):
            return deals
    return None if strict else []


async def ingest_store_on_demand(
    store_id: str,
    chain: str,
    postal_code: str,
    storage: PartitionedDealStorage,
    factory: DealAdapterFactory,
    tier: str = "primary",
    strict: bool = False,
) -> list[dict[str, Any]]:
    clean_chain = chain.strip().lower().replace(" ", "")
    lock_key = f"lock:ingest:{clean_chain}:{postal_code}"

    redis_client = storage.redis
    lock_ttl_seconds = int(os.getenv("INGEST_LOCK_TTL_SECONDS", "20"))

    # 1. Attempt to acquire ingestion lock
    acquired = await redis_client.set(lock_key, "1", nx=True, ex=lock_ttl_seconds)

    if not acquired:
        logger.info("Store %s is currently being ingested by another request. Awaiting result...", store_id)
        max_polls = max(50, lock_ttl_seconds * 2)
        for _ in range(max_polls):
            await asyncio.sleep(0.5)
            cached = await _find_cached_deals(storage, postal_code, chain, store_id, tier, strict)
            if cached is not None and (strict or cached):
                return cached
            # If lock cleared, worker finished or released
            lock_val = await redis_client.get(lock_key)
            if not lock_val:
                await asyncio.sleep(0.5)
                cached = await _find_cached_deals(storage, postal_code, chain, store_id, tier, strict)
                if cached is not None and (strict or cached):
                    return cached
                break

        # Final fallback check before attempting recovery
        cached = await _find_cached_deals(storage, postal_code, chain, store_id, tier, strict)
        if cached is not None and (strict or cached):
            return cached

        # If previous worker crashed or timed out without saving deals, try acquiring the lock to recover
        acquired = await redis_client.set(lock_key, "1", nx=True, ex=lock_ttl_seconds)
        if not acquired:
            if strict:
                raise RuntimeError("Deal ingestion is still in progress")
            return []

    try:
        try:
            adapter = await factory.get_or_load_adapter(chain)
        except Exception as exc:
            logger.warning("Unable to load adapter for %s; checking registered adapters: %s", chain, exc)
            adapter = factory.get_adapter(chain)
    except Exception:
        await redis_client.delete(lock_key)
        raise
    if adapter is None:
        await redis_client.delete(lock_key)
        if strict:
            raise RuntimeError(f"No deal adapter available for {chain}")
        return []

    # 2. Worker executing the scrape
    try:
        # Step 4a: Call the adapter to fetch the metadata & flyer_id if supported
        flyer_id = None
        meta = None
        try:
            metadata_options = {"strict": True} if strict else {}
            meta = await adapter.fetch_flyer_metadata(postal_code, chain_id=chain, **metadata_options)
            if meta and meta[0]:
                flyer_id = str(meta[0])
        except Exception as exc:
            logger.warning("Error fetching flyer metadata for %s: %s", chain, exc)
            if strict:
                raise

        valid_from, valid_to, deals = await adapter.get_normalized_deals(
            postal_code=postal_code,
            store_id=store_id,
            merchant_name=chain,
            flyer_metadata=meta,
            **({"strict": True} if strict else {}),
        )
        if deals or strict:
            if not flyer_id:
                flyer_id = str(store_id)

            valid_to_utc = (
                valid_to.astimezone(timezone.utc)
                if valid_to.tzinfo
                else valid_to.replace(tzinfo=timezone.utc)
            )
            now_utc = datetime.now(timezone.utc)
            diff_seconds = int((valid_to_utc - now_utc).total_seconds())
            ttl_seconds = max(diff_seconds, 86400)

            # Step 4b: Cache routing key
            await storage.set_flyer_id_for_postal(postal_code, chain, flyer_id, ttl=ttl_seconds)

            # Cache store context for future lookups without query params
            try:
                store_ctx = {"postal_code": postal_code, "chain_id": chain, "flyer_id": flyer_id}
                await redis_client.set(f"deals:store:{store_id}:context", json.dumps(store_ctx), ex=ttl_seconds)
            except Exception:
                pass

            # Step 4c: Process and save deals by flyer_id
            deal_dicts: list[dict[str, Any]] = [
                d.model_dump(mode="json") if hasattr(d, "model_dump") else dict(d)
                for d in deals
            ]
            await storage.save_deals(flyer_id=flyer_id, deals=deal_dicts, valid_from=valid_from, valid_to=valid_to)

            return _filter_deals_by_tier(deal_dicts, tier)
        return []
    except Exception as exc:
        logger.error("On-demand ingestion failed for store %s (%s): %s", store_id, chain, exc, exc_info=True)
        if strict:
            raise
        return []
    finally:
        # 3. Always release lock so queued readers can complete immediately
        try:
            await redis_client.delete(lock_key)
        except Exception:
            pass
