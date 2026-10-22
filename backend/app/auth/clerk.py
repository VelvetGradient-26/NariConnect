from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.config import CLERK_ISSUER, CLERK_AUTHORIZED_PARTIES, AUTH_DEV_BYPASS

security = HTTPBearer()

DEV_TOKEN = "dev_test_123"
DEV_USER_ID = "dev_user_123"

# The Clerk instance publishes its public signing keys; keys are cached by the client.
_jwks_client = (
    jwt.PyJWKClient(f"{CLERK_ISSUER}/.well-known/jwks.json") if CLERK_ISSUER else None
)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials

    if not token:
        raise _unauthorized("Invalid authentication credentials")

    # Local testing only: enabled with AUTH_DEV_BYPASS=true
    if AUTH_DEV_BYPASS and token == DEV_TOKEN:
        return DEV_USER_ID

    if _jwks_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured (set CLERK_PUBLISHABLE_KEY)",
        )

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach Clerk to verify the token",
        )
    except jwt.PyJWTError as e:
        raise _unauthorized(f"Invalid token: {e}")

    try:
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=CLERK_ISSUER,
            options={"require": ["exp", "iss", "sub"]},
            leeway=10,  # tolerate small clock skew with Clerk (short-lived tokens)
        )
    except jwt.PyJWTError as e:
        raise _unauthorized(f"Invalid token: {e}")

    # Clerk sets `azp` to the origin that requested the token
    azp = decoded.get("azp")
    if azp and azp not in CLERK_AUTHORIZED_PARTIES:
        raise _unauthorized("Invalid token: unauthorized party")

    user_id = decoded.get("sub")
    if not user_id:
        raise _unauthorized("Invalid token: missing subject")
    return user_id
