import os
import jwt
import time
from typing import List
from fastapi import HTTPException, Request

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
JWT_EXP_DELTA_SECONDS = os.getenv("JWT_EXP_DELTA_SECONDS")


async def create_acess_token(user_id: str, roles: List[str]) -> str:
    """
    Create JWT with roles and permissions.
    
    Claims include:
    - sub: user ID (standard JWT)
    - email: user email
    - roles: list of role names for client-side caching
    - session_id: unique for audit logging
    - iat/exp: standard timing
    
    Why am I including roles in JWT?
    - Reduces database queries (client-side permission check)
    - Avoids N+1 problem on every request
    - Trade-off: role changes have ~5 min latency (acceptable)
    """
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "roles": roles,
        "session_id": f"{user_id}-{int(time.time())}",
        "iat": int(time.time()),
        "exp": int(time.time()) + int(JWT_EXP_DELTA_SECONDS)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return {
        "access_token": token
    }


def decode_jwt(token: str) -> dict:
    """Decode a JWT token and return the payload if valid"""
    try:
        # As we already use the iat and exp claims, PyJWT will handle expiration validation
        decoded_token = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return decoded_token
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="JWT token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid JWT token")


def get_user_email_from_token(request: Request) -> str:
    """Extract user email from JWT token in request headers."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = auth_header.split(" ")[1]
    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return payload.get("user_id")  # user_id contains the email