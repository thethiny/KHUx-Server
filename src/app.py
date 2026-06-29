"""
KHUx Private Server - Main FastAPI application.

Serves both the sqex-bridge.jp session handshake and the encrypted game API.
Run with: uvicorn src.app:app --host 0.0.0.0 --port 443 --ssl-keyfile key.pem --ssl-certfile cert.pem
"""

import hashlib
import json
import logging
import time
from base64 import b64encode
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Header, Request, Response

logging.basicConfig(level=logging.DEBUG, stream=__import__('sys').stdout, force=True)
logger = logging.getLogger("khux")
from sqlalchemy.orm import Session as DBSession

from .bridge import bridge_login
from .crypto import decrypt_request, encrypt_response
from .handlers import build_ret, dispatch
from .models import Session, User, create_tables, get_engine, get_session

# v1.0.1 path → action index (from server_api.json)
V1_PATH_MAP = {
    "/system/status": 0, "/user": 1, "/user/start": 2, "/user/detail": 3,
    "/user/profile": 4, "/user/chat": 5, "/user/stone": 6, "/user/shop": 7,
    "/user/birthday": 8, "/user/sphere": 9, "/user/keyblade": 10,
    "/user/skill": 11, "/user/item": 12, "/user/medal": 13,
    "/user/material": 14, "/user/album": 15, "/user/title": 16,
    "/user/support": 17, "/user/present": 18, "/user/avatar": 19,
    "/user/avatar/all": 20, "/user/avatar/parts": 21, "/payment/info": 22,
    "/system/need/url": 23, "/system/coppa": 24, "/system/master": 25,
    "/system/resource": 26, "/system/resourceEv": 27,
    "/system/information/list": 28, "/system/information/list/151203": 29,
    "/system/information/detail": 30, "/system/serialcode": 31,
    "/system/serialcode/campaign": 32, "/system/invitecode": 33,
    "/system/push/regist": 34, "/system/push/help": 35,
    "/user/update": 36, "/user/gender/update": 37,
    "/user/playstyle/update": 38, "/user/title/update": 39,
    "/user/birthday/create": 40, "/user/avatar/update": 41,
    "/user/sphere/update": 42, "/user/keyblade/update": 43,
    "/user/medal/lock": 44, "/user/support/update": 45,
    "/medal/skill/update": 46, "/user/present/receive": 47,
    "/user/material/sell": 48, "/user/medal/sell": 49, "/skill/sell": 50,
    "/keyblade/burst/max": 51, "/keyblade/enhance": 52,
    "/user/medal/enhance": 53, "/user/medal/evolve": 54,
    "/skill/evolve": 55, "/mypage": 56,
    "/user/sphere/check": 57, "/login/token": 58, "/login": 59,
    "/login/bonus": 60, "/tutorial/user/create": 61,
    "/tutorial/progress": 62, "/tutorial/clear": 63,
    "/tutorial/status": 64, "/shop/medal/max": 66,
    "/shop/ap/recover": 67, "/user/sphere/buy": 68,
    "/union/change": 69, "/gacha/list": 70, "/gacha/draw": 71,
    "/purchase/prepare": 72, "/purchase/finish": 73,
    "/party/create": 74, "/party/update": 75, "/party/notice": 76,
    "/party/login": 77, "/party": 78, "/party/leave": 79,
    "/party/member/list": 80, "/party/search/active": 81,
    "/party/application/160310": 82, "/party/application/list": 83,
    "/party/application/cancel": 84, "/party/applicant/list": 85,
    "/party/applicant/agree": 86, "/party/applicant/reject": 87,
    "/party/leader/change": 88, "/party/admin/appoint": 89,
    "/party/admin/dismiss": 90, "/party/member/expel": 91,
    "/party/invite/search": 92, "/party/invite/offer/160310": 93,
    "/party/invite/list": 94, "/party/invite/cancel": 95,
    "/party/offer/list": 96, "/party/offer/agree": 97,
    "/party/offer/reject": 98, "/stage": 99, "/stage/160310": 100,
    "/stage/event": 101, "/stage/support/list": 102,
    "/stage/start": 103, "/stage/retire": 104, "/stage/continue": 105,
    "/stage/clear": 106, "/raid": 107, "/raid/list": 108,
    "/raid/reward": 109, "/raid/reward/151101": 110,
    "/raid/member": 111, "/raid/start": 112, "/raid/clear": 113,
    "/colosseum": 114, "/colosseum/reward/list": 115,
    "/colosseum/start": 116, "/colosseum/retire": 117,
    "/colosseum/clear": 118,
    "/ranking/weekly/user": 119, "/ranking/monthly/user": 120,
    "/ranking/weekly/user/own": 121, "/ranking/monthly/user/own": 122,
    "/ranking/lux": 123, "/ranking/lux/own": 124,
    "/ranking/party": 125, "/ranking/party/own": 126,
    "/ranking/colosseum": 127, "/ranking/colosseum/own": 128,
    "/ranking/parade": 129, "/ranking/reward/check": 130,
    "/campaign": 131, "/campaign/pincode": 132,
    "/campaign/pincode/status": 137, "/user/option": 138,
    "/user/option/update": 139, "/link/members": 140,
    "/user/link": 141, "/system/uuid": 144,
    "/user/album/challenge/update": 145,
}

