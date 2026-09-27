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

    def get_adapter(self, store_chain: str) -> BaseDealAdapter:
        """
        Case-insensitive lookup returning the adapter instance for a store chain.
        Raises ValueError if the chain is unknown.
        """
        if not store_chain:
            raise ValueError(
                f"Invalid store chain: '{store_chain}'. Supported chains: {self.supported_chains()}"
            )

        key = store_chain.strip().lower()
        if key not in self._registry:
            raise ValueError(
                f"Unsupported store chain: '{store_chain}'. Supported chains: {self.supported_chains()}"
            )
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
        storage: PartitionedDealStorage,
    ) -> dict[str, Any]:
        """
        Convenience method to resolve the adapter for store_chain, fetch normalized deals,
        persist them to local partition files and Redis via storage, and return a summary.
        """
        adapter = self.get_adapter(store_chain)
        logger.info(
            "Fetching circular deals for chain=%s store_id=%s postal_code=%s",
            store_chain,
            store_id,
            postal_code,
        )

        valid_from, valid_to, deals = await adapter.get_normalized_deals(
            postal_code=postal_code, store_id=store_id
        )

        deals_payload: list[dict[str, Any]] = [
            deal.model_dump(mode="json") if hasattr(deal, "model_dump") else (deal if isinstance(deal, dict) else deal.__dict__)
            for deal in deals
        ]

        partitions = await storage.save_deals(
            store_id=store_id,
            deals=deals_payload,
            valid_from=valid_from,
            valid_to=valid_to,
        )

        logger.info(
            "Successfully fetched and persisted %d deals for store %s into %d partition files",
            len(deals),
            store_id,
            len(partitions),
        )

        return {
            "store_chain": store_chain.strip().lower(),
            "store_id": store_id,
            "deal_count": len(deals),
            "partitions": partitions,
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
