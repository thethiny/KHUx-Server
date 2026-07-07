"""
MedalMisc ID enum — mapped from 20 call sites in v1.0.1 decompile.
Each entry has 3 int values (16-byte struct). Values /10000 unless noted.
"""
from enum import IntEnum


class MedalMisc(IntEnum):
    # ── Stat growth curve exponents (101-105) ────────────────────────
    # value[0] = exponent for pow() interpolation between base and max stats
    # Used in BattleUtil::calcMedalStatus, switched by medal rarity
    STAT_CURVE_RARITY_1 = 101           # [6000, 0, 0]  → 0.6 exponent
    STAT_CURVE_RARITY_2 = 102           # [10000, 0, 0] → 1.0 (linear)
    STAT_CURVE_RARITY_3 = 103           # [18000, 0, 0] → 1.8 exponent
    STAT_CURVE_RARITY_4 = 104           # [10000, 0, 0] → 1.0 (linear)
    STAT_CURVE_RARITY_5 = 105           # [10000, 0, 0] → 1.0 (linear)

    # ── EXP curve parameters (106-111) ───────────────────────────────
    # value[0] = exponent, value[1] = max/scaling exp, value[2] = curve param
    # Used in BattleUtil::calcMedalExp, switched by medal rarity
    EXP_CURVE_RARITY_1 = 106            # [150, 321787, 21000]
    EXP_CURVE_RARITY_2 = 107            # [150, 500000, 21000]
    EXP_CURVE_RARITY_3 = 108            # [150, 558693, 22000]
    EXP_CURVE_RARITY_4 = 109            # [150, 2795303, 22000]
    EXP_CURVE_RARITY_5 = 110            # [150, 360000, 18000]
    EXP_CURVE_RARITY_6 = 111            # [150, 500000, 18000]

    # ── Medal mixing/fusion (112-114) ────────────────────────────────
    # Used in SceneMixedMedal::calcMixedExp
    MIXING_EXP_CURVE = 112              # [150, 13000, 10000] pow() curve params
    MIXING_SAME_ATTR_BONUS = 113        # [15000, 0, 0] → 1.5x same-attribute bonus
    MIXING_SKILL_SLOT_MATCH = 114       # [15000, 0, 0] → skill slot matching param

    # ── Material panel (115) ─────────────────────────────────────────
    MATERIAL_PANEL_PARAM = 115          # [80, 0, 0]

    # ── Unreferenced in v1.0.1 (116-119) ────────────────────────────
    UNKNOWN_116 = 116                   # [800, 0, 0]
    UNKNOWN_117 = 117                   # [100, 0, 0]
    UNKNOWN_118 = 118                   # [15000, 0, 0]
    UNKNOWN_119 = 119                   # [20000, 0, 0]

    # ── Skill mix panel UI (121-122) ─────────────────────────────────
    SKILL_MIX_ICON_SCALE = 121          # [2000, 0, 0] → 0.2
    SKILL_MIX_THRESHOLD = 122           # [10000, 0, 0] → 1.0

    # ── Material attribute bonus (123) ───────────────────────────────
    MATERIAL_SAME_ATTR_BONUS = 123      # [2500, 0, 0] → 0.25 (25% bonus)