# v5.0.1 path → action ID (kept for backwards compat)
V5_PATH_MAP = {
    "userData": 1, "startStage": 4, "endStage": 5, "equipMedal": 10,
    "levelUpMedal": 11, "evolveMedal": 12, "guiltMedal": 13,
    "equipKeyblade": 15, "getUserMaterials": 16, "configuration": 17,
    "eventData": 18, "activeCampaignIds": 34, "tutorial": 35,
    "eventCategory": 109, "campaigns": 143,
}

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

engine = get_engine()
SessionLocal = get_session(engine)


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Lifespan (startup/shutdown)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB tables on startup."""
    create_tables(engine)
    yield


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(title="KHUx Private Server", lifespan=lifespan)


@app.middleware("http")
async def log_response_headers(request: Request, call_next):
    response = await call_next(request)
    ct = response.headers.get("content-type", "NONE")
    logger.info("    [HEADER] %s %s -> content-type=%s", request.method, request.url.path, ct)
    return response

# ---------------------------------------------------------------------------
# Bridge endpoint (sqex-bridge.jp session handshake)
# ---------------------------------------------------------------------------


@app.post("/bridge/{path:path}")
@app.post("/bridge")
async def bridge_endpoint(request: Request, db: DBSession = Depends(get_db)):
    logger.info(">>> BRIDGE request: %s %s", request.method, request.url)
    result = await bridge_login(request, db)
    logger.info("<<< BRIDGE response: %s", result)
    return result


@app.put("/system/status")
@app.post("/system/status")
async def system_status(request: Request):
    """
    v1.0.1+: System status check. Client sends appSignature (MD5 hash),
    expects JSON with maintenance flag and an encrypted server URL.
    The server field is AES-encrypted with key = MD5(result + current).
    """
    body = await request.body()
    logger.info(">>> SYSTEM STATUS: %s", body)

    current_version = "1.0.1"
    server_url = "http://api.sp.kingdomhearts.com"

    # From decompiled code (libcocos2dcpp_0003.c lines 1150-1185):
    #   key_input = systemStatusUpdateResult + current  ("SoRaRiKuKaiRi" + "1.0.1")
    #   md5_hex = MD5(key_input) as hex string (32 chars = 0x20 bytes)
    #   Cipher::Cipher uses this 32-byte hex string directly as AES-256-CBC key
    md5_hex = hashlib.md5(("SoRaRiKuKaiRi" + current_version).encode()).hexdigest()
    aes_key = md5_hex.encode("ascii")  # 32 bytes (hex chars, not raw digest)
    from .crypto import encrypt
    encrypted_server = b64encode(encrypt(server_url.encode("utf-8"), aes_key)).decode("ascii")

    # The status callback checks: if (*(_DWORD *)(operator[]("maintenance") + 12))
    # In rapidjson, offset+12 is the type/flags field:
    #   kNullType=0, kFalseType=1, kTrueType=2, kObjectType=3, kNumberType=5/6
    # So JSON false (type=1) is truthy! JSON null (type=0) is falsy.
    # Integer 0 has kNumberType at offset+12 (nonzero) — also truthy.
    # Only null (type=0) or absent field works. Use 0 since the client
    # accesses it unconditionally (absent would crash), but actually
    # rapidjson operator[] returns a null ref for missing keys (type=0).
    # Safest: omit the field entirely — rapidjson returns kNullType(0) for missing keys.
    return {
        "appStatus": {
            "mode": "",
            "current": current_version,
            "server": encrypted_server,
        },
    }


@app.get("/login/token")
async def login_token(request: Request):
    """
    v1.0.1 action 57 (GET /login/token): Pre-session login token request.
    Returns the bridge URL so the client can create a session.
    Called BEFORE session exists — no X-Sqex-Hole-Nsid header yet.
    """
    logger.info(">>> LOGIN TOKEN: %s %s", request.method, request.url)
    return {
        "url": "http://api.sp.kingdomhearts.com/bridge",
        "nativeToken": "server-issued-token",
    }


@app.get("/")
@app.post("/")
async def root_endpoint(request: Request):
    body = await request.body()
    logger.info(">>> ROOT request: %s %s headers=%s body=%s",
                request.method, request.url, dict(request.headers), body[:200])
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_action_id(request_path: str) -> int:
    """Map a URL path to an action ID. Checks v1.0.1 paths first, then v5.0.1."""
    clean = "/" + request_path.strip("/") if not request_path.startswith("/") else request_path
    if clean in V1_PATH_MAP:
        return V1_PATH_MAP[clean]
    segment = clean.rsplit("/", 1)[-1]
    if segment.isdigit():
        return int(segment)
    return V5_PATH_MAP.get(segment, -1)


# ---------------------------------------------------------------------------
# Game API endpoint
# ---------------------------------------------------------------------------


@app.api_route("/login/{path:path}", methods=["POST"])
@app.api_route("/login", methods=["POST"])
@app.api_route("/system/{path:path}", methods=["GET", "POST", "PUT"])
@app.api_route("/user/{path:path}", methods=["GET", "POST", "PUT"])
@app.api_route("/user", methods=["GET", "POST", "PUT"])
@app.api_route("/medal/{path:path}", methods=["GET", "POST", "PUT"])
@app.api_route("/skill/{path:path}", methods=["GET", "POST", "PUT"])
@app.api_route("/keyblade/{path:path}", methods=["GET", "POST", "PUT"])
@app.api_route("/mypage", methods=["GET", "POST"])
@app.api_route("/stage/{path:path}", methods=["GET", "POST", "PUT"])
@app.api_route("/stage", methods=["GET", "POST"])
@app.api_route("/raid/{path:path}", methods=["GET", "POST", "PUT"])
@app.api_route("/raid", methods=["GET", "POST"])
@app.api_route("/colosseum/{path:path}", methods=["GET", "POST", "PUT"])
@app.api_route("/colosseum", methods=["GET", "POST"])
@app.api_route("/ranking/{path:path}", methods=["GET", "POST"])
@app.api_route("/campaign/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@app.api_route("/campaign", methods=["GET", "POST"])
@app.api_route("/gacha/{path:path}", methods=["GET", "POST"])
@app.api_route("/party/{path:path}", methods=["GET", "POST", "PUT"])
@app.api_route("/party", methods=["GET", "POST"])
@app.api_route("/shop/{path:path}", methods=["GET", "POST"])
@app.api_route("/union/{path:path}", methods=["GET", "POST"])
@app.api_route("/purchase/{path:path}", methods=["GET", "POST"])
@app.api_route("/payment/{path:path}", methods=["GET", "POST"])
@app.api_route("/link/{path:path}", methods=["GET", "POST"])
@app.api_route("/tutorial/{path:path}", methods=["GET", "POST", "PUT"])
async def game_api(
    request: Request,
    path: str = "",
    db: DBSession = Depends(get_db),
    x_sqex_hole_nsid: str = Header(None, alias="X-Sqex-Hole-Nsid"),
):
    """
    Game API endpoint. Handles both v1.0.1 (GET/POST with path-based routing)
    and v5.0.1 (POST /user/* with encrypted body).
    """
    full_path = request.url.path
    logger.info(">>> GAME API: %s %s nsid=%s", request.method, full_path, x_sqex_hole_nsid)

    if not x_sqex_hole_nsid:
        logger.warning("!!! No session ID header")
        return Response(content="Missing session", status_code=401)

    session = (
        db.query(Session)
        .filter(
            Session.session_id == x_sqex_hole_nsid,
            Session.is_active == True,
        )
        .first()
    )
    if session is None:
        return Response(content="Invalid session", status_code=401)

    session.last_active_at = datetime.utcnow()

    user = db.query(User).filter(User.id == session.user_id).first()
    if user is None:
        return Response(content="User not found", status_code=404)

    body = await request.body()
    body_str = body.decode("utf-8")

    # Try to decrypt (v5.0.1 encrypted body), fall back to raw parsing
    payload = {}
    if body_str:
        try:
            payload = decrypt_request(body_str, session.security_key)
        except Exception:
            # v1.0.1 may send unencrypted JSON or form-encoded
            try:
                payload = json.loads(body_str) if body_str.startswith("{") else {}
            except Exception:
                payload = {}

    action_id = _resolve_action_id(full_path)
    logger.info("    action_id=%d payload_keys=%s", action_id, list(payload.keys()) if payload else [])
    response_data = dispatch(action_id, payload, user, db)

    import json as _json
    resp_json = _json.dumps(response_data, separators=(",", ":"))
    logger.info("<<< Response action=%d: %s", action_id, resp_json[:500])

    # Return plain JSON with application/json content-type.
    # The v1.0.1 client detects response format from headers.
    db.commit()
    return Response(content=resp_json, media_type="application/json")


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def catch_all(request: Request, path: str = ""):
    body = await request.body()
    headers = dict(request.headers)
    logger.warning("!!! UNMATCHED %s /%s headers=%s body=%s",
                    request.method, path, headers, body[:500])
    from .handlers import build_response
    return build_response()
