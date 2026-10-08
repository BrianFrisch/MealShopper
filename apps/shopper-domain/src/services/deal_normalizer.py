import sys
from pathlib import Path

# Ensure shopper-domain root is in sys.path
_parent = str(Path(__file__).resolve().parent.parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from deal_normalizer import (
    VALID_CATEGORIES,
    NormalizedCategory,
    NormalizedDealItemOutput,
    DealExpansionItem,
    BatchDealExpansionResponse,
    NormalizedItem,
    DealExpansionResponse,
    needs_multi_item_expansion,
    expand_and_normalize_deals_batch,
    expand_and_normalize_deal,
    expand_and_normalize_deals,
    DealNormalizer,
    get_default_semaphore,
)

