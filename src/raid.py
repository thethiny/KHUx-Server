"""Raid bosses (raid master tables + the client's Raid* parsers; schemas in claude_sessions / recomp JOURNAL).

Shared raids (2026-10-14, rules from the KHUX Wiki "Raid Boss" page): a boss lives in the `raids` table and is
shared with the discoverer's PARTY - members see it in /raid/list and may join; every player who fought it is a
`raid_participants` row with their damage. Rewards when it falls: Victory (rewardId) to every participant, MVP
(mvpRewardId) to the top damage dealer and to the host (discoverer) - once if the same player -, All Points
Defeated (destroyAllRewardId) to everyone when every part was destroyed. A boss the player summoned goes up a
level each time they defeat it; levels reset monthly. Discovery: after ~75 defeated enemies (68-82 per cycle).

A raid is discovered on the first clear of a story stage whose stage row has `raidBoss` (a raidSetting id):
/stage/clear raises userPoint.raidPoint (SceneBattleResult::startResult sets the client's "raid discovered"
flag when raidPoint grows), then /raid answers raidStatus 3 with the boss, which SceneAdventureSelect shows on
the map. The raid lives in the user's state document under "raid":
  {raidId, stageId, settingId, enemyId, level, hp: [per part], maxHp: [...], end, status, damage}

raidStatus (SceneAdventureSelect::initStageRaidChack): 1 defeated (reward popup), 2 escaped, 3 appeared/active,
0 nothing.
"""
import json
import random
import time

from .master import MASTER_JSON_DATA
from .models import Raid, RaidParticipant

KILLS_MIN, KILLS_MAX = 68, 82        # enemies to defeat before a boss appears (wiki: "trending toward 75")
# story quest numbers (1-based story order) that always / never bring a boss (KHUX Wiki Talk:Raid Boss)
ALWAYS_SPAWN_QUESTS = {24, 66, 102, 183, 200, 230, 660, 715}
NEVER_SPAWN_QUESTS = {3}

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


def build(stage_id, setting_id, level=1, now=None, rare=False):
    """A new boss record for `stage_id` from raidSetting `setting_id` at `level`: its normal boss, or its Omega
    (rareBossId, rareBossUpTime, rareUseAp) when `rare`."""
    now = now or time.time()
    setting = _row("raidSetting", "raidSettingId", setting_id)
    if not setting:
        return None
    enemy = _row("raidEnemy", "raidEnemyId", setting["rareBossId"] if rare else setting["bossId"])
    if not enemy:
        return None
    ids = part_enemy_ids(enemy)
    hp = [_row("raidEnemy", "raidEnemyId", i)["hp"][_level_index(enemy, level)] for i in ids]
    return {
        "stageId": stage_id, "settingId": setting_id, "enemyId": enemy["raidEnemyId"], "level": level,
        "useAp": setting.get("rareUseAp" if rare else "useAp", 10), "rare": bool(rare),
        "hp": hp, "maxHp": list(hp),
        # bossUpTime is in MINUTES: normal bosses have a 10-minute limit, Omega 20 (wiki / 2016 guides)
        "end": now + 60 * max(setting.get("rareBossUpTime" if rare else "bossUpTime", 10), 1),
        "status": RAID_STATUS_ACTIVE, "damage": 0,
    }


def part_enemy_ids(enemy):
    """Raid boss parts as the client numbers them (partsId 1..n): the boss itself, then its `validParts`
    sub-parts. Each sub-part is its own raidEnemy row (name str_rdb_dummy, own HP growth/attribute), e.g.
    Behemoth 3 -> [3, 30002], Darkside 1 -> [1, 10002, 10003]. At most 6 (RaidBase::Info has 6 slots)."""
    ids = [enemy["raidEnemyId"]]
    for pid in enemy.get("parts", [])[:enemy.get("validParts", 0)]:
        if _row("raidEnemy", "raidEnemyId", pid):
            ids.append(pid)
    return ids[:6]


def refresh(raid, now=None):
    """Fill sub-parts of older records and apply the escape when the time ran out."""
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


# --------------------------------------------------------------------------- shared storage (raids table)
def load(row):
    d = json.loads(row.data or "{}")
    d["raidId"] = row.id
    return refresh(d)


def save(row, d):
    row.status = d["status"]
    row.data = json.dumps({k: v for k, v in d.items() if k != "raidId"})


def by_id(db, raid_id):
    return db.get(Raid, int(raid_id or 0))


def own(db, uid):
    """The player's latest discovered boss (row) or None."""
    return db.query(Raid).filter(Raid.discoverer_id == uid).order_by(Raid.id.desc()).first()


