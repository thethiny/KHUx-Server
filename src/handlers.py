"""
KHUx Private Server — Action handlers for v4.3.1.

Based on decompiled libcocos2dcpp.so (arm64-v8a) analysis.
"""

import hashlib
import logging
import os
import threading
import time
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy.orm import Session as DBSession

from .enums import Misc, clamp_progression
from .information import CATEGORIES, NOTICES
from .master import MASTER_KEY_HEX, MASTER_TABLE_NAMES, get_master_encrypted
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
        "versionRes": 0,  # tutorial flow handles initial download; >0 causes re-download every session (game never saves resource_revision)
        "versionDat": 24,   # must match master_rev; bumping forces re-download + "update detected" popup
        "functionFlags": 0,
        "serverTime": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
    }


def build_response(user: Optional[User] = None, **extra) -> dict:
    resp = {"ret": build_ret(user)}
    resp.update(extra)
    return resp


# ---------------------------------------------------------------------------
# Login handlers (v4.3.1 uses /system/login and /khux/login)
# DEBUG: set to a progression value to skip tutorial steps on fresh login
# 0=full tutorial, 7=skip to union selection, 995=tutorial done
DEBUG_SKIP_TO = int(os.getenv("KHUX_DEBUG_SKIP_TO", "0"))
DEBUG_MODE = bool(os.getenv("KHUX_DEBUG_MODE", ""))

