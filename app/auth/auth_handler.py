import os
import jwt
import time
from typing import Dict

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
JWT_EXP_DELTA_SECONDS = os.getenv("JWT_EXP_DELTA_SECONDS")


def token_response(token: str):
    return {
        "access_token": token
    }

def sign_jwt(user_id: str) -> Dict[str, str]:
    """Generate a JWT token for a given user ID."""
    payload = {
        "user_id": user_id,
        "expires": time.time() + int(JWT_EXP_DELTA_SECONDS)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token_response(token)


def decode_jwt(token: str) -> dict:
    """Decode a JWT token and return the payload if valid, else return an empty dict."""
    try:
        decoded_token = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if decoded_token["expires"] >= time.time():
            return decoded_token
        else:
            return None
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None