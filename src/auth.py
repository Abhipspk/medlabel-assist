import hashlib
import hmac
import os
import time

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SECRET = os.environ.get("MEDLABEL_JWT_SECRET", "dev-only-secret-change-me")  # production: secrets manager
ALGO = "HS256"
TOKEN_MINUTES = 30
_SALT = b"demo-salt-not-for-production"


def _hash(password):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), _SALT, 100_000).hex()


# Demo users. A real deployment uses a user database or the company's SSO.
USERS = {
    "analyst1": {"role": "analyst", "hash": _hash("analyst-pass")},
    "auditor1": {"role": "auditor", "hash": _hash("auditor-pass")},
    "admin1": {"role": "admin", "hash": _hash("admin-pass")},
}


def authenticate(username, password):
    user = USERS.get(username)
    candidate = _hash(password)                       # always hash, so timing doesn't leak who exists
    if user and hmac.compare_digest(user["hash"], candidate):
        return {"user": username, "role": user["role"]}
    return None


def make_token(user):
    payload = {"sub": user["user"], "role": user["role"],
               "exp": int(time.time()) + TOKEN_MINUTES * 60}
    return jwt.encode(payload, SECRET, algorithm=ALGO)


bearer = HTTPBearer()


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        p = jwt.decode(creds.credentials, SECRET, algorithms=[ALGO])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    return {"user": p["sub"], "role": p["role"]}


def require_role(*roles):
    def dep(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Your role is not allowed to do this")
        return user
    return dep