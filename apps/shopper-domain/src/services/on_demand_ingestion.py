import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any

from src.ingestion.factory import DealAdapterFactory
from src.storage.deal_storage import PartitionedDealStorage

logger = logging.getLogger(__name__)


async def ingest_store_on_demand(
    store_id: str,
    chain: str,
    postal_code: str,
    storage: PartitionedDealStorage,
    factory: DealAdapterFactory,
    tier: str = "primary",
) -> list[dict[str, Any]]:
 
    # lock_key = f"lock:ingest:{store_id}"
    clean_chain = chain.strip().lower().replace(" ", "")
    lock_key = f"lock:ingest:{clean_chain}:{postal_code}"
 
    redis_client = storage.redis
    lock_ttl_seconds = 20

    # 1. Attempt to acquire ingestion lock
    acquired = await redis_client.set(lock_key, "1", nx=True, ex=lock_ttl_seconds)

    if not acquired:
        logger.info("Store %s is currently being ingested by another request. Awaiting result...", store_id)
        # Poll up to 25 seconds (50 x 500ms) for the scraping worker to complete
        for _ in range(50):
            await asyncio.sleep(0.5)
            flyer_id = await storage.get_flyer_id_for_postal(postal_code, chain)
            target_ids: list[str] = []
            if flyer_id:
                target_ids.append(flyer_id)
            if store_id:
                target_ids.append(store_id)
            for fid in target_ids:
                deals = await storage.get_deals_by_flyer_id(fid, tier)
                if deals:
                    return deals
            # If lock cleared, worker finished or released
            lock_val = await redis_client.get(lock_key)
            if not lock_val:
                # Lock released; give a quick second for keys to settle and check once more
                await asyncio.sleep(0.5)
                deals = await storage.get_deals_by_flyer_id(store_id, tier)
                if deals:
                    return deals
                break

        # Final fallback check
        flyer_id = await storage.get_flyer_id_for_postal(postal_code, chain)
        target_ids: list[str] = []
        if flyer_id:
            target_ids.append(flyer_id)
        if store_id:
            target_ids.append(store_id)
        for fid in target_ids:
            deals = await storage.get_deals_by_flyer_id(fid, tier)
            if deals:
                return deals
        return []

    try:
        adapter = await factory.get_or_load_adapter(chain)
    except Exception:
        adapter = factory.get_adapter(chain)
    if adapter is None:
        await redis_client.delete(lock_key)
        return []

    # 2. Worker executing the scrape
    try:
        # Step 4a: Call the adapter to fetch the metadata & flyer_id if supported
        flyer_id = None
        try:
            meta = await adapter.fetch_flyer_metadata(postal_code, chain_id=chain)
            if meta and meta[0]:
                flyer_id = str(meta[0])
        except Exception as exc:
            logger.warning("Error fetching flyer metadata for %s: %s", chain, exc)

        valid_from, valid_to, deals = await adapter.get_normalized_deals(
            postal_code=postal_code,
            store_id=store_id,
            merchant_name=chain,
        )
        if deals:
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

            return deal_dicts
        return []
    except Exception as exc:
        logger.error("On-demand ingestion failed for store %s (%s): %s", store_id, chain, exc, exc_info=True)
        return []
    finally:
        # 3. Always release lock so queued readers can complete immediately
        try:
            await redis_client.delete(lock_key)
        except Exception:
            pass
