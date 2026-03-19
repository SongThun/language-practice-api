import time
import uuid

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

security = HTTPBearer()

_JWT_AUDIENCE = "authenticated"
_JWT_ISSUER = f"{settings.SUPABASE_URL}/auth/v1"

# Cache the JWKS (JSON Web Key Set) from Supabase with TTL
_jwks_cache: tuple[dict, float] | None = None
_JWKS_TTL_SECONDS = 3600  # 1 hour

# Module-level httpx client for JWKS fetches
_http_client = httpx.AsyncClient()


async def _get_jwks() -> dict:
    """Fetch JWKS from Supabase for JWT verification. Cached for 1 hour."""
    global _jwks_cache

    if _jwks_cache is not None:
        data, fetched_at = _jwks_cache
        if time.monotonic() - fetched_at < _JWKS_TTL_SECONDS:
            return data

    jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    response = await _http_client.get(jwks_url)
    response.raise_for_status()
    data = response.json()
    _jwks_cache = (data, time.monotonic())
    return data


def _decode_hs256(token: str) -> uuid.UUID:
    """Decode an HS256 JWT using the Supabase JWT secret and return the user UUID."""
    secret = settings.SUPABASE_SERVICE_ROLE_KEY
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Server misconfigured: missing JWT verification key",
        )
    payload = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience=_JWT_AUDIENCE,
        issuer=_JWT_ISSUER,
    )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim",
        )
    return uuid.UUID(user_id)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> uuid.UUID:
    """Verify Supabase JWT and return the user_id (sub claim).

    Uses the Supabase JWKS endpoint to verify the token signature.
    Falls back to HS256 verification with the Supabase JWT secret if JWKS fails.
    """
    token = credentials.credentials

    try:
        # Try JWKS-based verification first
        jwks = await _get_jwks()
        # Extract the signing key from JWKS
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        keys_by_kid = {k["kid"]: k for k in jwks.get("keys", []) if "kid" in k}
        rsa_key = keys_by_kid.get(kid, {})

        if rsa_key:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=_JWT_AUDIENCE,
                issuer=_JWT_ISSUER,
            )
            user_id = payload.get("sub")
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing sub claim",
                )
            return uuid.UUID(user_id)
        else:
            # Fallback: verify with Supabase JWT secret (HS256)
            return _decode_hs256(token)

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {e}",
        ) from e
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify authentication token: JWKS fetch failed",
        ) from e
