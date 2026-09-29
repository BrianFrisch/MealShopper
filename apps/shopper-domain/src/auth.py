# apps/shopper-domain/src/auth.py
import logging
from typing import Any, Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

logger = logging.getLogger(__name__)
security = HTTPBearer()

def require_admin_role(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    token = credentials.credentials
    try:
        # Decode claims payload; Gateway handles edge verification
        payload = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": True,
                "verify_aud": False,
            },
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except Exception as exc:
        logger.error("Failed to decode token claims: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {exc}",
        )

    # Check for role claim (handles standard 'role' and MS claim URI)
    role = (
        payload.get("role")
        or payload.get("http://schemas.microsoft.com/ws/2008/06/identity/claims/role")
    )
    if role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator authorization required for this action",
        )

    return payload