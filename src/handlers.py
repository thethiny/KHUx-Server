"""
KHUx Private Server — Action handlers for v4.3.1.

Based on decompiled libcocos2dcpp.so (arm64-v8a) analysis.
"""

import logging
import os
import time
from typing import Callable, Optional

from sqlalchemy.orm import Session as DBSession

from .models import User

logger = logging.getLogger(__name__)

handlers: dict[int, Callable] = {}


def register(action_id: int):
    def decorator(fn: Callable):
        handlers[action_id] = fn
        return fn
    return decorator


def dispatch(action_id: int, request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    handler = handlers.get(action_id)
    if handler:
        return handler(request_data, user, db_session)
    return default_handler(action_id, request_data, user, db_session)


def build_ret(user: Optional[User] = None) -> dict:
    """
    v4.3.1 Ret::parse (sub_67EB98) — 16 required fields.
    All booleans must be JSON bool, all numbers must be JSON int,
    serverTime is a Unix timestamp STRING.
    """
    return {
        "isMaintenance": False,
        "sessionTO": False,
        "isNewDayPeriod": 0,
        "versionApp": "1.0.1",
        "versionRes": 7,
        "versionDat": 3,
        "functionFlags": 0,
        "serverTime": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
    }


def build_response(user: Optional[User] = None, **extra) -> dict:
    resp = {"ret": build_ret(user)}
    resp.update(extra)
    return resp


# ---------------------------------------------------------------------------
# Login handlers (v4.3.1 uses /system/login and /khux/login)
# ---------------------------------------------------------------------------
@register(59)  # POST /login
def handle_login(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    is_new = not user.tutorial_done if user else True
    logger.info("LOGIN HANDLER: user=%s tutorial_done=%s is_new=%s",
                user.id if user else None, user.tutorial_done if user else None, is_new)
    return build_response(user,
        login={
            "newcomer": is_new,
            "tutorial": is_new,
            "acquirableLoginBonus": False,
            "progression": 0,
        },
        phase=0,
        popupFlag=0,
        isFinished=0,
    )


# ---------------------------------------------------------------------------
# Startup chain handlers
# ---------------------------------------------------------------------------
@register(6)  # GET /user/stone
def handle_user_stone(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userStone={"freeStone": 3000, "payStone": 0})


@register(7)  # GET /user/shop
def handle_user_shop(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userBenefits=[])


@register(9)  # GET /user/sphere
def handle_user_sphere(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        userSphere={"userSphereDatas": [], "notChargedSphereBoardIds": []})


@register(10)  # GET /user/keyblade
def handle_user_keyblade(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userKeyblades=[{
        "userKeybladeId": 1, "category": 0, "keybladeId": 1000,
        "deckMedals": [], "burst": 0,
        "totalAttack": 100, "totalDefense": 100,
        "isFavorite": 1, "getDatetime": "2026-01-01 00:00:00",
    }])


@register(11)  # GET /user/skill
def handle_user_skill(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userSkills=[])


@register(13)  # GET /user/medal
def handle_user_medal(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userMedals=[])


@register(14)  # GET /user/material
def handle_user_material(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userMaterials=[])


@register(16)  # GET /user/title
def handle_user_title(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userTitles=[])


@register(17)  # GET /user/support
def handle_user_support(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    uid = user.id if user else 1
    return build_response(user,
        supportUser={
            "supportUserId": uid, "level": 1, "partyId": 0,
            "userName": user.user_name if user else "Player",
            "titleLeftId": 0, "titleRightId": 0, "titlePlateId": 0,
            "userKeybladeId": 0, "keybladeId": 0,
            "userMedalId": 0, "medalId": 0,
            "lastActionDatetime": "2026-01-01 00:00:00",
        })


@register(20)  # GET /user/avatar/all
def handle_user_avatar_all(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userAvatars=[])


@register(21)  # GET /user/avatar/parts
def handle_user_avatar_parts(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    parts = [
        {"userAvatarPartsId": i + 1, "partsType": p_type, "avatarPartsId": p_id,
         "getDatetime": "2026-01-01 00:00:00"}
        for i, (p_type, p_id) in enumerate([
            (1, 30001), (1, 30002),   # body male/female
            (2, 20001), (2, 20002),   # face male/female
            (3, 40001), (3, 40002),   # hair male/female
        ])
    ]
    return build_response(user, userAvatarParts=parts)


@register(62)  # POST /tutorial/progress
def handle_tutorial_progress(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    progression = request_data.get("progression", 0)
    name = request_data.get("name", "")
    logger.info("TUTORIAL PROGRESS: progression=%s payload=%s", progression, request_data)
    if name and user:
        user.user_name = name
        db_session.add(user)
    return build_response(user,
        tutorial={
            "userTutorialId": 1,
            "progression": progression,
            "name": name or (user.user_name if user else ""),
            "inviteCode": "",
        },
    )


@register(64)  # GET /tutorial/status
def handle_tutorial_status(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, phase=0, popupFlag=0, isFinished=0)


@register(100)  # GET /stage/160310
def handle_stage(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, stories=[], newStageId=0)


@register(107)  # GET /raid
def handle_raid(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        raidStatus=0,
        raid={
            "raidId": 0, "level": 0, "useAp": 0,
            "timeLeft": "2099-01-01 00:00:00",
            "feverFlag": 0, "feverTime": "2099-01-01 00:00:00",
            "stageId": 0, "parts": [],
        })


@register(103)  # POST /stage/start
def handle_stage_start(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    logger.info("STAGE START: full payload = %s", request_data)
    stage_id = request_data.get("stageId", 1001010)
    keyblade_id = request_data.get("userKeybladeId", 1)
    return build_response(user,
        userRandomEnemies=[],
        userEnemyDropItems=[],
        userTreasures=[],
        startStageData={
            "stageId": stage_id,
            "supportUserId": 0,
            "userKeybladeId": keyblade_id,
            "clearMissionIds": [],
            "stageSkip": 0,
        },
        campaigns=[],
    )


@register(138)  # GET /user/option
def handle_user_option(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        userOption={"isNoticeAp": 0, "isNoticeHelp": 0, "isNoticeEvent": 0})


@register(141)  # GET /user/link
def handle_user_link(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, linkInfos=[])


# ---------------------------------------------------------------------------
# User data handler
# ---------------------------------------------------------------------------
@register(1)  # GET /user
def handle_user(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    uid = user.id if user else 1
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    resp = build_response(user)
    resp.update({
        "userData": {
            "user": {
                "userId": uid,
                "nativeUserId": uid,
                "platformId": 2,
                "userName": user.user_name if user else "Player",
                "gender": 0,
                "comment": "",
                "deviceType": 2,
                "continueLoginCount": 1,
                "isFleeze": 0,
                "fleezedDatetime": "2000-01-01 00:00:00",
                "nativeTagName": "player_tag",
            },
            "userDetail": {
                "level": 1, "exp": 0, "luxRank": 0, "luxGetRatio": 100,
                "titleLeftId": 0, "titleRightId": 0, "titlePlateId": 0,
                "maxDeckCost": 30,
                "playTimezones": [0, 0, 0, 0, 0, 0],
                "playFrequently": 0, "partyId": 0, "unionId": 1,
                "maxMedal": 100, "mvpCount": 0, "equipCoordinateNo": 0,
                "lastClearStageId": 0,
                "lastPlayNormalSphereBoardId": 0, "lastPlayStageSphereBoardId": 0,
                "lastPlayRaidSphereBoardId": 0, "lastPlayColosseumSphereBoardId": 0,
                "isGuilt": 0,
            },
            "userPoint": {
                "money": 0, "lux": 0, "totalLux": 0,
                "spherePoint": 0, "kizunaPoint": 0, "raidPoint": 0,
                "attack": 100, "defense": 100, "baseHp": 100,
                "hp": 100, "ap": 50, "maxHp": 100, "maxAp": 50,
                "lastApDatetime": now,
                "stageSpherePoint": 0, "raidSpherePoint": 0,
                "colosseumSpherePoint": 0, "stageSkipTicket": 0,
            },
            "lastActionDatetime": now,
            "stageResumption": {
                "resumptionStatus": 0,
                "stageId": 0,
                "raidId": 0,
                "colosseumStageId": 0,
            },
        },
        "userMedals": [],
        "userSkills": [],
        "userAvatar": {
            "myCoordinateNo": 0, "gender": 0,
            "hairPartsId": 40001, "hairColorPartsId": 0,
            "facePartsId": 20001, "bodyPartsId": 30001, "skinPartsId": 0,
            "accessoriesPartsIds": [],
        },
        "userKeyblade": {
            "userKeybladeId": 1, "category": 0, "keybladeId": 1000,
            "deckMedals": [], "burst": 0,
            "totalAttack": 100, "totalDefense": 100,
            "isFavorite": 1, "getDatetime": "2026-01-01 00:00:00",
        },
        "userRecord": {},
        "userRanking": {"lux": 0, "rank": 0},
        "userPopUp": {"isPopBenefitStone": 0},
        "linkPlatformId": "",
    })
    return resp


@register(2)  # GET /user/start
def handle_user_start(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user)


@register(5)  # GET /user/chat
def handle_user_chat(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    uid = user.id if user else 1
    return build_response(user,
        userData={
            "userChat": {
                "userId": uid,
                "tagName": "player_tag",
                "userEndpointUrl": "http://api.sp.kingdomhearts.com",
                "stampIds": [0, 0, 0, 0, 0, 0],
            },
        },
        authToken="server_auth_token",
        userToken="server_user_token",
    )


@register(78)  # GET /party
def handle_party(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        party={
            "partyId": 0,
            "unionId": 0,
            "rank": 0,
            "name": "",
            "playStyle": 0,
            "agreeType": 0,
            "message": "",
            "memberCount": 0,
            "leaderUserId": 0,
            "adminUserIds": [],
            "leaderAppointDate": "2000-01-01 00:00:00",
            "newcomerDate": "2000-01-01 00:00:00",
            "chatId": 0,
            "chatEndpointUrl": "",
        },
        supportUsers=[],
    )


@register(23)  # GET /system/need/url
def handle_need_url(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    base = "http://api.sp.kingdomhearts.com"
    return build_response(user,
        support=base, register=base, update=base, help=base,
        staff=base, agreement=f"{base}/agreement", license=f"{base}/agreement",
        shikin=base, tokutei=base, store=base,
    )


@register(24)  # GET /system/coppa
def handle_coppa(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    from datetime import datetime
    return build_response(user,
        misc={
            "116": 300,     # tutorial download jewel reward amount
            "900": 15,      # COPPA minimum age (chat restriction threshold)
            "901": 15,      # under-age bracket upper bound
            "902": 18,      # adult age threshold
            "903": 30,      # purchase limit $ for under-15
            "904": 100,     # purchase limit $ for 15-17
            "905": 1920,    # year picker start
            "906": datetime.now().year,  # year picker end (current year)
            "907": 0,       # 0=show birthday page, nonzero=skip
        },
    )


@register(25)  # GET /system/master
def handle_master(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    from .app import MASTER_TABLE_NAMES, _get_master_encrypted, MASTER_KEY_HEX
    base_url = "http://api.sp.kingdomhearts.com/data/master"
    resp = build_response(user, master={"revision": 1, "count": len(MASTER_TABLE_NAMES)})
    for i, name in enumerate(MASTER_TABLE_NAMES):
        _, md5_hex = _get_master_encrypted(name)
        resp[name] = {
            "revision": 1,
            "url": f"{base_url}/m{i:03d}.jpg",
            "key": MASTER_KEY_HEX,
            "md5": md5_hex,
        }
    logger.info("MASTER: serving %d tables (encrypted)", len(MASTER_TABLE_NAMES))
    return resp


import threading as _threading

_resource_md5_cache: dict = {}
_resource_md5_lock = _threading.Lock()
_resource_md5_ready = _threading.Event()


def _resource_md5(path: str) -> str:
    import hashlib as _hashlib
    _resource_md5_ready.wait()
    mtime = os.path.getmtime(path)
    cache_key = f"{path}:{mtime}"
    with _resource_md5_lock:
        cached = _resource_md5_cache.get(cache_key)
    if cached:
        return cached
    _hash_resource(path)
    with _resource_md5_lock:
        return _resource_md5_cache.get(cache_key, "")


def _hash_resource(path: str):
    import hashlib as _hashlib
    if not os.path.isfile(path):
        return
    mtime = os.path.getmtime(path)
    cache_key = f"{path}:{mtime}"
    size = os.path.getsize(path)
    logger.info("Hashing %s (%d MB)...", os.path.basename(path), size >> 20)
    h = _hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    with _resource_md5_lock:
        _resource_md5_cache[cache_key] = h.hexdigest()
    logger.info("Hashed %s -> %s", os.path.basename(path), _resource_md5_cache[cache_key])


RESOURCE_CHUNK_SIZE = 250 * 1024 * 1024


def _hash_resource_chunk(path: str, offset: int, end: int):
    import hashlib as _hashlib
    mtime = os.path.getmtime(path)
    cache_key = f"{path}:{mtime}:{offset}:{end}"
    h = _hashlib.md5()
    with open(path, "rb") as f:
        f.seek(offset)
        remaining = end - offset
        while remaining > 0:
            data = f.read(min(1 << 20, remaining))
            if not data:
                break
            h.update(data)
            remaining -= len(data)
    with _resource_md5_lock:
        _resource_md5_cache[cache_key] = h.hexdigest()


def _hash_resource_chunks(path: str, chunk_size: int):
    """Hash a file in fixed-size chunks and store per-chunk MD5s."""
    import hashlib as _hashlib
    if not os.path.isfile(path):
        return
    file_size = os.path.getsize(path)
    mtime = os.path.getmtime(path)
    logger.info("Hashing %s (%d MB) in %d MB chunks...",
                os.path.basename(path), file_size >> 20, chunk_size >> 20)
    with open(path, "rb") as f:
        offset = 0
        chunk_idx = 0
        while offset < file_size:
            end = min(offset + chunk_size, file_size)
            h = _hashlib.md5()
            f.seek(offset)
            remaining = end - offset
            while remaining > 0:
                data = f.read(min(1 << 20, remaining))
                if not data:
                    break
                h.update(data)
                remaining -= len(data)
            cache_key = f"{path}:{mtime}:{offset}:{end}"
            with _resource_md5_lock:
                _resource_md5_cache[cache_key] = h.hexdigest()
            logger.info("  chunk %d: %d-%d -> %s", chunk_idx, offset, end, _resource_md5_cache[cache_key])
            offset = end
            chunk_idx += 1
    _hash_resource(path)


def _prehash_resources():
    data_dir = os.environ.get("KHUX_DATA_DIR", "")
    repo_dir = os.environ.get("KHUX_REPO_DIR", "")
    misc_mp4 = os.path.join(data_dir, "misc.mp4")
    misc_png = os.path.join(repo_dir, "validate_data", "misc.png") if repo_dir else ""
    if misc_mp4:
        _hash_resource_chunks(misc_mp4, RESOURCE_CHUNK_SIZE)
    if misc_png:
        _hash_resource(misc_png)
    _resource_md5_ready.set()


_hash_thread = _threading.Thread(target=_prehash_resources, daemon=True)
_hash_thread.start()


@register(26)  # GET /system/resource
def handle_resource(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    base_url = "http://api.sp.kingdomhearts.com/data/resource"
    data_dir = os.environ["KHUX_DATA_DIR"]
    repo_dir = os.getenv("KHUX_REPO_DIR", "")
    misc_mp4 = os.path.join(data_dir, "misc.mp4")
    misc_png = os.path.join(repo_dir, "validate_data", "misc.png") if repo_dir else ""
    versions = []
    if os.path.isfile(misc_mp4) and misc_png and os.path.isfile(misc_png):
        file_size = os.path.getsize(misc_mp4)
        mtime = os.path.getmtime(misc_mp4)
        data_chunks = []
        offset = 0
        while offset < file_size:
            end = min(offset + RESOURCE_CHUNK_SIZE, file_size)
            chunk_size = end - offset
            cache_key = f"{misc_mp4}:{mtime}:{offset}:{end}"
            with _resource_md5_lock:
                md5 = _resource_md5_cache.get(cache_key, "")
            if not md5:
                _hash_resource_chunk(misc_mp4, offset, end)
                with _resource_md5_lock:
                    md5 = _resource_md5_cache.get(cache_key, "")
            data_chunks.append({
                "url": f"{base_url}/misc.mp4?offset={offset}&size={chunk_size}",
                "md5": md5,
                "size": chunk_size,
            })
            offset = end
        versions.append({
            "data": data_chunks,
            "index": [{
                "url": f"{base_url}/misc.png",
                "md5": _resource_md5(misc_png),
                "size": os.path.getsize(misc_png),
            }],
        })
    logger.info("RESOURCE: serving %d data chunks + index", len(versions[0]["data"]) if versions else 0)
    return build_response(user,
        resource={
            "mode": 1,
            "minVersion": 0,
            "versions": versions,
        },
    )


@register(61)  # POST /tutorial/user/create
def handle_tutorial_user_create(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    if user and not user.tutorial_done:
        db_session.add(user)
    return build_response(user,
        login={
            "newcomer": True,
            "tutorial": True,
            "acquirableLoginBonus": False,
            "progression": 0,
        },
        tutorial={
            "userTutorialId": 1,
            "progression": 0,
            "name": "",
            "inviteCode": "",
        },
        phase=0,
        popupFlag=0,
        isFinished=0,
    )


@register(28)  # GET /system/information/list
@register(29)  # GET /system/information/list/151203
def handle_information_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    from .information import NOTICES, CATEGORIES
    infos = []
    for n in NOTICES:
        cat_label, _ = CATEGORIES[n["cat"]]
        infos.append({
            "informationId": n["id"],
            "category": n["cat"],
            "categoryName": cat_label,
            "title": n["title"],
            "date": f"2026/{n['date']}",
            "isNew": 0,
        })
    return build_response(user, informations=infos)


@register(30)  # GET /system/information/detail
def handle_information_detail(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    info_id = request_data.get("informationId", 1)
    return build_response(user, information={
        "informationId": info_id,
        "url": f"http://api.sp.kingdomhearts.com/dark/information/detail/{info_id}",
    })


@register(76)  # GET /party/notice
def handle_party_notice(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, notice="")


@register(108)  # GET /raid/list
def handle_raid_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, raidList=[], raidBossList=[])


@register(129)  # GET /ranking/parade
def handle_ranking_parade(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, parades=[])


@register(131)  # GET /campaign
def handle_campaign(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, campaigns=[])


@register(56)  # GET /mypage
def handle_mypage(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        loginBonus=[],
        events=[],
        notifications=[],
    )


def default_handler(action_id: int, request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    logger.warning("Unhandled action_id=%d request_keys=%s", action_id, list(request_data.keys()))
    return build_response(user)
