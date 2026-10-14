"""Ranking periods and rewards (MypageInfo.rankingRewards flags -> /ranking/reward/check 130).

Client behaviour (decompile, see recomp/JOURNAL.md 2026-10-14):
- 56 raises a flag per type; MyPage then calls 130 {type} for each raised flag (type 1 = Lux weekly/monthly,
  2 = Party, 3 = Coliseum, 4 = Lux) and shows one result popup per lastRankingResults entry.
- The popup picks the reward row ITSELF from master data: master `ranking` row lastRankingId -> rankingReward ids
  startRank..endRank (categories 1, 3, 4) or unionStartRank/EndRank[lastUnionRank-1] (categories 2, 5; union place
  must be 1..5); the first row with startRank <= lastRank <= endRank. The server grants exactly that row in the
  same 130 response ("rankingReward" object).
- openRankingIds = the ranking id open now for the type (Party title dates, the reward-list button).

Rankings in 1.0.1: Lux = category 5 (weekly, union-aware), Party = category 3 (weekly), Coliseum = category 4
(monthly). Periods use party.week_start / month_start (08:00 server time). Every period has its own master row
(dated_rows, appended to the served `ranking` table at load): its dates are the period's (as UTC, like every time
the client is sent), its reward fields those of the category's 2015-16 rows in rotation (GUESS: RK5). Rows cover
DATED_YEARS; changing KHUX_WEEK_START or the server's time zone changes them - bump master_rev then.
"""
from datetime import datetime, timedelta

from .models import RankingPeriod, User
from . import party as gparty

LUX, PARTY, COLISEUM = 5, 3, 4
TYPE_CATEGORIES = {1: (1, 2), 2: (PARTY,), 3: (COLISEUM,), 4: (LUX,)}
FLAG_OF_CATEGORY = {1: "rankingLuxWeekly", 2: "rankingLuxMonthly", LUX: "rankingLux", PARTY: "rankingParty",
                    COLISEUM: "rankingColosseum"}
EPOCH = datetime(2015, 1, 5, 8, 0)          # a Monday; weekly period numbers count from here


def _master(table):
    from .master import MASTER_JSON_DATA
    return MASTER_JSON_DATA.get(table, [])


DATED_BASE = 1000000                        # dated rankingId = category * DATED_BASE + period number
DATED_YEARS = (2025, 2035)


def rows(category, table=None):
    """The category's original (2015-16) rows."""
    return sorted((r for r in (table if table is not None else _master("ranking"))
                   if r.get("category") == category and r["rankingId"] < DATED_BASE),
                  key=lambda r: r["rankingId"])


def dated_rows(table):
    """One ranking row per period of DATED_YEARS for the Lux, Party and Coliseum rankings."""
    out = []
    first, last = datetime(DATED_YEARS[0], 1, 1, 12), datetime(DATED_YEARS[1], 12, 31, 12)
    for cat in (LUX, PARTY, COLISEUM):
        base = rows(cat, table)
        if not base:
            continue
        seen, t = set(), first
        while t <= last:
            number, start, end = period_bounds(cat, t)
            if number not in seen:
                seen.add(number)
                src = base[number % len(base)]
                out.append(dict(src, rankingId=cat * DATED_BASE + number,
                                startDatetime=gparty.fmt_local(start),
                                endDatetime=gparty.fmt_local(end - timedelta(seconds=1))))
            t += timedelta(days=1)
    return out


def ranking_row(ranking_id):
    return next((r for r in _master("ranking") if r.get("rankingId") == ranking_id), None)


def reward_row(reward_id):
    return next((r for r in _master("rankingReward") if r.get("rankingRewardId") == reward_id), None)


