"""
KHUx Private Server — Action handlers for v4.3.1.

Based on decompiled libcocos2dcpp.so (arm64-v8a) analysis.
"""

import hashlib
import logging
import math
import os
import random
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy.orm import Session as DBSession

from .enums import Misc
from .information import NOTICES
from .master import MASTER_KEY_HEX, MASTER_TABLE_NAMES, get_master_encrypted
from .models import Party, PartyApplication, PartyOffer, RaidParticipant, User
from . import state as gstate
from . import raid as graid
from . import colosseum as gcol
from . import party as gparty
from . import ranking as granking
from . import stagemap
from . import gacha
from . import events as gevents

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


# master data revision: ret.versionDat and /system/master revision must be equal
MASTER_REV = 55


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
        # DataDownloader downloads resources (misc.mp4/png via /system/resource) only when versionRes !=
        # AppState's saved resource revision. A fresh install has revision 0, so 0 here means a fresh
        # install never gets the resources (later screens miss their layouts) - run with KHUX_VERSION_RES=1.
        # The old ">0 re-downloads every session" was /system/resource sending minVersion 0 (fixed there).
        "versionRes": int(os.environ.get("KHUX_VERSION_RES", "0")),
        "versionDat": MASTER_REV,   # bumping forces the master re-download + "update detected" popup
        # menu buttons the client shows: 0x01 party "Invitation code", 0x02 Other menu "Serial code", 0x04 shop
        # benefit (VIP pass: "unlock all Special Quests" button + locked-quest offer) (0x08 KHchi avatar link,
        # 0x10 transfer, 0x20 support, 0x80 fund settlement: off)
        "functionFlags": 0x07,
        "serverTime": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
    }


def build_error(user: Optional[User], message: str) -> dict:
    """An error the client shows as-is: HTTP 400 + a valid ret with ret.error (Ret::parse; Client::parseResponse
    -> status 4 -> handleError shows ret.error; verifyResponse is skipped). app.py pops __http_status."""
    resp = {"ret": dict(build_ret(user), error=message)}
    resp["__http_status"] = 400
    return resp


def build_response(user: Optional[User] = None, **extra) -> dict:
    resp = {"ret": build_ret(user)}
    resp.update(extra)
    return resp


# ---------------------------------------------------------------------------
# Login handlers

