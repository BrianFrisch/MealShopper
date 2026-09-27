from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

try:
    from src.ingestion.models import NormalizedDealItem
except ImportError:
    from ..models import NormalizedDealItem


class BaseDealAdapter(ABC):
    """
    Abstract base class for grocery store circular/deal adapters.
    """

    @abstractmethod
    async def get_normalized_deals(
        self,
        postal_code: str,
        store_id: str,
        merchant_name: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[datetime, datetime, list[NormalizedDealItem]]:
        """
        Fetch circular promotions for a given postal code and store ID,
        returning a tuple of (valid_from, valid_to, normalized_deals).
        """
        pass

    async def close(self) -> None:
        """Closes any underlying client or network connections."""
        pass

    async def __aenter__(self) -> "BaseDealAdapter":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
