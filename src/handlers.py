import logging
import time
from datetime import datetime, timezone
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
    Build the 'ret' sub-object for v1.0.1 responses.

    From Ret::parse (libcocos2dcpp_0002.c:12948-13099):
      isMaintenance  - MUST be JSON boolean (rapidjson kFalseType=257 or kTrueType=258)
      sessionTO      - MUST be JSON boolean
      isNewDayPeriod - MUST be integer
      versionApp     - MUST be string
      versionRes     - MUST be integer
      versionDat     - MUST be integer
      functionFlags  - MUST be integer
      serverTime     - MUST be string (parsed by Date::init)
    """
    now = datetime.now(timezone.utc)
    return {
        "isMaintenance": False,
        "sessionTO": False,
        "isNewDayPeriod": 0,
        "versionApp": "1.0.1",
        "versionRes": 1,
        "versionDat": 1,
        "functionFlags": 0,
        "serverTime": now.strftime("%Y-%m-%d %H:%M:%S"),
    }


def build_response(user: Optional[User] = None, **extra) -> dict:
    """
    Build a complete API response.

    v1.0.1 format: {"ret": {...}, ...extra_fields}
    Do NOT include root "maintenance" — a root maintenance field with ANY
    non-null type (including false, type=257) triggers maintenance mode
    when Ret::parse fails. (libcocos2dcpp_0003.c:770-774)
    """
    resp = {"ret": build_ret(user)}
    resp.update(extra)
    # Ensure response starts with {"ret" so the client's plain-JSON
    # detection pattern matches. Python dicts preserve insertion order.
    return resp


# ---------------------------------------------------------------------------
# Action 1: GET /user — full user data
# ---------------------------------------------------------------------------
@register(1)
def handle_user_data(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    if user is None:
        return build_response()

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Complete GET /user response structure from decompile analysis
    # (libcocos2dcpp_0002.c:26200-26360) — 12 sub-parsers, all required
    return build_response(user,
        userData={
            "user": {
                "userId": user.id,
                "nativeUserId": user.id,
                "platformId": user.platform_id,
                "userName": user.user_name,
                "gender": 1,
                "comment": "",
                "deviceType": user.device_type,
                "continueLoginCount": user.continue_login_count,
                "isFleeze": 0,
                "fleezedDatetime": "2020-01-01 00:00:00",
                "nativeTagName": user.user_name,
            },
            "stageResumption": {
                "resumptionStatus": 0,
                "stageId": 0,
                "raidId": 0,
                "colosseumStageId": 0,
            },
            "userDetail": {
                "level": user.level,
                "exp": user.exp,
                "luxRank": user.lux_rank,
                "luxGetRatio": user.lux_get_ratio,
                "titleLeftId": user.title_left_id,
                "titleRightId": user.title_right_id,
                "titlePlateId": user.title_plate_id,
                "maxDeckCost": user.max_deck_cost,
                "playTimezones": [0, 0, 0, 0, 0, 0],
                "playFrequently": 0,
                "partyId": 0,
                "unionId": user.union_id or 1,
                "maxMedal": user.max_medal,
                "mvpCount": user.mvp_count,
                "equipCoordinateNo": user.equip_coordinate_no,
                "lastClearStageId": user.last_clear_stage_id,
                "lastPlayNormalSphereBoardId": 0,
                "lastPlayStageSphereBoardId": 0,
                "lastPlayRaidSphereBoardId": 0,
                "lastPlayColosseumSphereBoardId": 0,
                "isGuilt": 0,
            },
            "userPoint": {
                "money": user.money,
                "lux": user.lux,
                "totalLux": user.total_lux,
                "spherePoint": 0,
                "kizunaPoint": 0,
                "raidPoint": 0,
                "attack": user.attack,
                "defense": user.defense,
                "baseHp": user.base_hp,
                "hp": user.hp,
                "ap": user.ap,
                "maxHp": user.max_hp,
                "maxAp": user.max_ap,
                "lastApDatetime": now_str,
                "stageSpherePoint": 0,
                "raidSpherePoint": 0,
                "colosseumSpherePoint": 0,
                "stageSkipTicket": 0,
            },
            "lastActionDatetime": now_str,
        },
        userMedals=[],
        userSkills=[],
        userAvatar={
            "myCoordinateNo": 0,
            "gender": user.gender or 1,
            "hairPartsId": 1,
            "hairColorPartsId": 1,
            "facePartsId": 1,
            "bodyPartsId": 1,
            "skinPartsId": 1,
            "accessoriesPartsIds": [],
        },
        userKeyblade={
            "userKeybladeId": 1,
            "category": 1,
            "keybladeId": 1,
            "deckMedals": [],
            "burst": 0,
            "totalAttack": 0,
            "totalDefense": 0,
            "isFavorite": 0,
            "getDatetime": "2020-01-01 00:00:00",
        },
        userRecord={},
        userRanking={
            "lux": 0,
            "rank": 0,
        },
        linkPlatformId="",
        userPopUp={"isPopBenefitStone": 0},
    )


# ---------------------------------------------------------------------------
# Action 58: GET /login/token — pre-session, no handler needed (handled in app.py)
# Action 59: POST /login — session login
# ---------------------------------------------------------------------------
@register(59)
def handle_login(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    """
    Login::parse (libcocos2dcpp_0002.c:13296-13364) expects:
      login.newcomer            - boolean
      login.tutorial            - boolean
      login.acquirableLoginBonus - boolean
      login.progression         - integer
    All four are REQUIRED with correct types.
    """
    if user:
        user.continue_login_count += 1
        user.last_login_at = datetime.utcnow()
        db_session.flush()
    return build_response(user, login={
        "newcomer": False,
        "tutorial": False,
        "acquirableLoginBonus": False,
        "progression": 0,
    })


# ---------------------------------------------------------------------------
# Action 60: POST /login/bonus
# ---------------------------------------------------------------------------
@register(60)
def handle_login_bonus(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user)


# ---------------------------------------------------------------------------
# Action 61: POST /tutorial/user/create (login action — triggers status flow)
# ---------------------------------------------------------------------------
@register(61)
def handle_tutorial_create(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    """
    TutorialProgress::parse (libcocos2dcpp_0002.c:25863-25953) expects:
      tutorial.userTutorialId - int64
      tutorial.progression    - int (0=start, controls which fields are needed)
      tutorial.name           - string
      tutorial.inviteCode     - string
    """
    return build_response(user, tutorial={
        "userTutorialId": 1,
        "progression": 0,
        "name": "Player",
        "inviteCode": "",
    })


# ---------------------------------------------------------------------------
# Action 25: GET /system/master — master data table versions
# ---------------------------------------------------------------------------
MASTER_TABLES = [
    "albumChallenge", "avatarCombination", "avatarParts", "badstatus",
    "battleMisc", "buff", "burst", "chapter", "colosseum", "colosseumStage",
    "drawMedalList", "drawMedalType", "drawSkillList", "drawSkillType",
    "enemyAttack", "enemy", "evCampaign", "evGroupPattern", "evResource",
    "evStage", "guiltProb", "initItem", "keyblade", "loginBonus", "material",
    "medal", "medalMisc", "misc", "mypageBackground", "player",
    "raidEnemyAttack", "raidEnemy", "raidReward", "raidSetting", "ranking",
    "rankingReward", "reward", "serialcodeReward", "shop", "skillExp",
    "skill", "sphereArray", "sphere", "sphereMasu", "stage", "stamp",
    "title", "tutorialMisc", "world",
]

@register(25)
def handle_system_master(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    """
    MasterDataManager::update (libcocos2dcpp_0028.c:3232) expects:
      master.revision (int), master.count (int)
      + 49 table objects each with: revision (int), url (string), key (string 32), md5 (string)
    Tables with revision <= local revision are skipped but still counted.
    Setting all to 0 means no downloads needed.
    """
    tables = {}
    for name in MASTER_TABLES:
        tables[name] = {
            "revision": 0,
            "url": "",
            "key": "00000000000000000000000000000000",
            "md5": "d41d8cd98f00b204e9800998ecf8427e",
        }
    return build_response(user, master={"revision": 0, "count": len(MASTER_TABLES)}, **tables)


# ---------------------------------------------------------------------------
# Action 26: GET /system/resource — resource data versions
# ---------------------------------------------------------------------------
@register(26)
def handle_system_resource(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    """
    ResourceDataManager::update expects:
      resource.mode (int, 1 or 2), resource.minVersion (int), resource.versions (array)
    """
    return build_response(user, resource={
        "mode": 1,
        "minVersion": 0,
        "versions": [],
    })


# ---------------------------------------------------------------------------
# Action 24: GET /system/coppa — age restriction values per region
# ---------------------------------------------------------------------------
@register(24)
def handle_system_coppa(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    """
    SystemCoppa::parse (libcocos2dcpp_0002.c:21727-21848) expects
    misc object with numeric entries 116, 900-907 (all unsigned ints).
    """
    return build_response(user, misc={
        "116": 13,   # US COPPA age
        "900": 0, "901": 0, "902": 0, "903": 0,
        "904": 0, "905": 0, "906": 0, "907": 0,
    })


# ---------------------------------------------------------------------------
# Action 23: GET /system/need/url — required URLs for various pages
# ---------------------------------------------------------------------------
@register(23)
def handle_system_need_url(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    """
    SystemNeedUrl::parse (libcocos2dcpp_0002.c:21550-21678) expects
    11 string fields — all required or parse fails.
    """
    base = "http://api.sp.kingdomhearts.com"
    return build_response(user,
        support=f"{base}/support",
        register=f"{base}/register",
        update=f"{base}/update",
        help=f"{base}/help",
        staff=f"{base}/staff",
        agreement=f"{base}/agreement",
        license=f"{base}/license",
        shikin=f"{base}/shikin",
        tokutei=f"{base}/tokutei",
        store="https://play.google.com/store",
    )


# ---------------------------------------------------------------------------
# Action 62: POST /tutorial/progress
# ---------------------------------------------------------------------------
@register(62)
def handle_tutorial_progress(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, tutorial={
        "userTutorialId": 1,
        "progression": request_data.get("progression", 0),
        "name": "Player",
        "inviteCode": "",
    })


# ---------------------------------------------------------------------------
# Action 63: POST /tutorial/clear
# ---------------------------------------------------------------------------
@register(63)
def handle_tutorial_clear(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, tutorial={
        "userTutorialId": 1,
        "progression": 999,
        "name": "Player",
        "inviteCode": "",
    })


# ---------------------------------------------------------------------------
# Action 64/65: GET/PUT /tutorial/status
# ---------------------------------------------------------------------------
@register(64)
def handle_tutorial_status_get(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, tutorial={
        "userTutorialId": 1,
        "progression": 0,
        "name": "Player",
        "inviteCode": "",
    })

@register(65)
def handle_tutorial_status_put(request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    return build_response(user, tutorial={
        "userTutorialId": 1,
        "progression": 0,
        "name": "Player",
        "inviteCode": "",
    })


# ---------------------------------------------------------------------------
# Default handler
# ---------------------------------------------------------------------------
def default_handler(action_id: int, request_data: dict, user: Optional[User], db_session: DBSession) -> dict:
    logger.warning("Unhandled action_id=%d request=%s, returning empty ret", action_id, request_data)
    return build_response(user)
