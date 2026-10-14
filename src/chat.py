"""Party chat (the client's ChatManager; spec in recomp/JOURNAL.md 2026-10-15).

Chat is a separate REST service in the client: no game session, no encryption, raw JSON bodies (no Content-Type
sent), auth = header X-HTTP-USER-TOKEN (the userToken of /user/chat, action 5). Two base URLs:
`userChat.userEndpointUrl` (action 5) for /user..., and `party.chatEndpointUrl` + `party.chatId` for /chat/...
Both point at BASE (this router); chatId = the party id.

Client rules that matter:
- getUser's chatEntry must contain the player's party chatId, else opening chat fails (error 105000002).
- messages come in ascending messageNumber (1-based per chat); messageStatus != 0 hides one (deleted).
- nickName MUST be the sender's numeric user id (std::stoi; display name and rank come from the party list).
- chatUnreadCount = messages after the player's chatReadMessageNumber (PUT /user/chat/{chatId}).
- write calls only need a 2xx; responses need an application/json content type.
"""
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func

from .models import ChatBlock, ChatMessage, ChatRead, PartyMember, User

logger = logging.getLogger(__name__)

PREFIX = "/chatsvc"
BASE = "http://api.sp.kingdomhearts.com" + PREFIX
_SECRET = (os.environ.get("KHUX_CHAT_SECRET") or "khux-private-server-chat").encode()

router = APIRouter(prefix=PREFIX)
_get_db = None                       # set by app.py (its get_db dependency)


def token(uid: int) -> str:
    """The per-user chat token (action 5 userToken; sent back as X-HTTP-USER-TOKEN)."""
    sig = hmac.new(_SECRET, str(uid).encode(), hashlib.sha256).hexdigest()[:16]
    return f"{uid}.{sig}"


def tag_name(uid: int) -> str:
    return f"t_{uid}"


def stamp_ids() -> list:
    """Owned stamps: every valid stamp (GUESS: CH1 - the starting set is unknown)."""
    from .master import MASTER_JSON_DATA
    return [r["stampId"] for r in MASTER_JSON_DATA.get("stamp") or [] if r.get("validStamp")]


def _uid_from(request: Request):
    t = request.headers.get("X-HTTP-USER-TOKEN") or ""
    uid = t.split(".", 1)[0]
    return int(uid) if uid.isdigit() and hmac.compare_digest(token(int(uid)), t) else None


def _json(obj, status=200):
    return Response(content=json.dumps(obj), status_code=status, media_type="application/json")


async def _body(request: Request) -> dict:
    raw = await request.body()
    try:
        return json.loads(raw.decode("utf-8") or "{}")
    except ValueError:
        return {}