# ---------------------------------------------------------------------------
@register(59)  # POST /login
def handle_login(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    raw_progression = user.tutorial_progression if user else 0
    if DEBUG_SKIP_TO and raw_progression < DEBUG_SKIP_TO:
        raw_progression = DEBUG_SKIP_TO
    progression = clamp_progression(raw_progression)
    newcomer = progression == 0
    tutorial = not user.tutorial_done and progression < 6 if user else True
    logger.info("LOGIN HANDLER: user=%s tutorial_done=%s progression=%s newcomer=%s tutorial=%s",
                user.id if user else None, user.tutorial_done if user else None,
                progression, newcomer, tutorial)
    return build_response(user,
        login={
            "newcomer": newcomer,
            "tutorial": tutorial,
            "acquirableLoginBonus": False,
            "progression": progression,
        },
        phase=50,
        popupFlag=0,
        isFinished=0,
    )


# ---------------------------------------------------------------------------
# Startup chain handlers
# ---------------------------------------------------------------------------
@register(6)  # GET /user/stone
def handle_user_stone(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userStone={"freeStone": user.free_stone if user else 300, "payStone": user.pay_stone if user else 0})


@register(7)  # GET /user/shop
def handle_user_shop(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userBenefits=[])


@register(9)  # GET /user/sphere
def handle_user_sphere(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        userSphere={"userSphereDatas": [], "notChargedSphereBoardIds": []})


def _get_player_stats(level: int) -> dict:
    from .master import MASTER_JSON_DATA
    players = MASTER_JSON_DATA.get("player", [])
    for p in players:
        if p.get("lv") == level:
            return p
    return {"lv": level, "needExp": 999999, "ap": 16, "cost": 42, "hp": 3000}


def _user_point(user: Optional[User]) -> dict:
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    if user:
        stats = _get_player_stats(user.level)
        return {
            "money": user.money, "lux": user.lux, "totalLux": user.total_lux,
            "spherePoint": 0, "kizunaPoint": 0, "raidPoint": 0,
            "attack": user.attack, "defense": user.defense, "baseHp": stats["hp"],
            "hp": stats["hp"], "ap": stats["ap"], "maxHp": stats["hp"], "maxAp": stats["ap"],
            "lastApDatetime": now,
            "stageSpherePoint": 0, "raidSpherePoint": 0,
            "colosseumSpherePoint": 0, "stageSkipTicket": 0,
        }
    return {
        "money": 0, "lux": 0, "totalLux": 0,
        "spherePoint": 0, "kizunaPoint": 0, "raidPoint": 0,
        "attack": 0, "defense": 0, "baseHp": 3000,
        "hp": 3000, "ap": 16, "maxHp": 3000, "maxAp": 16,
        "lastApDatetime": now,
        "stageSpherePoint": 0, "raidSpherePoint": 0,
        "colosseumSpherePoint": 0, "stageSkipTicket": 0,
    }


def _user_avatar(user: Optional[User]) -> dict:
    if not user:
        return {"myCoordinateNo": 0, "gender": 0,
                "hairPartsId": 40001, "hairColorPartsId": 0,
                "facePartsId": 20001, "bodyPartsId": 30001, "skinPartsId": 0,
                "accessoriesPartsIds": []}
    acc = [int(x) for x in user.accessories_parts_ids.split(",") if x] if user.accessories_parts_ids else []
    return {"myCoordinateNo": user.equip_coordinate_no, "gender": user.gender,
            "hairPartsId": user.hair_parts_id, "hairColorPartsId": user.hair_color_parts_id,
            "facePartsId": user.face_parts_id, "bodyPartsId": user.body_parts_id,
            "skinPartsId": user.skin_parts_id, "accessoriesPartsIds": acc}


_STARTING_MEDALS = [
    {"userMedalId": 1, "medalId": 13021, "level": 1, "exp": 0,
     "attackUpperNumber": 0, "defenseUpperNumber": 0, "burstUpperNumber": 0,
     "lock": 0, "upperCost": 0, "guiltFactor": 0, "userSkills": [],
     "getDatetime": "2026-01-01 00:00:00"},
    {"userMedalId": 2, "medalId": 11021, "level": 1, "exp": 0,
     "attackUpperNumber": 0, "defenseUpperNumber": 0, "burstUpperNumber": 0,
     "lock": 0, "upperCost": 0, "guiltFactor": 0, "userSkills": [],
     "getDatetime": "2026-01-01 00:00:00"},
    {"userMedalId": 3, "medalId": 13031, "level": 1, "exp": 0,
     "attackUpperNumber": 0, "defenseUpperNumber": 0, "burstUpperNumber": 0,
     "lock": 0, "upperCost": 0, "guiltFactor": 0, "userSkills": [],
     "getDatetime": "2026-01-01 00:00:00"},
]


@register(10)  # GET /user/keyblade
def handle_user_keyblade(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userKeyblades=[{
        "userKeybladeId": 1, "category": 0, "keybladeId": 1000,
        "deckMedals": [1, 2, 3],
        "burst": 0,
        "totalAttack": 3960, "totalDefense": 3747,
        "isFavorite": 1, "getDatetime": "2026-01-01 00:00:00",
    }])


@register(11)  # GET /user/skill
def handle_user_skill(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userSkills=[])


@register(13)  # GET /user/medal
def handle_user_medal(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userMedals=_STARTING_MEDALS)


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
    return build_response(user, userAvatars=[_user_avatar(user)])


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


@register(37)  # POST /user/gender/update
def handle_gender_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    gender = request_data.get("gender", 0)
    logger.info("GENDER UPDATE: %s", gender)
    if user:
        user.gender = gender
        db_session.add(user)
    return build_response(user)


@register(41)  # POST /user/avatar/update
def handle_avatar_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    logger.info("AVATAR UPDATE: %s", request_data)
    if user:
        user.hair_parts_id = request_data.get("hairPartsId", user.hair_parts_id)
        user.hair_color_parts_id = request_data.get("hairColorPartsId", user.hair_color_parts_id)
        user.face_parts_id = request_data.get("facePartsId", user.face_parts_id)
        user.body_parts_id = request_data.get("bodyPartsId", user.body_parts_id)
        user.skin_parts_id = request_data.get("skinPartsId", user.skin_parts_id)
        acc = request_data.get("accessoriesPartsIds", [])
        user.accessories_parts_ids = ",".join(str(x) for x in acc) if acc else ""
        user.equip_coordinate_no = request_data.get("myCoordinateNo", user.equip_coordinate_no)
        db_session.add(user)
    return build_response(user, userAvatar=_user_avatar(user))


@register(63)  # POST /tutorial/clear
def handle_tutorial_clear(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    logger.info("TUTORIAL CLEAR: payload=%s", request_data)
    return build_response(user,
        login={
            "newcomer": False,
            "tutorial": False,
            "acquirableLoginBonus": False,
            "progression": 995,
        },
        partyId=0,
    )


@register(69)  # POST /union/change
def handle_union_change(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    union_id = request_data.get("unionId", 1)
    logger.info("UNION CHANGE: %s", union_id)
    if user:
        user.union_id = union_id
        db_session.add(user)
    return build_response(user)


_PROGRESSION_MAP = {0: 0, 1: 1, 3: 3, 4: 4, 5: 5, 6: 6, 995: 995}


@register(62)  # POST /tutorial/progress
def handle_tutorial_progress(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    raw_progression = request_data.get("progression", 0)
    progression = _PROGRESSION_MAP.get(raw_progression, raw_progression)
    if DEBUG_SKIP_TO and progression < DEBUG_SKIP_TO:
        progression = DEBUG_SKIP_TO
    name = request_data.get("name", "")
    logger.info("TUTORIAL PROGRESS: raw=%s mapped=%s (skip_to=%s) payload=%s",
                raw_progression, progression, DEBUG_SKIP_TO, request_data)
    if user:
        if name:
            user.user_name = name
        avatar_data = request_data.get("updateAvatarData")
        if avatar_data:
            user.gender = avatar_data.get("gender", user.gender)
            user.hair_parts_id = avatar_data.get("hairPartsId", user.hair_parts_id)
            user.hair_color_parts_id = avatar_data.get("hairColorPartsId", user.hair_color_parts_id)
            user.face_parts_id = avatar_data.get("facePartsId", user.face_parts_id)
            user.body_parts_id = avatar_data.get("bodyPartsId", user.body_parts_id)
            user.skin_parts_id = avatar_data.get("skinPartsId", user.skin_parts_id)
            acc = avatar_data.get("accessoriesPartsIds", [])
            user.accessories_parts_ids = ",".join(str(x) for x in acc) if acc else ""
        union_id = request_data.get("unionId")
        if union_id is not None:
            user.union_id = union_id
        if progression > user.tutorial_progression:
            user.tutorial_progression = progression
        if raw_progression >= 995: # Union is at 6, tutorial at 995. Must be set to 6 to avoid re-download on failed tutorial.
            user.tutorial_done = True
        db_session.add(user)
    tutorial_resp = {
        "userTutorialId": 1,
        "progression": progression,
        "name": name or (user.user_name if user else ""),
        "inviteCode": "",
    }
    if progression >= 4:
        tutorial_resp["unionId"] = user.union_id if user else 0
    if progression >= 5:
        tutorial_resp["avatar"] = _user_avatar(user)
    newcomer = progression == 0
    tutorial_active = not user.tutorial_done if user else True
    return build_response(user,
        login={
            "newcomer": newcomer,
            "tutorial": tutorial_active,
            "acquirableLoginBonus": False,
            "progression": progression,
        },
        tutorial=tutorial_resp,
    )


@register(64)  # GET /tutorial/status
def handle_tutorial_status(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, phase=50, popupFlag=0, isFinished=0)


@register(65)  # PUT /tutorial/status
def handle_tutorial_status_put(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    phase = request_data.get("phase", 0)
    logger.info("TUTORIAL STATUS PUT: phase=%s", phase)
    if user and phase >= 995:
        user.tutorial_done = True
        db_session.add(user)
    return build_response(user, phase=phase, popupFlag=0, isFinished=0)


@register(100)  # GET /stage/160310
def handle_stage(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    if user and not user.tutorial_stage_reached:
        user.tutorial_stage_reached = True
        db_session.add(user)
    return build_response(user,
        stories=[
            {"stageId": 1010, "useAp": 0, "score": 0, "clearMissionIds": []},
        ],
        newStageId=1010,
        raidStatus=0,
        events=[],
        supportUsers=[],
    )


@register(80)  # GET /party/member/list
def handle_party_member_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    uid = user.id if user else 1
    return build_response(user,
        userParty={
            "userId": uid,
            "partyId": 0,
            "isJoin": 0,
            "isLeader": 0,
            "isAdmin": 0,
            "flagFirstReward": 0,
            "joinDate": "2026-01-01 00:00:00",
        },
        partyMembers=[],
    )


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


@register(110)  # GET /raid/reward/151101
def handle_raid_reward(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        userData={"userPoint": _user_point(user)},
        raidRewards=[],
    )


@register(103)  # POST /stage/start
def handle_stage_start(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    stage_id = request_data.get("stageId", 1010)
    keyblade_id = request_data.get("userKeybladeId", 1)
    logger.info("STAGE START: stageId=%s keybladeId=%s payload=%s", stage_id, keyblade_id, request_data)
    return build_response(user,
        userData={"userPoint": _user_point(user)},
        userRandomEnemies=[],
        userEnemyDropItems=[
            {"uniqueEnemyId": 2, "dropItemTypeIds": [11, 13]},
            {"uniqueEnemyId": 3, "dropItemTypeIds": [11, 13]},
            {"uniqueEnemyId": 5, "dropItemTypeIds": [11, 13]},
            {"uniqueEnemyId": 6, "dropItemTypeIds": [11, 13]},
            {"uniqueEnemyId": 8, "dropItemTypeIds": [11, 13]},
            {"uniqueEnemyId": 9, "dropItemTypeIds": [11, 13]},
            {"uniqueEnemyId": 10, "dropItemTypeIds": [11, 13]},
        ],
        userTreasures=[
            {"uniqueTreasureId": 11, "dropItemTypeIds": [11, 13]},
        ],
        startStageData={
            "stageId": stage_id,
            "supportUserId": 0,
            "userKeybladeId": keyblade_id,
            "clearMissionIds": [],
            "stageSkip": 0,
        },
        campaigns=[],
        supportUsers=[],
    )


def _user_detail(user: Optional[User]) -> dict:
    return {
        "level": user.level if user else 1,
        "exp": user.exp if user else 0,
        "luxRank": user.lux_rank if user else 0,
        "luxGetRatio": 100,
        "titleLeftId": 0, "titleRightId": 0, "titlePlateId": 0,
        "maxDeckCost": user.max_deck_cost if user else 30,
        "playTimezones": [0, 0, 0, 0, 0, 0],
        "playFrequently": 0, "partyId": 0, "unionId": user.union_id if user else 1,
        "maxMedal": 100, "mvpCount": 0, "equipCoordinateNo": 0,
        "lastClearStageId": user.last_clear_stage_id if user else 0,
        "lastPlayNormalSphereBoardId": 0, "lastPlayStageSphereBoardId": 0,
        "lastPlayRaidSphereBoardId": 0, "lastPlayColosseumSphereBoardId": 0,
        "isGuilt": 0,
    }


def _stage_resumption(user=None) -> dict:
    # resumptionStatus=1 causes auto-battle-start with stageId=0 (broken)
    # until proper battle resumption is implemented, always return 0
    return {
        "resumptionStatus": 0,
        "stageId": 0,
        "raidId": 0,
        "colosseumStageId": 0,
    }


@register(106)  # POST /stage/clear
def handle_stage_clear(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    stage_id = request_data.get("stageId", 1010)
    logger.info("STAGE CLEAR: stageId=%s payload=%s", stage_id, request_data)
    if user:
        get_point = request_data.get("getPoint", {})
        user.exp += get_point.get("exp", 0)
        user.money += get_point.get("money", 0)
        user.lux += get_point.get("lux", 0)
        user.total_lux += get_point.get("lux", 0)
        user.last_clear_stage_id = stage_id
        while True:
            next_stats = _get_player_stats(user.level + 1)
            need = next_stats.get("needExp", 999999)
            if user.exp < need:
                break
            user.level += 1
            logger.info("LEVEL UP: -> %d (exp=%d, need=%d)", user.level, user.exp, need)
        db_session.add(user)
    return build_response(user,
        userData={
            "userPoint": _user_point(user),
            "userDetail": _user_detail(user),
            "stageResumption": _stage_resumption(user),
        },
        userStone={"freeStone": user.free_stone if user else 300, "payStone": user.pay_stone if user else 0},
        stageRewardUserMedalIds=[],
        firstClearFlag=1,
        userMaterials=[],
        userMedals=_STARTING_MEDALS,
        userSkills=[],
        userTitles=[],
        userKeyblades=[{
            "userKeybladeId": 1, "category": 0, "keybladeId": 1000,
            "deckMedals": [1, 2, 3],
            "burst": 0,
            "totalAttack": 3960, "totalDefense": 3747,
            "isFavorite": 1, "getDatetime": "2026-01-01 00:00:00",
        }],
    )


@register(137)  # GET /user/option
def handle_user_option(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        userOption={"isNoticeAp": 0, "isNoticeHelp": 0, "isNoticeEvent": 0})


@register(140)  # GET /user/link
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
                "gender": user.gender if user else 0,
                "comment": user.comment if user else "",
                "deviceType": 2,
                "continueLoginCount": 1,
                "isFleeze": 0,
                "fleezedDatetime": "2000-01-01 00:00:00",
                "nativeTagName": "player_tag",
            },
            "userDetail": _user_detail(user),
            "userPoint": _user_point(user),
            "lastActionDatetime": now,
            "stageResumption": _stage_resumption(user),
        },
        "userMedals": _STARTING_MEDALS,
        "userSkills": [],
        "userAvatar": _user_avatar(user),
        "userKeyblade": {
            "userKeybladeId": 1, "category": 0, "keybladeId": 1000,
            "deckMedals": [1],
            "burst": 0,
            "totalAttack": 3960, "totalDefense": 3747,
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
    uid = user.id if user else 1
    return build_response(user,
        partyId=0,
        party={
            "partyId": 0,
            "unionId": user.union_id if user else 0,
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
        partyLeader={
            "supportUserId": uid,
            "level": 1,
            "userName": user.user_name if user else "Player",
            "titleLeftId": 0, "titleRightId": 0, "titlePlateId": 0,
            "addKizunaPoint": 0,
            "keybladeId": 1000,
            "isParty": 0,
            "isGuilt": 0,
            "userMedal": _STARTING_MEDALS[0],
            "userSkills": [],
            "userAvatar": _user_avatar(user),
            "lastActionDatetime": "2026-01-01 00:00:00",
            "earnLuxRank": 0,
        },
        userParty={
            "userId": uid,
            "partyId": 0,
            "isJoin": 0,
            "isLeader": 0,
            "isAdmin": 0,
            "flagFirstReward": 0,
            "joinDate": "2026-01-01 00:00:00",
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


@register(24)  # GET /system/coppa — sent BEFORE master data download; misc IDs inline
def handle_coppa(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        misc={
            Misc.TUTORIAL_DOWNLOAD_JEWEL_REWARD: 300,
            Misc.COPPA_MIN_AGE: 13,
            Misc.COPPA_UNDERAGE_UPPER: 16,
            Misc.COPPA_ADULT_AGE: 20,
            Misc.COPPA_PURCHASE_LIMIT_MINOR: 5000,
            Misc.COPPA_PURCHASE_LIMIT_TEEN: 30000,
            Misc.COPPA_YEAR_PICKER_START: 1910,
            Misc.COPPA_YEAR_PICKER_END: datetime.now().year - Misc.COPPA_MIN_AGE,
            Misc.COPPA_UNKNOWN_907: 30,
        },
    )


@register(25)  # GET /system/master
def handle_master(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    base_url = "http://api.sp.kingdomhearts.com/data/master"
    master_rev = 24
    resp = build_response(user, master={"revision": master_rev, "count": len(MASTER_TABLE_NAMES)})
    for i, name in enumerate(MASTER_TABLE_NAMES):
        _, md5_hex = get_master_encrypted(name)
        rev = master_rev
        resp[name] = {
            "revision": rev,
            "url": f"{base_url}/m{i:03d}.jpg",
            "key": MASTER_KEY_HEX,
            "md5": md5_hex,
        }
    logger.info("MASTER: serving %d tables (encrypted)", len(MASTER_TABLE_NAMES))
    return resp


_resource_md5_cache: dict = {}
_resource_md5_lock = threading.Lock()
_resource_md5_ready = threading.Event()


def _resource_md5(path: str) -> str:
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
    if not os.path.isfile(path):
        return
    mtime = os.path.getmtime(path)
    cache_key = f"{path}:{mtime}"
    size = os.path.getsize(path)
    logger.info("Hashing %s (%d MB)...", os.path.basename(path), size >> 20)
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    with _resource_md5_lock:
        _resource_md5_cache[cache_key] = h.hexdigest()
    logger.info("Hashed %s -> %s", os.path.basename(path), _resource_md5_cache[cache_key])


RESOURCE_CHUNK_SIZE = 250 * 1024 * 1024


def _hash_resource_chunk(path: str, offset: int, end: int):
    mtime = os.path.getmtime(path)
    cache_key = f"{path}:{mtime}:{offset}:{end}"
    h = hashlib.md5()
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
            h = hashlib.md5()
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


_hash_thread = threading.Thread(target=_prehash_resources, daemon=True)
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
            "revision": 1,
            "data": data_chunks,
            "index": [{
                "url": f"{base_url}/misc.png",
                "md5": _resource_md5(misc_png),
                "size": os.path.getsize(misc_png),
                "revision": 1,
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
    is_new = True
    progression = DEBUG_SKIP_TO if DEBUG_SKIP_TO else 0
    if DEBUG_SKIP_TO >= 995:
        is_new = False
    return build_response(user,
        login={
            "newcomer": is_new,
            "tutorial": is_new,
            "acquirableLoginBonus": False,
            "progression": progression,
        },
        tutorial={
            "userTutorialId": 1,
            "progression": progression,
            "name": "",
            "inviteCode": "",
        },
        phase=50,
        popupFlag=0,
        isFinished=0,
    )


@register(28)  # GET /system/information/list
@register(29)  # GET /system/information/list/151203
def handle_information_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
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
    return build_response(user, informations=infos, popUpViewUrl=[])


@register(30)  # GET /system/information/detail
def handle_information_detail(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    info_id = request_data.get("informationId", 1)
    return build_response(user, information={
        "informationId": info_id,
        "url": f"http://api.sp.kingdomhearts.com/dark/information/detail/{info_id}",
    })


@register(76)  # GET /party/notice
def handle_party_notice(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        hasNewOffer=0, isApply=0, hasNewApplicant=0, isNewLeader=0, newcomerUsers=[])


@register(108)  # GET /raid/list
def handle_raid_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, raids=[], raidList=[], raidBossList=[])


@register(129)  # GET /ranking/parade
def handle_ranking_parade(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, unionParade={"rankingUnionResult": [], "rankingUnionTopRanker": []})


@register(131)  # GET /campaign
def handle_campaign(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, campaigns=[])


@register(57)  # POST /user/sphere/check
def handle_sphere_check(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    check_type = request_data.get("checkType", 1)
    return build_response(user,
        checkType=check_type,
        notChargedSphereBoardIds=[],
        userSphere={"userSphereDatas": [], "notChargedSphereBoardIds": []},
    )


@register(56)  # GET /mypage
def handle_mypage(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        adminMypageTexts=[],
        openBanners=[],
        userPresentCount=0,
        isChangeCoordinate=0,
        rankingRewards={
            "rankingColosseum": 0, "rankingParty": 0,
            "rankingLuxWeekly": 0, "rankingLuxMonthly": 0, "rankingLux": 0,
        },
        backgroundId=150911,
        isNewAlbumChallenge=0,
        loginBonus=[],
        events=[],
        notifications=[],
    )


def default_handler(action_id: int, request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    logger.warning("Unhandled action_id=%d request_keys=%s", action_id, list(request_data.keys()))
    return build_response(user)