def visible(db, uids, now=None):
    """Active bosses discovered by these players (the player + their party), as (row, record)."""
    out = []
    for row in db.query(Raid).filter(Raid.discoverer_id.in_(list(uids)), Raid.status == RAID_STATUS_ACTIVE):
        d = load(row)
        save(row, d)                         # persist an escape
        if d["status"] == RAID_STATUS_ACTIVE:
            out.append((row, d))
    return out


def participant(db, raid_id, uid, create=True):
    p = db.get(RaidParticipant, (raid_id, uid))
    if p is None and create:
        p = RaidParticipant(raid_id=raid_id, user_id=uid, damage=0, rewarded=False)
        db.add(p)
        db.flush()
    return p


def participants(db, raid_id):
    return db.query(RaidParticipant).filter(RaidParticipant.raid_id == raid_id).all()


def create(db, uid, stage_id, setting_id, level, rare=False):
    d = build(stage_id, setting_id, level, rare=rare)
    if not d:
        return None, None
    row = Raid(discoverer_id=uid, status=d["status"], data="{}")
    db.add(row)
    db.flush()
    save(row, d)
    participant(db, row.id, uid)             # the host always shares the rewards
    return row, load(row)


def migrate_legacy(db, st, uid):
    """Raids stored in the player's own state document before shared raids: move them to the table."""
    old = st.pop("raid", None)
    if old and not own(db, uid):
        row = Raid(discoverer_id=uid, status=old.get("status", RAID_STATUS_NONE), data="{}")
        db.add(row)
        db.flush()
        save(row, {k: v for k, v in old.items() if k not in ("raidId", "rewarded", "seen_escape")})
        p = participant(db, row.id, uid)
        p.damage, p.rewarded = int(old.get("damage", 0)), bool(old.get("rewarded"))


def boss_level(st, enemy_id):
    """The level of this boss for its summoner this month (wiki: +1 per defeat of a boss you summoned, reset
    monthly)."""
    rec = st.get("raid_levels", {}).get(str(enemy_id))
    return rec["level"] if rec and rec.get("month") == time.strftime("%Y-%m", time.gmtime()) else 1


def level_up(st, enemy_id):
    month = time.strftime("%Y-%m", time.gmtime())
    st.setdefault("raid_levels", {})[str(enemy_id)] = {"level": boss_level(st, enemy_id) + 1, "month": month}


def kills_threshold(st, power=10000):
    """Enemies to defeat before the next boss (rolled once per cycle, scaled by a raid-encounter campaign)."""
    if not st.get("raid_kill_goal"):
        st["raid_kill_goal"] = random.randint(KILLS_MIN, KILLS_MAX)
    return max(1, st["raid_kill_goal"] * 10000 // max(power, 1))


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


def reward_rows(raid, mvp=True):
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
        if key == "partAllId" and not all_parts or key == "mvpId" and not mvp:
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


# --------------------------------------------------------------------------- Omega bosses
def omega_due(st, setting):
    """Whether this discovery is the setting's Omega (raidEnemy.rare 2; the client draws Raid_Rare_Pop for it).
    The client never reads rareUpType / rareUpTypeArg, so the rule is ours. GUESS: R5:
      rareUpType 3: after the player has defeated the trigger boss (rareUpTriggerBossId) rareUpTypeArg times this
                    month since their last Omega (10000 on the early-quest settings = never);
      rareUpType 2: a 1-in-rareUpTypeArg chance per discovery;
      rareUpType 1: always.
    Settings whose Omega is the boss itself (event rows) never switch."""
    rare_id, trigger = setting.get("rareBossId", 0), setting.get("rareUpTriggerBossId", 0)
    if not rare_id or rare_id == setting.get("bossId") or not _row("raidEnemy", "raidEnemyId", rare_id):
        return False
    kind, arg = setting.get("rareUpType", 0), max(int(setting.get("rareUpTypeArg", 0) or 0), 1)
    if kind == 1:
        return True
    if kind == 2:
        return random.randrange(arg) == 0
    if kind == 3:
        month = time.strftime("%Y-%m", time.gmtime())
        mark = st.get("raid_omega_mark", {}).get(str(trigger))
        since = mark["defeats"] if mark and mark.get("month") == month else 0
        return boss_level(st, trigger) - 1 - since >= arg
    return False


def omega_spawned(st, setting):
    """Restart the rareUpType 3 count after an Omega appears."""
    trigger = setting.get("rareUpTriggerBossId", 0)
    st.setdefault("raid_omega_mark", {})[str(trigger)] = {
        "defeats": boss_level(st, trigger) - 1, "month": time.strftime("%Y-%m", time.gmtime())}