def _fmt(dt):
    """Chat times are Japan time (UTC+9): the client shows createAt minus 9 h plus the device's offset (the chat
    service was a separate Japanese server; the game API uses UTC)."""
    return (dt + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")


def _party_of(db, uid):
    m = db.get(PartyMember, uid)
    return m.party_id if m else 0


def _member(db, uid, chat_id):
    return bool(uid) and chat_id and _party_of(db, uid) == chat_id


def _last_number(db, chat_id):
    return db.query(func.max(ChatMessage.number)).filter(ChatMessage.chat_id == chat_id).scalar() or 0


def _db():
    yield from _get_db()


# --------------------------------------------------------------------------- /user ...
@router.get("/user")
def get_user(request: Request, db=Depends(_db)):
    uid = _uid_from(request)
    if uid is None:
        return _json({"error": "unauthorized"}, 401)
    entries = []
    chat_id = _party_of(db, uid)
    if chat_id:
        read = db.get(ChatRead, (uid, chat_id))
        read_no = read.read_number if read else 0
        unread = db.query(func.count(ChatMessage.id)).filter(
            ChatMessage.chat_id == chat_id, ChatMessage.number > read_no, ChatMessage.status == 0,
            ChatMessage.user_id != uid).scalar() or 0
        entries.append({"chatId": chat_id, "chatReadMessageNumber": read_no, "chatUnreadCount": unread})
    blocks = []
    for b in db.query(ChatBlock).filter(ChatBlock.user_id == uid):
        o = db.get(User, b.blocked_user_id)
        blocks.append({"tagName": tag_name(b.blocked_user_id), "userEndPointUrl": "",
                       "nickName": str(b.blocked_user_id), "userImageUrl": "",
                       "messageData": (o.user_name if o else ""), "createAt": _fmt(b.created_at)})
    return _json({"chatEntry": entries, "blockEntry": blocks})


@router.put("/user/chat/{chat_id}")
async def put_read(chat_id: int, request: Request, db=Depends(_db)):
    uid = _uid_from(request)
    if uid is None:
        return _json({"error": "unauthorized"}, 401)
    n = int((await _body(request)).get("chatReadMessageNumber") or 0)
    rec = db.get(ChatRead, (uid, chat_id)) or ChatRead(user_id=uid, chat_id=chat_id, read_number=0)
    rec.read_number = max(rec.read_number or 0, n)
    db.add(rec)
    db.commit()
    return _json({})


@router.post("/user/block")
async def block(request: Request, db=Depends(_db)):
    uid = _uid_from(request)
    if uid is None:
        return _json({"error": "unauthorized"}, 401)
    tag = str((await _body(request)).get("tagName") or "")
    target = int(tag[2:]) if tag.startswith("t_") and tag[2:].isdigit() else 0
    if target and target != uid and not db.get(ChatBlock, (uid, target)):
        db.add(ChatBlock(user_id=uid, blocked_user_id=target))
        db.commit()
    return _json({})


@router.delete("/user/block/{tag}")
def unblock(tag: str, request: Request, db=Depends(_db)):
    uid = _uid_from(request)
    if uid is None:
        return _json({"error": "unauthorized"}, 401)
    target = int(tag[2:]) if tag.startswith("t_") and tag[2:].isdigit() else 0
    rec = db.get(ChatBlock, (uid, target))
    if rec:
        db.delete(rec)
        db.commit()
    return _json({})


# --------------------------------------------------------------------------- /chat ...
@router.get("/chat/message/{chat_id}")
def get_messages(chat_id: int, request: Request, count: int = 100, startMessageNumber: int = 0,
                 startIndex: int = -1, db=Depends(_db)):
    uid = _uid_from(request)
    if uid is None:
        return _json({"error": "unauthorized"}, 401)
    if not _member(db, uid, chat_id):
        return _json({"entry": [], "startIndex": 0, "itemPerPage": count, "totalResults": 0})
    q = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id)
    total = q.count()
    if startMessageNumber > 0:
        rows = q.filter(ChatMessage.number >= startMessageNumber).order_by(ChatMessage.number).limit(count).all()
    elif startIndex >= 0:
        rows = q.order_by(ChatMessage.number).offset(startIndex).limit(count).all()
    else:                                            # newest `count`
        rows = sorted(q.order_by(ChatMessage.number.desc()).limit(count).all(), key=lambda m: m.number)
    entry = [{"messageNumber": m.number, "tagName": tag_name(m.user_id), "userEndPointUrl": "",
              "nickName": str(m.user_id), "userImageUrl": "", "messageData": m.data,
              "messageStatus": m.status, "createAt": _fmt(m.created_at)} for m in rows]
    return _json({"entry": entry, "startIndex": max(startIndex, 0), "itemPerPage": count, "totalResults": total})


@router.post("/chat/message/report")
async def report(request: Request, db=Depends(_db)):
    uid = _uid_from(request)
    logger.info("CHAT REPORT by %s: %s", uid, await _body(request))
    return _json({})


@router.post("/chat/message/{chat_id}/{_reply}")
async def post_message(chat_id: int, _reply: int, request: Request, db=Depends(_db)):
    uid = _uid_from(request)
    if uid is None:
        return _json({"error": "unauthorized"}, 401)
    if not _member(db, uid, chat_id):
        return _json({"error": "not a member"}, 403)
    text = str((await _body(request)).get("messageData") or "")[:500]
    if text.strip():
        n = _last_number(db, chat_id) + 1
        db.add(ChatMessage(chat_id=chat_id, number=n, user_id=uid, data=text, status=0, created_at=datetime.utcnow()))
        rec = db.get(ChatRead, (uid, chat_id)) or ChatRead(user_id=uid, chat_id=chat_id, read_number=0)
        rec.read_number = max(rec.read_number or 0, n)          # your own message is read
        db.add(rec)
        db.commit()
        logger.info("CHAT %s #%s from %s: %r", chat_id, n, uid, text[:80])
    return _json({})


@router.delete("/chat/message/{chat_id}/{number}")
def delete_message(chat_id: int, number: int, request: Request, db=Depends(_db)):
    uid = _uid_from(request)
    if uid is None:
        return _json({"error": "unauthorized"}, 401)
    m = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id, ChatMessage.number == number).first()
    if m and m.user_id == uid:
        m.status = 1
        db.commit()
    return _json({})
