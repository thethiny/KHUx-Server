"""
KHUx Private Server — Action handlers for v4.3.1.

Based on decompiled libcocos2dcpp.so (arm64-v8a) analysis.
"""

import logging
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
        "versionRes": 1,
        "versionDat": 1,
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
    return build_response(user, userAvatarParts=[])


@register(62)  # POST /tutorial/progress
def handle_tutorial_progress(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    progression = request_data.get("progression", 0)
    logger.info("TUTORIAL PROGRESS: progression=%s payload=%s", progression, request_data)
    return build_response(user,
        tutorial={
            "userTutorialId": 1,
            "progression": progression,
            "name": "",
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
            "hairPartsId": 0, "hairColorPartsId": 0,
            "facePartsId": 0, "bodyPartsId": 0, "skinPartsId": 0,
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
        staff=base, agreement=base, license=base, shikin=base,
        tokutei=base, store=base,
    )


@register(24)  # GET /system/coppa
def handle_coppa(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        misc={str(k): 0 for k in [116, 900, 901, 902, 903, 904, 905, 906, 907]},
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


@register(26)  # GET /system/resource
def handle_resource(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    import hashlib as _hashlib
    import os as _os
    base_url = "http://api.sp.kingdomhearts.com/data/resource"
    KEY = "5CA56C5827FA15CF1ECE2A37180953B801DEBFD0A71DD6AA6DD1D4F414A5FBC4"
    resource = {"revision": 1, "count": 0, "mode": 0, "minVersion": ""}
    # Serve resource files from D:/Modding/KHUx/R/
    RES_DIR = "D:/Modding/KHUx/R"
    if _os.path.isdir(RES_DIR):
        for fname in sorted(_os.listdir(RES_DIR)):
            if fname.endswith(".mp4"):
                name = fname.replace(".mp4", "")
                fpath = _os.path.join(RES_DIR, fname)
                with open(fpath, "rb") as f:
                    md5 = _hashlib.md5(f.read()).hexdigest()
                resource[name] = {
                    "revision": 1,
                    "url": f"{base_url}/{fname}",
                    "key": KEY,
                    "md5": md5,
                }
                resource["count"] += 1
    logger.info("RESOURCE: serving %d entries", resource["count"])
    return build_response(user, resource=resource, mode=0, minVersion="")


@register(61)  # POST /tutorial/user/create
def handle_tutorial_user_create(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    if user:
        user.tutorial_done = False
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


def default_handler(action_id: int, request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    logger.warning("Unhandled action_id=%d request_keys=%s", action_id, list(request_data.keys()))
    return build_response(user)
