"""
Shared attribute/type enums used across medal, enemy, keyblade, burst, etc.
Derived from field values in 4.3.1 extracted data.
"""
from enum import IntEnum


class Attribute(IntEnum):
    """Medal/enemy/slot elemental attribute. Used in damage matching formula."""
    POWER = 1       # Fire — red. Advantage vs Speed, weak vs Magic.
    SPEED = 2       # Wind — green. Advantage vs Magic, weak vs Power.
    MAGIC = 3       # Water — blue. Advantage vs Power, weak vs Speed.
    NEUTRAL = 4     # No element — no advantage/weakness.
    EXTRA = 5       # Special (5.0.1+)


class DarkLight(IntEnum):
    """Medal upright/reversed affinity. Affects keyblade slot DL accord bonus."""
    UPRIGHT = 1
    REVERSED = 2
    NEUTRAL = 3     # No affinity — slot accepts either.


class EnemyKind(IntEnum):
    """Enemy movement type. Used in shuffleSkill targeting."""
    GROUND = 1
    AERIAL = 2


class AttackType(IntEnum):
    """AttackTarget type in StageActorManager. Selects damage formula path."""
    NORMAL = 1      # Direct tap — single target, uses BM(100)
    AOE = 2         # Swipe — multi target, uses BM(101)
    BURST = 3       # Keyblade burst — uses burst master data for v13


class MedalRarity(IntEnum):
    """Medal star rarity. Determines stat curve (MedalMisc 101-105) and EXP curve (106-111)."""
    STAR_1 = 1
    STAR_2 = 2
    STAR_3 = 3
    STAR_4 = 4
    STAR_5 = 5
    STAR_6 = 6
    STAR_7 = 7      # Supernova tier (later versions)
