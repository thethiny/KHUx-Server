"""
sqex-bridge.jp session handshake handler.

v5.0.1: Client sends form-encoded UUID=<device_uuid>
v1.0.1: Client sends JSON {"UUID": "...", "deviceType": 2, "nativeToken": "..."}

Both return: {nativeSessionId, sharedSecurityKey}

CRITICAL: The v1.0.1 client does qmemcpy(v19, *(const void **)v8, sizeof(v19))
which copies exactly 32 bytes from the sharedSecurityKey string.
(libcocos2dcpp_0003.c line 955)
So the key string MUST be exactly 32 characters — the client uses the raw
ASCII bytes of the string as the AES-256 key.
"""

import json
import os
from uuid import uuid4

from fastapi import Request
from sqlalchemy.orm import Session as DBSession

from .models import Session, User


def _generate_key_string() -> str:
    """Generate a 32-character key string (16 random bytes hex-encoded)."""
    return os.urandom(16).hex()


def _parse_uuid_from_body(text: str) -> str:
    text = text.strip()
    if text.startswith("{"):
        data = json.loads(text)
        return data["UUID"]
    for pair in text.split("&"):
        if "=" in pair:
            key, _, value = pair.partition("=")
            if key.strip() == "UUID":
                return value.strip()
    raise ValueError("Missing UUID in request body")


async def bridge_login(request: Request, db: DBSession):
    body = await request.body()
    device_uuid = _parse_uuid_from_body(body.decode("utf-8"))

    user = db.query(User).filter(User.uuid == device_uuid).first()
    if user is None:
        user = User(uuid=device_uuid)
        db.add(user)
        db.commit()
        db.refresh(user)

    # 32-char hex string — client copies these 32 ASCII bytes as the AES key
    key_string = _generate_key_string()
    session_id = uuid4().hex
    native_token = uuid4().hex

    db.query(Session).filter(
        Session.user_id == user.id,
        Session.is_active == True,
    ).update({"is_active": False})

    session = Session(
        user_id=user.id,
        session_id=session_id,
        security_key=key_string.encode("ascii"),  # store the 32 ASCII bytes
        native_token=native_token,
    )
    db.add(session)
    db.commit()

    return {
        "nativeToken": native_token,
        "nativeSessionId": session_id,
        "sharedSecurityKey": key_string,
    }
