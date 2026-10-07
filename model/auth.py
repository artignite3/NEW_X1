"""Supabase session verification; deployment cannot silently disable authentication."""
from dataclasses import dataclass
from functools import lru_cache
import os
from uuid import UUID

import jwt
import requests
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from dotenv import load_dotenv

load_dotenv()
bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: str
    access_token: str | None = None
    is_admin: bool = False
    aal: str = "aal1"


def auth_config():
    environment = os.getenv("APP_ENV", "production")
    if environment not in {"development", "test", "staging", "production"}:
        raise HTTPException(503, "Invalid application environment")
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    required = environment in {"staging", "production"} or bool(url or key)
    if required and (not url.startswith("https://") or not key):
        raise HTTPException(503, "Authentication is not configured")
    return {"required": required, "url": url, "key": key}


@lru_cache(maxsize=4)
def jwks_client(url):
    return jwt.PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json", timeout=5,
                          cache_jwk_set=True, lifespan=300)


def verify_token(token, url):
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") not in {"RS256", "ES256"} or not header.get("kid"):
            raise jwt.InvalidTokenError("Use an asymmetric Supabase signing key")
        key = jwks_client(url).get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256", "ES256"],
            audience="authenticated", issuer=f"{url}/auth/v1",
            options={"require": ["exp", "iat", "sub", "iss", "aud"]})
        identity = str(UUID(claims["sub"]))
        if claims.get("role") != "authenticated" or claims.get("is_anonymous"):
            raise jwt.InvalidTokenError("User session required")
        metadata = claims.get("app_metadata") or {}
        if not isinstance(metadata, dict):
            raise jwt.InvalidTokenError("Invalid account metadata")
        admin = metadata.get("role") == "admin"
        aal = claims.get("aal", "aal1")
        # User metadata is never trusted to grant privileges.
        if admin and aal != "aal2":
            raise HTTPException(403, "Administrator authenticator verification required")
        return Principal(identity, token, admin, aal)
    except HTTPException:
        raise
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(503, "Authentication service temporarily unavailable")
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise HTTPException(401, "Invalid or expired session", headers={"WWW-Authenticate": "Bearer"})


def require_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    config = auth_config()
    if not config["required"]:
        return Principal("00000000-0000-0000-0000-000000000001")
    if credentials is None or len(credentials.credentials) > 8192:
        raise HTTPException(401, "Sign in to continue", headers={"WWW-Authenticate": "Bearer"})
    principal = verify_token(credentials.credentials, config["url"])
    if principal.aal != "aal2":
        try:
            response = requests.get(f"{config['url']}/auth/v1/user", timeout=5,
                headers={"apikey": config["key"], "Authorization": f"Bearer {principal.access_token}"})
            if response.status_code in {401, 403}:
                raise HTTPException(401, "Invalid or expired session")
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get("id") != principal.user_id:
                raise ValueError("Invalid account response")
            factors = data.get("factors") or []
            if not isinstance(factors, list) or not all(isinstance(f, dict) for f in factors):
                raise ValueError("Invalid factor response")
            if any(f.get("status") == "verified" for f in factors):
                raise HTTPException(403, "Complete authenticator verification to continue")
        except (requests.RequestException, ValueError, TypeError):
            raise HTTPException(503, "Authentication service temporarily unavailable")
    return principal
