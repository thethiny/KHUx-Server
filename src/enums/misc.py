"""
Misc ID enum — mapped from 73 call sites in v1.0.1 decompile.
General game constants: level caps, jewel costs, text limits, UI params.
Values from server/data/misc.json (sourced from 1.1.3 m files).
"""
from enum import IntEnum


class Misc(IntEnum):
    # ── Player progression (100-105) ─────────────────────────────────
    MAX_PLAYER_LEVEL = 100              # 300 — Used in calcLuxGaugePer, level-up detection
    AP_RECHARGE_MINUTES = 101           # 3 — Minutes per 1 AP recovery tick
    MISC_102 = 102                      # 50 (150 in 5.0.1) — near AP entries, possibly AP-related
    BASE_MEDAL_SLOTS = 103              # 5 — Initial medal slot count
    MAX_MEDAL_SLOTS = 104               # 500 — Hard cap on total medal slots
    MISC_105 = 105                      # 60 — possibly starting AP or base AP count

    # ── Adventure unlock thresholds (106, 122-123) ───────────────────
    ADVENTURE_UNLOCK_LEVEL_1 = 106      # 130 — Player level gate for adventure tier 1

    # ── Stage parameters (107-110) ───────────────────────────────────
    STAGE_PARAM_1 = 107                 # 0 — StageManager float at offset +89
    STAGE_PARAM_2 = 108                 # 100 — StageManager float at offset +90
    STAGE_PARAM_3 = 109                 # 100 — StageManager float at offset +91
    MISC_110 = 110                      # 8600 — large, possibly item capacity or display limit

    # ── Jewel costs (111-117) ────────────────────────────────────────
    MEDAL_SLOT_EXPAND_COST = 111        # 100 — Jewels to expand medal slots / sphere board buy
    AP_RECOVERY_COST = 112              # 100 — Jewels to recover AP
    CONTINUE_COST = 113                 # 100 — Jewels to continue after defeat
    UNION_CHANGE_COST = 114             # 100 — Jewels to switch unions
    INVITATION_COST = 115               # 300 — Invitation code jewel cost
    TUTORIAL_DOWNLOAD_JEWEL_REWARD = 116  # 300 — Jewels awarded after tutorial download
    PARTY_CREATION_COST = 117           # 100 — Party member limit / creation cost

    # ── Capacity limits (118-129) ────────────────────────────────────
    MAX_JEWEL_CAPACITY = 118            # 500000 — Maximum jewels a player can hold
    MISC_119 = 119                      # 450 (945 in 5.0.1) — near capacity IDs, possibly avatar parts limit
    MEDAL_ABILITY_LEVEL_MAX = 120       # 30 — Max ability level for medals
    MISC_121 = 121                      # 200 (34 in 5.0.1) — rebalanced threshold
    ADVENTURE_UNLOCK_LEVEL_2 = 122      # 6 — Player level gate for adventure tier 2
    ADVENTURE_UNLOCK_LEVEL_3 = 123      # 14 — Player level gate for adventure tier 3
    MISC_124 = 124                      # 1000000 — likely max currency cap (MEDIUM confidence)
    MISC_125 = 125                      # 0 (940 in 5.0.1) — disabled in 1.1.3, enabled later
    MISC_126 = 126                      # 20 — small limit, possibly friend/notification cap
    MISC_127 = 127                      # 99 — classic max level, possibly keyblade or skill level cap
    MISC_128 = 128                      # 60 — possibly time constant or capacity
    MISC_129 = 129                      # 500 — possibly material/inventory cap

    # ── Raid boss HP display (200-203) ───────────────────────────────
    MISC_200 = 200                      # 3000 — raid group, possibly raid base param
    RAID_HP_DIGITS_NORMAL = 201         # 20000 — HP indicator digits (normal boss)
    RAID_HP_DIGITS_OMEGA = 202          # 20000 — HP indicator digits (omega/special boss)
    RAID_HP_DIGITS_SUPER = 203          # 300000 — HP indicator digits (super boss)

    # ── Colosseum (300-304) ──────────────────────────────────────────
    MISC_300 = 300                      # 3000 — colosseum group start
    MISC_301 = 301                      # 16 — colosseum tier/board count
    MISC_302 = 302                      # 38 — colosseum max round
    MISC_303 = 303                      # 30000 — colosseum reward cap
    MISC_304 = 304                      # 999 — colosseum max rank display

    # ── Tutorial triggers (400-407) ──────────────────────────────────
    MISC_400 = 400                      # 4 — possibly total tutorial phases
    MISC_401 = 401                      # 150 — tutorial exp/reward threshold
    MISC_402 = 402                      # 5 — tutorial medal reward count
    TUTORIAL_12_MEDAL_THRESHOLD = 403   # 300 — Medal count to trigger shop tutorial
    MISC_404 = 404                      # 2 — tutorial rarity requirement
    TUTORIAL_13_RARITY3_COUNT = 405     # 1 — Tier-3+ medals needed for tutorial 13
    TUTORIAL_13_LEVEL_THRESHOLD = 406   # 5 — Player level for tutorial 13 eligibility
    MISC_407 = 407                      # 15 — tutorial completion threshold

    # ── Events (500-501) ─────────────────────────────────────────────
    MISC_500 = 500                      # 30 — event duration or raid limit
    MISC_501 = 501                      # 200 — event max participants

    # ── Avatar board (600-610) ───────────────────────────────────────
    MISC_600 = 600                      # 50 — avatar board base cost
    MISC_601 = 601                      # 50 — avatar board upgrade cost
    MISC_610 = 610                      # 300 — avatar board premium cost

    # ── MyPage / Banner / Shop (700-707) ─────────────────────────────
    BANNER_SCROLL_SPEED = 700           # 35000 — /10000 float, MyPage banner auto-scroll
    BANNER_CACHE_DAYS = 701             # 100 — Days to cache banner images
    MISC_702 = 702                      # 2 — banner/UI page count
    MISC_703 = 703                      # 27 — shop category ID
    MISC_704 = 704                      # 29 — shop category ID (adjacent to 705=28, 706=30)
    SHOP_ITEM_DISCOUNTED = 705          # 28 — Discounted magic stone shop item ID
    SHOP_ITEM_NORMAL = 706              # 30 — Non-discounted magic stone shop item ID
    MISC_707 = 707                      # 100000 (170000 in 5.0.1) — shop price cap or display limit

    # ── Party (800-811) ──────────────────────────────────────────────
    PARTY_MEMBER_LIMIT = 800            # 30 — Max party members (alert display)
    PARTY_CREATION_ALERT_COST = 801     # 30 — Party creation jewel cost (alert)
    MISC_802 = 802                      # 10 — party min level or related threshold
    PARTY_MEMBER_LIMIT_ALT = 803        # 5 — Party member limit (alternate text ID)
    PLAYER_NAME_MAX_LEN = 804           # 8 — Max characters for player name
    PROFILE_COMMENT_MAX_LEN = 805       # 20 — Max characters for profile comment
    PARTY_NAME_MAX_LEN = 806            # 14 — Max characters for party name
    PARTY_MESSAGE_MAX_LEN = 807         # 20 — Max characters for party description
    SOCIAL_MESSAGE_MAX_LEN = 808        # 20 — Max characters for offer/join/request messages
    CHAT_MESSAGE_MAX_LEN = 809          # 40 — Max characters for chat messages
    FB_SHARE_COMMENT_MAX_LEN = 810      # 40 — Max characters for Facebook share comment
    FB_SHARE_API_MAX_LEN = 811          # 30 — Max length for Facebook sharing API string

    # ── COPPA / Birthday popup (900-907) ────────────────────────────
    COPPA_MIN_AGE = 900                 # 13 — Chat restriction age threshold
    COPPA_UNDERAGE_UPPER = 901          # 16 — Under-age bracket upper bound
    COPPA_ADULT_AGE = 902               # 20 — Adult age threshold
    COPPA_PURCHASE_LIMIT_MINOR = 903    # 5000 — Purchase limit $ for minors
    COPPA_PURCHASE_LIMIT_TEEN = 904     # 30000 — Purchase limit $ for teens
    COPPA_YEAR_PICKER_START = 905       # 1910 — Year picker start year
    COPPA_YEAR_PICKER_END = 906         # 2016 — Year picker end year (game launch year)
    COPPA_UNKNOWN_907 = 907             # 30 — Purpose unknown

    # ── Stage animation (1000) ───────────────────────────────────────
    STAGE_SKIP_ANIM_SPEED = 1000        # 30000 — /10000 float, skip animation speed
