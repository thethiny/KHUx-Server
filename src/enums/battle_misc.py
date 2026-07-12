"""
BattleMisc ID enum — mapped from 40 call sites in v1.0.1 decompile.
Values from 1.1.3 binary (m002.jpg). All values /10000 unless noted.
"""
from enum import IntEnum


class BattleMisc(IntEnum):
    # ── Damage formula (100-115) ─────────────────────────────────────
    SINGLE_TARGET_BASE_MULT = 100       # 10000 → 1.0x (Direct Attack)
    MULTI_TARGET_BASE_MULT = 101        # 6666  → 0.67x (Swipe Attack)
    ELEMENTAL_ADVANTAGE = 102           # 15000 → 1.5x (was 50000 in 5.0.1)
    ELEMENTAL_NEUTRAL = 103             # 10000 → 1.0x
    ELEMENTAL_WEAK = 104                # 6666  → 0.67x
    CRITICAL_CHANCE = 105               # 600   → 6%
    CRITICAL_MULTIPLIER = 106           # 15000 → 1.5x
    PLAYER_ATK_BASE_CONSTANT = 107      # 1110  (flat addend in damage formula)
    ENEMY_ATK_BASE_CONSTANT = 108       # 455   (flat addend in enemy formula)
    PLAYER_ATK_STAT_WEIGHT = 109        # 3000  → 0.3x
    ENEMY_ATK_STAT_WEIGHT = 110         # 10000 → 1.0x
    PLAYER_DEF_STAT_WEIGHT = 111        # 10000 → 1.0x (enemy def when player attacks)
    ENEMY_DEF_STAT_WEIGHT = 112         # 3500  → 0.35x (player def when enemy attacks)
    DAMAGE_VARIANCE = 113               # 300   → ±3%
    BATTLE_MISC_114 = 114               # 5000 → 0.5x — possibly min damage mult
    BATTLE_MISC_115 = 115               # 10000 → 1.0x — possibly max damage cap

    # ── Enemy movement (120-121) ─────────────────────────────────────
    APPROACH_X_THRESHOLD = 120          # 480
    APPROACH_Y_THRESHOLD = 121          # 320

    # ── Raid damage scaling (130-133) ────────────────────────────────
    BATTLE_MISC_130 = 130               # 4000 — raid damage scaling (134-145 added in 4.3.1)
    BATTLE_MISC_131 = 131               # 1000 (100000 in 5.0.1) — raid damage cap
    BATTLE_MISC_132 = 132               # 20000 (4000000 in 5.0.1) — raid HP scaling
    BATTLE_MISC_133 = 133               # 1000 — raid damage base constant

    # ── Ability multiplier (200) ─────────────────────────────────────
    BATTLE_MISC_200 = 200               # 12000 → 1.2x — possibly medal ability damage mult

    # ── Attack prizes (300-402) ──────────────────────────────────────
    BATTLE_MISC_300 = 300               # 5 — possibly prize tier count
    PRIZE_COEFF_A_UPPER = 301           # 20000
    PRIZE_COEFF_A_LOWER = 302           # 12500
    BATTLE_MISC_400 = 400               # 20 — prize group B base
    PRIZE_COEFF_B_UPPER = 401           # 12500
    PRIZE_COEFF_B_LOWER = 402           # 12500

    # ── Keyblade ability (500) ───────────────────────────────────────
    BATTLE_MISC_500 = 500               # 10000 → 1.0x — possibly keyblade ability base mult

    # ── Buff system (600-602) ────────────────────────────────────────
    BATTLE_MISC_600 = 600               # 99 — likely max buff/debuff level (MEDIUM confidence)
    BATTLE_MISC_601 = 601               # 5000 → 0.5x — buff correction per level
    BATTLE_MISC_602 = 602               # 180 — buff duration or animation angle

    # ── Per-attribute buff corrections (700-704) ─────────────────────
    BATTLE_MISC_700 = 700               # 5000 → 0.5x — buff correction: general (MEDIUM confidence)
    BATTLE_MISC_701 = 701               # 5000 → 0.5x — buff correction: power
    BATTLE_MISC_702 = 702               # 5000 → 0.5x — buff correction: speed
    BATTLE_MISC_703 = 703               # 5000 → 0.5x — buff correction: magic
    BATTLE_MISC_704 = 704               # 5000 → 0.5x — buff correction: neutral

    # ── Defense buff correction (800) ────────────────────────────────
    BATTLE_MISC_800 = 800               # 5000 → 0.5x — counterpart to 700-704

    # ── Short-term finish bonus (900-910) ────────────────────────────
    FINISH_BONUS_RATE_SOLO = 900        # 18000
    FINISH_BONUS_RATE_MULTI = 901       # 4000
    CRUSHING_MONEY_RATE_SOLO = 902      # 15000
    CRUSHING_MONEY_RATE_MULTI = 903     # 12000
    FINISH_BONUS_COEFF_SOLO = 904       # 1200
    FINISH_BONUS_COEFF_MULTI = 905      # 600
    BATTLE_MISC_906 = 906               # 20000 → 2.0x — finish bonus group, reserved
    BATTLE_MISC_907 = 907               # 12000 → 1.2x — finish bonus group, reserved
    FINISH_TIME_OVERRIDE_SOLO = 908     # 25000
    FINISH_TIME_OVERRIDE_MULTI = 909    # 15000
    FINISH_TIME_BASE = 910              # 10000

    # ── LUX / Crushing prizes (1000-1004) ────────────────────────────
    LUX_BASE_MULTIPLIER = 1000          # 30 (raw int, NOT /10000)
    LUX_SCALING_DIVISOR = 1001          # 10000000
    LUX_SCALING_EXPONENT = 1002         # 10500 → 1.05
    BATTLE_MISC_1003 = 1003             # 21625 — lux curve parameter
    BATTLE_MISC_1004 = 1004             # 30000 → 3.0x — lux max multiplier

    # ── Symbol encounter (1100) ──────────────────────────────────────
    SYMBOL_ENEMY_HP_MODIFIER = 1100     # 1840 → 0.184x
