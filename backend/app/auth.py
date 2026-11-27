from fastapi import Request, Response, Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import jwt, JWTError
from typing import Optional, Dict, Any
import time
import os

# OIDC configuration - these would typically come from settings
# Keycloak configuration
KEYCLOAK_URL: str = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_REALM: str = os.environ.get("KEYCLOAK_REALM", "sentinel")
KEYCLOAK_CLIENT_ID: str = os.environ.get("KEYCLOAK_CLIENT_ID", "sentinel-frontend")
KEYCLOAK_CLIENT_SECRET: str = os.environ.get("KEYCLOAK_CLIENT_SECRET", "")
OIDC_ISSUER: str = os.environ.get("OIDC_ISSUER", f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}")
OIDC_AUDIENCE: str = os.environ.get("OIDC_AUDIENCE", "sentinel-api")

# Cookie settings for session
AUTH_COOKIE_NAME: str = "sentinel_session"
AUTH_COOKIE_MAX_AGE: int = 86400  # 24 hours
AUTH_COOKIE_SAMESITE: str = "lax"
AUTH_COOKIE_SECURE: bool = False  # Set True in production with HTTPS


def _get_keycloak_jwks_url() -> str:
    """Get the JWKS URL from Keycloak."""
    return f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certificates"


def _verify_oauth2_token(
    token: str,
    expected_audience: str = OIDC_AUDIENCE,
) -> Dict[str, Any]:
    """Verify an OAuth2/JWT token from Keycloak."""
    try:
        # Get the token payload, verify signature using Keycloak's JWKS
        # In production, we'd fetch and cache the JWKS
        payload = jwt.decode(
            token,
            options={"verify_signature": False},  # TODO: enable with JWKS
            audience=expected_audience,
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
        )


class UserInfo:
    """Represents authenticated user info from OIDC."""
    def __init__(self, payload: Dict[str, Any]):
        self.sub: str = payload.get("sub", "")  # Keycloak user ID
        self.email: str = payload.get("email", "")
        self.name: str = payload.get("name", "")
        self.role: str = payload.get("role", "viewer")  # Default to viewer
        self.realms: list = payload.get("realm_access", {}).get("roles", [])
        self.resource_access: dict = payload.get("resource_access", {})

    @property
    def is_authenticated(self) -> bool:
        return bool(self.sub)

    @property
    def is_viewer(self) -> bool:
        return self.role == "viewer" or "viewer" in self.realms

    @property
    def is_operator(self) -> bool:
        return self.role == "operator" or "operator" in self.realms

    @property
    def is_admin(self) -> bool:
        return self.role == "admin" or "admin" in self.realms


def get_token_from_cookie(request: Request) -> Optional[str]:
    """Extract the auth token from the HttpOnly cookie."""
    cookie_val = request.cookies.get(AUTH_COOKIE_NAME)
    if not cookie_val:
        return None
    return cookie_val


def get_token_from_header(authorization: str = ...) -> Optional[str]:
    """Extract the auth token from the Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization[7:]


async def get_current_user(
    request: Request,
    token: str = Depends(get_token_from_header),
) -> UserInfo:
    """Dependency that validates the OIDC token and returns user info."""
    # Try cookie first, then header
    if not token:
        token = get_token_from_cookie(request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = _verify_oauth2_token(token)
    user = UserInfo(payload)

    if not user.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return user


async def get_optional_current_user(
    request: Request,
    token: str = Depends(get_token_from_header),
) -> Optional[UserInfo]:
    """Optional auth dependency - returns None if not authenticated."""
    if not token:
        token = get_token_from_cookie(request)

    if not token:
        return None

    try:
        payload = _verify_oauth2_token(token)
        return UserInfo(payload)
    except HTTPException:
        return None


# Role-based dependencies
def require_role(
    allowed_roles: list[str] = ["viewer", "operator", "admin"]
):
    """Create a dependency that requires specific roles."""
    async def dependency(
        current_user: UserInfo = Depends(get_current_user),
    ) -> UserInfo:
        if not any(
            getattr(current_user, f"is_{role}")
            for role in allowed_roles
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {allowed_roles}",
            )
        return current_user
    return dependency


require_viewer = require_role(["viewer", "operator", "admin"])
require_operator = require_role(["operator", "admin"])
require_admin = require_role(["admin"])
