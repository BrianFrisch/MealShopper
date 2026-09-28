import logging
from typing import Any, Optional
import httpx

try:
    from src.ingestion.adapters.base import BaseDealAdapter
    from src.ingestion.adapters.flipp_adapter import FlippAdapter, DEFAULT_TIMEOUT
    from src.ingestion.adapters.aldi_adapter import AldiAdapter
    from src.storage.deal_storage import PartitionedDealStorage
except ImportError:
    from .adapters.base import BaseDealAdapter
    from .adapters.flipp_adapter import FlippAdapter, DEFAULT_TIMEOUT
    from .adapters.aldi_adapter import AldiAdapter
    from ..storage.deal_storage import PartitionedDealStorage

logger = logging.getLogger(__name__)


class DealAdapterFactory:
    """
    Factory for instantiating and resolving store deal ingestion adapters.
    Maintains a registry of supported store chains and provides convenience
    orchestration for fetching and persisting normalized circular deals.
    """

    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._client = client
        self._timeout = timeout
        self._registry: dict[str, BaseDealAdapter] = {
            "ralphs": FlippAdapter(
                client=self._client, timeout=self._timeout, merchant_name="Ralphs"
            ),
            "aldi": AldiAdapter(client=self._client, timeout=self._timeout),
        }

    def register_adapter(self, store_chain: str, adapter: BaseDealAdapter) -> None:
        """Registers or overrides an adapter for a given store chain key."""
        if not store_chain:
            raise ValueError("store_chain cannot be empty")
        self._registry[store_chain.strip().lower()] = adapter

    def get_adapter(self, store_chain: str) -> Optional[Any]:
        """
        Retrieves an adapter for the specified chain.
        Returns None and logs a warning if the chain is unsupported.
        """
        if not store_chain:
            logger.warning("Empty store chain provided to DealAdapterFactory.")
            return None

        key = store_chain.strip().lower()
        if key not in self._registry:
            logger.warning(
                "Unsupported store chain '%s'. Supported chains: %s. Proceeding without circular deals.",
                store_chain,
                self.supported_chains(),
            )
            return None

        return self._registry[key]

    def supported_chains(self) -> list[str]:
        """Returns a list of all currently supported store chain keys."""
        return list(self._registry.keys())

    async def close(self) -> None:
        """Closes all underlying adapters in the registry."""
        for adapter in self._registry.values():
            await adapter.close()

    async def __aenter__(self) -> "DealAdapterFactory":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def fetch_and_persist(
        self,
        store_chain: str,
        store_id: str,
        postal_code: str,
        storage: Any
    ) -> dict[str, Any]:
        adapter = self.get_adapter(store_chain)
        if adapter is None:
            return {
                "store_chain": store_chain,
                "store_id": store_id,
                "deal_count": 0,
                "partitions": [],
                "status": "unsupported_chain",
            }

        try:
            valid_from, valid_to, deals = await adapter.get_normalized_deals(
                postal_code=postal_code,
                store_id=store_id,
                merchant_name=store_chain
            )
            if not deals:
                return {
                    "store_chain": store_chain,
                    "store_id": store_id,
                    "deal_count": 0,
                    "partitions": [],
                    "status": "no_deals_found",
                }

            deal_dicts = [d.model_dump() if hasattr(d, "model_dump") else d for d in deals]
            written_paths = await storage.save_deals(store_id, deal_dicts, valid_from, valid_to)

            return {
                "store_chain": store_chain,
                "store_id": store_id,
                "deal_count": len(deals),
                "partitions": written_paths,
                "status": "success",
            }
        except Exception as exc:
            logger.error(
                "Failed to fetch circular deals for '%s' (store %s): %s",
                store_chain,
                store_id,
                exc,
                exc_info=True,
            )
            return {
                "store_chain": store_chain,
                "store_id": store_id,
                "deal_count": 0,
                "partitions": [],
                "status": "error",
            }


async def fetch_and_persist(
    store_chain: str,
    store_id: str,
    postal_code: str,
    storage: PartitionedDealStorage,
    client: Optional[httpx.AsyncClient] = None,
) -> dict[str, Any]:
    """
    Module-level convenience function to fetch and persist deals using DealAdapterFactory.
    """
    factory = DealAdapterFactory(client=client)
    return await factory.fetch_and_persist(
        store_chain=store_chain,
        store_id=store_id,
        postal_code=postal_code,
        storage=storage,
    )