# --------------------------------------------------------------------------- periods
def period_bounds(category, now=None):
    """(number, start, end) of the CURRENT period of a category."""
    now = now or datetime.now()
    if category == COLISEUM:
        start = gparty.month_start(now)
        end = gparty.month_start((start + timedelta(days=32)).replace(day=1, hour=gparty.ROLLOVER_HOUR))
        return start.year * 12 + start.month - 1, start, end
    start = gparty.week_start(now)
    return int((start - EPOCH).days // 7), start, start + timedelta(days=7)


def ranking_id_for(category, number):
    """The period's own dated row; the rotation row when the period is outside DATED_YEARS."""
    rid = category * DATED_BASE + number
    if ranking_row(rid):
        return rid
    rs = rows(category)
    return rs[number % len(rs)]["rankingId"] if rs else 0


def open_ranking_ids(rtype, now=None):
    out = []
    for cat in TYPE_CATEGORIES.get(rtype, ()):
        if cat in (1, 2):                    # the old Lux weekly / monthly rankings are not run (GUESS: RK6)
            continue
        number, _, _ = period_bounds(cat, now)
        rid = ranking_id_for(cat, number)
        if rid:
            out.append(rid)
    return out


# --------------------------------------------------------------------------- reward row: the client's own rule
def reward_id_for(ranking_id, rank, union_rank):
    r = ranking_row(ranking_id)
    if not r or rank <= 0:
        return 0
    if r["category"] in (2, 5):
        u = min(max(union_rank, 1), 5) - 1
        lo, hi = r["unionStartRank"][u], r["unionEndRank"][u]
    else:
        lo, hi = r["startRank"], r["endRank"]
    for rid in range(lo, hi + 1):
        row = reward_row(rid)
        if row and row["startRank"] <= rank <= row["endRank"]:
            return rid
    return 0


def reward_items(reward_id):
    """[(type, id, num, skillType, skillId, skillLv)] of a rankingReward row (only its first validReward slots)."""
    row = reward_row(reward_id)
    if not row:
        return []
    n = min(int(row.get("validReward", 0) or 0), 10)
    return [(row["type"][k], row["id"][k], row["num"][k], row["skillType"][k], row["skillId"][k], row["skillLv"][k])
            for k in range(n)]


# --------------------------------------------------------------------------- closing
def _union_places(db, start, end):
    """{unionId: place 1..5}: unions by Lux in the window; unions without Lux after them, by id."""
    totals = gparty.lux_between(db, start, end, "union")
    order = [u for u, _, _ in gparty.ranked(totals)]
    order += [u for u in range(1, 6) if u not in order]
    return {u: min(i + 1, 5) for i, u in enumerate(order[:5])}


def close_due(db, results_sink, now=None):
    """Close the last finished period of each category once. results_sink(user_id, result_dict) stores a
    player's result. Only players who took part (Lux > 0 / a Coliseum record) get one."""
    for cat in (LUX, PARTY, COLISEUM):
        number, start, _ = period_bounds(cat, now)
        prev = number - 1
        if db.get(RankingPeriod, (cat, prev)):
            continue
        if cat == COLISEUM:
            p_start = gparty.month_start(start - timedelta(days=1))
        else:
            p_start = start - timedelta(days=7)
        rid = ranking_id_for(cat, prev)
        db.add(RankingPeriod(category=cat, period=prev, ranking_id=rid))
        db.flush()
        if not rid:
            continue
        unions = _union_places(db, p_start, start)
        out = []
        if cat == LUX:
            for uid, _, rank in gparty.ranked(gparty.lux_between(db, p_start, start, "user")):
                u = db.get(User, uid)
                out.append((uid, rank, unions.get(u.union_id if u else 0, 5)))
        elif cat == PARTY:
            party_rank = {pid: rank for pid, _, rank in gparty.ranked(gparty.lux_between(db, p_start, start, "party"))}
            for uid, pid in gparty.contributors(db, p_start, start):
                if pid in party_rank:
                    u = db.get(User, uid)
                    out.append((uid, party_rank[pid], unions.get(u.union_id if u else 0, 5)))
        else:
            out = coliseum_results(db, p_start)
        for uid, rank, union_rank in out:
            results_sink(uid, {"category": cat, "rankingId": rid, "rank": int(rank), "unionRank": int(union_rank),
                               "rewardId": reward_id_for(rid, rank, union_rank), "status": "pending"})


def coliseum_results(db, month_start_dt):
    """[(user_id, rank, union_place)] of a finished Coliseum month: tier, round, earliest (as the live ranking)."""
    import json
    from .models import UserState
    from . import colosseum as gcol
    key = gcol.month_key(gcol.current_season(month_start_dt.timestamp()), month_start_dt.timestamp())
    recs = []
    for us in db.query(UserState).all():
        try:
            rec = (json.loads(us.data or "{}").get("colosseum") or {}).get(key)
        except ValueError:
            rec = None
        if rec and rec.get("total"):
            recs.append((us.user_id, rec))
    recs.sort(key=lambda r: (-r[1]["rank"], -r[1]["stageCount"], r[1].get("reached") or "9999"))
    return [(uid, i + 1, 1) for i, (uid, _) in enumerate(recs)]
