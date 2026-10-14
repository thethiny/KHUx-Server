"""Per-stage chests and enemy drops (data from tools/extract_stage_maps.py -> data/stage_maps.json).

The client decides what a chest / defeated enemy gives from three things (StageUtil::getTreasurePrizes /
getEnemyDropPrizes): the map file's rewardId for that uniqueTreasureId / uniqueEnemyId, the master `reward`
row, and the /stage/start lists userTreasures / userEnemyDropItems. Reward slot k is given only when
dropItemTypeIds[k] equals reward.type[k] (2..20), so the server rolls the drops here and sends each slot's
type (0 = not dropped). /stage/clear then reports the uniqueIds the player opened / defeated.
"""
import json
import logging
import os
import random
from typing import Optional

logger = logging.getLogger(__name__)

_DATA = os.path.join(os.path.dirname(__file__), "..", "data", "stage_maps.json")
_maps: Optional[dict] = None


def stage_map(stage_id: int) -> dict:
    global _maps
    if _maps is None:
        try:
            with open(_DATA, encoding="utf-8") as f:
                _maps = json.load(f)
        except FileNotFoundError:
            logger.warning("stage_maps.json missing - run tools/extract_stage_maps.py; chests/drops will be empty")
            _maps = {}
    return _maps.get(str(stage_id), {"treasures": [], "enemies": []})


def _reward_row(reward_id: int) -> Optional[dict]:
    from .master import MASTER_JSON_DATA
    return next((r for r in MASTER_JSON_DATA.get("reward", []) if r["rewardId"] == reward_id), None)


def roll(reward_id: int, always: bool = False, medal_power: int = 10000) -> list:
    """One roll over the reward slots; at most one slot drops. The client never reads reward.odds (only
    master::Reward::parse touches +120), so the rule is server-side and comes from the data + play memory:
    chests always give something (user) -> odds are relative weights; enemy drops are odds out of 100000
    (enemy rows sum to ~1000, i.e. ~1% medal drops). Returns dropItemTypeIds - reward.type[k] for the
    dropped slot, 0 for the others. medal_power (10000 = x1): a medal-drop campaign multiplies the odds of
    medal slots (reward type 3)."""
    row = _reward_row(reward_id)
    n = row.get("validReward", 0) if row else 0
    drop = [0] * n
    odds = [row["odds"][k] * medal_power // 10000 if row["type"][k] == MEDAL else row["odds"][k]
            for k in range(n)] if n else []
    total = sum(odds)
    if n == 0 or total <= 0:
        return drop
    r, acc = random.randrange(total if always else 100000), 0
    for k in range(n):
        acc += odds[k]
        if r < acc:
            drop[k] = row["type"][k]
            break
    return drop


MEDAL = 3      # reward type of a medal


def roll_stage(stage_id: int, medal_power: int = 10000) -> dict:
    """Roll every chest and enemy symbol of a story stage -> {"treasures": {uid: [types]}, "enemies": {...}}
    (only the ones that drop something)."""
    m = stage_map(stage_id)
    out = {"treasures": {}, "enemies": {}}
    for kind, key in (("treasures", "uniqueTreasureId"), ("enemies", "uniqueEnemyId")):
        for e in m[kind]:
            drop = roll(e["rewardId"], always=(kind == "treasures"), medal_power=medal_power)
            if any(drop):
                out[kind][str(e[key])] = {"rewardId": e["rewardId"], "drop": drop}
    return out


def items(entry: dict) -> list:
    """(type, id, num) for the dropped slots of a rolled entry."""
    row = _reward_row(entry["rewardId"]) or {}
    return [(t, row["id"][k], row["num"][k]) for k, t in enumerate(entry["drop"]) if t]
