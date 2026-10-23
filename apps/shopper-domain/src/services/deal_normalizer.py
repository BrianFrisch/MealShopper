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
    NON_PRIMARY_MEAT_TERMS,
    is_excluded_primary_meat_item,
    resolve_protein_subtype,
    needs_multi_item_expansion,
    expand_and_normalize_deals_batch,
    expand_and_normalize_deal,
    expand_and_normalize_deals,
    DealNormalizer,
    get_default_semaphore,
)

