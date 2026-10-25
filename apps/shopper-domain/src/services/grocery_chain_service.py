# apps/shopper-domain/src/services/grocery_chain_service.py
import logging
from typing import Any, Dict, List, Optional, cast
from config import SHOPPER_DATABASE_URL

try:
    import asyncpg  # type: ignore
except ImportError:
    asyncpg = None

logger = logging.getLogger(__name__)


class GroceryChainService:
    """
    Service responsible for grocery chain metadata retrieval and modifications.
    """

    _chains_cache: Optional[List[Dict[str, Any]]] = None
    _chain_by_id_cache: Dict[str, Dict[str, str]] = {}

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or SHOPPER_DATABASE_URL

    async def get_chain_metadata(self, chain_id: str) -> Dict[str, str]:
        """Retrieve grocery chain metadata from the database for a specific chain."""
        chain_key = chain_id.strip().lower()
        if self.db_url == SHOPPER_DATABASE_URL and chain_key in self._chain_by_id_cache:
            return dict(self._chain_by_id_cache[chain_key])

        conn = await asyncpg.connect(self.db_url)
        try:
            row: Any = await conn.fetchrow(
                "SELECT chain_id, display_name, adapter_name, spider_name, flyer_source_type "
                "FROM fn_get_grocery_chains($1);",
                chain_key,
            )
            if not row:
                raise ValueError(f"Unsupported chain: {chain_id}")
            chain_value = cast(str, row["chain_id"])
            spider_value = cast(Optional[str], row["spider_name"])
            flyer_source_value = cast(Optional[str], row["flyer_source_type"])
            spider = spider_value or chain_value
            metadata = {
                "chain_id": chain_value,
                "display_name": cast(str, row["display_name"]),
                "adapter_name": cast(str, row["adapter_name"]),
                "spider": spider,
                "spider_name": spider,
                "flyer_source_type": flyer_source_value or "flipp",
            }
            if self.db_url == SHOPPER_DATABASE_URL:
                self._chain_by_id_cache[chain_key] = metadata
                self._chain_by_id_cache[chain_value.strip().lower()] = metadata
            return metadata
        finally:
            await conn.close()

    async def get_all_chains(self) -> List[Dict[str, Any]]:
        """Retrieve all active grocery chains from the database."""
        if self.db_url == SHOPPER_DATABASE_URL and self._chains_cache is not None:
            return [dict(c) for c in self._chains_cache]

        conn = None
        try:
            conn = await asyncpg.connect(self.db_url, timeout=3)
            rows: Any = await conn.fetch(
                "SELECT chain_id, display_name, adapter_name, spider_name, flyer_source_type, is_active "
                "FROM fn_get_grocery_chains(NULL);"
            )
            chains: List[Dict[str, Any]] = []
            for row in rows:
                chain_value = cast(str, row["chain_id"])
                adapter_value = cast(str, row["adapter_name"])
                spider_value = cast(Optional[str], row["spider_name"])
                flyer_source_value = cast(Optional[str], row["flyer_source_type"])
                active_value = cast(Optional[bool], row.get("is_active", True))
                spider = spider_value or chain_value
                entry = {
                    "chain_id": chain_value,
                    "display_name": cast(str, row["display_name"]),
                    "adapter_name": adapter_value,
                    "spider": spider,
                    "spider_name": spider,
                    "flyer_source_type": flyer_source_value or "flipp",
                    "is_active": active_value if active_value is not None else True,
                }
                chains.append(entry)
                if self.db_url == SHOPPER_DATABASE_URL:
                    meta_str = {k: str(v) for k, v in entry.items() if k != "is_active"}
                    self._chain_by_id_cache[chain_value.strip().lower()] = meta_str
                    self._chain_by_id_cache[cast(str, row["display_name"]).strip().lower()] = meta_str
            if self.db_url == SHOPPER_DATABASE_URL and chains:
                GroceryChainService._chains_cache = chains
            return chains
        except Exception as exc:
            logger.warning("Failed to fetch all chains from database: %s", exc)
            return []
        finally:
            if conn is not None:
                await conn.close()

    async def upsert_chain(
        self,
        chain_id: str,
        display_name: str,
        adapter_name: str,
        spider_name: Optional[str] = None,
        flyer_source_type: str = "flipp",
    ) -> None:
        """Upsert grocery chain definition into the database."""
        conn = await asyncpg.connect(self.db_url)
        try:
            await conn.execute(
                "CALL sp_upsert_grocery_chain($1, $2, $3, $4, $5);",
                chain_id.strip().lower(),
                display_name,
                adapter_name,
                spider_name,
                flyer_source_type,
            )
            GroceryChainService._chains_cache = None
            GroceryChainService._chain_by_id_cache.clear()
        finally:
            await conn.close()