# ---------------------------------------------------------------------------
@register(59)  # POST /login
def handle_login(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # login.progression picks the screen a relaunch resumes at (sub_67F3C0): 1 invitation / download,
    # 2 download, 3 name, 4 avatar, 5 union, 6 the tutorial battle (anything else: the EULA). Send the stored
    # step as-is; the client re-downloads by itself when the resources are missing.
    progression = min(max(user.tutorial_progression or 0, 0), 6) if user else 0
    newcomer = progression == 0
    # Report the tutorial as finished once the union is joined (progression 6). A relaunch with
    # tutorial=true at 6 makes the client send /tutorial/clear (63) and jump to the stage/raid flow
    # (100, 107) assuming user data is already loaded; its callback then reads the never-loaded keyblade
    # buffer (APIManager+236, filled by actions 9/10) and crashes (sub_71CAC0, seen on the emulator).
    # The tutorial battle itself runs in the same session right after the union selection.
    tutorial = not user.tutorial_done and progression < 6 if user else True
    logger.info("LOGIN HANDLER: user=%s tutorial_done=%s progression=%s newcomer=%s tutorial=%s",
                user.id if user else None, user.tutorial_done if user else None,
                progression, newcomer, tutorial)
    if user:
        user.last_login_at = datetime.utcnow()          # party leader absence (PartyLogin.isAbsenceLeader)
        db_session.add(user)
    bonus = bool(user and not tutorial and user.tutorial_done and
                 gstate.load(user, db_session).get("loginbonus", {}).get("last_day") != _bonus_day())
    if user and user.tutorial_done:              # dated login gifts (HD Aqua, holiday medals...) -> present box
        with gstate.State(user, db_session) as st:
            for name, items in gevents.due_login_gifts(st):
                for rtype, rid, num in items:
                    add_present(st, rtype, rid, num, name)
                logger.info("LOGIN GIFT: %s -> user %s", name, user.id)
    return build_response(user,
        login={
            "newcomer": newcomer,
            "tutorial": tutorial,
            # true sends the client to /login/bonus (60) and SceneLoginBonus after the notices
            "acquirableLoginBonus": bonus,
            "progression": progression,
        },
        phase=user.tutorial_phase if user else 50,
        popupFlag=_popup_flag(user, db_session),
        isFinished=_tutorial_finished(user),
    )


# ---------------------------------------------------------------------------
# Startup chain handlers
# ---------------------------------------------------------------------------
@register(6)  # GET /user/stone
def handle_user_stone(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userStone={"freeStone": user.free_stone if user else 300, "payStone": user.pay_stone if user else 0})


@register(7)  # GET /user/shop
def handle_user_shop(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # UserShop: the player's active purchase benefits (VIP pass: benefitId 100) - replaces the client's list
    return build_response(user, userBenefits=_active_benefits(gstate.load(user, db_session) if user else {}))


def _active_benefits(st: dict) -> list:
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    return [{"benefitId": int(b), "endDatetime": end} for b, end in (st.get("benefits") or {}).items() if end > now]


def _benefit_end() -> str:
    """A weekly benefit (VIP pass, shop benefitResetWeek "Sunday") ends at the weekly reset: "until Sun. 23:59 (PDT)"
    = Monday 06:59:59 UTC (GUESS: V1)."""
    now = datetime.utcnow()
    end = (now + timedelta(days=(7 - now.weekday()) % 7)).replace(hour=6, minute=59, second=59, microsecond=0)
    if end <= now:
        end += timedelta(days=7)
    return end.strftime("%Y-%m-%d %H:%M:%S")


@register(9)  # GET /user/sphere
def handle_user_sphere(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # verifyResponse case 9 (libcocos2dcpp_0003.c LABEL_141): UserSphere::parse(doc, 0) = userSphere
    # {userSphereDatas: [Sphere], notChargedSphereBoardIds: [int]}; it becomes the owned-board map (APIManager+180)
    # the board select screen lists from. Boards the player qualifies for are granted here too, so the list is
    # never empty (the initItem boards at least); /user/sphere/check announces later ones as NEW.
    with gstate.State(user, db_session) as st:
        closed = gstate.close_spheres(st)          # limited boards whose (replayed) period is over
        added = gstate.sync_spheres(st, _lux_rank(user))
        boards = gstate.sphere_list(st)
    if added or closed:
        logger.info("SPHERE GET: granted %s, closed %s", [b["sphereBoardId"] for b in added], closed)
    return build_response(user, userSphere=_user_sphere(boards))


def _get_player_stats(level: int) -> dict:
    from .master import MASTER_JSON_DATA
    players = MASTER_JSON_DATA.get("player", [])
    for p in players:
        if p.get("lv") == level:
            return p
    return {"lv": level, "needExp": 999999, "ap": 16, "cost": 42, "hp": 3000}


def _lux_rank(user: Optional[User]) -> int:
    """The player level shown everywhere is the Lux rank (UserDetail.luxRank): the highest `player` row whose
    needExp (cumulative Lux) totalLux has reached - SceneUtil::calcLuxGaugePer(luxRank, totalLux) draws the
    gauge from player[rank].needExp to player[rank+1].needExp, capped at misc 100 (300). Rank 0 is invalid
    (it makes "to next level" = player[1].needExp - totalLux = negative)."""
    from .master import MASTER_JSON_DATA
    total = (user.total_lux or 0) if user else 0
    cap = _misc(100, 300)
    rank = 1
    for p in MASTER_JSON_DATA.get("player", []):
        if p["lv"] <= cap and p["needExp"] <= total:
            rank = max(rank, p["lv"])
    return rank


def _add_lux(user: Optional[User], lux: int) -> None:
    """Add Lux and apply rank-ups: each new rank grants that player row's luxMedal as Avatar Coins (the
    result screen's level-up popup sums player[r].luxMedal into Txt_Coin_Label = TextData 103100038 "You got
    %d Avatar Coins!", and shows 103100049 "AP fully restored!")."""
    if not user:
        return
    before = _lux_rank(user)
    from sqlalchemy.orm import object_session
    if object_session(user) is not None and lux > 0:
        gparty.record_lux(object_session(user), user, lux)
    user.lux = (user.lux or 0) + lux
    user.total_lux = (user.total_lux or 0) + lux
    after = _lux_rank(user)
    if after > before:
        coins = sum(_get_player_stats(r).get("luxMedal", 0) for r in range(before + 1, after + 1))
        user.sphere_point = (user.sphere_point or 0) + coins
        logger.info("LUX RANK UP: %d -> %d (totalLux=%d, +%d avatar coins)", before, after, user.total_lux, coins)
    user.lux_rank = user.level = after


def _user_point(user: Optional[User], recovered: bool = False) -> dict:
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    if user:
        stats = _get_player_stats(_lux_rank(user))
        hp = stats["hp"] + (user.hp_prize or 0)
        ap = stats["ap"] + (getattr(user, "ap_prize", 0) or 0)     # + Avatar Board Max AP nodes
        # TEST ONLY: KHUX_AP=n sends n as the current AP (the AP recovery dialog on quest start); the recovery's own
        # response (/shop/ap/recover) still sends a full gauge
        cur = int(os.environ["KHUX_AP"]) if os.environ.get("KHUX_AP") and not recovered else ap
        return {
            "money": user.money, "lux": user.lux, "totalLux": user.total_lux,
            "spherePoint": user.sphere_point or 0, "kizunaPoint": user.kizuna_point or 0,
            "raidPoint": user.raid_point or 0,
            "attack": user.attack, "defense": user.defense, "baseHp": hp,
            "hp": hp, "ap": cur, "maxHp": hp, "maxAp": ap,
            "lastApDatetime": now,
            "stageSpherePoint": user.stage_sphere_point or 0, "raidSpherePoint": user.raid_sphere_point or 0,
            "colosseumSpherePoint": user.colosseum_sphere_point or 0, "stageSkipTicket": 0,
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


def _equip_coordinate(user: Optional[User]) -> int:
    # outfit slots are 1..6 (see state.COORDINATE_SLOTS); older saves stored 0
    no = user.equip_coordinate_no if user else 1
    return no if 1 <= no <= gstate.COORDINATE_SLOTS else 1


def _user_avatar(user: Optional[User]) -> dict:
    # the equipped outfit (the User columns mirror it)
    if not user:
        return {"myCoordinateNo": 1, "gender": 0,
                "hairPartsId": 40001, "hairColorPartsId": 0,
                "facePartsId": 20001, "bodyPartsId": 30001, "skinPartsId": 0,
                "accessoriesPartsIds": []}
    acc = [int(x) for x in user.accessories_parts_ids.split(",") if x] if user.accessories_parts_ids else []
    return {"myCoordinateNo": _equip_coordinate(user), "gender": user.gender,
            "hairPartsId": user.hair_parts_id, "hairColorPartsId": user.hair_color_parts_id,
            "facePartsId": user.face_parts_id, "bodyPartsId": user.body_parts_id,
            "skinPartsId": user.skin_parts_id, "accessoriesPartsIds": acc}


def _user_avatars(user: Optional[User], db_session: DBSession) -> list:
    # UserAvatarAll::parse (0x49F95C): userAvatars[] of Coordinate, every saved outfit
    if not user:
        return [_user_avatar(user)]
    # SceneAvatarEdit::initMyCordinateButton (0x7058C8) keeps only the slots 1..6 it finds and the slot button
    # cycles all six (an out_of_range throw on a missing one), so every slot is sent; unsaved ones copy slot 1
    saved = {c["myCoordinateNo"]: c for c in gstate.load(user, db_session)["coordinates"]}
    first = saved.get(1) or next(iter(saved.values()), None) or _user_avatar(user)
    return [dict(saved.get(no) or first, myCoordinateNo=no) for no in range(1, gstate.COORDINATE_SLOTS + 1)]


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
    {"userMedalId": 4, "medalId": 33043, "level": 1, "exp": 0,
     "attackUpperNumber": 0, "defenseUpperNumber": 0, "burstUpperNumber": 0,
     "lock": 0, "upperCost": 0, "guiltFactor": 0, "userSkills": [],
     "getDatetime": "2026-01-01 00:00:00"},
]


def _user_keyblades(user: Optional[User], db_session: DBSession) -> list:
    return gstate.load(user, db_session)["keyblades"]


def _user_medals(user: Optional[User], db_session: DBSession) -> list:
    return gstate.load(user, db_session)["medals"]


def _lead_medal(user: Optional[User], db_session: DBSession) -> dict:
    """The medal shown for this user as a support/party leader: slot 1 of the favourite keyblade's deck."""
    st = gstate.load(user, db_session)
    kb = next((k for k in st["keyblades"] if k.get("isFavorite")), st["keyblades"][0] if st["keyblades"] else None)
    mid = kb["deckMedals"][0] if kb and kb["deckMedals"] else None
    return next((m for m in st["medals"] if m["userMedalId"] == mid), st["medals"][0] if st["medals"] else
                _STARTING_MEDALS[0])


@register(10)  # GET /user/keyblade
def handle_user_keyblade(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userKeyblades=_user_keyblades(user, db_session))


@register(105)  # POST /stage/continue
def handle_stage_continue(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # onRespond case 105 runs UserStone::parse + UserKeyblade::parse (needs >= 1 keyblade, each fed to
    # APIManager::updateKeyblade). Without them the continue fails and the client retries forever.
    # A continue costs 100 Jewels (KHUX Wiki Talk:Shop: "100 Jewels to continue? If you choose to continue, the
    # special attack gauge will be maxed out" - the gauge refill is the client's).
    # During the tutorial the continue is free: StageUI::openContinueDialog says so while
    # TutorialStatus.isFinished is 0 (T1). The client checks the Jewels before it asks (102600016).
    if user and _tutorial_finished(user) and _spend_jewels(user, _misc(113, 100)):   # misc 113 (GUESS: Q3)
        db_session.add(user)
    logger.info("STAGE CONTINUE: user=%s", user.id if user else None)
    return build_response(user,
        userStone={"freeStone": user.free_stone if user else 300, "payStone": user.pay_stone if user else 0},
        userKeyblades=_user_keyblades(user, db_session),
    )


@register(11)  # GET /user/skill
def handle_user_skill(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userSkills=[])


@register(13)  # GET /user/medal
def handle_user_medal(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userMedals=_user_medals(user, db_session))


@register(14)  # GET /user/material
def handle_user_material(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userMaterials=gstate.materials_list(gstate.load(user, db_session)))


@register(16)  # GET /user/title
def handle_user_title(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # Fetched in the login chain (callbackUserAvatarPartsGet -> executeUserTitleGet). verifyResponse case 16 runs
    # UserTitle::parse (0x4A1688) and REPLACES the owned list at APIManager+268 with it; one bad record (missing
    # key / wrong type) makes the parse return null. Records: {userTitleId: uint64, titleId: int}.
    # The title picker (AvatarInfoDialog::openPopUpSelectSubName) lists 0 ("none") + these titleIds.
    titles = gstate.load(user, db_session).get("titles", []) if user else         [{"userTitleId": i + 1, "titleId": t} for i, t in enumerate(gstate.default_title_ids())]
    return build_response(user, userTitles=[{"userTitleId": int(t["userTitleId"]), "titleId": int(t["titleId"])}
                                            for t in titles])


@register(17)  # GET /user/support
def handle_user_support(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, supportUser=_support_user(user, db_session))


def _max_medal(user: Optional[User]) -> int:
    return (user.max_medal or _misc(102, 50)) if user else _misc(102, 50)     # M1: a new box holds 50


def _support_medal(user: Optional[User], db_session: DBSession) -> dict:
    """The medal other players borrow: the one picked with /user/support/update, else deck slot 1 (GUESS: S1)."""
    st = gstate.load(user, db_session)
    mid = st.get("support_medal")
    return next((m for m in st["medals"] if m["userMedalId"] == mid), None) or _lead_medal(user, db_session)


def _support_user(user: Optional[User], db_session: DBSession) -> dict:
    # UserSupport::parse (0002.c:16505): supportUser {supportUserId u64, level, partyId u64, userName, titles,
    # userKeybladeId u64, keybladeId, userMedalId u64, medalId, lastActionDatetime}
    uid = user.id if user else 1
    medal = _support_medal(user, db_session) if user else {"userMedalId": 0, "medalId": 0}
    kbs = gstate.load(user, db_session)["keyblades"] if user else []
    kb = next((k for k in kbs if k.get("isFavorite")), kbs[0] if kbs else {"userKeybladeId": 0, "keybladeId": 0})
    return {"supportUserId": uid, "level": _lux_rank(user), "partyId": _party_id(user),
            "userName": user.user_name if user else "Player", **_user_titles(user),
            "userKeybladeId": kb["userKeybladeId"], "keybladeId": kb["keybladeId"],
            "userMedalId": medal["userMedalId"], "medalId": medal["medalId"],
            "lastActionDatetime": _last_action(user)}


@register(20)  # GET /user/avatar/all
def handle_user_avatar_all(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userAvatars=_user_avatars(user, db_session))


@register(21)  # GET /user/avatar/parts
def handle_user_avatar_parts(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # UserAvatarParts::parse (0x49FC0C): userAvatarParts[] of Part {userAvatarPartsId (uint64), partsType (int),
    # avatarPartsId (int), getDatetime}; replaces the owned list (APIManager+204). Owned parts: the initItem
    # category-100 rows plus Avatar Board / reward unlocks (state.avatar_parts).
    return build_response(user, userAvatarParts=_avatar_parts(gstate.load(user, db_session)))


def _avatar_parts(st: dict) -> list:
    return [{"userAvatarPartsId": int(p["userAvatarPartsId"]), "partsType": int(p["partsType"]),
             "avatarPartsId": int(p["avatarPartsId"]), "getDatetime": p["getDatetime"]}
            for p in st.get("avatar_parts", [])]


def _user_titles(user: Optional[User]) -> dict:
    """The profile title ("default message"): left title + right title + plate, as chosen with action 39."""
    return {"titleLeftId": int(user.title_left_id or 0) if user else 0,
            "titleRightId": int(user.title_right_id or 0) if user else 0,
            "titlePlateId": int(user.title_plate_id or 0) if user else 0}


def _title_ids() -> set:
    return gstate.title_ids()


@register(38)  # POST /user/playstyle/update {playTimezones: [slot 1..6, up to 3], playFrequently}
def handle_play_style_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # profile -> Play Style; verifyResponse case 38 parses UserDetail (userData.userDetail)
    if user:
        zones = [int(z) for z in request_data.get("playTimezones", []) if 1 <= int(z) <= 6][:6]
        user.play_timezones = ",".join(str(z) for z in zones)
        user.play_frequently = int(request_data.get("playFrequently", 0))
        db_session.add(user)
    return build_response(user, userData={"userDetail": _user_detail(user)})


@register(39)  # POST /user/title/update {titleLeftId, titleRightId, titlePlateId}
def handle_user_title_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # Request ids are sent as uint64 (APIManager::executeUserTitleUpdate). verifyResponse cases 38/39
    # (asm 0x4BBA36) run only UserDetail::parse = userData.userDetail (titleLeftId/RightId/PlateId are int)
    # and fail the call when it is missing.
    if user:
        known = _title_ids()
        owned = gstate.owned_title_ids(gstate.load(user, db_session))
        for key, attr in (("titleLeftId", "title_left_id"), ("titleRightId", "title_right_id"),
                          ("titlePlateId", "title_plate_id")):
            try:
                val = int(request_data.get(key, getattr(user, attr) or 0))
            except (TypeError, ValueError):
                logger.warning("TITLE UPDATE: bad %s=%r", key, request_data.get(key))
                continue
            # left/right are title master ids the player owns (the picker offers 0 + the action-16 list); the plate
            # id has no master table we know of, so only range-check it. Re-sending the current value is accepted.
            if val < 0 or val > 0x7FFFFFFF or (
                    key != "titlePlateId" and val and val != (getattr(user, attr) or 0)
                    and ((known and val not in known) or val not in owned)):
                logger.warning("TITLE UPDATE: unknown/unowned %s=%s, keeping %s", key, val, getattr(user, attr))
                continue
            setattr(user, attr, val)
        db_session.add(user)
        logger.info("TITLE UPDATE: %s", _user_titles(user))
    return build_response(user, userData={"userDetail": _user_detail(user)})


def _user_obj(user: Optional[User]) -> dict:
    """userData.user (hole::network::api::User::parse)."""
    uid = user.id if user else 1
    return {
        "userId": uid,
        "nativeUserId": uid,
        "platformId": 2,
        "userName": user.user_name if user else "Player",
        "gender": user.gender if user else 0,
        "comment": user.comment if user else "",
        "deviceType": 2,
        "continueLoginCount": max(user.continue_login_count or 0, 1) if user else 1,   # the login streak (O7)
        "isFleeze": 0,
        "fleezedDatetime": "2000-01-01 00:00:00",
        "nativeTagName": "player_tag",
    }


# 36 / 37: verifyResponse runs User::parse ("userData") then UserDetail::parse (case 36/37 -> LABEL_24 -> 30)
@register(36)  # POST /user/name/update {name, comment}
def handle_name_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    name, comment = request_data.get("name"), request_data.get("comment")
    logger.info("NAME UPDATE: name=%r comment=%r", name, comment)
    if user:
        if isinstance(name, str) and name.strip():
            user.user_name = name[:13]              # the client's edit box allows 13 characters
        if isinstance(comment, str):
            user.comment = comment[:128]
        db_session.add(user)
    return build_response(user, userData={"user": _user_obj(user), "userDetail": _user_detail(user)})


@register(37)  # POST /user/gender/update
def handle_gender_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # APIManager::executeUserGenderUpdate sends {"changeGender": 1|2}; the equipped outfit follows
    gender = int(request_data.get("changeGender") or 0)
    logger.info("GENDER UPDATE: %s", gender)
    if user and gender in (1, 2):
        user.gender = gender
        db_session.add(user)
        with gstate.State(user, db_session) as st:
            for c in st.get("coordinates", []):
                if c.get("myCoordinateNo") == _equip_coordinate(user):
                    c["gender"] = gender
    return build_response(user, userData={"user": _user_obj(user), "userDetail": _user_detail(user)})


@register(41)  # POST /user/avatar/update
def handle_avatar_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # APIManager::executeUserAvatarUpdate (0x4C8B54) sends updateAvatarData: [Coordinate + defaultFlag] for the
    # outfits it changed; defaultFlag 1 marks the equipped one. verifyResponse case 41 parses UserAvatarAll
    # (userAvatars) and UserDetail (userData.userDetail, equipCoordinateNo).
    logger.info("AVATAR UPDATE: %s", request_data)
    entries = request_data.get("updateAvatarData", [])
    if isinstance(entries, dict):
        entries = [entries]
    if user:
        with gstate.State(user, db_session) as st:
            for c in entries:
                rec = gstate.set_coordinate(st, c)
                if rec and c.get("defaultFlag"):
                    user.equip_coordinate_no = rec["myCoordinateNo"]
            equipped = next((x for x in st["coordinates"] if x["myCoordinateNo"] == _equip_coordinate(user)), None)
        if equipped:
            user.gender = equipped["gender"]
            user.hair_parts_id = equipped["hairPartsId"]
            user.hair_color_parts_id = equipped["hairColorPartsId"]
            user.face_parts_id = equipped["facePartsId"]
            user.body_parts_id = equipped["bodyPartsId"]
            user.skin_parts_id = equipped["skinPartsId"]
            user.accessories_parts_ids = ",".join(str(x) for x in equipped["accessoriesPartsIds"])
        db_session.add(user)
    return build_response(user, userAvatars=_user_avatars(user, db_session),
                          userData={"userDetail": _user_detail(user)})


@register(63)  # POST /tutorial/clear
def handle_tutorial_clear(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    logger.info("TUTORIAL CLEAR: payload=%s", request_data)
    if user and user.tutorial_progression < 6:
        # an invited player skips the Union choice (progression 6; the inviter's Union is used) and clears from
        # 5. Without this, every later login reports the tutorial unfinished and replays SceneUnionRegister.
        user.tutorial_progression = 6
        db_session.add(user)
    return build_response(user,
        login={
            "newcomer": False,
            "tutorial": False,
            "acquirableLoginBonus": False,
            "progression": user.tutorial_progression if user else 6,
        },
        **_invite_bonus(user, db_session),
    )


def _invite_owner(db_session: DBSession, code: str) -> Optional[User]:
    from .models import UserState
    import json as _json
    for us in db_session.query(UserState).all():
        try:
            if (_json.loads(us.data or "{}").get("invite") or {}).get("code") == code:
                return db_session.get(User, us.user_id)
        except ValueError:
            continue
    return None


INVITE_CAP = 10        # GUESS: IC2 - how many invitees pay the inviter (invited + remaining)


def _invite_bonus(user: Optional[User], db_session: DBSession) -> dict:
    """TutorialClear.inviteBonus {user, party, firstReward, inviteStone} for a player who redeemed an invite code
    (once). The client then shows: joined the inviter's party (firstReward != 0) + "Received %d Jewels for using an
    invitation code" (misc 115) + first-party Jewels (misc 117), or "Unable to join" (firstReward 0). Both players
    get misc 115 Jewels in the present box (texts 104010001 "You'll both get %d Jewels"; GUESS: IC1)."""
    if not user:
        return {}
    with gstate.State(user, db_session) as st:
        inv = st.get("invited_by")
        if not inv or inv.get("delivered"):
            return {}
        inv["delivered"] = True
        jewels = _misc(115, 300)
        add_present(st, gstate.ITEM_JEWEL if hasattr(gstate, "ITEM_JEWEL") else 2, 0, jewels, "Invitation Code")
    inviter = db_session.get(User, inv["userId"])
    if inviter is None:
        return {}
    with gstate.State(inviter, db_session) as ist:
        rec = ist.setdefault("invite", {"code": _make_invite_code(db_session), "invited": 0})
        if rec["invited"] < INVITE_CAP:
            rec["invited"] += 1
            add_present(ist, 2, 0, jewels, "Invitation Code")
    p = gparty.party_of(db_session, inviter.id)
    joined = 0
    if p and len(gparty.members(db_session, p.id)) < gparty.max_members():
        if gparty.membership(db_session, user.id):
            gparty.leave(db_session, user.id)
        gparty._join(db_session, user.id, p)
        _after_join(db_session, user.id)
        user.union_id = inviter.union_id
        db_session.add(user)
        joined = 1
    party_obj = gparty.party_obj(db_session, p) if p else gparty.party_obj(db_session, Party(
        id=0, union_id=inviter.union_id or 0, name="", message="", play_style=0, agree_type=0,
        leader_user_id=inviter.id, admin_ids=""))
    logger.info("INVITE BONUS: user %s, inviter %s, joined party %s", user.id, inviter.id, p.id if joined else 0)
    return {"inviteBonus": {"user": _user_obj(inviter), "party": party_obj, "firstReward": joined,
                            "inviteStone": jewels}}


def _make_invite_code(db_session: DBSession) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        code = "".join(random.choice(alphabet) for _ in range(8))
        if _invite_owner(db_session, code) is None:
            return code


@register(69)  # POST /union/change
def handle_union_change(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # verifyResponse case 69 needs userData.userDetail + userStone (it failed with ret only). The client refuses
    # while in a party and charges misc 114 (100) Jewels, checking the balance itself (GUESS: U1 - every change).
    union_id = int(request_data.get("unionId", 1) or 1)
    logger.info("UNION CHANGE: %s", union_id)
    if user and union_id != user.union_id and _spend_jewels(user, _misc(114, 100)):
        user.union_id = union_id
        db_session.add(user)
        # the week's Lux no longer counts (2016 guide: "will be reset to zero and not count towards the week's
        # rankings")
        from .models import LuxLedger
        db_session.query(LuxLedger).filter(LuxLedger.user_id == user.id,
                                           LuxLedger.at >= gparty.week_start()).delete()
    return build_response(user, userData={"userDetail": _user_detail(user)}, userStone=_user_stone(user))


@register(62)  # POST /tutorial/progress
def handle_tutorial_progress(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # the client sends steps 1-6 (executeTutorialProgress callers); the tutorial is done by /tutorial/status 995
    progression = int(request_data.get("progression", 0) or 0)
    name = request_data.get("name", "")
    logger.info("TUTORIAL PROGRESS: %s payload=%s", progression, request_data)
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
            with gstate.State(user, db_session) as st:                  # the tutorial avatar is outfit 1
                gstate.set_coordinate(st, {**avatar_data, "myCoordinateNo": 1})
            user.equip_coordinate_no = 1
        union_id = request_data.get("unionId")
        if union_id is not None:
            user.union_id = union_id
        if progression > user.tutorial_progression:
            user.tutorial_progression = progression
        db_session.add(user)
    code = str(request_data.get("inviteCode") or "").strip().upper()
    if user and code:
        inviter = _invite_owner(db_session, code)
        if inviter is None or inviter.id == user.id:
            return build_error(user, "This invitation code is not valid.")
        with gstate.State(user, db_session) as st:
            st["invited_by"] = {"userId": inviter.id, "code": code, "delivered": False}
        logger.info("INVITE CODE %s: user %s invited by %s", code, user.id, inviter.id)
    pending = gstate.load(user, db_session).get("invited_by") if user else None
    tutorial_resp = {
        "userTutorialId": 1,
        "progression": progression,
        "name": name or (user.user_name if user else ""),
        # non-empty makes the client send /tutorial/clear right after the avatar (to show the invite bonus);
        # empty again once delivered (a repeat would show "Unable to join")
        "inviteCode": pending["code"] if pending and not pending.get("delivered") else "",
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
    phase = user.tutorial_phase if user else 50
    # isFinished (TutorialStatus+16): while 0 the game treats the player as in the tutorial - e.g. the battle
    # Continue dialog offered the free "During the tutorial..." revive at level 102 (user report)
    return build_response(user, phase=phase, popupFlag=_popup_flag(user, db_session),
                          isFinished=_tutorial_finished(user))


def _tutorial_finished(user: Optional[User]) -> int:
    return 1 if user and (user.tutorial_done or (user.tutorial_phase or 0) >= 995) else 0


def _popup_flag(user: Optional[User], db_session: DBSession, add: int = 0) -> int:
    """Guide popups already shown, as the client's bitmask (PUT /tutorial/status {popupFlag}: one bit per
    tutorialMisc guide). Sent back so a guide is not shown again every session."""
    if not user:
        return 0
    with gstate.State(user, db_session) as st:
        st["popup_flag"] = st.get("popup_flag", 0) | add
        flag = st["popup_flag"]
    # Post-tutorial guide 17 (= StageUI tutorial widget 103, the treasure-chest guide shown on entering a map's
    # second area, tutorialMisc 10061) can fire in an area with no treasure (stage 1060 area 2: empty map treasure
    # list) and then never completes (executingTutorial1006 waits for getCurrentEventMapTreasure) - the battle is
    # stuck under the mask. Mark it seen (bit 1 << (17 - 1)) once the tutorial is done. OPEN: find the 1.0.1
    # trigger semantics (StageManager+96 / +328 vs num2 / num1) and let it show where a treasure exists.
    if user.tutorial_done:
        flag |= 1 << 16
    return flag


@register(65)  # PUT /tutorial/status
def handle_tutorial_status_put(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # body is {phase} (tutorial step; order 50,100,200,210,220,300,400,410,500,600,700,710,995 per the
    # client's table at 0xDEC5F0) or {popupFlag} (a guide popup seen)
    phase = request_data.get("phase")
    flag = request_data.get("popupFlag", 0)
    logger.info("TUTORIAL STATUS PUT: phase=%s popupFlag=%s", phase, flag)
    if user and phase is not None:
        if phase > user.tutorial_phase:
            user.tutorial_phase = phase
        if phase >= 995:
            user.tutorial_done = True
        db_session.add(user)
    return build_response(user, phase=user.tutorial_phase if user else (phase or 0),
                          popupFlag=_popup_flag(user, db_session, flag), isFinished=_tutorial_finished(user))


@register(43)  # POST /user/keyblade/update
def handle_keyblade_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # APIManager::executeUserKeybladeUpdate sends {"userKeyblades": [{userKeybladeId, userMedalIds, isFavorite}]}
    changes = request_data.get("userKeyblades", [])
    logger.info("KEYBLADE UPDATE: %s", changes)
    with gstate.State(user, db_session) as st:
        for c in changes:
            kb = next((k for k in st["keyblades"] if k["userKeybladeId"] == c.get("userKeybladeId")), None)
            if kb is None:
                continue
            if "userMedalIds" in c:
                kb["deckMedals"] = gstate.fit_deck(c["userMedalIds"], kb["keybladeId"])
            if "isFavorite" in c:
                kb["isFavorite"] = int(c["isFavorite"])
        keyblades = st["keyblades"]
    return build_response(user, userKeyblades=keyblades)


def _medal_row(medal_id: int) -> dict:
    from .master import MASTER_JSON_DATA
    return next((m for m in MASTER_JSON_DATA.get("medal", []) if m["medalId"] == medal_id), {})


def _burst_row(burst_id) -> Optional[dict]:
    from .master import MASTER_JSON_DATA
    return next((b for b in MASTER_JSON_DATA.get("burst", []) if b.get("burstId") == burst_id), None)


def _medal_misc(misc_id: int) -> list:
    from .master import MASTER_JSON_DATA
    return next((m["value"] for m in MASTER_JSON_DATA.get("medalMisc", []) if m["medalMiscId"] == misc_id),
                [0, 0, 0])


def _medal_need_exp(medal: dict, lv: int) -> int:
    """BattleUtil::calcNeedExp: cumulative EXP for level lv+1; curve = medalMisc 105+expType
    [maxLevelRef, scale, exponent*10000]."""
    v = _medal_misc(105 + medal.get("expType", 1) if 1 <= medal.get("expType", 1) <= 6 else 106)
    if v[0] <= 1:
        return 1 << 30
    return int(v[1] * pow(lv / (v[0] - 1.0), v[2] / 10000.0))


def _fusion_exp(base: dict, base_row: dict, comp: dict, comp_row: dict) -> int:
    """SceneMixedMedal::calcMixedExp for one component medal, floored after every step as the client does:
    floor(materialExp + medalMisc 112 level curve), x medalMisc 113 if same attribute, x medalMisc 114 if the two
    share a `source` entry, x the running fusion-EXP campaign (evCampaign type 11, SceneMixedMedal+940)."""
    v = _medal_misc(112)
    exp = math.floor(comp_row.get("materialExp", 0)
                     + v[1] * pow((comp["level"] - 1) / max(v[0] - 1, 1), v[2] / 10000.0))
    if comp_row.get("attribute") == base_row.get("attribute"):
        exp = math.floor(exp * (_medal_misc(113)[0] / 10000.0))
    src_b = set(base_row.get("source", [])[:base_row.get("validSource", 0)])
    src_c = set(comp_row.get("source", [])[:comp_row.get("validSource", 0)])
    if src_b & src_c:
        exp = math.floor(exp * (_medal_misc(114)[0] / 10000.0))
    return int(math.floor(exp * (_campaign_power(11) / 10000.0)))


def _burst_up(base_row: dict, comp_row: dict, comp: dict) -> int:
    """Special-attack levels a component adds (SceneMixedMedal::isBurstUpMedal + updateMaterial): its
    burstUpperNumber + 1 when it shares the base's group (groupId, else medalId), its group is one of the base's
    burstEnhanceCategory, or it is a type-8 (special-attack material) medal; else 0."""
    def group(r):
        return r.get("groupId") or r.get("medalId")
    hit = (group(comp_row) == group(base_row) or group(comp_row) in (base_row.get("burstEnhanceCategory") or [])[:2]
           or comp_row.get("type") == 8)
    return comp.get("burstUpperNumber", 0) + 1 if hit else 0


def _fusion_cost(base: dict, base_row: dict, n: int) -> int:
    """SceneMixedMedal::updateMaterial: components x medalMisc 115 (80) x the base's level x the fusion-cost
    campaign (evCampaign type 14, "Half Munny cost!"); x medalMisc 123 (25%) when the base is at its max level."""
    cost = int(_campaign_power(14) / 10000.0 * (n * _medal_misc(115)[0] * base["level"]))
    if base["level"] == base_row.get("maxLv"):
        cost = int(_medal_misc(123)[0] / 10000.0 * cost)
    return cost


@register(53)  # POST /user/medal/enhance (fusion)
def handle_medal_enhance(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {baseUserMedalId, componentUserMedalIds, isOverwriteSkill}
    # response (verifyResponse case 53): userSkills + userData.userPoint + UserMedalEnhance {before/after
    # EnhanceUserMedal (UserMedal), enhanceEffect, overwriteSkills [], successOverwrite} + componentUserMedalIds
    logger.info("MEDAL ENHANCE: %s", request_data)
    base_id = request_data.get("baseUserMedalId")
    comps = set(request_data.get("componentUserMedalIds", [])) - {base_id}
    with gstate.State(user, db_session) as st:
        base = next((m for m in st["medals"] if m["userMedalId"] == base_id), None)
        if base is None:
            return build_error(user, "That Medal is no longer available.")
        before = dict(base)
        base_row = _medal_row(base["medalId"])
        cost = _fusion_cost(base, base_row, len(comps))      # from the base as it was, like the client's preview
        gained, burst_up = 0, 0
        for m in st["medals"]:
            if m["userMedalId"] in comps:
                row = _medal_row(m["medalId"])
                gained += _fusion_exp(base, base_row, m, row)
                burst_up += _burst_up(base_row, row, m)
        st["medals"] = [m for m in st["medals"] if m["userMedalId"] not in comps]
        for kb in st["keyblades"]:
            kb["deckMedals"] = [0 if mid in comps else mid for mid in kb["deckMedals"]]
        base["exp"] += gained
        while base["level"] < base_row.get("maxLv", 1) and base["exp"] >= _medal_need_exp(base_row, base["level"]):
            base["level"] += 1
        if burst_up:
            cap = (_burst_row(base_row.get("burstId")) or {}).get("maxEnhanceCount", 0)
            base["burstUpperNumber"] = min(base.get("burstUpperNumber", 0) + burst_up, cap)
        after = dict(base)
    if user:
        user.money = max(0, user.money - cost)
    logger.info("MEDAL ENHANCE: +%d exp -> lv %d exp %d, special +%d, cost %d", gained, after["level"],
                after["exp"], burst_up, cost)
    return build_response(user,
        userSkills=[],
        userData={"userPoint": _user_point(user)},
        beforeEnhanceUserMedal=before,
        afterEnhanceUserMedal=after,
        enhanceEffect=0,
        overwriteSkills=[],
        successOverwrite=0,
        # case 53 also reads the consumed medals back (IsUint64 array) to drop them from the client's list
        componentUserMedalIds=sorted(comps),
    )


# The tutorial's draw step ("Try equipping your new Medal!") expects KH II King Mickey from this banner.
# drawMedalType 10 (drawType 5 = tutorial): one medal for 300 Jewels, exactly the starting Jewels (users.free_stone
# default 300; misc 116 = 300 may be it, meaning unconfirmed - misc 100 is the Lux rank cap). The client checks free + paid Jewels >= price before drawing (DrawScrollView::hasMagicStone), so a higher price
# strands a new player at the guide (GUESS: T2 for which drawType 5 row is the tutorial's).
_TUTORIAL_BANNER = {"id": 10, "sortId": 1, "name": "Jewel Draw", "description": "Get a 3\u2605 Medal or better!",
                    "price": 300, "payType": 1, "pool": [33043], "lots": [{"count": 1, "rates": {}}]}


def _quests_cleared(user: Optional[User], db_session: DBSession) -> int:
    return len(gstate.load(user, db_session)["stages"]) if user else 0


@register(70)  # GET /gacha/list
def handle_gacha_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # Our own banners (data/banners.json, src/gacha.py), unlocked by story progress.
    if user and not user.tutorial_done:
        entries = [gacha.list_entry(_TUTORIAL_BANNER)]
    else:
        done = _quests_cleared(user, db_session)
        entries = [gacha.list_entry(b) for b in gacha.banners() if gacha.unlocked(b, done)]
    return build_response(user, gachaList=entries)


@register(71)  # POST /gacha/draw
def handle_gacha_draw(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {drawMedalTypeId, count}; the banner decides how many medals one purchase gives
    draw_type_id = request_data.get("drawMedalTypeId")
    tutorial = bool(user and not user.tutorial_done)
    b = _TUTORIAL_BANNER if tutorial else gacha.banner(draw_type_id)
    if b is None or (not tutorial and not gacha.unlocked(b, _quests_cleared(user, db_session))):
        logger.warning("GACHA DRAW refused: banner %s not available", draw_type_id)
        b, ids = None, []
    elif user and not tutorial and (user.free_stone or 0) + (user.pay_stone or 0) < b["price"]:
        logger.warning("GACHA DRAW refused: %s Jewels needed", b["price"])
        b, ids = None, []
    else:
        ids = gacha.draw(b)
    if user and b:
        # Jewels only (no real money on the private server); free Jewels are spent first. The tutorial draw costs
        # its 300 too (the starting Jewels; never below 0)
        price = b["price"]
        free = min(user.free_stone or 0, price)
        user.free_stone = (user.free_stone or 0) - free
        user.pay_stone = max((user.pay_stone or 0) - (price - free), 0)
        db_session.add(user)
    with gstate.State(user, db_session) as st:
        owned = {m["medalId"] for m in st["medals"]}
        drawn = [gstate.add_medal(st, mid) for mid in ids]
    first = []
    for m in drawn:
        if m["medalId"] not in owned:
            first.append(m["userMedalId"])
            owned.add(m["medalId"])
    logger.info("GACHA DRAW: banner %s count=%s -> %s", draw_type_id, request_data.get("count"), ids)
    return build_response(user,
        userData={"userPoint": _user_point(user)},
        userStone=_user_stone(user),
        userMedals=drawn,
        userSkills=[],
        userMaterials=[],
        # addType 1 = no bonus: anything else makes SceneDrawRaise open the "You got a bonus!" popup (+684), whose
        # exit skips the shop's normal return - and with it the tutorial's next guide (phase 210)
        gachaBonus={"addType": 1, "userMedalIds": []},
        firstGetUserMedalIds=first,
    )


@register(101)  # GET /stage/event
def handle_stage_event(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # StageEvent::parse: events[] + raidStatus (IsUint, required - without it every Events / Special Quests tap
    # failed verifyResponse). eventCategory 1 = Special Quests, 2 = Events (events.py has the schedule).
    category = int(request_data.get("eventCategory") or 2)
    clears = gstate.load(user, db_session)["stages"] if user else {}
    benefits = {b["benefitId"] for b in _active_benefits(gstate.load(user, db_session))} if user else set()
    events = [gevents.entry(r, end, clears, lock) for r, _, end, lock in gevents.active(category, benefits=benefits)]
    logger.info("EVENTS (category %s): %s", category, [e["eventStageId"] for e in events])
    return build_response(user, events=events, raidStatus=0)


# The offline-style default friend: when nobody else is around, the game lends "Sora" with KH II King Mickey - the
# same medal as the tutorial draw (user, from the original game). It grows with progress: 3* (33043) at the start up
# to 6* (33046) after 60 quests; the exact growth steps are ours.
_SORA_SUPPORT_ID = 999999999


def _last_action(user: Optional[User]) -> str:
    """lastActionDatetime (UTC, shown as "Last Login N ago"): the player's last login; now for "Sora"."""
    t = getattr(user, "last_login_at", None) or getattr(user, "created_at", None)
    return t.strftime("%Y-%m-%d %H:%M:%S") if t else time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


# Friend Points (kizuna) the owner of a shared medal earns each time someone uses it: 10 from a party member, 5 from
# anyone else (JP before 1.20; khuxwiki Currencies - GUESS: O8). The Sora fallback earns nothing.
KIZUNA_PARTY, KIZUNA_OTHER = 10, 5


def _same_party(db_session: DBSession, a: Optional[User], b_id: int) -> bool:
    pid = gparty.party_id_of(db_session, a.id) if a else 0
    return bool(pid) and pid == gparty.party_id_of(db_session, b_id)


def _support_entry(uid: int, name: str, level: int, medal: dict, avatar: dict, user: Optional[User] = None,
                   is_party: bool = False) -> dict:
    return {
        "supportUserId": uid, "level": level, "userName": name,
        "titleLeftId": 0, "titleRightId": 0, "titlePlateId": 0,
        "addKizunaPoint": 0 if uid == _SORA_SUPPORT_ID else (KIZUNA_PARTY if is_party else KIZUNA_OTHER),
        "keybladeId": 1000, "isParty": int(is_party), "isGuilt": 0,
        "userMedal": medal, "userSkills": [], "userAvatar": avatar,
        "lastActionDatetime": _last_action(user), "earnLuxRank": 0,
    }


def _sora_support(user: Optional[User], db_session: DBSession) -> dict:
    rare = 3 + min(3, _quests_cleared(user, db_session) // 20)
    medal = gstate.new_medal(_SORA_SUPPORT_ID, 33040 + rare)
    return _support_entry(_SORA_SUPPORT_ID, "Sora", _lux_rank(user), medal, _user_avatar(None))


SUPPORT_LIST_SIZE = 10


@register(102)  # GET /stage/support/list
def handle_stage_support_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # Party members first, then players of your Union with the closest player level (Lux rank) - "based on your
    # player level and the level of the other friends ... only medals from players in your own Union" (GameFAQs
    # 2016) -, ties by player id so the same people recur as you advance; other Unions only fill the list when
    # yours has too few (a small server). Never yourself; nobody else -> the default friend Sora. GUESS: S2
    others = []
    if user:
        pid = gparty.party_id_of(db_session, user.id)
        mates = {m.user_id for m in gparty.members(db_session, pid)} if pid else set()
        mine = _lux_rank(user)
        pool = db_session.query(User).filter(User.id != user.id, User.tutorial_done.is_(True)).all()
        pool.sort(key=lambda o: (o.id not in mates, (o.union_id or 0) != (user.union_id or 0),
                                 abs(_lux_rank(o) - mine), o.id))
        others = pool[:SUPPORT_LIST_SIZE]
    # each player lends the medal they chose as their support medal (45), not their lead medal
    supports = [_supporter(db_session, user, o.id) for o in others]
    return build_response(user, supportUsers=supports or [_sora_support(user, db_session)])


def _supporter(db_session: DBSession, user: Optional[User], support_uid) -> dict:
    """The SupportUser entry for a supporter id (Sora or another player)."""
    support_uid = int(support_uid or 0)
    o = db_session.get(User, support_uid) if support_uid and support_uid != _SORA_SUPPORT_ID else None
    if o is None:
        return _sora_support(user, db_session)
    e = _support_entry(o.id, o.user_name or "Player", _lux_rank(o), _support_medal(o, db_session), _user_avatar(o), o,
                       is_party=_same_party(db_session, user, o.id))
    kbs = _user_keyblades(o, db_session)                           # the owner's favourite keyblade, as in 80
    kb = next((k for k in kbs if k.get("isFavorite")), kbs[0] if kbs else None)
    e["keybladeId"] = kb["keybladeId"] if kb else 1000
    return e


def _chosen_supporters(db_session: DBSession, user: Optional[User], request_data: dict,
                       friend_points: bool = True) -> list:
    """supportUsers for 103 / 112: verifyResponse parses StageSupportList from them too, which REPLACES the list
    from 102; BattleUtil::getSupportMedal then looks the chosen supportUserId up in it. Empty = no friend medal in
    battle (the bug the user saw)."""
    sid = int(request_data.get("supportUserId") or 0)
    if not sid:
        return []
    entry = _supporter(db_session, user, sid)
    owner = db_session.get(User, sid) if sid != _SORA_SUPPORT_ID else None
    if friend_points and owner is not None and user is not None and owner.id != user.id:   # owner's Friend Points
        owner.kizuna_point = (owner.kizuna_point or 0) + entry["addKizunaPoint"]
        db_session.add(owner)
        logger.info("FRIEND POINTS: user %s +%s (medal used by %s)", owner.id, entry["addKizunaPoint"], user.id)
    return [entry]


@register(100)  # GET /stage/160310
def handle_stage(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    if user and not user.tutorial_stage_reached:
        user.tutorial_stage_reached = True
        db_session.add(user)
    # Story quests unlock one after another (stage master: stageKind 1, ordered by id). Every cleared quest
    # plus the next one is listed; newStageId is the newest unlocked quest.
    st = gstate.load(user, db_session)
    stories = []
    new_stage_id = gstate.story_order()[0]
    for sid in gstate.story_order():
        rec = st["stages"].get(str(sid))
        row = gstate.stage_row(sid)
        stories.append({"stageId": sid, "useAp": row["useAp"] if row else 0,
                        "score": rec["luxRecord"] if rec else 0,
                        "clearMissionIds": rec["clearMissionIds"] if rec else []})
        new_stage_id = sid
        if rec is None:
            break
    return build_response(user, stories=stories, newStageId=new_stage_id)


@register(107)  # GET /raid
def handle_raid(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # hole::network::api::Raid::init needs raidStatus + raid (RaidBase::Info) + discoverer + mvp
    # (RaidBase::User: userId, name, level, userAvatar Coordinate). Without discoverer/mvp the parse fails,
    # APIManager keeps a NULL raid buffer and the tutorial resume crashes in the raid callback (sub_71CAC0).
    # raidStatus (the player's OWN boss): 3 up (shown on the quest map when raidId != 0, timeLeft ahead and
    # parts[0].hp > 0), 1 defeated (reward popup from /raid/reward/151101), 2 escaped, 0 none.
    uid = user.id if user else 0
    with gstate.State(user, db_session) as st:
        graid.migrate_legacy(db_session, st, uid)
        row = graid.own(db_session, uid)
        raid = graid.load(row) if row else None
        if row:
            graid.save(row, raid)
        status = raid["status"] if raid else graid.RAID_STATUS_NONE
        me = graid.participant(db_session, row.id, uid, create=False) if row else None
        seen = st.setdefault("raid_seen_escape", [])
        if raid and status == graid.RAID_STATUS_DEFEATED and (me is None or me.rewarded):
            status = graid.RAID_STATUS_NONE
        if raid and status == graid.RAID_STATUS_ESCAPED:
            if row.id in seen:
                status = graid.RAID_STATUS_NONE
            else:
                seen.append(row.id)              # report an escape once, then the slot is free again
        info = graid.info(raid if status != graid.RAID_STATUS_NONE else None)
        mvp = _raid_mvp(db_session, row.id) if row else uid
    logger.info("RAID: status=%s raid=%s", status, info)
    return build_response(user, raidStatus=status, raid=info, discoverer=_raid_user(user),
                          mvp=_raid_user(db_session.get(User, mvp) or user))


def _raid_user(user: Optional[User]) -> dict:
    return {"userId": user.id if user else 0, "name": user.user_name if user and user.user_name else "",
            "level": _lux_rank(user), "userAvatar": _user_avatar(user)}


def _raid_mvp(db_session: DBSession, raid_id: int) -> int:
    """The participant with the most damage (0 = none)."""
    ps = graid.participants(db_session, raid_id)
    return max(ps, key=lambda p: p.damage).user_id if ps else 0


def _raid_party(db_session: DBSession, uid: int) -> list:
    """Players whose bosses this player sees and may join: themself + their party (wiki: party members can
    pay 10 AP to assist; help requests go to the party)."""
    pid = gparty.party_id_of(db_session, uid)
    return [uid] + ([m.user_id for m in gparty.members(db_session, pid) if m.user_id != uid] if pid else [])


def _raid_rewards(user: Optional[User], db_session: DBSession, with_users: bool) -> list:
    """Pending rewards of defeated raids this player fought (each handed out once), as RaidReward entries.
    Victory (subdue) to every participant; MVP to the top damage dealer and to the host (discoverer), once if
    the same player; All Points Defeated to everyone when every part fell (raid.reward_rows). subdueId / mvpId
    / partAllId are 1-based SLOT numbers in the boss's reward tables (table ids crashed RaidBossResultPopUp)."""
    out = []
    uid = user.id if user else 0
    pending = db_session.query(RaidParticipant).filter(RaidParticipant.user_id == uid,
                                                       RaidParticipant.rewarded.is_(False)).all()
    with gstate.State(user, db_session) as st:
        for me in pending:
            row = graid.by_id(db_session, me.raid_id)
            raid = graid.load(row) if row else None
            if not raid or raid["status"] != graid.RAID_STATUS_DEFEATED:
                continue
            me.rewarded = True
            mvp_uid = _raid_mvp(db_session, row.id)
            slots, items = graid.reward_rows(raid, mvp=uid in (mvp_uid, row.discoverer_id))
            medals = []
            for rtype, rid, num in items:
                medals += _grant(user, st, rtype, rid, num)
            entry = {
                "raidId": raid["raidId"], "level": raid["level"], **slots,
                "parts": graid.info(raid)["parts"],
                "mvpTotalDamage": max((p.damage for p in graid.participants(db_session, row.id)), default=0),
                "userMedals": medals, "userSkills": [], "userMaterials": gstate.materials_list(st),
            }
            if with_users:
                entry["discoverer"] = _raid_user(db_session.get(User, row.discoverer_id))
                entry["mvp"] = _raid_user(db_session.get(User, mvp_uid))
            out.append(entry)
    logger.info("RAID REWARD: %s", out)
    return out


@register(110)  # GET /raid/reward/151101
def handle_raid_reward(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userData={"userPoint": _user_point(user)},
                          raidRewards=_raid_rewards(user, db_session, with_users=False))


@register(109)  # GET /raid/reward
def handle_raid_reward_all(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userData={"userPoint": _user_point(user)},
                          raidRewards=_raid_rewards(user, db_session, with_users=True))


@register(111)  # GET /raid/member {raidId}
def handle_raid_member(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # cooperators [{user: RaidBase::User, damage}], discovererUserId, mvpUserId. RaidBossResultPopUp reads
    # cooperators.at(): never send it empty.
    row = graid.by_id(db_session, request_data.get("raidId")) or graid.own(db_session, user.id if user else 0)
    coop = []
    if row:
        for p in sorted(graid.participants(db_session, row.id), key=lambda p: -p.damage):
            o = db_session.get(User, p.user_id)
            if o:
                coop.append({"user": _raid_user(o), "damage": p.damage})
    if not coop:
        coop = [{"user": _raid_user(user), "damage": 0}]
    return build_response(user, cooperators=coop,
                          discovererUserId=row.discoverer_id if row else (user.id if user else 0),
                          mvpUserId=(_raid_mvp(db_session, row.id) if row else 0) or (user.id if user else 0))


@register(112)  # POST /raid/start {raidId, supportUserId, userKeybladeId}
def handle_raid_start(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # The boss may be the player's own or a party member's (/raid/list). The fighter becomes a participant.
    logger.info("RAID START: %s", request_data)
    uid = user.id if user else 0
    resume = not int(request_data.get("raidId") or 0) and user is not None and \
        bool(gstate.load(user, db_session).get("raid_playing"))
    if resume:
        # a resumed raid fight (stageResumption status 2): the client sends 0s, the server knows the fight
        st0 = gstate.load(user, db_session)
        saved = st0.get("stage_start") or {}
        request_data = {**request_data, "raidId": st0["raid_playing"],
                        "supportUserId": saved.get("supportUserId", 0), "userKeybladeId": saved.get("userKeybladeId", 1)}
        logger.info("RAID RESUME: %s", request_data)
    row = graid.by_id(db_session, request_data.get("raidId")) or graid.own(db_session, uid)
    raid = graid.load(row) if row else None
    if row:
        graid.participant(db_session, row.id, uid)
        with gstate.State(user, db_session) as st:
            st["raid_playing"] = row.id
            st["stage_keyblade"] = request_data.get("userKeybladeId", 1)
            st["stage_start"] = {"supportUserId": int(request_data.get("supportUserId") or 0),
                                 "userKeybladeId": request_data.get("userKeybladeId", 1)}
    return build_response(user,
        userData={"userPoint": _user_point(user)},
        raid=graid.info(raid),
        players=[], vitalsLog=[], partsLog=[],
        startRaidData={"raidId": row.id if row else 0,
                       "supportUserId": request_data.get("supportUserId", 0),
                       "userKeybladeId": request_data.get("userKeybladeId", 1)},
        discovererUserId=row.discoverer_id if row else uid,
        campaigns=[],
        supportUsers=_chosen_supporters(db_session, user, request_data, friend_points=not resume),
    )


@register(113)  # POST /raid/clear
def handle_raid_clear(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {parts:[{raidEnemyId, partsId, hp, damage}], getPoint:{exp, money, lux}, maximumDamage, burst}.
    # Damage goes to the SHARED boss (the one started with 112) and to this player's participant row.
    logger.info("RAID CLEAR: %s", request_data)
    uid = user.id if user else 0
    with gstate.State(user, db_session) as st:
        # the boss /raid/start (112) opened; each start counts one clear (a repeat finds none: status 5)
        row = graid.by_id(db_session, st.pop("raid_playing", None))
        raid = graid.load(row) if row else None
        before = raid["status"] if raid else None
        if raid and raid["status"] == graid.RAID_STATUS_ACTIVE:
            dealt = graid.apply_damage(raid, request_data.get("parts"))
            graid.participant(db_session, row.id, uid).damage += dealt
            graid.save(row, raid)
            if raid["status"] == graid.RAID_STATUS_DEFEATED:
                host = db_session.get(User, row.discoverer_id)
                if host:                                     # the summoner's boss goes up a level (wiki)
                    if host.id == uid:
                        graid.level_up(st, raid["enemyId"])
                    else:
                        with gstate.State(host, db_session) as hst:
                            graid.level_up(hst, raid["enemyId"])
                logger.info("RAID DEFEATED: %s (host %s)", row.id, row.discoverer_id)
        _store_burst(st, request_data.get("burst"))
        # raidTimeStatus (RaidClear::TimeStatus, BattleResultDialog::openRaidResult): 1 = the fight ended in time
        # (boss still up - "support request sent" when reliefFlag - or beaten by this player), 2 = "The Raid Boss
        # has escaped." (time ran out), 3/4 = "A party member defeated the Raid Boss!" (someone else finished it
        # first; the damage does not count toward MVP), 5 = "No available Raid Boss."
        if raid is None:
            time_status = 5
        elif before == graid.RAID_STATUS_ACTIVE:
            time_status = 1
        elif before == graid.RAID_STATUS_DEFEATED:
            time_status = 3
        else:
            time_status = 2
    if user and raid is not None:
        gp = request_data.get("getPoint", {})
        user.exp += gp.get("exp", 0)
        user.money += gp.get("money", 0)
        _add_lux(user, gp.get("lux", 0))
    return build_response(user,
        userData={"userPoint": _user_point(user), "userDetail": _user_detail(user),
                  "stageResumption": _stage_resumption(user, db_session)},
        raidTimeStatus=time_status,
        reliefFlag=0,
        userSkills=[], userTitles=[],
        userKeyblades=_user_keyblades(user, db_session),
    )


@register(108)  # GET /raid/list: the player's own boss + their party members' active bosses
def handle_raid_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    uid = user.id if user else 0
    raids = []
    for row, raid in graid.visible(db_session, _raid_party(db_session, uid)):
        raids.append({"raid": graid.info(raid), "discoverer": _raid_user(db_session.get(User, row.discoverer_id))})
    return build_response(user, raids=raids)


@register(103)  # POST /stage/start
def handle_stage_start(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    stage_id = int(request_data.get("stageId") or 0)
    resume = stage_id == 0 and user is not None and bool(user.current_stage_id)
    if resume:
        # A resumed quest (stageResumption status 1 at boot): the client sends stageId / supportUserId /
        # userKeybladeId 0 and expects the server to start the quest that was open, as it was started.
        saved = gstate.load(user, db_session).get("stage_start") or {}
        stage_id = user.current_stage_id
        request_data = {**request_data, "stageId": stage_id, "supportUserId": saved.get("supportUserId", 0),
                        "userKeybladeId": saved.get("userKeybladeId", 1)}
        logger.info("STAGE RESUME: stage %s with %s", stage_id, saved)
    keyblade_id = request_data.get("userKeybladeId", 1)
    logger.info("STAGE START: stageId=%s keybladeId=%s payload=%s", stage_id, keyblade_id, request_data)
    if user:
        user.current_stage_id = stage_id
        db_session.add(user)
    # chests and enemy drops are rolled now and granted at /stage/clear for the uniqueIds the player
    # opened / defeated (see stagemap.py)
    drops = stagemap.roll_stage(stage_id, medal_power=_campaign_power(1, stage_id))   # medal-drop campaigns
    with gstate.State(user, db_session) as st:
        st["stage_drops"] = {"stageId": stage_id, **drops}
        st["stage_keyblade"] = keyblade_id
        st["stage_start"] = {"supportUserId": int(request_data.get("supportUserId") or 0),
                             "userKeybladeId": keyblade_id}
        cleared = list((st["stages"].get(str(stage_id)) or {}).get("clearMissionIds", []))
    logger.info("STAGE DROPS: %s", drops)
    return build_response(user,
        userData={"userPoint": _user_point(user)},
        # uniqueSymbolEnemyIds listed here are NOT spawned (StageManager::hasRandomEnemySymbol skips teams whose
        # random-symbol id is in the list); empty = every random team appears
        userRandomEnemies=[],
        userEnemyDropItems=[{"uniqueEnemyId": int(uid), "dropItemTypeIds": e["drop"]}
                            for uid, e in drops["enemies"].items()],
        userTreasures=[{"uniqueTreasureId": int(uid), "dropItemTypeIds": e["drop"]}
                       for uid, e in drops["treasures"].items()],
        startStageData={
            "stageId": stage_id,
            # the chosen supporter, echoed: BattleUtil::getSupportMedal looks this id up in the 102 support
            # list to put the friend's medal on the battle deck (0 = no friend medal in battle)
            "supportUserId": int(request_data.get("supportUserId") or 0),
            "userKeybladeId": keyblade_id,
            # missions already cleared on this stage: the result screen (BattleResultScrollView::
            # loadStageResultData) lists a mission reward only for missions cleared now and not in here
            "clearMissionIds": cleared,
            "stageSkip": 0,
        },
        campaigns=[r["campaignId"] for r in gevents.active_campaigns() if gevents.campaign_applies(r, stage_id)],
        supportUsers=_chosen_supporters(db_session, user, request_data, friend_points=not resume),
    )


def _party_id(user: Optional[User]) -> int:
    from sqlalchemy.orm import object_session
    db = object_session(user) if user is not None else None
    return gparty.party_id_of(db, user.id) if db is not None else 0


def _play_timezones(user: Optional[User]) -> list:
    # UserDetail::parse keeps up to 6 entries: the chosen time slots (1..6), not a 6-slot mask
    return [int(x) for x in (user.play_timezones or "").split(",") if x] if user else []


def _user_detail(user: Optional[User]) -> dict:
    return {
        "level": _lux_rank(user),
        "exp": user.exp if user else 0,
        "luxRank": _lux_rank(user),
        "luxGetRatio": 100,
        **_user_titles(user),
        # the player row's cost for the rank (42 at rank 1 ... 440) plus Avatar Board deck-cost nodes; the client
        # never reads player.cost itself, so the server applies it (like player.ap / hp in UserPoint)
        "maxDeckCost": _get_player_stats(_lux_rank(user)).get("cost", 42) + ((user.deck_cost_prize or 0) if user else 0),
        "playTimezones": _play_timezones(user),
        "playFrequently": (user.play_frequently or 0) if user else 0, "partyId": _party_id(user), "unionId": user.union_id if user else 1,
        "maxMedal": _max_medal(user), "mvpCount": 0, "equipCoordinateNo": _equip_coordinate(user),
        "lastClearStageId": user.last_clear_stage_id if user else 0,
        "lastPlayNormalSphereBoardId": 0, "lastPlayStageSphereBoardId": 0,
        "lastPlayRaidSphereBoardId": 0, "lastPlayColosseumSphereBoardId": 0,
        "isGuilt": 0,
    }


def _stage_resumption(user=None, db_session=None) -> dict:
    """StageResumption: a quest started and neither cleared nor retired (the app was closed or crashed). At boot
    SceneUtil::moveToMyPageOrResumeStage goes straight back into it (StartDeckEditDialog::startAdventure)
    instead of MyPage: status 1 = story quest (stageId), 2 = raid (raidId), 3 = Coliseum. In 1.0.1 the quest
    starts over; returning to the same room came later (user, O12). Coliseum resumption is not offered."""
    out = {"resumptionStatus": 0, "stageId": 0, "raidId": 0, "colosseumStageId": 0}
    if not user or not user.tutorial_done:
        return out
    if user.current_stage_id:
        out.update(resumptionStatus=1, stageId=user.current_stage_id)
    elif db_session is not None:
        row = graid.by_id(db_session, gstate.load(user, db_session).get("raid_playing"))
        if row is not None and graid.load(row)["status"] == graid.RAID_STATUS_ACTIVE:
            out.update(resumptionStatus=2, raidId=row.id)
    return out


@register(106)  # POST /stage/clear
def handle_stage_clear(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # The clear request has no stageId: it is the stage /stage/start (103) opened. Each start counts one clear;
    # a clear with no start before it (a repeat) is refused instead of counted again.
    stage_id = user.current_stage_id if user else 0
    if not stage_id:
        logger.warning("STAGE CLEAR without a stage start: refused (payload=%s)", request_data)
        return build_error(user, "This quest has already been cleared.")
    user.current_stage_id = 0
    db_session.add(user)
    logger.info("STAGE CLEAR: stageId=%s payload=%s", stage_id, request_data)
    new_medals, first_clear, new_titles = [], 0, []
    with gstate.State(user, db_session) as st:
        title_mark = gstate.title_mark(st)
        rec = st["stages"].get(str(stage_id))
        first_clear = int(rec is None)
        if rec is None:
            rec = st["stages"][str(stage_id)] = {"clearMissionIds": [], "luxRecord": 0, "clears": 0}
        rec["clears"] += 1
        lux = request_data.get("getPoint", {}).get("lux", 0)
        rec["luxRecord"] = max(rec["luxRecord"], lux)
        row = gstate.stage_row(stage_id) or {}
        rewards = []
        if first_clear:
            for k in range(row.get("validClearGetItem", 0)):
                rewards.append((row["clearGetItemType"][k], row["clearGetItemId"][k], row["clearGetItemNum"][k], 1))
        for mid in request_data.get("clearMissionIds", []):
            if mid not in rec["clearMissionIds"] and 1 <= mid <= row.get("validSubmission", 0):
                rec["clearMissionIds"].append(mid)
                k = mid - 1
                rewards.append((row["submissionRewardType"][k], row["submissionItemId"][k], row["submissionItemNum"][k],
                                2))
        rec["clearMissionIds"].sort()
        for m in request_data.get("getMaterials", []):
            gstate.add_material(st, m["materialId"], m.get("number", 1))
        new_medals += _grant_drops(user, st, stage_id, request_data)
        _store_burst(st, request_data.get("burst"))
        reward_medals = []      # StageClear::Reward {rewardkind, userMedalId, display} per new medal
        for rtype, rid, num, kind in rewards:
            got = _grant(user, st, rtype, rid, num)
            new_medals += got
            reward_medals += [{"rewardkind": kind, "userMedalId": m["userMedalId"], "display": 1} for m in got]
        # stage master clearGetTitle (validClearGetTitle): no-op when already owned, so a clear made before
        # titles were granted still earns it
        if row.get("validClearGetTitle") and gstate.add_title(st, row.get("clearGetTitle")):
            logger.info("  TITLE %s (clearGetTitle)", row.get("clearGetTitle"))
        new_titles = gstate.titles_since(st, title_mark)
        materials = gstate.materials_list(st)
        # Raid boss discovery (KHUX Wiki "Raid Boss" + talk page): a boss appears after the player has defeated
        # ~75 enemies (68-82, rolled per cycle; GUESS: R1 for the exact range), on a stage with raidBoss (a
        # raidSetting id) and no own boss up; which boss = the stage's raidSetting (the last quest cleared).
        # A raid-encounter campaign (evCampaign type 6, power/10000) shortens the count.
        st["raid_kills"] = st.get("raid_kills", 0) + int(request_data.get("enemyDeadNumber", 0) or 0) \
            + int(request_data.get("rareEnemyDeadNumber", 0) or 0)
        own = graid.own(db_session, user.id) if user else None
        own_up = own is not None and graid.load(own)["status"] == graid.RAID_STATUS_ACTIVE
        raid_found = False
        story = gstate.story_order()
        quest_no = story.index(stage_id) + 1 if stage_id in story else 0
        always = quest_no in graid.ALWAYS_SPAWN_QUESTS and first_clear
        if first_clear and quest_no:
            # story milestone bonuses (campaigns.json quest_bonus: every 5th quest 150 Jewels + 10,000 munny,
            # khux-guides 2015-09; GUESS: Q4) -> present box
            for label, items in gevents.quest_bonuses(quest_no):
                for rtype, rid, num in items:
                    add_present(st, rtype, rid, num, label)
                logger.info("STORY MILESTONE: quest %s -> %s %s", quest_no, label, items)
        lure = gevents.is_lure_stage(stage_id)      # raid-event quests always bring their boss (GUESS: R7)
        always = always or lure
        never = quest_no in graid.NEVER_SPAWN_QUESTS
        if user and row.get("raidBoss") and not never and not own_up and (always or st["raid_kills"] >= graid.kills_threshold(
                st, _campaign_power(6, stage_id))):
            setting = graid._row("raidSetting", "raidSettingId", row["raidBoss"]) or {}
            # an Omega-encounter campaign (type 8, power 200000 = "100% Raid Boss Omega Encounter") forces the rare boss
            omega_boost = _campaign_power(8, stage_id)
            omega = (lure and "Ω" in (row.get("name") or "")) or graid.omega_due(st, setting) or (
                omega_boost > 10000 and setting.get("rareBossId") not in (None, 0, setting.get("bossId"))
                and random.randrange(200000) < omega_boost)
            boss_id = setting.get("rareBossId" if omega else "bossId", 0)
            new_row, raid = graid.create(db_session, user.id, stage_id, row["raidBoss"],
                                         graid.boss_level(st, boss_id), rare=omega)
            if new_row:
                raid_found = True
                if omega:
                    graid.omega_spawned(st, setting)
                logger.info("RAID DISCOVERED: stage %s setting %s boss %s%s level %s after %s kills", stage_id,
                            row["raidBoss"], boss_id, " (OMEGA)" if omega else "", raid["level"], st["raid_kills"])
                st["raid_kills"], st["raid_kill_goal"] = 0, 0
    if user:
        get_point = request_data.get("getPoint", {})
        user.exp += get_point.get("exp", 0)
        user.money += get_point.get("money", 0)
        _add_lux(user, get_point.get("lux", 0))
        # the result screen plays "raid boss appeared" when userPoint.raidPoint grew
        # (SceneBattleResult::startResult -> SceneAdventureSelect::raidBossAnim), so it only rises on a discovery
        if raid_found:
            user.raid_point = (user.raid_point or 0) + max(get_point.get("raidPoint", 0), 1)
        if stage_id in gstate.story_order():
            user.last_clear_stage_id = max(user.last_clear_stage_id or 0, stage_id)
        db_session.add(user)
    return build_response(user,
        userData={
            "userPoint": _user_point(user),
            "userDetail": _user_detail(user),
            "stageResumption": _stage_resumption(user, db_session),
        },
        userStone={"freeStone": user.free_stone if user else 300, "payStone": user.pay_stone if user else 0},
        # objects, not ids (StageClear::parse runs Reward::init on each: rewardkind IsInt, userMedalId IsUint64,
        # display IsInt). The 1.0.1 client never reads the records back (only firstClearFlag, which it writes over
        # byte 0 of the same buffer); the result screen builds its reward rows from the stage master instead.
        stageRewardUserMedalIds=reward_medals,
        firstClearFlag=first_clear,
        userMaterials=materials,
        userMedals=new_medals,
        userSkills=[],
        # newly obtained titles: StageClear::parse keeps them for SceneBattleResult's "title obtained" popup
        userTitles=new_titles,
        userKeyblades=_user_keyblades(user, db_session),
    )


# drop types the client applies itself: 4 Munny / 11 Lux go into getPoint (StageSkipActionMap::
# takeTreasureContent, AvatarActor::setPrizeContent), 8 attack gauge / 9 HP are in-battle pickups
_CLIENT_APPLIED_DROPS = {4, 8, 9, 11}


def _grant_drops(user: Optional[User], st: dict, stage_id: int, request_data: dict) -> list:
    """Grant the rolled contents of the chests opened (getTreasures) and enemies defeated (getEnemyDropItems:
    uniqueEnemyIds) during this quest. Returns new medals."""
    rolled = st.pop("stage_drops", None) or {}
    if rolled.get("stageId") != stage_id:
        return []
    got = []
    for kind, key in (("treasures", "getTreasures"), ("enemies", "getEnemyDropItems")):
        for uid in request_data.get(key, []):
            entry = rolled.get(kind, {}).get(str(uid))
            if not entry:
                continue
            for rtype, rid, num in stagemap.items(entry):
                if rtype not in _CLIENT_APPLIED_DROPS:
                    logger.info("  DROP from %s %s", "chest" if kind == "treasures" else "enemy", uid)
                    got += _grant(user, st, rtype, rid, num)
    return got


def _campaign_power(campaign_type: int, stage_id: Optional[int] = None) -> int:
    """Multiplier (10000 = 100.00%) of the running evCampaigns of this type covering the stage (events.py)."""
    return gevents.campaign_power(campaign_type, stage_id)


def _misc(misc_id: int, default: int) -> int:
    from .master import MASTER_JSON_DATA
    return next((m["value"] for m in MASTER_JSON_DATA.get("misc", []) if m.get("miscId") == misc_id), default)


def _grant(user: Optional[User], st: dict, rtype: int, rid: int, num: int) -> list:
    """Give a reward (stage first-clear / mission). Types per SceneUtil::setItemImageData; returns new medals."""
    logger.info("  REWARD type=%s id=%s num=%s", rtype, rid, num)
    if rtype == gstate.ITEM_MEDAL:
        return [gstate.add_medal(st, rid) for _ in range(max(num, 1))]
    if rtype == gstate.ITEM_MATERIAL:
        gstate.add_material(st, rid, num)
    elif rtype == gstate.ITEM_TITLE:
        # unique per player; the caller collects new ones with gstate.title_mark / titles_since
        if gstate.add_title(st, rid) is None:
            logger.info("  title %s already owned or unknown", rid)
    elif rtype == gstate.ITEM_KEYBLADE:
        for _ in range(max(num, 1)):
            gstate.add_keyblade(st, rid)
    elif rtype in gstate.ITEM_AVATAR_PARTS:
        # unique per player; callers collect new ones by userAvatarPartsId (they only grow)
        if gstate.add_avatar_part(st, rid) is None:
            logger.info("  avatar part %s already owned or unknown", rid)
    elif user and rtype in _POINT_REWARDS:
        col = _POINT_REWARDS[rtype]
        setattr(user, col, (getattr(user, col) or 0) + num)
        if rtype == 11:
            user.total_lux += num
            user.lux_rank = user.level = _lux_rank(user)
    else:
        logger.warning("  REWARD type %s not granted yet", rtype)
    return []


# reward type -> User column. Names from the client's own text (SceneUtil::setItemImageData -> TextData):
# 2 Jewel, 4 Munny, 6 Friend Point, 8 Attack Prize, 9 HP Prize, 10 Raid Points, 11 Lux, 14 Avatar Coins,
# 15 Event Coins, 16 Raid Coins, 17 Coliseum Coins. Not points: 3 medal, 5 material, 7 title, 12 avatar board
# unlock, 13 keyblade, 18/19/20/23 avatar parts, 24 stamp.
_POINT_REWARDS = {
    2: "free_stone", 4: "money", 6: "kizuna_point", 8: "attack", 9: "hp_prize", 10: "raid_point",
    11: "lux", 14: "sphere_point", 15: "stage_sphere_point", 16: "raid_sphere_point",
    17: "colosseum_sphere_point",
}


def _master_row(table: str, key: str, value: int) -> dict:
    from .master import MASTER_JSON_DATA
    return next((r for r in MASTER_JSON_DATA.get(table, []) if r.get(key) == value), {})


def _user_stone(user: Optional[User]) -> dict:
    return {"freeStone": user.free_stone if user else 300, "payStone": user.pay_stone if user else 0}


def _store_burst(st: dict, burst) -> None:
    """The battle's CP (StageState+12; one gauge step = 10000) is sent by /stage/retire and /stage/clear as
    `burst`; it carries over on the keyblade the quest was played with."""
    if burst is None:
        return
    kid = st.get("stage_keyblade")
    for kb in st["keyblades"]:
        if kb["userKeybladeId"] == kid:
            kb["burst"] = int(burst)


def _remove_medals(st: dict, ids: set) -> None:
    st["medals"] = [m for m in st["medals"] if m["userMedalId"] not in ids]
    for kb in st["keyblades"]:
        kb["deckMedals"] = [0 if mid in ids else mid for mid in kb["deckMedals"]]


@register(44)  # POST /user/medal/lock
def handle_medal_lock(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {userMedalIds: [...], isLocks: [1|0 ...]} (parallel arrays; executeUserMedalLock)
    # response: userMedals[] - the client runs updateMedal on each
    flags = dict(zip(request_data.get("userMedalIds", []), request_data.get("isLocks", [])))
    changed = []
    with gstate.State(user, db_session) as st:
        for m in st["medals"]:
            if m["userMedalId"] in flags:
                m["lock"] = 1 if flags[m["userMedalId"]] else 0
                changed.append(dict(m))
    logger.info("MEDAL LOCK: %s", flags)
    return build_response(user, userMedals=changed)


@register(48)  # POST /user/material/sell
def handle_material_sell(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {userMaterialId, number}; price = material.sell x number (SceneSellOutMaterialItem preview)
    # response: userData.userPoint + top-level userMaterial (one object, the row after the sale)
    umid, num = request_data.get("userMaterialId"), max(int(request_data.get("number", 0)), 0)
    with gstate.State(user, db_session) as st:
        have = st["materials"].get(str(umid), 0)
        num = min(num, have)
        st["materials"][str(umid)] = have - num
        row = {"userMaterialId": umid, "materialId": umid, "number": have - num}
    price = _master_row("material", "materialId", umid).get("sell", 0) * num
    if user:
        user.money += price
        db_session.add(user)
    logger.info("MATERIAL SELL: %s x%d -> +%d munny", umid, num, price)
    return build_response(user, userData={"userPoint": _user_point(user)}, userMaterial=row)


@register(49)  # POST /user/medal/sell
def handle_medal_sell(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {userMedalIds: [...]}. Price per SceneSaleMedal::updateSellInfo: munny = medal.sell +
    # medal.sellPerLv x (level - 1); plus medal.sellSpherePoint (Avatar Coins) when the medal's special attack
    # is fully enhanced (burstUpperNumber == burst.maxEnhanceCount >= 1).
    # response: userData.userPoint, userSkills[], top-level sellUserMedalIds (client removeMedals)
    ids = set(request_data.get("userMedalIds", []))
    munny = coins = 0
    with gstate.State(user, db_session) as st:
        sold = [m for m in st["medals"] if m["userMedalId"] in ids and not m.get("lock")]
        for m in sold:
            row = _master_row("medal", "medalId", m["medalId"])
            munny += row.get("sell", 0) + row.get("sellPerLv", 0) * (m["level"] - 1)
            cap = _master_row("burst", "burstId", row.get("burstId", 0)).get("maxEnhanceCount", 0)
            if cap >= 1 and m.get("burstUpperNumber", 0) == cap:
                coins += row.get("sellSpherePoint", 0)
        sold_ids = [m["userMedalId"] for m in sold]
        _remove_medals(st, set(sold_ids))
    if user:
        user.money += munny
        user.sphere_point = (user.sphere_point or 0) + coins
        db_session.add(user)
    logger.info("MEDAL SELL: %s -> +%d munny +%d avatar coins", sold_ids, munny, coins)
    return build_response(user, userData={"userPoint": _user_point(user)}, userSkills=[],
                          sellUserMedalIds=sold_ids)


@register(51)  # POST /keyblade/burst/max
def handle_keyblade_burst_max(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {userKeybladeId}; cost misc 120 Jewels (StartDeckEditDialog::openAbilityMaxPopup)
    # response: userStone + top-level userKeyblade (one keyblade object; client updateKeyblade)
    kid = request_data.get("userKeybladeId")
    cost = _misc(120, 30)
    with gstate.State(user, db_session) as st:
        kb = next(k for k in st["keyblades"] if k["userKeybladeId"] == kid)
        kb["burst"] = _master_row("keyblade", "keybladeId", kb["keybladeId"]).get("maxBurstGauge", 0) * 10000
        kb = dict(kb)
    if user:
        # free Jewels are spent before paid ones (user)
        free = min(user.free_stone or 0, cost)
        user.free_stone = (user.free_stone or 0) - free
        user.pay_stone = max((user.pay_stone or 0) - (cost - free), 0)
        db_session.add(user)
    logger.info("KEYBLADE BURST MAX: %s -> burst %d (-%d jewels)", kid, kb["burst"], cost)
    return build_response(user, userStone=_user_stone(user), userKeyblade=kb)


@register(52)  # POST /keyblade/enhance
def handle_keyblade_enhance(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {userKeybladeId}. SceneDeckEdit::updateKeyBladePanel: needs needMaterialNum[i] of
    # needMaterialId[i] (i < validNeedMaterial) and a non-zero evolveId; no munny cost.
    # response: userKeyblades[], userMaterials[], userTitles[]
    kid = request_data.get("userKeybladeId")
    with gstate.State(user, db_session) as st:
        kb = next(k for k in st["keyblades"] if k["userKeybladeId"] == kid)
        row = _master_row("keyblade", "keybladeId", kb["keybladeId"])
        need = [(row["needMaterialId"][i], row["needMaterialNum"][i]) for i in range(row.get("validNeedMaterial", 0))]
        if row.get("evolveId") and all(st["materials"].get(str(m), 0) >= n for m, n in need):
            for m, n in need:
                st["materials"][str(m)] -= n
            logger.info("KEYBLADE ENHANCE: %s %s -> %s", kid, kb["keybladeId"], row["evolveId"])
            kb["keybladeId"] = row["evolveId"]
            kb["deckMedals"] = gstate.fit_deck(kb["deckMedals"], kb["keybladeId"])   # may gain slots
        else:
            logger.warning("KEYBLADE ENHANCE refused: %s (evolveId %s, need %s)", kid, row.get("evolveId"), need)
        keyblades, materials = st["keyblades"], gstate.materials_list(st)
    return build_response(user, userKeyblades=keyblades, userMaterials=materials, userTitles=[])


@register(54)  # POST /user/medal/evolve
def handle_medal_evolve(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {baseUserMedalId, attachmentMedalIds}. SceneEvolveMedal::init: costs medal.evolveMoney, becomes
    # medal.evolveId, consumes the evolveNeedId medals (sent as attachmentMedalIds).
    # response: userData.userPoint, beforeEvolveUserMedal / afterEvolveUserMedal (same userMedalId: the client
    # only removes attachmentMedalIds), attachmentMedalIds
    base_id = request_data.get("baseUserMedalId")
    attach = list(request_data.get("attachmentMedalIds", []))
    with gstate.State(user, db_session) as st:
        base = next(m for m in st["medals"] if m["userMedalId"] == base_id)
        before = dict(base)
        row = _master_row("medal", "medalId", base["medalId"])
        if row.get("evolveId"):
            # evolving resets the medal to LV 1 of its new cap (the client's Evolve preview shows LV 1/<new max>;
            # 2015-16 guides: "max it, evolve it - back to level 1 - max it again"). The client allows Evolve only
            # at max level.
            base["medalId"] = row["evolveId"]
            base["level"], base["exp"] = 1, 0
            _remove_medals(st, set(attach))
            cost = row.get("evolveMoney", 0)
        else:
            logger.warning("MEDAL EVOLVE refused: %s has no evolveId", base["medalId"])
            attach, cost = [], 0
        after = dict(base)
    if user:
        user.money = max(0, user.money - cost)
        db_session.add(user)
    logger.info("MEDAL EVOLVE: %s %s -> %s (-%d munny, used %s)", base_id, before["medalId"], after["medalId"],
                cost, attach)
    return build_response(user, userData={"userPoint": _user_point(user)},
                          beforeEvolveUserMedal=before, afterEvolveUserMedal=after, attachmentMedalIds=attach)


@register(104)  # POST /stage/retire
def handle_stage_retire(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {burst} (the battle's CP); response userKeyblades[] + userData.stageResumption
    logger.info("STAGE RETIRE: %s", request_data)
    if user:
        user.current_stage_id = 0                     # the quest is over: nothing to resume or clear
        db_session.add(user)
    with gstate.State(user, db_session) as st:
        _store_burst(st, request_data.get("burst"))
        st.pop("stage_drops", None)
        st.pop("raid_playing", None)
        keyblades = st["keyblades"]
    return build_response(user, userKeyblades=keyblades,
                          userData={"stageResumption": _stage_resumption(user, db_session)})


# UserProfile::Record::init needs all 53 keys (uint64); values are what we track, else 0.
_RECORD_KEYS = (
    "login continueLogin getMoney getSpherePoint useMoney sellMedal sellMedalCount sellMaterial sellMaterialCount "
    "getKizunaPoint useKizunaPoint zukanMedal yamiSpeedZukan yamiPowerZukan yamiMagicZukan hikariSpeedZukan "
    "hikariPowerZukan hikariMagicZukan getMedal medalEnhanceSuccess medalEnhanceBigSuccess medalEnhanceGreatSuccess "
    "medalEvolveSuccess keybladeEnhance useMaterial kizunaDraw raiseDraw getStar1Medal getStar2Medal getStar3Medal "
    "getStar4Medal getStar5Medal getStar6Medal stageClear challengeClear dropEnemy dropMimic dropRareEnemy "
    "bossBattleJoinMe bossBattleJoinOther dropBoss getLux getLuxMax dropParts maxDamageOneTurn openTreasure "
    "getMaterial openAllSphere openGrid unionPersonalRankingHighest unionPartyRankingHighest "
    "totalPersonalRankingHighest colosseumRankingHighest").split()


def _user_record(user: Optional[User], st: dict) -> dict:
    rec = dict.fromkeys(_RECORD_KEYS, 0)
    if user:
        rec.update(login=1, continueLogin=1, getMoney=max(user.money or 0, 0), getLux=user.total_lux or 0,
                   getMedal=len(st.get("medals", [])), stageClear=sum(r.get("clears", 0) for r in st.get("stages", {}).values()))
    return rec


@register(4)  # GET /user/profile (AvatarInfoDialog: tapping an avatar)
def handle_user_profile(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {userId, platformType}; response = UserProfile::parse: userData.{user, userDetail, userPoint,
    # lastActionDatetime}, userMedals[], userSkills[], userAvatar, userKeyblade, userRecord (53 uint64),
    # userRanking {lux, rank}, linkPlatformId; party only when userDetail.partyId != 0.
    target = user
    req_id = request_data.get("userId")
    if req_id and user and int(req_id) != user.id:
        target = db_session.get(User, int(req_id))
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    if target is None:                       # the default friend "Sora" (or an unknown id)
        sora = _sora_support(user, db_session)
        kb = {"userKeybladeId": 0, "category": 0, "keybladeId": 1000, "deckMedals": [sora["userMedal"]["userMedalId"]],
              "burst": 0, "totalAttack": 0, "totalDefense": 0, "isFavorite": 1, "getDatetime": now}
        uid, name, detail, point = _SORA_SUPPORT_ID, "Sora", _user_detail(None), _user_point(None)
        detail = dict(detail, level=sora["level"], luxRank=sora["level"])
        medals, avatar, record = [sora["userMedal"]], _user_avatar(None), _user_record(None, {})
        comment, gender = "", 0
    else:
        st = gstate.load(target, db_session)
        kb = next((k for k in st["keyblades"] if k.get("isFavorite")), st["keyblades"][0])
        deck = set(kb["deckMedals"])
        uid, name, detail, point = target.id, target.user_name or "Player", _user_detail(target), _user_point(target)
        medals = [m for m in st["medals"] if m["userMedalId"] in deck]
        avatar, record = _user_avatar(target), _user_record(target, st)
        comment, gender = target.comment or "", target.gender or 0
    return build_response(user,
        userData={
            "user": {"userId": uid, "nativeUserId": uid, "platformId": 2, "userName": name, "gender": gender,
                     "comment": comment, "deviceType": 2,
                     "continueLoginCount": max(target.continue_login_count or 0, 1) if target else 1, "isFleeze": 0,
                     "fleezedDatetime": "2000-01-01 00:00:00"},
            "userDetail": detail, "userPoint": point, "lastActionDatetime": _last_action(target) if target else now,
        },
        userMedals=medals, userSkills=[], userAvatar=avatar, userKeyblade=kb, userRecord=record,
        userRanking={"lux": point.get("totalLux", 0), "rank": 0}, linkPlatformId="",
        # UserProfile::parse requires "party" when userDetail.partyId != 0
        **({"party": gparty.party_obj(db_session, db_session.get(Party, detail["partyId"]))}
           if detail.get("partyId") and db_session.get(Party, detail["partyId"]) else {}),
    )


def _present_list(st: dict) -> list:
    return sorted(st.get("presents", []), key=lambda x: x["userPresentId"])


@register(18)  # GET /user/present (present box)
def handle_user_present(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # UserPresent::parse: userPresent {userPresentDatas[{userPresentId, resourceType, resourceId, number,
    # limitDatetime ("0000-00-00 00:00:00" = no expiry), comment, created}], presentCount, presentCountMax}
    st = gstate.load(user, db_session)
    presents = _present_list(st)
    return build_response(user, userPresent={
        "userPresentDatas": presents, "presentCount": len(presents), "presentCountMax": 999})


def add_present(st: dict, rtype: int, rid: int, num: int, comment: str, limit: str = "0000-00-00 00:00:00") -> dict:
    """Put an item in the player's present box (resourceType = item type: 2 Jewel, 3 Medal, 4 Munny, ...)."""
    st.setdefault("presents", [])
    pid = st.get("next_present", 1)
    st["next_present"] = pid + 1
    pr = {"userPresentId": pid, "resourceType": rtype, "resourceId": rid, "number": num,
          "limitDatetime": limit, "comment": comment,
          "created": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())}
    st["presents"].append(pr)
    return pr


@register(47)  # POST /user/present/receive
def handle_present_receive(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {receivePresentIds: [...]} (one, or every listed id for "receive all").
    # response: userData.userPoint, userStone, userMaterials, userMedals, userSkills, userKeyblades,
    # userAvatarParts, userTitles, lastUserPresentIds = the ids STILL in the box (the client marks every other
    # present as received). Medals stay in the box when the medal box is full (userDetail maxMedal).
    ids = set(request_data.get("receivePresentIds", []))
    with gstate.State(user, db_session) as st:
        kb_before = {k["userKeybladeId"] for k in st["keyblades"]}
        parts_before = {p["userAvatarPartsId"] for p in st.get("avatar_parts", [])}
        title_mark = gstate.title_mark(st)
        new_medals, kept = [], []
        for pr in _present_list(st):
            if pr["userPresentId"] not in ids:
                kept.append(pr)
                continue
            if pr["resourceType"] == gstate.ITEM_MEDAL and len(st["medals"]) + pr["number"] > _max_medal(user):
                kept.append(pr)                     # medal box full
                continue
            new_medals += _grant(user, st, pr["resourceType"], pr["resourceId"], pr["number"])
        st["presents"] = kept
        new_keyblades = [k for k in st["keyblades"] if k["userKeybladeId"] not in kb_before]
        new_parts = [p for p in _avatar_parts(st) if p["userAvatarPartsId"] not in parts_before]
        new_titles = gstate.titles_since(st, title_mark)
        materials = gstate.materials_list(st)
    if user:
        db_session.add(user)
    logger.info("PRESENT RECEIVE: %s -> %d left", sorted(ids), len(kept))
    return build_response(user,
        userData={"userPoint": _user_point(user)}, userStone=_user_stone(user),
        userMaterials=materials, userMedals=new_medals, userSkills=[], userKeyblades=new_keyblades,
        userAvatarParts=new_parts, userTitles=new_titles, lastUserPresentIds=[pr["userPresentId"] for pr in kept])


OPTION_KEYS = ("isNoticeAp", "isNoticeHelp", "isNoticeEvent")


def _user_option(user, db_session):
    saved = gstate.load(user, db_session).get("option", {}) if user else {}
    return {k: int(saved.get(k, 0)) for k in OPTION_KEYS}


@register(137)  # GET /user/option
def handle_user_option(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userOption=_user_option(user, db_session))


@register(138)  # POST /user/option/update {isNoticeAp, isNoticeHelp, isNoticeEvent}; the client parses userOption
def handle_user_option_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    if user:
        with gstate.State(user, db_session) as st:
            st["option"] = {k: int(request_data.get(k, 0)) for k in OPTION_KEYS}
    return build_response(user, userOption=_user_option(user, db_session))


@register(140)  # GET /user/link
def handle_user_link(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, linkInfos=[])


# ---------------------------------------------------------------------------
# User data handler
# ---------------------------------------------------------------------------
@register(1)  # GET /user
def handle_user(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # verifyResponse case 1 parses userData.{user, userPoint, userDetail, stageResumption} and
    # userPopUp.isPopBenefitStone, nothing else
    return build_response(user,
        userData={
            "user": _user_obj(user),
            "userDetail": _user_detail(user),
            "userPoint": _user_point(user),
            "stageResumption": _stage_resumption(user, db_session),
        },
        userPopUp={"isPopBenefitStone": 0},
    )


@register(2)  # GET /user/start
def handle_user_start(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user)


@register(5)  # GET /user/chat
def handle_user_chat(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # UserChat::parse: the party chat service (chat.py). userToken goes back as X-HTTP-USER-TOKEN on every chat
    # call; userEndpointUrl is the base of its /user... calls; stampIds = the stickers the player owns.
    from . import chat as gchat
    uid = user.id if user else 1
    return build_response(user,
        userData={
            "userChat": {
                "userId": uid,
                "tagName": gchat.tag_name(uid),
                "userEndpointUrl": gchat.BASE,
                "stampIds": gchat.stamp_ids(),
            },
        },
        authToken="server_auth_token",
        userToken=gchat.token(uid),
    )


@register(23)  # GET /system/need/url
def handle_need_url(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    base = "http://api.sp.kingdomhearts.com"
    return build_response(user,
        support=base, register=base, update=base, help=base,
        staff=base, agreement=f"{base}/agreement", license=f"{base}/agreement",
        shikin=base, tokutei=base, store=base,
    )


@register(22)  # GET /payment/info (opened by the Jewels button)
def handle_payment_info(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # verifyResponse case 22: PaymentInfo::parse (paymentInfo {cesaLimitAge, chargeMoneyThisMonth,
    # lastchargeMoneyThisMonth}, all ints) then SystemNeedUrl::parse (same keys as action 23).
    # No real money on the private server: nothing charged; cesaLimitAge 20 = adult bracket (misc COPPA_ADULT_AGE).
    base = "http://api.sp.kingdomhearts.com"
    return build_response(user,
        paymentInfo={"cesaLimitAge": 20, "chargeMoneyThisMonth": 0, "lastchargeMoneyThisMonth": 0},
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
            # 907 != 0 skips the birthday input of a new account (SceneBirthRegister::changeSceneLayer);
            # KHUX_MISC_907=0 shows it (to test the birthday popup)
            Misc.COPPA_UNKNOWN_907: int(os.environ.get("KHUX_MISC_907", "30")),
        },
    )


@register(25)  # GET /system/master
def handle_master(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    base_url = "http://api.sp.kingdomhearts.com/data/master"
    master_rev = MASTER_REV
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


def _prehash_resources():
    try:
        data_dir = os.environ.get("KHUX_DATA_DIR", "")
        repo_dir = os.environ.get("KHUX_REPO_DIR", "")
        misc_mp4 = os.path.join(data_dir, "misc.mp4") if data_dir else ""
        misc_png = os.path.join(repo_dir, "validate_data", "misc.png") if repo_dir else ""
        if misc_mp4:
            _hash_resource_chunks(misc_mp4, RESOURCE_CHUNK_SIZE)
        if misc_png:
            _hash_resource(misc_png)
    except Exception:
        logger.exception("resource hashing failed")
    finally:
        _resource_md5_ready.set()            # /system/resource must not wait forever


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
    # ResourceInfo::init ignores each entry's "revision": the client numbers the entries minVersion,
    # minVersion+1, ... and saves minVersion + len(versions) - 1 as its resource revision. That must equal
    # Ret.versionRes, otherwise DataDownloader sees a mismatch and downloads everything again next launch.
    version_res = build_ret(user)["versionRes"]
    return build_response(user,
        resource={
            "mode": 1,
            "minVersion": max(0, version_res - len(versions) + 1),
            "versions": versions,
        },
    )


@register(61)  # POST /tutorial/user/create
def handle_tutorial_user_create(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    if user and not user.tutorial_done:
        db_session.add(user)
    is_new = True
    progression = 0
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
        phase=user.tutorial_phase if user else 50,
        popupFlag=0,
        isFinished=_tutorial_finished(user),
    )


@register(28)  # GET /system/information/list
def handle_information_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # SystemInformationList::parse reads only a top-level viewUrl (the 1.0.1 client never calls this action)
    return build_response(user, viewUrl="http://api.sp.kingdomhearts.com/information/list")


@register(29)  # GET /system/information/list/151203
def handle_information_popups(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # Only popUpViewUrl is parsed: the notice pages the client opens as WebView popups at startup. Must not be
    # empty once the tutorial is past phase 710: SceneNotice::init then calls openNextPage() during its own
    # init, and with no pages the completion moves to MyPage (changeSceneLayer) while the notice layer is still
    # being created -> NULL layer -> crash in EventDispatcher::pauseEventListenersForTarget. The live server
    # always had a notice popup at login.
    popups = [f"http://api.sp.kingdomhearts.com/information/detail/{NOTICES[0]['id']}"] if NOTICES else []
    return build_response(user, popUpViewUrl=popups)


@register(30)  # GET /system/information/detail
def handle_information_detail(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # verifyResponse case 30 reads a top-level infoBody string (the 1.0.1 client never calls this action)
    return build_response(user, infoBody="")


@register(131)  # GET /campaign
def handle_campaign(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # the running evCampaign ids (APIManager+764): the client shows them and applies AP / Lux / drop boosts
    return build_response(user, campaigns=[r["campaignId"] for r in gevents.active_campaigns()])


# ---------------------------------------------------------------------------
# Avatar Boards ("sphere" boards). Records, grid and node layout: see state.py "avatar boards".
# ---------------------------------------------------------------------------
def _as_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _user_sphere(boards: list) -> dict:
    """userSphere for UserSphere::parse: userSphereDatas[] + notChargedSphereBoardIds[] (read when the parse is
    called with a3 = 0: actions 9 and 42). What "not charged" tracked is unknown (no reader found in the
    v1.0.1 client); it is always empty."""
    return {"userSphereDatas": boards, "notChargedSphereBoardIds": []}


def _spend_jewels(user: Optional[User], cost: int) -> bool:
    """Take `cost` Jewels, free ones first (as /keyblade/burst/max). False (nothing taken) when short."""
    if not user:
        return False
    free, paid = user.free_stone or 0, user.pay_stone or 0
    if free + paid < cost:
        return False
    take = min(free, cost)
    user.free_stone, user.pay_stone = free - take, paid - (cost - take)
    return True


# sphereMasu.rewardSelect values that are not item types (SphereUI::openPopUpcommon texts): 0 skill
# (TextData 103400044 "Skill"; also a medal node with medalCategory != 0, SphereUI::load_board), 12 Max HP
# (103400017 "Max HP increased by %d!"), 21 Max AP (103400018), 22 Keyblade cost capacity (103400019). The rest
# are item types: 3 medal, 5 material, 7 title, 13 keyblade, 18 / 23 avatar set, 19 / 20 avatar parts.
_MASU_SKILL, _MASU_MAX_HP, _MASU_MAX_AP, _MASU_DECK_COST = 0, 12, 21, 22


def _apply_masu_reward(user: Optional[User], st: dict, masu: dict, idx: int) -> list:
    """Grant node idx (0-based) of a board's sphereMasu row. Returns new medals."""
    def col(name):
        values = masu.get(name) or []
        return values[idx] if 0 <= idx < len(values) else 0
    kind, rid, value = col("rewardSelect"), col("rewardId"), col("rewardValue")
    if kind == gstate.ITEM_MEDAL and col("medalCategory"):
        kind = _MASU_SKILL
    logger.info("  NODE %d: reward %s id=%s value=%s", idx + 1, kind, rid, value)
    if kind == _MASU_MAX_HP:
        if user:
            user.hp_prize = (user.hp_prize or 0) + value
    elif kind == _MASU_MAX_AP:
        if user:
            user.ap_prize = (user.ap_prize or 0) + value
    elif kind == _MASU_DECK_COST:
        if user:
            user.deck_cost_prize = (user.deck_cost_prize or 0) + value
    elif kind == _MASU_SKILL:
        if rid:
            logger.warning("  skill node (skill %s) not granted: no skill store yet", rid)
    else:
        return _grant(user, st, kind, rid, max(value, 1))
    return []


@register(57)  # POST /user/sphere/check
def handle_sphere_check(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {checkType} (APIManager::executeUserSphereCheck(SphereLockType)): 1 from the map / result screen
    # once the Avatar Board tutorial (tutorialMisc 8) applies, 3 after battle results and other screens.
    # verifyResponse case 57 (LABEL_579) reads checkType back from the REQUEST; for checkType >= 3 it first needs
    # closeEventSphereBoardIds[] (sub_4C0E78: UserSphere::removeSphere each). Then UserSphere::parse(doc, 1)
    # (userSphere.userSphereDatas, no notChargedSphereBoardIds) - each record is setSphere'd into the owned map
    # and its sphereBoardId added to AppState's NEW board ids (sub_4C17D4). So: send only boards granted now.
    check_type = _as_int(request_data.get("checkType"), 1)
    with gstate.State(user, db_session) as st:
        closed = gstate.close_spheres(st) if check_type >= 3 else []
        added = gstate.sync_spheres(st, _lux_rank(user))
        added = [dict(b, unlockMasuIds=list(b["unlockMasuIds"])) for b in added]
    if added or closed:
        logger.info("SPHERE CHECK %s: new %s closed %s", check_type, [b["sphereBoardId"] for b in added], closed)
    return build_response(user,
        checkType=check_type,
        closeEventSphereBoardIds=closed,
        notChargedSphereBoardIds=[],
        userSphere=_user_sphere(added),
    )


@register(42)  # POST /user/sphere/update
def handle_sphere_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {sphereBoardId, releaseMasuId} (APIManager::executeUserSphereUpdate sends only the first node of
    # its set; SphereUI::sphereUpdateIncentive opens one node per call). releaseMasuId is the node number from
    # the grid (1..22). The client has already taken the cost from its coin count (SphereUI::DecPoint).
    # verifyResponse case 42 (LABEL_302) needs, and fails without: userData.userPoint, userData.userDetail,
    # userSphere (parse a3 = 0, records merged with setSphere), userMaterials, userMedals, userSkills,
    # userKeyblades, userAvatarParts, userTitles - each list then goes through APIManager::updateMaterial /
    # updateMedal / updateSkill / updateKeyblade / updateAvatarPart / updateTitle (upserts, sub_4C0F1A), so only
    # new medals, parts and titles are sent.
    board_id = _as_int(request_data.get("sphereBoardId"))
    node = _as_int(request_data.get("releaseMasuId"))
    new_medals = []
    with gstate.State(user, db_session) as st:
        parts_before = {p["userAvatarPartsId"] for p in st.get("avatar_parts", [])}
        title_mark = gstate.title_mark(st)
        rec = st["spheres"].get(str(board_id))
        row = gstate.sphere_row(board_id)
        masu = gstate.sphere_masu(row)
        coin = gstate.SPHERE_COIN.get((row or {}).get("type"))
        refused, cost, have = None, 0, 0
        if not (rec and row and masu and coin):
            refused = "board not owned / unknown"
        elif row.get("type") == gstate.SPHERE_BUY_TYPE and not rec.get("isBuy"):
            refused = "board not bought"
        elif node not in gstate.sphere_nodes(row):
            refused = "node not on the board"
        elif node in rec["unlockMasuIds"]:
            refused = "node already open"
        else:
            costs = masu.get("spherePoint") or []
            cost = max(costs[node - 1], 0) if node - 1 < len(costs) else 0
            have = (getattr(user, coin) or 0) if user else 0
            if have < cost:
                refused = "needs %d %s, has %d" % (cost, coin, have)
        if refused:
            logger.warning("SPHERE UPDATE refused: board %s node %s: %s", board_id, node, refused)
        else:
            if user:
                setattr(user, coin, have - cost)
            rec["unlockMasuIds"].append(node)
            rec["status"] = gstate.SPHERE_STARTED
            logger.info("SPHERE UPDATE: board %s node %s (-%d %s)", board_id, node, cost, coin)
            new_medals += _apply_masu_reward(user, st, masu, node - 1)
            if gstate.sphere_nodes(row) <= set(rec["unlockMasuIds"]):
                # every grid node open: the board's completion reward is node 23 (no cost)
                rec["status"] = gstate.SPHERE_COMPLETE
                logger.info("SPHERE COMPLETE: board %s", board_id)
                new_medals += _apply_masu_reward(user, st, masu, gstate.SPHERE_COMPLETE_MASU - 1)
        boards = [dict(rec, unlockMasuIds=list(rec["unlockMasuIds"]))] if rec else []
        materials = gstate.materials_list(st)
        keyblades = st["keyblades"]
        new_parts = [p for p in _avatar_parts(st) if p["userAvatarPartsId"] not in parts_before]
        new_titles = gstate.titles_since(st, title_mark)
    if user:
        db_session.add(user)
    return build_response(user,
        userData={"userPoint": _user_point(user), "userDetail": _user_detail(user)},
        userSphere=_user_sphere(boards),
        userMaterials=materials, userMedals=new_medals, userSkills=[], userKeyblades=keyblades,
        userAvatarParts=new_parts, userTitles=new_titles,
    )


@register(68)  # POST /user/sphere/buy
def handle_sphere_buy(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # request {sphereBoardId} (APIManager::executeUserSphereBuy, from SceneSphereBoardSelect::openBoardBuyDialog
    # for a listed type-2 board with isBuy 0; price = sphere.price Jewels, shown on the board row).
    # verifyResponse case 68 (LABEL_666) -> 69: UserStone::parse, then userSphere = ONE Sphere object
    # (Sphere::init; setSphere'd into the owned map when it parses), then UserDetail::parse + UserStone::parse
    # (both required).
    board_id = _as_int(request_data.get("sphereBoardId"))
    with gstate.State(user, db_session) as st:
        rec = st["spheres"].get(str(board_id))
        row = gstate.sphere_row(board_id)
        if not row or row.get("type") != gstate.SPHERE_BUY_TYPE:
            logger.warning("SPHERE BUY refused: %s is not a Jewel board", board_id)
        elif rec and rec.get("isBuy"):
            logger.info("SPHERE BUY: %s already bought", board_id)
        elif rec is None and not gstate.board_available(row, _lux_rank(user), gstate.now()):
            logger.warning("SPHERE BUY refused: %s is not on sale", board_id)
        elif not _spend_jewels(user, max(row.get("price", 0), 0)):
            logger.warning("SPHERE BUY refused: %s costs %s Jewels", board_id, row.get("price"))
        else:
            if rec is None:
                rec = gstate.new_sphere(st, row, True)
            rec["isBuy"] = 1
            logger.info("SPHERE BUY: %s (-%s Jewels)", board_id, row.get("price"))
        board = dict(rec, unlockMasuIds=list(rec["unlockMasuIds"])) if rec else None
    if user:
        db_session.add(user)
    extra = {"userSphere": board} if board else {}
    return build_response(user, userStone=_user_stone(user), userData={"userDetail": _user_detail(user)}, **extra)


def _ticker_texts() -> list:
    """Main-menu marquee: MypageInfo::AdminText {type, priority, text} from data/ticker.json."""
    import json
    path = os.path.join(os.path.dirname(__file__), "..", "data", "ticker.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)["texts"]
    except (OSError, ValueError, KeyError):
        return []


@register(56)  # GET /mypage
def handle_mypage(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user,
        adminMypageTexts=_ticker_texts(),
        # running events with a MyPage banner (OpenBanner type 1 = eventStageId; tapping opens the event)
        openBanners=[{"type": 1, "id": r["eventStageId"], "limitDate": gparty.fmt_local(end - timedelta(seconds=1))}
                     for cat in (2, 1) for r, _, end, lock in gevents.active(cat) if r.get("mypageBanner") and not lock],
        userPresentCount=len(gstate.load(user, db_session).get("presents", [])) if user else 0,
        isChangeCoordinate=0,
        # a flag per ranking with an undelivered result: MyPage then calls 130 for it and shows the popups
        rankingRewards=_ranking_flags(user, db_session),
        # the dated seasonal backgrounds (151211 Christmas 2015, 160111 New Year 2016, ...) have no art
        # (lwf/home/<id>) in our archive and would crash SceneMyPage::initField; only 150911 does
        backgroundId=150911,
        isNewAlbumChallenge=0,
    )


# --------------------------------------------------------------------------- Colosseum (114-118, 127/128)
# Shapes from verifyResponse cases 114-118 and their parsers (Colosseum::parse, ColosseumStart::parse,
# ColosseumClear::parse); progress rules in colosseum.py.

@register(114)  # GET /colosseum
def handle_colosseum(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # Colosseum::parse(doc, 0): colosseumInfo, colosseumStages[] {rank, stageCount, stageId, useAp}, userColosseum.
    # The stage list is shown only with status 1; a bad element fails the whole parse.
    with gstate.State(user, db_session) as st:
        rec = gcol.progress(st)
        stages = gcol.next_stage(rec)
        uc = gcol.user_colosseum(rec)
    return build_response(user, colosseumInfo=gcol.info(), colosseumStages=stages, userColosseum=uc)


@register(115)  # GET /colosseum/reward/list
def handle_colosseum_reward_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # ranks (rounds) whose completion reward was already given: the reward screen marks them cleared
    with gstate.State(user, db_session) as st:
        got = sorted(gcol.progress(st)["rewardRanks"])
    return build_response(user, getRewardRankIds=got)


@register(116)  # POST /colosseum/start {rank, stageCount, stageId, userKeybladeId}
def handle_colosseum_start(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # UserPoint + Colosseum::parse(doc, 1) (info + userColosseum) + ColosseumStart::parse (userTreasures[],
    # startColosseumData echo, campaigns[]). The client loads startColosseumData.stageId and echoes rank /
    # stageCount / stageId back in /colosseum/clear, so echo the request.
    logger.info("COLOSSEUM START: %s", request_data)
    start = {"rank": int(request_data.get("rank", 1)), "stageCount": int(request_data.get("stageCount", 1)),
             "stageId": int(request_data.get("stageId", 0)), "userKeybladeId": int(request_data.get("userKeybladeId", 1))}
    with gstate.State(user, db_session) as st:
        rec = gcol.progress(st)
        rec["pending"] = start
        st["stage_keyblade"] = start["userKeybladeId"]
        st.pop("stage_drops", None)
        uc = gcol.user_colosseum(rec)
    return build_response(user, userData={"userPoint": _user_point(user)},
                          colosseumInfo=gcol.info(), userColosseum=uc,
                          userTreasures=[], startColosseumData=start, campaigns=[])


@register(117)  # POST /colosseum/retire {burst}
def handle_colosseum_retire(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # same code as /stage/retire (case 104): userKeyblades[] + userData.stageResumption; progress unchanged
    logger.info("COLOSSEUM RETIRE: %s", request_data)
    with gstate.State(user, db_session) as st:
        _store_burst(st, request_data.get("burst"))
        gcol.progress(st)["pending"] = None
        keyblades = st["keyblades"]
    return build_response(user, userKeyblades=keyblades, userData={"stageResumption": _stage_resumption(user, db_session)})


@register(118)  # POST /colosseum/clear
def handle_colosseum_clear(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # UserPoint + UserDetail + ColosseumClear::parse (clearColosseums[] {rank, stageCount} - never empty: the
    # result screen reads its last element unchecked - then userMaterials/Medals/Skills/Titles/Keyblades) +
    # StageResumption. Rewards: the rank's per-stage reward, and its completion reward once.
    logger.info("COLOSSEUM CLEAR: %s", request_data)
    is_skip = bool(request_data.get("isSkip"))
    new_medals = []
    with gstate.State(user, db_session) as st:
        title_mark = gstate.title_mark(st)
        rec = gcol.progress(st)
        rec["pending"] = None
        cleared, stage_rewards, rank_rewards = gcol.clear(rec, request_data.get("stageCount"), is_skip,
                                                          rank_cleared=request_data.get("rank"))
        logger.info("  credited %s round(s) %s%s -> now rank %s count %s%s", len(cleared), cleared,
                    " (one-turn win: skip)" if is_skip else "", rec["rank"], rec["stageCount"],
                    f", rounds unlocked up to {rec['skip_to']}" if rec.get("skip_to") else "")
        for stage_reward in stage_rewards:           # skipped rounds pay their coins too (wiki)
            new_medals += _grant(user, st, stage_reward["stageRewardType"], stage_reward["stageRewardId"],
                                 stage_reward["stageRewardNum"])
        for rank_reward in rank_rewards:
            for k in range(rank_reward.get("validReward", 0)):
                new_medals += _grant(user, st, rank_reward["rewardType"][k], rank_reward["rewardId"][k],
                                     rank_reward["rewardNum"][k])
        _store_burst(st, request_data.get("burst"))
        new_titles = gstate.titles_since(st, title_mark)
        materials = gstate.materials_list(st)
        rec_rank, rec_count = rec["rank"], max(rec["stageCount"], 1)
    if user:
        _add_lux(user, int(request_data.get("lux", 0)))      # GUESS: C5
        db_session.add(user)
    return build_response(user,
        userData={"userPoint": _user_point(user), "userDetail": _user_detail(user),
                  "stageResumption": _stage_resumption(user, db_session)},
        clearColosseums=cleared or [{"rank": rec_rank, "stageCount": rec_count}],
        userMaterials=materials, userMedals=new_medals, userSkills=[], userTitles=new_titles,
        userKeyblades=_user_keyblades(user, db_session))


def _ranking_close(db_session: DBSession) -> None:
    """Close finished ranking periods (once each) and file every participant's result in their state."""
    def sink(uid, result):
        o = db_session.get(User, uid)
        if o:
            with gstate.State(o, db_session) as st:
                st.setdefault("ranking_results", []).append(result)
            logger.info("RANKING RESULT: user %s %s", uid, result)
    granking.close_due(db_session, sink)


def _ranking_flags(user: Optional[User], db_session: DBSession) -> dict:
    """MypageInfo.rankingRewards: 1 for each category with a pending result; pending -> announced (only
    announced results are paid in 130, so SceneRanking's own 130 calls - which show no popup - pay nothing)."""
    flags = {k: 0 for k in ("rankingColosseum", "rankingParty", "rankingLuxWeekly", "rankingLuxMonthly",
                            "rankingLux")}
    if not user:
        return flags
    _ranking_close(db_session)
    with gstate.State(user, db_session) as st:
        for r in st.get("ranking_results", []):
            if r["status"] in ("pending", "announced"):
                flags[granking.FLAG_OF_CATEGORY[r["category"]]] = 1
                r["status"] = "announced"
    return flags


@register(130)  # GET /ranking/reward/check {type}
def handle_ranking_reward_check(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # RankingReward::parse (0x4AD04C): lastRankingResults[] {lastRankingId, lastRank, lastUnionRank} (one popup
    # each; the client picks the reward row from master data itself), rankingRewardIds[] (no reader),
    # openRankingIds[] (the ranking open now: Party title dates, the reward-list button). verifyResponse case 130
    # then reads "rankingReward": [] = nothing, else an object with userMedals / userSkills / userAvatarParts /
    # userMaterials / userKeyblades / userTitles (+ userData.userPoint) - the items granted NOW, exactly the row
    # the popup shows. type: 1 Lux weekly/monthly, 2 Party, 3 Coliseum, 4 Lux.
    rtype = int(request_data.get("type", 0) or 0)
    cats = granking.TYPE_CATEGORIES.get(rtype, ())
    results, reward_ids, granted = [], [], None
    if user:
        _ranking_close(db_session)
        with gstate.State(user, db_session) as st:
            title_mark = gstate.title_mark(st)
            parts_before = {p["userAvatarPartsId"] for p in st.get("avatar_parts", [])}
            medals = []
            for r in st.get("ranking_results", []):
                if r["category"] not in cats or r["status"] != "announced":
                    continue
                r["status"] = "claimed"
                results.append({"lastRankingId": r["rankingId"], "lastRank": r["rank"],
                                "lastUnionRank": r["unionRank"]})
                if r.get("rewardId"):
                    reward_ids.append(r["rewardId"])
                    for rtype_, rid, num, _skt, _ski, _skl in granking.reward_items(r["rewardId"]):
                        medals += _grant(user, st, rtype_, rid, num)     # medal preset skills: not modelled
            if results:
                granted = {"userMedals": medals, "userSkills": [], "userMaterials": [], "userKeyblades": [],
                           "userAvatarParts": [p for p in _avatar_parts(st)
                                               if p["userAvatarPartsId"] not in parts_before],
                           "userTitles": gstate.titles_since(st, title_mark)}
        if results:
            db_session.add(user)
            granted["userData"] = {"userPoint": _user_point(user)}
            logger.info("RANKING REWARD: type %s -> %s (reward rows %s)", rtype, results, reward_ids)
    return build_response(user, lastRankingResults=results, rankingRewardIds=reward_ids,
                          openRankingIds=granking.open_ranking_ids(rtype), rankingReward=granted or [])


def _colosseum_ranking(user: Optional[User], db_session: DBSession, key: str) -> dict:
    # ColosseumRanking::parse(doc, key): rankingDatas[] {userData {user, userDetail}, userAvatar, userColosseum,
    # arrivalTime, rank}, rankingStatus (2 = rows shown), rankingTermStart/End. Order (wiki/guides 2016): "based
    # on what round and tier you completed, and when you completed it" - tier, then round, then earliest.
    # This server's players only (GUESS: C7); "Own" = the 5 places around the player.
    import json as _json
    from .models import UserState
    s = gcol.season() or {}
    mkey = gcol.month_key(gcol.current_season())
    rows = []
    for us in db_session.query(UserState).all():
        try:
            rec = (_json.loads(us.data or "{}").get("colosseum") or {}).get(mkey)
        except ValueError:
            rec = None
        if rec and rec.get("total"):
            rows.append((us.user_id, rec))
    rows.sort(key=lambda r: (-r[1]["rank"], -r[1]["stageCount"], r[1].get("reached") or "9999"))
    if key.endswith("Own") and user:
        idx = next((i for i, r in enumerate(rows) if r[0] == user.id), None)
        rows = rows[max(0, idx - 5):idx + 6] if idx is not None else []
        base = idx - min(idx, 5) if idx is not None else 0
    else:
        rows, base = rows[:100], 0
    datas = []
    for i, (uid, rec) in enumerate(rows):
        o = db_session.get(User, uid)
        if o:
            datas.append({"userData": {"user": _user_obj(o), "userDetail": _user_detail(o)},
                          "userAvatar": _user_avatar(o), "userColosseum": gcol.user_colosseum(rec),
                          "arrivalTime": rec.get("reached") or "2000-01-01 00:00:00", "rank": base + i + 1})
    return {key: {"rankingDatas": datas, "rankingStatus": 2,
                  # this month's season (monthly rotation, C2), not the master's 2015 dates
                  "rankingTermStart": gparty.fmt_local(_month()[0]),
                  "rankingTermEnd": gparty.fmt_local(_month()[1])}}


@register(127)  # GET /ranking/colosseum
def handle_ranking_colosseum(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, **_colosseum_ranking(user, db_session, "colosseumRanking"))


@register(128)  # GET /ranking/colosseum/own
def handle_ranking_colosseum_own(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, **_colosseum_ranking(user, db_session, "colosseumRankingOwn"))


# --------------------------------------------------------------------------- single-player batch
# Contracts from verifyResponse (checked against the disassembly) and the execute* builders; guesses in GUESSES.md.

@register(3)  # GET /user/detail {userId}: another player's detail (support / member list taps)
def handle_user_detail(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # UserDetail::parse into its own slot (APIManager+804). Only this server's players exist: look them up.
    target = db_session.get(User, int(request_data.get("userId", 0) or 0)) or user
    return build_response(user, userData={"userDetail": _user_detail(target)})


@register(15)  # GET /user/album
def handle_user_album(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # UserAlbum::parse: userAlbum {medalIds [int], allMedalCount int}; UserAlbumChallenge::parse:
    # userAlbumChallenge [] (no challenge data; the 1.0.1 challenge popup has no caller).
    # GUESS: A1 (medals ever owned), A2 (allMedalCount = medal master rows)
    from .master import MASTER_JSON_DATA
    ids = [int(x) for x in gstate.load(user, db_session).get("album", [])] if user else []
    return build_response(user, userAlbum={"medalIds": ids,
                                           "allMedalCount": len(MASTER_JSON_DATA.get("medal", [])) or 1},
                          userAlbumChallenge=[])


def _bonus_day(offset_days: int = 0) -> str:
    # the day turns over at 12:00 SERVER LOCAL time (user, 2026-10-14; the wiki's "11:00 UTC" was just the EN
    # server's own clock); offset_days -1 = the previous server day
    return time.strftime("%Y-%m-%d", time.localtime(time.time() - 12 * 3600 + offset_days * 86400))


def _login_rows(bonus_type: int) -> list:
    from .master import MASTER_JSON_DATA
    return sorted((r for r in MASTER_JSON_DATA.get("loginBonus", []) if r.get("bonusType") == bonus_type),
                  key=lambda r: r["day"])


@register(60)  # POST /login/bonus {}
def handle_login_bonus(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # LoginBonus::parse: loginBonus {continue {loginBonusId, dayCount}, total {loginBonusId, dayCount},
    # specials [int]}. continue.loginBonusId must be a bonusType-1 row (day 1-5): SceneLoginBonus indexes its
    # panel with that row's day. The response carries no user data, so rewards go to the present box (GUESS: L3).
    # bonusType 1 = the 5-day login bonus (50/50/100/100/200 Jewels) that REPEATS after day 5 (user, from old
    # videos, 2026-10-14; 2016 guides agree): 500 a cycle, six cycles = the 3000 Jewels a month the user remembers.
    # It is a streak: a missed day starts it again at day 1 (user, O7). bonusType 2 = lifetime total login days
    # (milestones day 1..1850), never reset.
    welcome_rows, total_rows = _login_rows(1), _login_rows(2)
    today = _bonus_day()
    with gstate.State(user, db_session) as st:
        lb = st.setdefault("loginbonus", {"last_day": "", "total": 0})
        lb.setdefault("welcome", min(lb.pop("streak", 0), 5))   # records from the first (repeating-streak) version
        first_today = lb["last_day"] != today
        grants = []
        if first_today:
            yesterday = _bonus_day(-1)
            in_a_row = lb["last_day"] == yesterday
            lb["last_day"] = today
            lb["total"] += 1
            lb["run"] = lb.get("run", 0) + 1 if in_a_row else 1        # consecutive days (continueLoginCount)
            lb["welcome"] = lb["welcome"] % len(welcome_rows) + 1 if in_a_row else 1
            grants.append(welcome_rows[lb["welcome"] - 1])
            if user:
                user.continue_login_count = lb["run"]
                db_session.add(user)
        total = lb["total"]
        cont = welcome_rows[max(lb["welcome"], 1) - 1]
        reached = next((r for r in total_rows if r["day"] == total), None)
        upcoming = next((r for r in total_rows if r["day"] > total), None)
        total_id = (reached or upcoming or {"loginBonusId": 0})["loginBonusId"]   # GUESS: L4
        if first_today and reached:
            grants.append(reached)
        for row in grants:
            add_present(st, row["rewardType"], row["rewardId"], row["rewardNum"], "Login Bonus")
        if first_today:
            logger.info("LOGIN BONUS: welcome %s/%s, total %s, granted %s", lb["welcome"], len(welcome_rows), total,
                        [r["loginBonusId"] for r in grants])
        welcome = lb["welcome"]
    # GUESS: L5 - specials (bonusType 3/4) are date-gated by 2015-16 dates: none active
    return build_response(user, loginBonus={"continue": {"loginBonusId": cont["loginBonusId"], "dayCount": welcome},
                                            "total": {"loginBonusId": total_id, "dayCount": total},
                                            "specials": []})


@register(66)  # POST /shop/medal/max: medal box +5 for Jewels
def handle_shop_medal_max(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # UserDetail (userData.userDetail) + UserStone. The client's own rules: cost misc 111 (100 Jewels), +misc 103
    # (5) slots, cap misc 104 (500); it refuses on its side when capped or short.
    if user:
        step, cap, cost = _misc(103, 5), _misc(104, 500), _misc(111, 100)
        cur = _max_medal(user)
        if cur + step <= cap and _spend_jewels(user, cost):
            user.max_medal = cur + step
            logger.info("MEDAL BOX: %s -> %s (-%s Jewels)", cur, user.max_medal, cost)
        db_session.add(user)
    return build_response(user, userData={"userDetail": _user_detail(user)}, userStone=_user_stone(user))


@register(67)  # POST /shop/ap/recover
def handle_shop_ap_recover(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # UserPoint + UserStone + UserKeyblade (userKeyblades[] required). Price misc 112 (100 Jewels), charged as
    # the client shows it. GUESS: P1 - AP is ignored server-side, so the dialog should rarely appear.
    if user and _spend_jewels(user, _misc(112, 100)):
        logger.info("AP RECOVER: -%s Jewels", _misc(112, 100))
        db_session.add(user)
    return build_response(user, userData={"userPoint": _user_point(user, recovered=True)}, userStone=_user_stone(user),
                          userKeyblades=_user_keyblades(user, db_session))


@register(45)  # POST /user/support/update {supportMedalId}
def handle_user_support_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # medal detail popup -> "set as support medal". UserSupport::parse (supportUser) required.
    mid = int(request_data.get("supportMedalId", 0) or 0)
    with gstate.State(user, db_session) as st:
        if any(m["userMedalId"] == mid for m in st["medals"]):
            st["support_medal"] = mid
            logger.info("SUPPORT MEDAL: %s", mid)
    return build_response(user, supportUser=_support_user(user, db_session))


# Never sent by the 1.0.1 client (no caller of their execute* builders): correct-shape stubs only.
@register(12)  # GET /user/item: no case in verifyResponse
def handle_user_item(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user)


@register(8)  # GET /user/birthday
@register(40)  # POST /user/birthday/create {year, month}
def handle_user_birthday(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # UserBirthday::parse: birthday int YYYYMM
    y, m = int(request_data.get("year", 2000) or 2000), int(request_data.get("month", 1) or 1)
    return build_response(user, birthday=y * 100 + m)


@register(19)  # GET /user/avatar {targetUserId}
def handle_user_avatar(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    target = db_session.get(User, int(request_data.get("targetUserId", 0) or 0)) or user
    return build_response(user, userAvatar=_user_avatar(target))


@register(46)  # POST /medal/skill/update
def handle_medal_skill_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userMedals=[], userSkills=[])


@register(50)  # POST /skill/sell
def handle_skill_sell(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userData={"userPoint": _user_point(user)}, userMedals=[], sellUserSkillIds=[])


@register(55)  # POST /skill/evolve
def handle_skill_evolve(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userData={"userPoint": _user_point(user)}, userMedals=[], userSkills=[],
                          userSkillIds=[])


@register(144)  # POST /user/album/challenge/update {challengeId}
def handle_album_challenge_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, userAlbumChallenge=[], userMaterials=[], userMedals=[], userSkills=[],
                          userAvatarParts=[], userKeyblades=[], userTitles=[], userStone=_user_stone(user),
                          userData={"userPoint": _user_point(user), "userDetail": _user_detail(user)})


@register(143)  # PUT /system/uuid {accessToken, platformType}: account transfer; nothing parsed
def handle_system_uuid(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user)


# --------------------------------------------------------------------------- multiplayer: parties + rankings
# Shapes from verifyResponse (checked against the disassembly) and the parsers: Party::init, UserParty::parse
# (a userParty with partyId != 0 needs a top-level "party"), PartyEx {party, partyLeader}, Applicant, Offer,
# PartyMemberList (SupportUser + Detail), LuxRanking, PartyRanking. Rules: party.py; guesses PT* / RK* in
# GUESSES.md. Not sent by 1.0.1: 119-122.

def _party_notice(st: dict) -> dict:
    return st.setdefault("party_notice", {"offer": 0, "applicant": 0, "leader": 0, "newcomers": []})


def _notify(db_session: DBSession, uid: int, key: str, newcomer: Optional[dict] = None) -> None:
    """Raise a /party/notice flag for another player (offer / applicant / leader / newcomer)."""
    target = db_session.get(User, uid)
    if not target:
        return
    with gstate.State(target, db_session) as st:
        n = _party_notice(st)
        if newcomer:
            n["newcomers"] = (n["newcomers"] + [newcomer])[-10:]
        else:
            n[key] = 1


def _notify_staff(db_session: DBSession, p, key: str, newcomer: Optional[dict] = None, skip: int = 0) -> None:
    for uid in [p.leader_user_id] + gparty.admins(p):
        if uid and uid != skip:
            _notify(db_session, uid, key, newcomer)


def _member_entry(db_session: DBSession, uid: int, detail: bool = False) -> dict:
    """SupportUser for a player (+ the Detail fields PartyMemberList reads when getDetail was sent)."""
    o = db_session.get(User, uid)
    if o is None:
        return _sora_support(None, db_session)
    e = _support_entry(o.id, o.user_name or "Player", _lux_rank(o), _support_medal(o, db_session), _user_avatar(o), o)
    e.update(_user_titles(o))
    kbs = _user_keyblades(o, db_session)
    kb = next((k for k in kbs if k.get("isFavorite")), kbs[0] if kbs else None)
    e["keybladeId"] = kb["keybladeId"] if kb else 1000
    e["isParty"] = 1
    if detail:
        e.update({"userKeyblade": kb, "userRanking": {"lux": int(o.total_lux or 0), "rank": 0},
                  # SceneMyPage::updateFukidashi prints it raw as "Quest %d" (text 101000039), and the quest list
                  # numbers quests by the stage master's `id`, so send that (quest 215), not the stageId (7150)
                  "lastStageId": (gstate.stage_row(o.last_clear_stage_id) or {}).get("id", 0), "comment": o.comment or "", "linkPlatformId": ""})
    return e


def _after_join(db_session: DBSession, uid: int) -> None:
    """The first party a player ever joins (or creates) gives misc 117 (100) Jewels - ScenePartyTop's entry
    layout says so while userParty.flagFirstReward is 0 (text 103810026). They go to the present box: the invite
    popup for this reward says "Collect rewards from your present box!"."""
    o, m = db_session.get(User, uid), gparty.membership(db_session, uid)
    if not o or not m:
        return
    with gstate.State(o, db_session) as st:
        if not st.get("party_first_reward"):
            st["party_first_reward"] = 1
            add_present(st, 2, 0, _misc(117, 100), "First Party Bonus")
            logger.info("PARTY FIRST JOIN: user %s +%s Jewels", uid, _misc(117, 100))
    m.flag_first_reward = 1


def _party_ex(db_session: DBSession, p) -> dict:
    return {"party": gparty.party_obj(db_session, p), "partyLeader": _member_entry(db_session, p.leader_user_id)}


def _party_reply(user: Optional[User], db_session: DBSession, **extra) -> dict:
    db_session.flush()
    return build_response(user, **gparty.with_party(db_session, user.id if user else 0), **extra)


@register(78)  # GET /party {partyId (only when viewing another party)}
def handle_party(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    pid = int(request_data.get("partyId", 0) or 0)
    if pid:
        p = db_session.get(Party, pid)
        if p:
            return build_response(user, **_party_ex(db_session, p))
    return _party_reply(user, db_session)


@register(80)  # GET /party/member/list {getDetail?, platformType?}  (every MyPage load, with getDetail=1)
def handle_party_member_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    uid = user.id if user else 0
    pid = gparty.party_id_of(db_session, uid)
    # the Detail fields always: PartyMemberList::parse reads them when present and the screens after /party/create
    # call this without getDetail (they re-asked forever without them)
    detail = True
    extra = {}
    if pid:
        extra["partyUserList"] = [_member_entry(db_session, m.user_id, detail)
                                  for m in gparty.members(db_session, pid)]
    return _party_reply(user, db_session, **extra)


@register(74)  # POST /party/create {name, message, playStyle, agreeType}
def handle_party_create(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # userParty (+party) + firstReward. Creation is free (GUESS: PT4).
    if user:
        p = gparty.create(db_session, user, str(request_data.get("name", ""))[:14],
                          str(request_data.get("message", ""))[:20],
                          int(request_data.get("playStyle", 0) or 0), int(request_data.get("agreeType", 0) or 0))
        logger.info("PARTY CREATE: %s by user %s", p.id, user.id)
        _after_join(db_session, user.id)
    return _party_reply(user, db_session, firstReward=0)


@register(75)  # POST /party/update {name, message, playStyle, agreeType}: leader only
def handle_party_update(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    if user:
        gparty.update(db_session, user.id, str(request_data.get("name", ""))[:14],
                      str(request_data.get("message", ""))[:20],
                      int(request_data.get("playStyle", 0) or 0), int(request_data.get("agreeType", 0) or 0))
    return _party_reply(user, db_session)


@register(79)  # POST /party/leave {}
def handle_party_leave(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    if user:
        p = gparty.party_of(db_session, user.id)
        leader_before = p.leader_user_id if p else 0
        gparty.leave(db_session, user.id)
        p = db_session.get(Party, p.id) if p else None
        if p and p.leader_user_id != leader_before:
            _notify(db_session, p.leader_user_id, "leader")
    return _party_reply(user, db_session)


@register(76)  # GET /party/notice
def handle_party_notice(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # {hasNewOffer, isApply, hasNewApplicant, isNewLeader, newcomerUsers[{userName, userId, joinDate, message}]};
    # flags are cleared once read
    n = {"offer": 0, "applicant": 0, "leader": 0, "newcomers": []}
    is_apply = 0
    if user:
        gparty.expire(db_session)
        with gstate.State(user, db_session) as st:
            n = dict(_party_notice(st))
            st["party_notice"] = {"offer": 0, "applicant": 0, "leader": 0, "newcomers": []}
        is_apply = int(db_session.query(PartyApplication).filter(
            PartyApplication.user_id == user.id, PartyApplication.status == gparty.PENDING).count() > 0)
    return build_response(user, hasNewOffer=n["offer"], isApply=is_apply, hasNewApplicant=n["applicant"],
                          isNewLeader=n["leader"], newcomerUsers=n["newcomers"])


@register(77)  # POST /party/login {}
def handle_party_login(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # userParty; in a party also isAbsenceLeader (party.leader_absent) + partyLeader. Grants nothing (GUESS: PT9).
    p = gparty.party_of(db_session, user.id) if user else None
    if not p:
        return _party_reply(user, db_session)
    absent = int(gparty.leader_absent(db_session, p))
    return _party_reply(user, db_session, isAbsenceLeader=absent,
                        partyLeader=_member_entry(db_session, p.leader_user_id))


@register(81)  # GET /party/search/active {playStyle, rank, agreeType, memberCount}
def handle_party_search(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    mine = gparty.party_id_of(db_session, user.id) if user else 0
    q = {k: int(request_data.get(k, 0) or 0) for k in ("playStyle", "agreeType", "memberCount", "rank")}
    found = gparty.search(db_session, q["playStyle"], q["agreeType"], q["memberCount"], q["rank"], exclude_party=mine)
    return build_response(user, partyList=[_party_ex(db_session, p) for p in found])


@register(82)  # POST /party/application/160310 {partyId, message}
def handle_party_apply(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # userParty + failedStatus; when 0 also partyApplicant + firstReward
    if not user:
        return _party_reply(user, db_session, failedStatus=gparty.FAILED_FULL)
    failed, a = gparty.apply(db_session, user, int(request_data.get("partyId", 0) or 0),
                             str(request_data.get("message", ""))[:20])
    if failed:
        return _party_reply(user, db_session, failedStatus=failed)
    p = db_session.get(Party, a.party_id)
    if a.status == gparty.AGREED:
        _after_join(db_session, user.id)
        _notify_staff(db_session, p, "", {"userName": user.user_name or "Player", "userId": user.id,
                                          "joinDate": gparty.fmt(datetime.utcnow()), "message": a.message})
    else:
        _notify_staff(db_session, p, "applicant")
    return _party_reply(user, db_session, failedStatus=0, partyApplicant=gparty.applicant_obj(a), firstReward=0)


@register(83)  # GET /party/application/list: my applications + their parties
def handle_party_application_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    apps = db_session.query(PartyApplication).filter(PartyApplication.user_id == (user.id if user else 0),
                                                     PartyApplication.status == gparty.PENDING).all()
    parties = [p for p in (db_session.get(Party, a.party_id) for a in apps) if p]
    return build_response(user, partyApplicants=[gparty.applicant_obj(a) for a in apps],
                          partyList=[_party_ex(db_session, p) for p in parties])


def _application(request_data: dict, db_session: DBSession):
    return db_session.get(PartyApplication, int(request_data.get("partyApplicantId", 0) or 0))


@register(84)  # POST /party/application/cancel {partyApplicantId}
def handle_party_application_cancel(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    a = _application(request_data, db_session)
    if a and user and a.user_id == user.id and a.status == gparty.PENDING:
        a.status = gparty.CANCELLED
    a = a or PartyApplication(id=0, user_id=user.id if user else 0, party_id=0, status=gparty.CANCELLED)
    return build_response(user, partyApplicant=gparty.applicant_obj(a))


@register(85)  # GET /party/applicant/list: applications to my party (leader / admins)
def handle_party_applicant_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    p = gparty.party_of(db_session, user.id) if user else None
    apps = db_session.query(PartyApplication).filter(PartyApplication.party_id == p.id,
                                                     PartyApplication.status == gparty.PENDING).all() if p else []
    return build_response(user, partyApplicants=[gparty.applicant_obj(a) for a in apps],
                          partyUserList=[_member_entry(db_session, a.user_id) for a in apps])


@register(86)  # POST /party/applicant/agree {partyApplicantId}
def handle_party_applicant_agree(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    a = _application(request_data, db_session)
    p = gparty.party_of(db_session, user.id) if user else None
    if a and p and a.party_id == p.id and gparty.is_staff(p, user.id) and gparty.accept_application(db_session, a):
        _after_join(db_session, a.user_id)
        joined = db_session.get(User, a.user_id)
        _notify_staff(db_session, p, "", {"userName": joined.user_name if joined else "Player",
                                          "userId": a.user_id, "joinDate": gparty.fmt(datetime.utcnow()),
                                          "message": a.message or ""})
    a = a or PartyApplication(id=0, user_id=0, party_id=0, status=gparty.REJECTED)
    return _party_reply(user, db_session, partyApplicant=gparty.applicant_obj(a))


@register(87)  # POST /party/applicant/reject {partyApplicantId}
def handle_party_applicant_reject(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    a = _application(request_data, db_session)
    p = gparty.party_of(db_session, user.id) if user else None
    if a and p and a.party_id == p.id and gparty.is_staff(p, user.id) and a.status == gparty.PENDING:
        a.status = gparty.REJECTED
    a = a or PartyApplication(id=0, user_id=0, party_id=0, status=gparty.REJECTED)
    return build_response(user, partyApplicant=gparty.applicant_obj(a))


@register(92)  # GET /party/invite/search {level, playTimezones, playFrequently, earnLuxRank}
def handle_party_invite_search(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # players of this server not in a party (the filters are advisory; GUESS: PT12)
    me = user.id if user else 0
    found = [o for o in db_session.query(User).filter(User.id != me, User.tutorial_done.is_(True)).limit(200)
             if not gparty.membership(db_session, o.id)][:30]
    return build_response(user, partyUserList=[_member_entry(db_session, o.id) for o in found])


@register(93)  # POST /party/invite/offer/160310 {userId, message}: failedStatus only
def handle_party_invite_offer(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    p = gparty.party_of(db_session, user.id) if user else None
    target = int(request_data.get("userId", 0) or 0)
    failed = gparty.FAILED_FULL
    if p and gparty.is_staff(p, user.id) and db_session.get(User, target):
        failed = gparty.offer(db_session, p, target, str(request_data.get("message", ""))[:20])
        if not failed:
            _notify(db_session, target, "offer")
    return build_response(user, failedStatus=failed)


@register(94)  # GET /party/invite/list: offers my party sent
def handle_party_invite_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    p = gparty.party_of(db_session, user.id) if user else None
    offers = db_session.query(PartyOffer).filter(PartyOffer.party_id == p.id,
                                                 PartyOffer.status == gparty.PENDING).all() if p else []
    return build_response(user, partyOffers=[gparty.offer_obj(o) for o in offers],
                          partyUserList=[_member_entry(db_session, o.user_id) for o in offers])


def _offer(request_data: dict, db_session: DBSession):
    return db_session.get(PartyOffer, int(request_data.get("partyOfferId", 0) or 0))


@register(95)  # POST /party/invite/cancel {partyOfferId}
def handle_party_invite_cancel(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    o = _offer(request_data, db_session)
    p = gparty.party_of(db_session, user.id) if user else None
    if o and p and o.party_id == p.id and gparty.is_staff(p, user.id) and o.status == gparty.PENDING:
        o.status = gparty.CANCELLED
    o = o or PartyOffer(id=0, user_id=0, party_id=0, status=gparty.CANCELLED)
    return build_response(user, partyOffer=gparty.offer_obj(o))


@register(96)  # GET /party/offer/list: offers I received + their parties
def handle_party_offer_list(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    gparty.expire(db_session)
    offers = db_session.query(PartyOffer).filter(PartyOffer.user_id == (user.id if user else 0),
                                                 PartyOffer.status == gparty.PENDING).all()
    parties = [p for p in (db_session.get(Party, o.party_id) for o in offers) if p]
    return build_response(user, partyOffers=[gparty.offer_obj(o) for o in offers],
                          partyList=[_party_ex(db_session, p) for p in parties])


@register(97)  # POST /party/offer/agree {partyOfferId}
def handle_party_offer_agree(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    o = _offer(request_data, db_session)
    if o and user and o.user_id == user.id and gparty.accept_offer(db_session, o):
        _after_join(db_session, user.id)
        p = db_session.get(Party, o.party_id)
        _notify_staff(db_session, p, "", {"userName": user.user_name or "Player", "userId": user.id,
                                          "joinDate": gparty.fmt(datetime.utcnow()), "message": o.message or ""})
    o = o or PartyOffer(id=0, user_id=0, party_id=0, status=gparty.REJECTED)
    return _party_reply(user, db_session, partyOffer=gparty.offer_obj(o))


@register(98)  # POST /party/offer/reject {partyOfferId}
def handle_party_offer_reject(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    o = _offer(request_data, db_session)
    if o and user and o.user_id == user.id and o.status == gparty.PENDING:
        o.status = gparty.REJECTED
    o = o or PartyOffer(id=0, user_id=0, party_id=0, status=gparty.REJECTED)
    return build_response(user, partyOffer=gparty.offer_obj(o))


def _role_change(request_data: dict, user: Optional[User], db_session: DBSession, key: str, action) -> dict:
    """88-91: leader-only role changes (expel: leader or admin) (GUESS: PT7); reply userParty (+party)."""
    p = gparty.party_of(db_session, user.id) if user else None
    target = int(request_data.get(key, 0) or 0)
    tm = gparty.membership(db_session, target)
    if p and tm and tm.party_id == p.id and target != user.id:
        action(p, target)
    return _party_reply(user, db_session)


@register(88)  # POST /party/leader/change {appointId}
def handle_party_leader_change(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    def act(p, uid):
        if p.leader_user_id == user.id:
            gparty.set_leader(p, uid)
            _notify(db_session, uid, "leader")
    target = int(request_data.get("appointId", 0) or 0)
    p = gparty.party_of(db_session, user.id) if user else None
    if p and target == user.id and p.leader_user_id != user.id:
        # takeover from an absent leader (PartyLogin.isAbsenceLeader)
        if gparty.leader_absent(db_session, p):
            gparty.set_leader(p, user.id)
        return _party_reply(user, db_session)
    return _role_change(request_data, user, db_session, "appointId", act)


@register(89)  # POST /party/admin/appoint {appointId}
def handle_party_admin_appoint(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # admins may promote too ("even (oddly enough) promote other members to moderator status", 2016 guide)
    return _role_change(request_data, user, db_session, "appointId",
                        lambda p, uid: gparty.is_staff(p, user.id) and gparty.appoint(p, uid))


@register(90)  # POST /party/admin/dismiss {dismissId}
def handle_party_admin_dismiss(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return _role_change(request_data, user, db_session, "dismissId",
                        lambda p, uid: p.leader_user_id == user.id and gparty.dismiss(p, uid))


@register(91)  # POST /party/member/expel {expelId}
def handle_party_member_expel(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return _role_change(request_data, user, db_session, "expelId",
                        lambda p, uid: gparty.is_staff(p, user.id) and gparty.expel(db_session, p, uid))


# Rankings. Only this server's players; weeks from 08:00 server-local time on KHUX_WEEK_START (user; times go out as UTC). rankingStatus 2 = in progress
# (SceneRanking builds rows only for 2; 1 "preparing", 3 "tallying", 4 other). lastRank = the player's own place,
# shown as "your rank" (0 = unranked).
def _lux_ranking(user: Optional[User], db_session: DBSession, since, until, own: bool) -> dict:
    rows = gparty.ranked(gparty.lux_since(db_session, since, "user"))
    my_rank = next((r for k, _, r in rows if user and k == user.id), 0)
    if own and user:                                         # the window around the player (GUESS: RK5)
        idx = next((i for i, r in enumerate(rows) if r[0] == user.id), None)
        rows = rows[max(0, idx - 5):idx + 6] if idx is not None else []
    datas = []
    for uid, lux, rank in rows[:100]:
        o = db_session.get(User, uid)
        if o:
            datas.append({"userData": {"user": _user_obj(o), "userDetail": _user_detail(o)},
                          "userAvatar": _user_avatar(o), "lux": min(lux, 2**31 - 1), "rank": rank})
    return {"rankingDatas": datas, "rankingStatus": 2, "rankingTermStart": gparty.fmt_local(since),
            "rankingTermEnd": gparty.fmt_local(until), "lastRank": my_rank}


def _week():
    start = gparty.week_start()
    return start, start + timedelta(days=7, seconds=-1)


def _month():
    start = gparty.month_start()
    nxt = gparty.month_start((start + timedelta(days=32)).replace(day=1, hour=gparty.ROLLOVER_HOUR))
    return start, nxt - timedelta(seconds=1)


@register(123)  # GET /ranking/lux
def handle_ranking_lux(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, luxRanking=_lux_ranking(user, db_session, *_week(), own=False))


@register(124)  # GET /ranking/lux/own
def handle_ranking_lux_own(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, luxRanking=_lux_ranking(user, db_session, *_week(), own=True))


@register(119)  # GET /ranking/weekly/user (never sent by 1.0.1)
def handle_ranking_weekly(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, luxRankingWeekly=_lux_ranking(user, db_session, *_week(), own=False))


@register(120)  # GET /ranking/monthly/user (never sent by 1.0.1)
def handle_ranking_monthly(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, luxRankingMonthly=_lux_ranking(user, db_session, *_month(), own=False))


@register(121)  # GET /ranking/weekly/user/own (never sent by 1.0.1)
def handle_ranking_weekly_own(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, luxRankingWeeklyOwn=_lux_ranking(user, db_session, *_week(), own=True))


@register(122)  # GET /ranking/monthly/user/own (never sent by 1.0.1)
def handle_ranking_monthly_own(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, luxRankingMonthlyOwn=_lux_ranking(user, db_session, *_month(), own=True))


def _party_ranking(user: Optional[User], db_session: DBSession, own: bool) -> dict:
    start, end = _week()
    rows = gparty.ranked(gparty.lux_since(db_session, start, "party"))
    mine = gparty.party_id_of(db_session, user.id) if user else 0
    my_rank = next((r for k, _, r in rows if mine and k == mine), 0)
    if own and user:
        idx = next((i for i, r in enumerate(rows) if r[0] == mine), None)
        rows = rows[max(0, idx - 5):idx + 6] if idx is not None else []
    datas = []
    for pid, lux, rank in rows[:100]:
        p = db_session.get(Party, pid)
        if p:
            datas.append({"party": gparty.party_obj(db_session, p), "rank": rank, "lux": min(lux, 2**31 - 1)})
    return {"rankingDatas": datas, "rankingStatus": 2, "lastRank": my_rank,
            "updateTime": gparty.fmt(datetime.utcnow()), "nextUpdateTime": gparty.fmt_local(end)}


@register(125)  # GET /ranking/party
def handle_ranking_party(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, partyRanking=_party_ranking(user, db_session, own=False))


@register(126)  # GET /ranking/party/own
def handle_ranking_party_own(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, partyRankingOwn=_party_ranking(user, db_session, own=True))


@register(129)  # GET /ranking/parade: LAST week's union standings + each union's top player, once a week
def handle_ranking_parade(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # The startup chain shows SceneUnionRanking whenever rankingUnionResult is non-empty, else goes to MyPage
    # (sub_6FACEC). So: last week's final result, the first time the player starts the game in a new week; empty
    # afterwards and when nobody earned Lux last week. GUESS: RK8
    this_week, _ = _week()
    start, end = this_week - timedelta(days=7), this_week
    empty = build_response(user, unionParade={"rankingUnionResult": [], "rankingUnionTopRanker": []})
    week_key = gparty.fmt(this_week)
    if user:
        with gstate.State(user, db_session) as st:
            if st.get("parade_seen") == week_key:
                return empty
            st["parade_seen"] = week_key
    last = gparty.lux_between(db_session, start, end, "union")
    if not any(last.values()):
        return empty
    # all 5 unions, always: the parade's name_1..name_5 labels index the list unchecked (.at(4) threw with one)
    lux_by_union = {u: 0 for u in range(1, 6)}
    lux_by_union.update({u: v for u, v in last.items() if u in lux_by_union})
    unions = gparty.ranked(lux_by_union)
    users = gparty.lux_between(db_session, start, end, "user")
    # one top player per union, in union order: SceneParade draws all five podium avatars (1st..5th) and an
    # empty slot crashes in Avatar::updateLWFPath. A union nobody played for gets a placeholder (GUESS: RK7).
    tops = []
    for union_id, _, union_rank in unions:
        best = max(((uid, lux) for uid, lux in users.items()
                    if (db_session.get(User, uid) or User(union_id=-1)).union_id == union_id),
                   key=lambda t: t[1], default=None)
        o = db_session.get(User, best[0]) if best else None
        if o:
            kbs = _user_keyblades(o, db_session)
            tops.append({"userData": {"user": _user_obj(o)},
                         "userKeyblade": next((k for k in kbs if k.get("isFavorite")), kbs[0] if kbs else {}),
                         "userAvatar": _user_avatar(o), "rank": union_rank, "lux": min(best[1], 2**31 - 1)})
        else:
            tops.append(_parade_placeholder(union_id, union_rank))
    return build_response(user, unionParade={
        "rankingUnionResult": [{"unionId": u, "rank": r, "lux": lux} for u, lux, r in unions],
        "rankingUnionTopRanker": tops})


def _parade_placeholder(union_id: int, rank: int) -> dict:
    """A union top ranker for a union without players: no name, a starting avatar and keyblade, 0 Lux."""
    user = dict(_user_obj(None), userId=0, nativeUserId=0, userName="---", comment="")
    return {"userData": {"user": user},
            "userKeyblade": {"userKeybladeId": 0, "category": 0, "keybladeId": 1000, "deckMedals": [],
                             "burst": 0, "totalAttack": 0, "totalDefense": 0, "isFavorite": 1,
                             "getDatetime": "2015-09-01 00:00:00"},
            "userAvatar": {"myCoordinateNo": 1, "gender": 1, "hairPartsId": 40001,
                           "hairColorPartsId": 50001, "facePartsId": 20001, "bodyPartsId": 1,
                           "skinPartsId": 30001, "accessoriesPartsIds": []},
            "rank": rank, "lux": 0}


@register(139)  # GET /link/members {platformIds, platformType}: social-network friends - none here
def handle_link_members(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, linkUserList=[])


# --------------------------------------------------------------------------- serial codes, invite codes, stubs
def _serial_codes() -> dict:
    import json as _json
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "serialcodes.json")
    try:
        return {k.upper(): int(v) for k, v in _json.load(open(path, encoding="utf-8")).get("codes", {}).items()}
    except (OSError, ValueError):
        return {}


@register(31)  # POST /system/serialcode {serialCode}
def handle_serialcode(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # UserPresent::parse (the whole present box). The rewards go to the present box; the client then says
    # "You have used a serial code to get an item. Go to Presents" (104000007). Unknown / used codes: an error the
    # client shows. Codes -> serialcodeReward ids in data/serialcodes.json (GUESS: SC1); master dates (2015) are
    # ignored (GUESS: SC2).
    code = str(request_data.get("serialCode") or "").strip().upper()
    rid = _serial_codes().get(code)
    row = _master_row("serialcodeReward", "serialcodeRewardId", rid) if rid else {}
    if not row or not user:
        return build_error(user, "This serial code is not valid.")
    with gstate.State(user, db_session) as st:
        used = st.setdefault("serial_used", [])
        if rid in used:
            return build_error(user, "This serial code has already been used.")
        used.append(rid)
        for k in range(min(int(row.get("validReward", 0) or 0), 10)):
            add_present(st, row["type"][k], row["id"][k], row["num"][k], row.get("name") or "Serial Code")
    logger.info("SERIAL CODE %s -> reward %s for user %s", code, rid, user.id)
    return handle_user_present({}, user, db_session)


@register(32)  # GET /system/serialcode/campaign: the serial-code list (activeCampaignIds -> serialcodeReward rows)
def handle_serialcode_campaign(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # every id must exist in the serialcodeReward master (no null check on the client)
    ids = sorted({rid for rid in _serial_codes().values()
                  if _master_row("serialcodeReward", "serialcodeRewardId", rid)})
    return build_response(user, activeCampaignIds=ids)


@register(33)  # GET /system/invitecode: the player's invitation code (party top "Invitation code" button)
def handle_invitecode(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # SystemInvitecode::parse: inviteCode str, invitedNumber, inviteRemainingNumber ("You have received Jewels
    # %d/%d times")
    if not user:
        return build_response(user, inviteCode="", invitedNumber=0, inviteRemainingNumber=0)
    with gstate.State(user, db_session) as st:
        rec = st.get("invite")
        if not rec:
            rec = st["invite"] = {"code": _make_invite_code(db_session), "invited": 0}
    return build_response(user, inviteCode=rec["code"], invitedNumber=rec["invited"],
                          inviteRemainingNumber=max(INVITE_CAP - rec["invited"], 0))


@register(34)  # POST /system/push/regist {deviceType, deviceToken}: no parser; nothing to push to
def handle_push_regist(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user)


@register(35)  # POST /system/push/help: "help me" push after an unfinished raid (no parser); bosses are already
def handle_push_help(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:  # party-shared
    return build_response(user)


def _shop_row(product_id) -> dict:
    return next((r for r in _master_table("shop") if r.get("productId") == product_id and r.get("status") == 1), {})


def _master_table(name: str) -> list:
    from .master import MASTER_JSON_DATA
    return MASTER_JSON_DATA.get(name) or []


@register(72)  # POST /purchase/prepare {productId, priceLocale}
def handle_purchase_prepare(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # Purchases are free on this server (GUESS: V2): the host's store always succeeds; 72 opens a transaction
    # (PurchasePrepare: bridgeTransId), 73 grants it.
    pid = str(request_data.get("productId") or "")
    if not user or not _shop_row(pid):
        return build_error(user, "This item is not available.")
    with gstate.State(user, db_session) as st:
        p = st.setdefault("purchases", {"next": 1, "pending": {}, "done": []})
        tid = p["next"]
        p["next"] = tid + 1
        p["pending"][str(tid)] = pid
    logger.info("PURCHASE PREPARE: %s -> transaction %s", pid, tid)
    return build_response(user, bridgeTransId=tid)


@register(73)  # POST /purchase/finish {bridgeTransId, purchaseData (base64 store json), dataSignature}
def handle_purchase_finish(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # verifyResponse case 73: userData.userPoint, userStone, paymentInfo, userBenefits (appended by the client),
    # receiptStatus. Grants number + bonus Jewels (free Jewels here) and the row's benefit (VIP pass: benefit 100,
    # every Special Quest until the weekly reset). A resent transaction is answered without granting again.
    import base64 as _b64
    import json as _json
    tid = str(request_data.get("bridgeTransId") or "")
    with gstate.State(user, db_session) as st:
        p = st.setdefault("purchases", {"next": 1, "pending": {}, "done": []})
        pid = p["pending"].pop(tid, None)
        if pid is None and tid not in p["done"]:
            try:
                pid = _json.loads(_b64.b64decode(request_data.get("purchaseData") or "")).get("productId")
            except (ValueError, TypeError):
                pid = None
        row = _shop_row(pid) if pid and tid not in p["done"] else {}
        if row and user:
            p["done"].append(tid)
            user.free_stone = (user.free_stone or 0) + int(row.get("number", 0)) + int(row.get("bonus", 0))
            st["skip_tickets"] = int(st.get("skip_tickets", 0)) + int(row.get("stageSkipTicket", 0))
            if row.get("benefitId"):
                st.setdefault("benefits", {})[str(row["benefitId"])] = _benefit_end()
            db_session.add(user)
            logger.info("PURCHASE: %s (transaction %s) -> +%s Jewels, benefit %s", pid, tid,
                        int(row.get("number", 0)) + int(row.get("bonus", 0)), row.get("benefitId") or "-")
        benefits = _active_benefits(st)
    return build_response(user, userData={"userPoint": _user_point(user)},
                          userStone={"freeStone": user.free_stone if user else 0, "payStone": user.pay_stone if user else 0},
                          paymentInfo={"cesaLimitAge": 20, "chargeMoneyThisMonth": 0, "lastchargeMoneyThisMonth": 0},
                          userBenefits=benefits, receiptStatus=1)


@register(132)  # GET /campaign/pincode (no callers) / 136 PUT /campaign/pincode/status: KHchi avatar link
@register(136)
def handle_pincode_status(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    # avatarSync {srcAccept, destAccept} (JSON booleans); the KHchi side no longer exists (button off: flag 0x08)
    return build_response(user, avatarSync={"srcAccept": False, "destAccept": False})


@register(133)  # POST /campaign/pincode: generate a link number (avatarSync.pinCode)
def handle_pincode_create(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, avatarSync={"srcAccept": False, "destAccept": False, "pinCode": "00000000"})


@register(134)  # PUT /campaign/pincode {pinCode}: no parser
@register(135)  # DELETE /campaign/pincode: no parser
def handle_pincode_other(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user)


@register(27)  # GET /system/resourceEv {resourceIds}: event resources - never sent without events
def handle_resource_ev(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, resourceEv=[])


@register(99)  # GET /stage: no callers in 1.0.1 (it uses 100 /stage/160310)
def handle_stage_root(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return handle_stage(request_data, user, db_session)


def default_handler(action_id: int, request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    logger.warning("Unhandled action_id=%d request_keys=%s", action_id, list(request_data.keys()))
    return build_response(user)
