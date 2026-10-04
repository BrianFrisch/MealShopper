import logging
from typing import Any, Dict, Optional
import httpx

try:
    from src.ingestion.adapters.base import BaseDealAdapter
    from src.ingestion.adapters.flipp_adapter import FlippAdapter, DEFAULT_TIMEOUT
    from src.ingestion.adapters.aldi_adapter import AldiAdapter
    from src.services.grocery_chain_service import GroceryChainService
except ImportError:
    from .adapters.base import BaseDealAdapter
    from .adapters.flipp_adapter import FlippAdapter, DEFAULT_TIMEOUT
    from .adapters.aldi_adapter import AldiAdapter
    from ..services.grocery_chain_service import GroceryChainService

logger = logging.getLogger(__name__)


class DealAdapterFactory:
    """
    Factory for instantiating and resolving store deal ingestion adapters.
    Maintains a registry of supported store chains populated dynamically from
    the database via GroceryChainService.
    """

    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = DEFAULT_TIMEOUT,
        db_url: Optional[str] = None,
        chain_service: Optional[Any] = None,
    ) -> None:
        self._client = client
        self._timeout = timeout
        self.chain_service = chain_service or GroceryChainService()
        self._registry: dict[str, BaseDealAdapter] = {}

    def _create_adapter_from_metadata(self, meta: Dict[str, Any]) -> BaseDealAdapter:
        """Instantiates an adapter instance based on chain metadata."""
        adapter_name = str(meta.get("adapter_name") or meta.get("chain_id") or "").strip().lower()
        display_name = str(meta.get("display_name") or meta.get("chain_id") or "").strip()

        if adapter_name == "aldi" or "aldi" in adapter_name:
            return AldiAdapter(client=self._client, timeout=self._timeout)
        return FlippAdapter(
            client=self._client,
            timeout=self._timeout,
            merchant_name=display_name or adapter_name.title(),
        )

    async def get_chain_metadata(self, chain_id: str) -> Dict[str, str]:
        """Retrieve grocery chain metadata from the database via GroceryChainService."""
        return await self.chain_service.get_chain_metadata(chain_id)

    async def load_chains_from_db(self) -> None:
        """Populate or update the adapter registry from the database using GroceryChainService."""
        try:
            chains = await self.chain_service.get_all_chains()
            for meta in chains:
                adapter = self._create_adapter_from_metadata(meta)
                chain_key = str(meta.get("chain_id") or "").strip().lower()
                if chain_key:
                    self._registry[chain_key] = adapter
                adapter_key = str(meta.get("adapter_name") or "").strip().lower()
                if adapter_key and adapter_key not in self._registry:
                    self._registry[adapter_key] = adapter
        except Exception as exc:
            logger.warning("Failed to populate chain adapters from database: %s", exc)

    async def get_or_load_adapter(self, store_chain: str) -> Optional[BaseDealAdapter]:
        """
        Retrieves adapter from cache or loads chain metadata dynamically from the DB.
        """
        if not store_chain:
            logger.warning("Empty store chain provided to DealAdapterFactory.")
            return None

        key = store_chain.strip().lower()
        if key in self._registry:
            return self._registry[key]

        try:
            await self.load_chains_from_db()
            if key in self._registry:
                return self._registry[key]

            meta = await self.chain_service.get_chain_metadata(key)
            adapter = self._create_adapter_from_metadata(meta)
            chain_key = str(meta.get("chain_id") or key).strip().lower()
            self._registry[chain_key] = adapter
            adapter_key = str(meta.get("adapter_name") or "").strip().lower()
            if adapter_key:
                self._registry.setdefault(adapter_key, adapter)
            return adapter
        except Exception as exc:
            logger.warning(
                "Unsupported store chain '%s'. Supported chains: %s. Proceeding without circular deals. (%s)",
                store_chain,
                self.supported_chains(),
                exc,
            )
            return None

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

