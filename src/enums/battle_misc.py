"""
BattleMisc ID enum — mapped from 40 call sites in v1.0.1 decompile.
Values from 1.1.3 binary (m002.jpg). All values /10000 unless noted.
"""
from enum import IntEnum


class BattleMisc(IntEnum):
    # ── Damage formula (100-113) ─────────────────────────────────────
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

    # ── Enemy movement (120-121) ─────────────────────────────────────
    APPROACH_X_THRESHOLD = 120          # 480
    APPROACH_Y_THRESHOLD = 121          # 320

    # ── Attack prizes (300-402) ──────────────────────────────────────
    PRIZE_COEFF_A_UPPER = 301           # 20000
    PRIZE_COEFF_A_LOWER = 302           # 12500
    PRIZE_COEFF_B_UPPER = 401           # 12500
    PRIZE_COEFF_B_LOWER = 402           # 12500

    # ── Short-term finish bonus (900-910) ────────────────────────────
    FINISH_BONUS_RATE_SOLO = 900        # 18000
    FINISH_BONUS_RATE_MULTI = 901       # 4000
    CRUSHING_MONEY_RATE_SOLO = 902      # 15000
    CRUSHING_MONEY_RATE_MULTI = 903     # 12000
    FINISH_BONUS_COEFF_SOLO = 904       # 1200
    FINISH_BONUS_COEFF_MULTI = 905      # 600
    FINISH_TIME_OVERRIDE_SOLO = 908     # 25000
    FINISH_TIME_OVERRIDE_MULTI = 909    # 15000
    FINISH_TIME_BASE = 910              # 10000

    # ── LUX / Crushing prizes (1000-1002) ────────────────────────────
    LUX_BASE_MULTIPLIER = 1000          # 30 (raw int, NOT /10000)
    LUX_SCALING_DIVISOR = 1001          # 10000000
    LUX_SCALING_EXPONENT = 1002         # 10500 → 1.05

    # ── Symbol encounter (1100) ──────────────────────────────────────
    SYMBOL_ENEMY_HP_MODIFIER = 1100     # 1840 → 0.184x
