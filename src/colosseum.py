"""Colosseum progress (actions 114-118, rankings 127/128).

Master data: `colosseumStage` (one row per season: stageId[] played in a loop, headColosseumId..termColosseumId)
and `colosseum` (one row per rank: `round`, `ap`, `arrivalStageCount`, per-stage reward, rank-completion reward).

The client works in ranks (a `colosseum` row's `round`, not its colosseumId) and stage counts (1-based within the
rank; reaching `arrivalStageCount` completes the rank, 999 = the endless last rank). The original server's rule
for which stages to offer is not in the client; we offer one row: the next stage of the player's current rank,
with stageId = season.stageId[(stageCount - 1) % loopStageCount] (the same loop StageManager::getColosseumRiseLevel
uses for the enemy level bonus).

Per-user state lives in state.py's document under "colosseum" -> "<colosseumStageId>@<YYYY-MM>" (a new record
each month: seasons reset on the 1st - KHUX Wiki "Coliseum Quests", guides 2015-16).

Skip (wiki: "If all enemy groups get defeated within 1 turn, the next several rounds will be unlocked at once.
Completing any round will lock skipped rounds."; "you will still get the Coliseum coins from the round you skip";
"The least number of rounds you can skip is 3"): the client flags a one-turn win with isSkip; the tier's
`excellentUnlockCount` (18, 18, 16, 14, 9, 7, 4, 3, 3, 3 - matches the wiki's Skip column) further rounds are then
offered at once (the client lists 2+ rows and shows tutorial popup 25). Clearing round k credits every round up to
k (their coins too) and locks the rest. A skip never crosses the tier's last round.
In the 1.0.1 era a skip unlocked exactly SKIP_ROUNDS = 10 rounds (the user; the per-tier counts on the wiki are a
later change). `excellentUnlockCount` (18/18/16/14/9/7/4/3/3/3) is therefore something else - meaning unknown.
"""
import time
from datetime import datetime

# Seasons are monthly (wiki). The master seasons are dated 2015-16, so the season served rotates by calendar month
# through the ones whose stage maps (stage/cl_stg*.bin) are in the game data (500/600/1200-1500 lack them).
# GUESS: C2 (the rotation itself; the client still shows the master's 2015-16 dates).
SEASONS_WITH_MAPS = [1, 2, 100, 200, 300, 400, 700, 800, 900, 1000, 1100]


def current_season(now=None):
    t = time.gmtime(now or time.time())
    return SEASONS_WITH_MAPS[(t.tm_year * 12 + t.tm_mon - 1) % len(SEASONS_WITH_MAPS)]


def month_key(season_id, now=None):
    return f"{season_id}@{time.strftime('%Y-%m', time.gmtime(now or time.time()))}"


CURRENT_SEASON = None   # resolved per call (current_season())
STATUS_OPEN = 1          # GUESS: C8. colosseumInfo.status: 1 lists the stages, 2 shows a "closed" text instead
ENDLESS = 999            # arrivalStageCount of the last rank
SKIP_ROUNDS = 10         # rounds a one-turn win unlocks (user, 1.0.1 era)


def _master(table):
    from .master import MASTER_JSON_DATA
    return MASTER_JSON_DATA.get(table, [])


def season(season_id=None):
    season_id = season_id or current_season()
    return next((r for r in _master("colosseumStage") if r.get("colosseumStageId") == season_id), None)


def ranks(season_id=None):
    """colosseum rows of the season, by round."""
    s = season(season_id or current_season()) or {}
    lo, hi = s.get("headColosseumId", 0), s.get("termColosseumId", -1)
    return sorted((r for r in _master("colosseum") if lo <= r.get("colosseumId", 0) <= hi), key=lambda r: r["round"])


def rank_row(rank, season_id=None):
    return next((r for r in ranks(season_id) if r["round"] == rank), None)


def progress(st, season_id=None):
    """The user's record for this month's season (created at rank 1)."""
    season_id = season_id or current_season()
    first = (ranks(season_id) or [{"round": 1}])[0]["round"]
    rec = st.setdefault("colosseum", {}).setdefault(month_key(season_id), {
        "rank": first, "stageCount": 0, "total": 0, "rewardRanks": [], "arrival": {}, "pending": None})
    rec.setdefault("skip_until", 0)
    rec.setdefault("reached", "")
    return rec


def info(season_id=None):
    return {"colosseumStageId": season_id or current_season(), "status": STATUS_OPEN}


def user_colosseum(rec):
    return {"userRank": rec["rank"], "userStageCount": rec["stageCount"], "userStageTotalCount": rec["total"]}


def next_stage(rec, season_id=None):
    """The rounds offered (colosseumStages): the next round of the current tier (wiki: you cannot go back), or
    after a skip every unlocked round up to rec["skip_until"]."""
    s, row = season(season_id), rank_row(rec["rank"], season_id)
    if not s or not row:
        return []
    ids = s.get("stageId") or []
    loop = max(min(s.get("loopStageCount") or len(ids), len(ids)), 1)
    first = rec["stageCount"] + 1
    last = max(first, rec.get("skip_until", 0))
    return [{"rank": rec["rank"], "stageCount": c, "stageId": ids[(c - 1) % loop], "useAp": row.get("ap", 0)}
            for c in range(first, last + 1)]


def clear(rec, round_cleared=None, is_skip=False, season_id=None):
    """Record a won round. Clearing round k credits every round from the next one up to k (skipped rounds pay
    their coins too) and locks the other unlocked rounds; a one-turn win (is_skip) unlocks the tier's
    excellentUnlockCount further rounds. Returns (cleared [{rank, stageCount}] - one per credited round, the
    client shows a reward row per entry -, stage reward row or None, how many stage rewards, rank reward row or
    None). The tier reward comes once, when its last round is credited (C3); the 999 tier is endless (C4)."""
    row = rank_row(rec["rank"], season_id) or {}
    arrival = row.get("arrivalStageCount", ENDLESS)
    top = max(rec["stageCount"] + 1, rec.get("skip_until", 0))
    k = min(max(int(round_cleared or rec["stageCount"] + 1), rec["stageCount"] + 1), top)
    if arrival != ENDLESS:
        k = min(k, arrival)
    cleared = [{"rank": rec["rank"], "stageCount": c} for c in range(rec["stageCount"] + 1, k + 1)]
    rec["total"] += len(cleared)
    rec["stageCount"] = k
    rec["skip_until"] = 0
    rec["reached"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stage_reward = row if row.get("validStageReward") else None
    rank_reward = None
    if arrival != ENDLESS and rec["stageCount"] >= arrival:
        if rec["rank"] not in rec["rewardRanks"]:
            rec["rewardRanks"].append(rec["rank"])
            rank_reward = row if row.get("validReward") else None
        rec["arrival"][str(rec["rank"])] = rec["reached"]
        nxt = [r["round"] for r in ranks(season_id) if r["round"] > rec["rank"]]
        if nxt:
            rec["rank"], rec["stageCount"] = nxt[0], 0
    elif is_skip:
        unlock = SKIP_ROUNDS
        rec["skip_until"] = rec["stageCount"] + unlock if arrival == ENDLESS else min(rec["stageCount"] + unlock, arrival)
    return cleared, stage_reward, len(cleared), rank_reward
