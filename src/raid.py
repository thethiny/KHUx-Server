"""Raid bosses (raid master tables + the client's Raid* parsers; schemas in claude_sessions / recomp JOURNAL).

A raid is discovered on the first clear of a story stage whose stage row has `raidBoss` (a raidSetting id):
/stage/clear raises userPoint.raidPoint (SceneBattleResult::startResult sets the client's "raid discovered"
flag when raidPoint grows), then /raid answers raidStatus 3 with the boss, which SceneAdventureSelect shows on
the map. The raid lives in the user's state document under "raid":
  {raidId, stageId, settingId, enemyId, level, hp: [per part], maxHp: [...], end, status, damage}

raidStatus (SceneAdventureSelect::initStageRaidChack): 1 defeated (reward popup), 2 escaped, 3 appeared/active,
0 nothing.
"""
import time

from .master import MASTER_JSON_DATA

RAID_STATUS_NONE, RAID_STATUS_DEFEATED, RAID_STATUS_ESCAPED, RAID_STATUS_ACTIVE = 0, 1, 2, 3


def _row(table, key, value):
    return next((r for r in MASTER_JSON_DATA.get(table) or [] if r.get(key) == value), None)


def _fmt(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t))


def _level_index(enemy, level):
    """Index into the enemy's growth arrays (baseLv thresholds) for `level`."""
    idx = 0
    for k in range(min(enemy.get("validGrowth", 1), len(enemy["baseLv"]))):
        if enemy["baseLv"][k] and level >= enemy["baseLv"][k]:
            idx = k
    return idx


def discover(st, stage_id, setting_id, now=None):
    """Create a raid for `stage_id` from raidSetting `setting_id` (its normal boss, level 1)."""
    now = now or time.time()
    setting = _row("raidSetting", "raidSettingId", setting_id)
    if not setting:
        return None
    enemy = _row("raidEnemy", "raidEnemyId", setting["bossId"])
    if not enemy:
        return None
    level = 1
    ids = part_enemy_ids(enemy)
    hp = [_row("raidEnemy", "raidEnemyId", i)["hp"][_level_index(enemy, level)] for i in ids]
    raid_id = st.get("next_raid", 1)
    st["next_raid"] = raid_id + 1
    raid = {
        "raidId": raid_id,
        "stageId": stage_id, "settingId": setting_id, "enemyId": enemy["raidEnemyId"], "level": level,
        "useAp": setting.get("useAp", 10),
        "hp": hp, "maxHp": list(hp),
        # bossUpTime is taken as hours the boss stays (10 for the first Dwarf Woodlands boss)
        "end": now + 3600 * max(setting.get("bossUpTime", 10), 1),
        "status": RAID_STATUS_ACTIVE, "damage": 0, "rewarded": False,
    }
    st["raid"] = raid
    return raid


def part_enemy_ids(enemy):
    """Raid boss parts as the client numbers them (partsId 1..n): the boss itself, then its `validParts`
    sub-parts. Each sub-part is its own raidEnemy row (name str_rdb_dummy, own HP growth/attribute), e.g.
    Behemoth 3 -> [3, 30002], Darkside 1 -> [1, 10002, 10003]. At most 6 (RaidBase::Info has 6 slots)."""
    ids = [enemy["raidEnemyId"]]
    for pid in enemy.get("parts", [])[:enemy.get("validParts", 0)]:
        if _row("raidEnemy", "raidEnemyId", pid):
            ids.append(pid)
    return ids[:6]


def current(st, now=None):
    """The user's raid, with escape applied when its time ran out."""
    raid = st.get("raid")
    if raid:
        enemy = _row("raidEnemy", "raidEnemyId", raid["enemyId"])
        ids = part_enemy_ids(enemy) if enemy else []
        for pid in ids[len(raid["hp"]):]:        # raids stored before sub-parts were modelled
            full = _row("raidEnemy", "raidEnemyId", pid)["hp"][_level_index(enemy, raid["level"])]
            raid["hp"].append(full)
            raid["maxHp"].append(full)
    if raid and raid["status"] == RAID_STATUS_ACTIVE and (now or time.time()) >= raid["end"]:
        raid["status"] = RAID_STATUS_ESCAPED
    return raid


def info(raid):
    """RaidBase::Info JSON."""
    if not raid:
        return {"raidId": 0, "level": 0, "useAp": 0, "timeLeft": "2099-01-01 00:00:00", "feverFlag": 0,
                "feverTime": "2099-01-01 00:00:00", "stageId": 0, "parts": []}
    enemy = _row("raidEnemy", "raidEnemyId", raid["enemyId"]) or {"raidEnemyId": raid["enemyId"]}
    parts = []
    for k, (pid, hp) in enumerate(zip(part_enemy_ids(enemy), raid["hp"])):
        pe = _row("raidEnemy", "raidEnemyId", pid) or {}
        parts.append({"raidEnemyId": pid, "partsId": k + 1, "hp": hp,
                      "attribute": pe.get("attribute", 1), "rare": pe.get("rare", 1)})
    return {"raidId": raid["raidId"], "level": raid["level"], "useAp": raid["useAp"],
            "timeLeft": _fmt(raid["end"]), "feverFlag": 0, "feverTime": _fmt(raid["end"]),
            "stageId": raid["stageId"], "parts": parts}


def apply_damage(raid, parts):
    """Apply /raid/clear `parts` [{raidEnemyId, partsId (1-based), hp, damage}]; returns total damage dealt.
    The boss is defeated when part 1 (the boss body) reaches 0 HP; sub-parts (arms etc.) only interrupt."""
    total = 0
    for p in parts or []:
        k = int(p.get("partsId", 0)) - 1
        if not 0 <= k < len(raid["hp"]):
            continue
        dmg = max(0, int(p.get("damage", 0)))
        total += dmg
        raid["hp"][k] = max(0, raid["hp"][k] - dmg)
    raid["damage"] += total
    if raid["hp"][0] == 0:
        raid["status"] = RAID_STATUS_DEFEATED
    return total


def reward_rows(raid):
    """Roll the defeated boss's three reward tables (raidEnemy rewardId / mvpRewardId / destroyAllRewardId for
    its level). Returns {"subdueId": slot, "mvpId": slot, "partAllId": slot} with 1-BASED slot numbers (the
    client shows table.type/id/num[slot - 1]: RaidBossResultPopUp -> sub_5B730C, std::array<int,4>::at) and
    the (type, id, num) items won. partAllId 0 = not every part was destroyed (no destroy-all reward)."""
    import random
    enemy = _row("raidEnemy", "raidEnemyId", raid["enemyId"]) or {}
    idx = _level_index(enemy, raid["level"]) if enemy else 0
    slots, items = {"subdueId": 0, "mvpId": 0, "partAllId": 0}, []
    all_parts = all(h == 0 for h in raid["hp"])
    for key, field in (("subdueId", "rewardId"), ("mvpId", "mvpRewardId"), ("partAllId", "destroyAllRewardId")):
        if key == "partAllId" and not all_parts:
            continue
        row = _row("raidReward", "raidRewardId", (enemy.get(field) or [0] * 5)[idx])
        if not row or not row.get("validReward"):
            continue
        n = min(row["validReward"], 4)
        # rarest slot first; each slot's odds is out of 100000 (slot 1 is the 100000 "always" entry)
        won = next((k for k in range(n - 1, 0, -1) if random.randrange(100000) < row["odds"][k]), 0)
        slots[key] = won + 1
        items.append((row["type"][won], row["id"][won], row["num"][won]))
    return slots, items
