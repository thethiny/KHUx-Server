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
`excellentUnlockCount` further rounds are then offered at once (the client lists 2+ rows and shows tutorial popup
25). The count is per tier AND per season: season 2 (Aug 2015) is a flat 10, Sep/Oct 2015 18/15/9/6/3/3, season 1
18/18/16/14/9/7/4/3/3/3, later seasons their own lists. The client shows this same number in the one-turn effect
(StageDirection::all1turn_start, Colosseum_RoundNum), so the server unlocks exactly that many. Clearing round k
credits every round up to k (their coins too) and locks the rest. A skip carries into the next tier at the offset
(the user's memory; the rows carry their own rank): from round 15 of a 20-round tier, a skip of 10 opens rounds
16-20 and rounds 1-5 of the next tier; every tier finished on the way pays its tier reward.
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
SKIP_ROUNDS = 10         # fallback when a tier row has no excellentUnlockCount


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
    if rec.pop("skip_until", 0):               # records from before cross-tier skips: drop the unlock
        rec["skip_to"] = None
    rec.setdefault("skip_to", None)            # [rank, stageCount]: the furthest round a skip unlocked
    rec.setdefault("reached", "")
    return rec


def info(season_id=None):
    return {"colosseumStageId": season_id or current_season(), "status": STATUS_OPEN}


def user_colosseum(rec):
    return {"userRank": rec["rank"], "userStageCount": rec["stageCount"], "userStageTotalCount": rec["total"]}


def _arrival(row):
    return row.get("arrivalStageCount", ENDLESS) if row else ENDLESS


def _next_pos(rank, count, season_id=None):
    """The round after (rank, count): the next tier's round 1 once the tier is full."""
    row = rank_row(rank, season_id)
    if _arrival(row) != ENDLESS and count >= _arrival(row):
        nxt = [r["round"] for r in ranks(season_id) if r["round"] > rank]
        if nxt:
            return nxt[0], 1
        return rank, count
    return rank, count + 1


def _positions(rec, season_id=None):
    """Every round the player may pick: the next one, or after a skip every one up to rec["skip_to"]."""
    pos = [(rec["rank"], rec["stageCount"] + 1)]
    target = tuple(rec["skip_to"]) if rec.get("skip_to") else pos[0]
    while pos[-1] < target and len(pos) < 1000:
        nxt = _next_pos(*pos[-1], season_id)
        if nxt == pos[-1]:
            break
        pos.append(nxt)
    return pos


def next_stage(rec, season_id=None):
    """The rounds offered (colosseumStages): the next round (wiki: you cannot go back), or after a skip every
    unlocked round, possibly into the next tier."""
    s = season(season_id)
    if not s:
        return []
    ids = s.get("stageId") or []
    loop = max(min(s.get("loopStageCount") or len(ids), len(ids)), 1)
    out = []
    for rank, c in _positions(rec, season_id):
        row = rank_row(rank, season_id)
        if row and ids:
            out.append({"rank": rank, "stageCount": c, "stageId": ids[(c - 1) % loop], "useAp": row.get("ap", 0)})
    return out


def clear(rec, round_cleared=None, is_skip=False, season_id=None, rank_cleared=None):
    """Record a won round (rank_cleared, round_cleared). Every unlocked round up to it is credited (skipped rounds
    pay their coins too) and the others lock; a one-turn win (is_skip) then unlocks the cleared tier's
    excellentUnlockCount further rounds, carrying into the next tier. Returns (cleared [{rank, stageCount}] - one
    per credited round, the client shows a reward row per entry -, stage reward rows (one per credited round, of
    that round's tier), tier reward rows (each tier finished now, once ever; C3); the 999 tier is endless (C4)."""
    pos = _positions(rec, season_id)
    want = (int(rank_cleared or pos[0][0]), int(round_cleared or pos[0][1]))
    upto = max((k for k, p in enumerate(pos) if p <= want), default=0)
    cleared, stage_rewards, rank_rewards = [], [], []
    for rank, c in pos[:upto + 1]:
        row = rank_row(rank, season_id) or {}
        cleared.append({"rank": rank, "stageCount": c})
        if row.get("validStageReward"):
            stage_rewards.append(row)
        rec["rank"], rec["stageCount"] = rank, c
        if _arrival(row) != ENDLESS and c >= _arrival(row):
            rec["arrival"][str(rank)] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            if rank not in rec["rewardRanks"]:
                rec["rewardRanks"].append(rank)
                if row.get("validReward"):
                    rank_rewards.append(row)
    rec["total"] += len(cleared)
    rec["skip_to"] = None
    rec["reached"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    last_row = rank_row(rec["rank"], season_id) or {}
    if is_skip:
        target, unlock = (rec["rank"], rec["stageCount"]), int(last_row.get("excellentUnlockCount") or SKIP_ROUNDS)
        for _ in range(unlock):
            nxt = _next_pos(*target, season_id)
            if nxt == target:
                break
            target = nxt
        rec["skip_to"] = list(target)
    # a finished tier moves the player to the next tier's start (round 0 = nothing cleared there yet)
    if _arrival(last_row) != ENDLESS and rec["stageCount"] >= _arrival(last_row):
        nxt = [r["round"] for r in ranks(season_id) if r["round"] > rec["rank"]]
        if nxt:
            rec["rank"], rec["stageCount"] = nxt[0], 0
    return cleared, stage_rewards, rank_rewards
