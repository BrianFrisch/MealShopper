from typing import Any, Dict
from fastapi import APIRouter, Depends

from dependencies import get_store_repository
from geo_service import StoreRepository
from models import (
    LegacyStoreRequest,
    StoreDiscoveryRequest,
    StoreDiscoveryResponse,
)

router = APIRouter(prefix="/v1/shopper/stores", tags=["Stores"])


@router.post("/discover", response_model=StoreDiscoveryResponse)
async def discover_stores_v1(
    payload: StoreDiscoveryRequest,
    store_repo: StoreRepository = Depends(get_store_repository),
) -> StoreDiscoveryResponse:
    matched_stores = await store_repo.find_nearby(
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_miles=payload.radius_miles,
        max_stores=payload.max_stores,
    )
    return StoreDiscoveryResponse(
        stores=matched_stores,
        total_found=len(matched_stores),
    )


@router.post("")
@router.post("/")
async def discover_stores_legacy(
    payload: LegacyStoreRequest,
    store_repo: StoreRepository = Depends(get_store_repository),
) -> Dict[str, Any]:
    matched = await store_repo.find_nearby(
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_miles=payload.radius_miles,
        max_stores=payload.max_stores,
    )
    return {
        "stores": [
            {
                "id": s.id,
                "store_id": s.id,
                "name": s.name,
                "address": f"{s.street}, {s.city}",
                "distance_miles": s.distance_miles or 0.0,
            }
            for s in matched
        ]
    }
