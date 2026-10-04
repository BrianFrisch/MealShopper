import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException

from config import SHOPPER_DATABASE_URL
from models import AdminStoreImportRequest
from src.auth import require_admin_role
from src.services.store_importer import StoreImportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin/stores", tags=["Admin - Store Management"])


@router.post(
    "/import",
    dependencies=[Depends(require_admin_role)],
)
async def import_stores_admin(
    payload: AdminStoreImportRequest,
    current_admin: Dict[str, Any] = Depends(require_admin_role),
) -> Dict[str, Any]:
    importer = StoreImportService(db_url=SHOPPER_DATABASE_URL)
    try:
        result = await importer.run_import_alltheplaces(
            chain_id=payload.chain_id,
            region_state=payload.region,
            include_all_brands=payload.all_brands,
        )
        return {
            "status": "success",
            "initiated_by": current_admin.get("sub", "unknown_admin"),
            **result,
        }
    except Exception as exc:
        logger.error("Import operation failed: %r", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Import operation failed: {type(exc).__name__}: {str(exc) or repr(exc)}",
        )
