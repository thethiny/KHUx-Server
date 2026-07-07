"""
Misc ID enum — mapped from 73 call sites in v1.0.1 decompile.
General game constants: level caps, jewel costs, text limits, UI params.
Values from server/data/misc.json (sourced from 5.0.1, not yet verified against 1.1.3).
"""
from enum import IntEnum


class Misc(IntEnum):
    # ── Player progression (100-101) ─────────────────────────────────
    MAX_PLAYER_LEVEL = 100              # 900 — Used in calcLuxGaugePer, level-up detection
    AP_RECHARGE_MINUTES = 101           # 3 — Minutes per 1 AP recovery tick

    # ── Medal slots (103-104) ────────────────────────────────────────
    BASE_MEDAL_SLOTS = 103              # 5 — Initial medal slot count
    MAX_MEDAL_SLOTS = 104               # 3000 — Hard cap on total medal slots

    # ── Adventure unlock thresholds (106, 122-123) ───────────────────
    ADVENTURE_UNLOCK_LEVEL_1 = 106      # 130 — Player level gate for adventure tier 1
    ADVENTURE_UNLOCK_LEVEL_2 = 122      # 6 — Player level gate for adventure tier 2
    ADVENTURE_UNLOCK_LEVEL_3 = 123      # 14 — Player level gate for adventure tier 3

    # ── Stage parameters (107-109) ───────────────────────────────────
    STAGE_PARAM_1 = 107                 # 0 — StageManager float at offset +89
    STAGE_PARAM_2 = 108                 # 100 — StageManager float at offset +90
    STAGE_PARAM_3 = 109                 # 100 — StageManager float at offset +91

    # ── Jewel costs (111-115, 117) ───────────────────────────────────
    MEDAL_SLOT_EXPAND_COST = 111        # 100 — Jewels to expand medal slots / sphere board buy
    AP_RECOVERY_COST = 112              # 100 — Jewels to recover AP
    CONTINUE_COST = 113                 # 100 — Jewels to continue after defeat
    UNION_CHANGE_COST = 114             # 100 — Jewels to switch unions
    INVITATION_COST = 115               # 300 — Invitation code jewel cost
    PARTY_CREATION_COST = 117           # 100 — Party member limit / creation cost

    # ── Capacity limits (118, 120) ───────────────────────────────────
    MAX_JEWEL_CAPACITY = 118            # 500000 — Maximum jewels a player can hold
    MEDAL_ABILITY_LEVEL_MAX = 120       # 30 — Max ability level for medals

    # ── Raid boss HP display (201-203) ───────────────────────────────
    RAID_HP_DIGITS_NORMAL = 201         # 20000 — HP indicator digits (normal boss)
    RAID_HP_DIGITS_OMEGA = 202          # 20000 — HP indicator digits (omega/special boss)
    RAID_HP_DIGITS_SUPER = 203          # 300000 — HP indicator digits (super boss)

    # ── Tutorial triggers (403-406) ──────────────────────────────────
    TUTORIAL_12_MEDAL_THRESHOLD = 403   # 300 — Medal count to trigger shop tutorial
    TUTORIAL_13_RARITY3_COUNT = 405     # 1 — Tier-3+ medals needed for tutorial 13
    TUTORIAL_13_LEVEL_THRESHOLD = 406   # 5 — Player level for tutorial 13 eligibility

    # ── MyPage UI (700-701) ──────────────────────────────────────────
    BANNER_SCROLL_SPEED = 700           # 35000 — /10000 float, MyPage banner auto-scroll
    BANNER_CACHE_DAYS = 701             # 100 — Days to cache banner images

    # ── Shop item IDs (705-706) ──────────────────────────────────────
    SHOP_ITEM_DISCOUNTED = 705          # 28 — Discounted magic stone shop item ID
    SHOP_ITEM_NORMAL = 706              # 30 — Non-discounted magic stone shop item ID

    # ── Party alerts (800-803) ───────────────────────────────────────
    PARTY_MEMBER_LIMIT = 800            # 30 — Max party members (alert display)
    PARTY_CREATION_ALERT_COST = 801     # 30 — Party creation jewel cost (alert)
    PARTY_MEMBER_LIMIT_ALT = 803        # 5 — Party member limit (alternate text ID)

    # ── Text length limits (804-811) ─────────────────────────────────
    PLAYER_NAME_MAX_LEN = 804           # 8 — Max characters for player name
    PROFILE_COMMENT_MAX_LEN = 805       # 20 — Max characters for profile comment
    PARTY_NAME_MAX_LEN = 806            # 14 — Max characters for party name
    PARTY_MESSAGE_MAX_LEN = 807         # 20 — Max characters for party description
    SOCIAL_MESSAGE_MAX_LEN = 808        # 20 — Max characters for offer/join/request messages
    CHAT_MESSAGE_MAX_LEN = 809          # 40 — Max characters for chat messages
    FB_SHARE_COMMENT_MAX_LEN = 810      # 40 — Max characters for Facebook share comment
    FB_SHARE_API_MAX_LEN = 811          # 30 — Max length for Facebook sharing API string

    # ── COPPA / Birthday popup (900-907) ────────────────────────────
    # Served in action 24 (/system/coppa) BEFORE master data download.
    # These are Misc table IDs but sent inline in the coppa response.
    COPPA_MIN_AGE = 900                 # 13 — Chat restriction age threshold
    COPPA_UNDERAGE_UPPER = 901          # 16 — Under-age bracket upper bound
    COPPA_ADULT_AGE = 902               # 20 — Adult age threshold
    COPPA_PURCHASE_LIMIT_MINOR = 903    # 5000 — Purchase limit for minors (cents/yen)
    COPPA_PURCHASE_LIMIT_TEEN = 904     # 30000 — Purchase limit for teens (cents/yen)
    COPPA_YEAR_PICKER_START = 905       # 1910 — Year picker start year
    COPPA_YEAR_PICKER_END = 906         # 2016 — Year picker end year (game launch year)
    COPPA_SKIP_BIRTHDAY = 907           # 30 — Tutorial state; nonzero side-effect skips birthday page

    # ── Tutorial reward (116) ────────────────────────────────────────
    TUTORIAL_DOWNLOAD_JEWEL_REWARD = 116  # 300 — Jewels awarded after tutorial download

    # ── Stage animation (1000) ───────────────────────────────────────
    STAGE_SKIP_ANIM_SPEED = 1000        # 30000 — /10000 float, skip animation speed
