from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException

from dependencies import get_store_repository
from geo_service import StoreRepository
from models import (
    LegacyStoreRequest,
    StoreContextResponse,
    StoreDiscoveryRequest,
    StoreDiscoveryResponse,
)

router = APIRouter(prefix="/v1/shopper/stores", tags=["Stores"])


@router.get("/{store_id}", response_model=StoreContextResponse)
async def get_store_v1(
    store_id: str,
    store_repo: StoreRepository = Depends(get_store_repository),
) -> StoreContextResponse:
    store = await store_repo.get_store_context(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found.")

    return StoreContextResponse(
        id=store.id,
        store_id=store.id,
        name=store.name,
        address=store.street,
        street=store.street,
        city=store.city,
        state=store.state,
        zip_code=store.zip_code,
        postal_code=store.zip_code,
    )


@router.post("/discover", response_model=StoreDiscoveryResponse)
async def discover_stores_v1(
    payload: StoreDiscoveryRequest,
    store_repo: StoreRepository = Depends(get_store_repository),
) -> StoreDiscoveryResponse:
    matched_stores = await store_repo.find_nearby(
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_miles=payload.radius_miles
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
    )
    return {
        "stores": [
            {
                "id": s.id,
                "store_id": s.id,
                "name": s.name,
                "address": s.street,
                "street": s.street,
                "city": s.city,
                "state": s.state,
                "zip_code": s.zip_code,
                "postal_code": s.zip_code,
                "distance_miles": s.distance_miles or 0.0,
            }
            for s in matched
        ]
    }
