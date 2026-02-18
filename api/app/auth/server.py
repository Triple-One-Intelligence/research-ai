import time
import jwt
import secrets
from fastapi import APIRouter, Depends, Form, Header, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from .config import (
    ACCESS_TOKEN_EXPIRE_SECONDS,
    JWT_SECRET,
    JWT_ALGORITHM,
    SERVER_CREDENTIALS,
)

# --- MODELS ---
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int

# --- JWT LOGIC ---
def create_token(sub: str, token_type: str, expires_delta: int) -> str:
    now = int(time.time())
    payload = {"sub": sub, "type": token_type, "exp": now + expires_delta, "iat": now}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "iat", "sub", "type"]},
    )

def oauth_error(error: str, status_code: int, www_authenticate: str | None = None):
    headers = {}
    if www_authenticate:
        headers["WWW-Authenticate"] = www_authenticate
    return JSONResponse(content={"error": error}, status_code=status_code, headers=headers)

basic = HTTPBasic(auto_error=False)

# --- ROUTER ---
router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/token", response_model=TokenResponse)
async def token(
    request: Request,
    grant_type: str = Form(...),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    basic_creds: HTTPBasicCredentials | None = Depends(basic),
):
    if "application/x-www-form-urlencoded" not in (request.headers.get("content-type") or "").lower():
        return oauth_error("invalid_request", status.HTTP_400_BAD_REQUEST)

    if grant_type != "client_credentials":
        return oauth_error("unsupported_grant_type", status.HTTP_400_BAD_REQUEST)

    cid = basic_creds.username if basic_creds else client_id
    csec = basic_creds.password if basic_creds else client_secret

    if not cid or not csec:
        return oauth_error(
            "invalid_client",
            status.HTTP_401_UNAUTHORIZED,
            www_authenticate='Basic realm="token"',
        )

    expected = SERVER_CREDENTIALS.get(cid)
    if not expected or not secrets.compare_digest(expected, csec):
        return oauth_error(
            "invalid_client",
            status.HTTP_401_UNAUTHORIZED,
            www_authenticate='Basic realm="token"',
        )

    return TokenResponse(
        access_token=create_token(cid, "access", ACCESS_TOKEN_EXPIRE_SECONDS),
        expires_in=ACCESS_TOKEN_EXPIRE_SECONDS,
    )


@router.get("/validate")
async def validate(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        return JSONResponse(
            content={"error": "missing_header"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        token_str = authorization[7:]
        payload = decode_token(token_str)
        if payload["type"] != "access":
            raise ValueError("Not an access token")
    except Exception:
        return JSONResponse(
            content={"error": "invalid_token"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    return JSONResponse(
        content={"status": "valid"},
        status_code=status.HTTP_200_OK,
        headers={"X-Auth-User": payload["sub"]},
    )
