"""Parties (guilds) and the Lux / party / union rankings: the shared, multi-user state (models.Party*, LuxLedger).

Wire shapes come from the client's parsers (Party::init, UserParty, Applicant, Offer, PartyEx; see handlers.py
"multiplayer"). Rules the client does not dictate are GUESSes recorded in GUESSES.md (PT*, RK*).
"""
from datetime import datetime, timedelta

from sqlalchemy import func

from .models import LuxLedger, Party, PartyApplication, PartyMember, PartyOffer, User

NEVER = "2000-01-01 00:00:00"
PENDING, AGREED, REJECTED, CANCELLED = 0, 1, 2, 3
# agreeType (client enum, ScenePartyCreate / search popup): 1 not accepting, 2 approval required, 3 auto-approve
AGREE_CLOSED, AGREE_APPROVAL, AGREE_AUTO = 1, 2, 3
# party rank tiers (img/partyRank/Party_RankIcon%d.png): 1 Diamond ... 5 Bronze - never 0
RANK_BRONZE = 5
FAILED_FULL, FAILED_TOO_MANY = 1, 2          # GUESS: PT6 (the client only checks failedStatus != 0)


def _misc(misc_id, default):
    from .master import MASTER_JSON_DATA
    return next((m["value"] for m in MASTER_JSON_DATA.get("misc", []) if m.get("miscId") == misc_id), default)


def max_members():
    return 30                                # hard-coded in the client (ScenePartyTop "%d/%d", 0016:13292)


def max_applications():
    return _misc(803, 5)                     # GUESS: PT1


def max_admins():
    return _misc(802, 10)                    # GUESS: PT2


def _chat_base():
    from .chat import BASE
    return BASE


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else NEVER


def fmt_local(dt):
    """A naive server-LOCAL datetime (week/month boundaries) as the UTC the client expects: it shows every time
    the server sends as UTC converted to the device's zone (serverTime is UTC too)."""
    if not dt:
        return NEVER
    return datetime.utcfromtimestamp(dt.timestamp()).strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------- lookups
def membership(db, uid):
    return db.get(PartyMember, uid) if uid else None


def party_of(db, uid):
    m = membership(db, uid)
    return db.get(Party, m.party_id) if m else None


def party_id_of(db, uid):
    m = membership(db, uid)
    return m.party_id if m else 0


def members(db, party_id):
    return db.query(PartyMember).filter(PartyMember.party_id == party_id).order_by(PartyMember.join_date).all()


def admins(p):
    return [int(x) for x in (p.admin_ids or "").split(",") if x]


def is_staff(p, uid):
    """Leader or admin (GUESS: PT7 - who may accept, reject, invite, expel)."""
    return p is not None and (p.leader_user_id == uid or uid in admins(p))


# --------------------------------------------------------------------------- wire objects
def party_obj(db, p):
    """Party::init: every field required."""
    return {"partyId": p.id, "unionId": p.union_id or 0, "rank": party_rank(db, p.id), "name": p.name or "",
            "playStyle": p.play_style or 0, "agreeType": p.agree_type or 0, "message": p.message or "",
            "memberCount": len(members(db, p.id)), "leaderUserId": p.leader_user_id or 0,
            "adminUserIds": admins(p), "leaderAppointDate": fmt(p.leader_appoint_at),
            "newcomerDate": fmt(p.newcomer_at), "chatId": p.id or 0,
            "chatEndpointUrl": _chat_base() if p.id else ""}


def user_party(db, uid):
    """UserParty (top-level "userParty"). partyId 0 = not in a party; otherwise "party" must be sent too."""
    m = membership(db, uid)
    p = db.get(Party, m.party_id) if m else None
    if not p:
        return {"userId": uid, "partyId": 0, "isJoin": 0, "isLeader": 0, "isAdmin": 0, "flagFirstReward": 0,
                "joinDate": NEVER}
    return {"userId": uid, "partyId": p.id, "isJoin": 1, "isLeader": int(p.leader_user_id == uid),
            "isAdmin": int(uid in admins(p)), "flagFirstReward": m.flag_first_reward or 0,
            "joinDate": fmt(m.join_date)}


def with_party(db, uid):
    """{"userParty": ..., ["party": ...]}: every response carrying a userParty with partyId != 0 needs "party"
    too (UserParty::parse fails without it)."""
    up = user_party(db, uid)
    out = {"userParty": up}
    if up["partyId"]:
        out["party"] = party_obj(db, db.get(Party, up["partyId"]))
    return out


def applicant_obj(a):
    return {"userId": a.user_id, "partyId": a.party_id, "message": a.message or "", "status": a.status,
            "applicationDate": fmt(a.created_at), "agreeDate": fmt(a.agreed_at), "partyApplicantId": a.id}


def offer_obj(o):
    return {"userId": o.user_id, "partyId": o.party_id, "message": o.message or "", "status": o.status,
            "offerDate": fmt(o.created_at), "agreeDate": fmt(o.agreed_at), "partyOfferId": o.id}


# --------------------------------------------------------------------------- lifecycle
def _join(db, uid, p, first_reward=0):
    for a in db.query(PartyApplication).filter(PartyApplication.user_id == uid,
                                               PartyApplication.status == PENDING):
        a.status = CANCELLED                 # joining a party withdraws the other applications
    db.add(PartyMember(user_id=uid, party_id=p.id, join_date=datetime.utcnow(), flag_first_reward=first_reward))
    p.newcomer_at = datetime.utcnow()
    db.flush()


def create(db, user, name, message, play_style, agree_type):
    if membership(db, user.id):
        leave(db, user.id)
    p = Party(union_id=user.union_id or 0, name=name, message=message, play_style=play_style,
              agree_type=agree_type, leader_user_id=user.id)
    db.add(p)
    db.flush()
    _join(db, user.id, p)
    return p


def update(db, uid, name, message, play_style, agree_type):
    """Leader or moderator (admin) may edit name, play style, approval and message (2016 guide)."""
    p = party_of(db, uid)
    if p and is_staff(p, uid):
        p.name, p.message, p.play_style, p.agree_type = name, message, play_style, agree_type
    return p


def leave(db, uid):
    """Leave the party. A leaving leader hands over to an admin, else the longest-standing member; an empty
    party is disbanded (GUESS: PT7)."""
    m = membership(db, uid)
    if not m:
        return
    p = db.get(Party, m.party_id)
    db.delete(m)
    db.flush()
    rest = members(db, p.id) if p else []
    if p and not rest:
        db.delete(p)
    elif p:
        p.admin_ids = ",".join(str(a) for a in admins(p) if a != uid)
        if p.leader_user_id == uid:
            heirs = [a for a in admins(p) if any(r.user_id == a for r in rest)] or [rest[0].user_id]
            set_leader(p, heirs[0])
    db.flush()


def set_leader(p, uid):
    p.admin_ids = ",".join(str(a) for a in admins(p) if a != uid)
    p.leader_user_id = uid
    p.leader_appoint_at = datetime.utcnow()


def appoint(p, uid):
    if uid != p.leader_user_id and uid not in admins(p) and len(admins(p)) < max_admins():
        p.admin_ids = ",".join(str(a) for a in admins(p) + [uid])


def dismiss(p, uid):
    p.admin_ids = ",".join(str(a) for a in admins(p) if a != uid)


def expel(db, p, uid):
    m = membership(db, uid)
    if m and m.party_id == p.id and uid != p.leader_user_id:
        db.delete(m)
        dismiss(p, uid)
        db.flush()


# --------------------------------------------------------------------------- applications / offers
def apply(db, user, party_id, message):
    """(failedStatus, application or None). agreeType 3 (auto-approve) takes the player at once, 2 waits for the
    leader / admins, 1 (not accepting) refuses."""
    p = db.get(Party, party_id)
    if p is None or len(members(db, p.id)) >= max_members() or (p.agree_type or 0) == AGREE_CLOSED:
        return FAILED_FULL, None
    pending = db.query(PartyApplication).filter(PartyApplication.user_id == user.id,
                                                PartyApplication.status == PENDING).count()
    if pending >= max_applications():
        return FAILED_TOO_MANY, None
    a = PartyApplication(user_id=user.id, party_id=p.id, message=message, status=PENDING)
    db.add(a)
    db.flush()
    if (p.agree_type or 0) == AGREE_AUTO:     # auto-approve: the client goes straight to the party top
        if membership(db, user.id):
            leave(db, user.id)
        _join(db, user.id, p)
        a.status, a.agreed_at = AGREED, datetime.utcnow()
    return 0, a


def offer(db, party, uid, message):
    """failedStatus for inviting uid (0 = sent). A party can have 30 invitations out (footer 103850016 (30, 72))."""
    if len(members(db, party.id)) >= max_members():
        return FAILED_FULL
    if db.query(PartyOffer).filter(PartyOffer.party_id == party.id, PartyOffer.status == PENDING).count() >= 30:
        return FAILED_TOO_MANY
    if membership(db, uid) and membership(db, uid).party_id == party.id:
        return FAILED_FULL
    db.add(PartyOffer(user_id=uid, party_id=party.id, message=message, status=PENDING))
    db.flush()
    return 0


def accept_application(db, a):
    p = db.get(Party, a.party_id)
    if a.status != PENDING or p is None or len(members(db, p.id)) >= max_members():
        return False
    if membership(db, a.user_id):
        leave(db, a.user_id)
    _join(db, a.user_id, p)
    a.status, a.agreed_at = AGREED, datetime.utcnow()
    return True


def accept_offer(db, o):
    p = db.get(Party, o.party_id)
    if o.status != PENDING or p is None or len(members(db, p.id)) >= max_members():
        return False
    if membership(db, o.user_id):
        leave(db, o.user_id)
    _join(db, o.user_id, p)
    o.status, o.agreed_at = AGREED, datetime.utcnow()
    return True


def expire(db, hours=72):
    """Pending applications / offers lapse after 72 hours: the client's own text (ScenePartyManagement footer
    103810008 "You can send up to 5 requests. Requests that have not been responded to within 72 hours will
    automatically be canceled."; invitations: 103850016 with (30, 72))."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    for cls in (PartyApplication, PartyOffer):
        for x in db.query(cls).filter(cls.status == PENDING, cls.created_at < cutoff):
            x.status = CANCELLED


def search(db, play_style=0, agree_type=0, scale=0, rank=0, exclude_party=0):
    """Parties with room and open to joins; each filter applies when non-zero (0 = "no preference").
    scale (PartyScale): 1 = 1-10 members, 2 = 11-20, 3 = 21-29."""
    out = []
    for p in db.query(Party).order_by(Party.newcomer_at.desc()).limit(300):
        n = len(members(db, p.id))
        if p.id == exclude_party or n >= max_members() or (p.agree_type or 0) == AGREE_CLOSED:
            continue
        if (play_style and p.play_style != play_style) or (agree_type and p.agree_type != agree_type):
            continue
        if scale and not (1 + 10 * (scale - 1) <= n <= 10 * scale):
            continue
        if rank and party_rank(db, p.id) != rank:
            continue
        out.append(p)
    return out[:30]


# --------------------------------------------------------------------------- rankings
# The week turns over at 08:00 SERVER LOCAL time on the server's default weekday (user, 2026-10-14): Monday unless
# the host sets KHUX_WEEK_START (0 = Monday .. 6 = Sunday). Months turn over at 08:00 on the 1st.
import os as _os
WEEK_START_DAY = int(_os.environ.get("KHUX_WEEK_START", "0")) % 7
ROLLOVER_HOUR = 8


def week_start(now=None):
    """Start of the current ranking week (naive server-local datetime)."""
    now = now or datetime.now()
    start = (now - timedelta(days=(now.weekday() - WEEK_START_DAY) % 7)).replace(
        hour=ROLLOVER_HOUR, minute=0, second=0, microsecond=0)
    return start if start <= now else start - timedelta(days=7)


def month_start(now=None):
    now = now or datetime.now()
    start = now.replace(day=1, hour=ROLLOVER_HOUR, minute=0, second=0, microsecond=0)
    return start if start <= now else (start - timedelta(days=1)).replace(day=1)


def record_lux(db, user, lux):
    if lux and user is not None:
        db.add(LuxLedger(user_id=user.id, union_id=user.union_id or 0, party_id=party_id_of(db, user.id),
                         lux=int(lux), at=datetime.now()))


def lux_since(db, since, group, key=None):
    """{group value: Lux} since a time; group = "user" / "party" / "union"."""
    col = {"user": LuxLedger.user_id, "party": LuxLedger.party_id, "union": LuxLedger.union_id}[group]
    q = db.query(col, func.sum(LuxLedger.lux)).filter(LuxLedger.at >= since).group_by(col)
    return {k: int(v or 0) for k, v in q if k}


def lux_between(db, start, end, group):
    """{group value: Lux} earned in [start, end); group = "user" / "party" / "union"."""
    col = {"user": LuxLedger.user_id, "party": LuxLedger.party_id, "union": LuxLedger.union_id}[group]
    q = db.query(col, func.sum(LuxLedger.lux)).filter(LuxLedger.at >= start, LuxLedger.at < end).group_by(col)
    return {k: int(v or 0) for k, v in q if k}


def contributors(db, start, end):
    """[(user_id, party_id)] who earned Lux for a party in [start, end)."""
    q = db.query(LuxLedger.user_id, LuxLedger.party_id).filter(
        LuxLedger.at >= start, LuxLedger.at < end, LuxLedger.party_id != 0, LuxLedger.lux > 0).distinct()
    return [(u, p) for u, p in q]


def ranked(totals):
    """[(key, lux, rank)] by Lux, ties sharing a rank."""
    rows, last, rank = [], None, 0
    for i, (k, v) in enumerate(sorted(totals.items(), key=lambda kv: -kv[1])):
        if v != last:
            rank, last = i + 1, v
        rows.append((k, v, rank))
    return rows


def party_rank(db, party_id):
    """The party's tier, 1 Diamond .. 5 Bronze, from its place in this week's party ranking (GUESS: PT13 - top
    5% Diamond, 15% Platinum, 35% Gold, 65% Silver, else Bronze). Party Lux = its members' Lux (GUESS: RK3)."""
    rows = ranked(lux_since(db, week_start(), "party"))
    pos = next((r for k, _, r in rows if k == party_id), None)
    if pos is None or not rows:
        return RANK_BRONZE
    frac = pos / len(rows)
    return next(t for t, cut in ((1, .05), (2, .15), (3, .35), (4, .65), (5, 1.01)) if frac <= cut)


def leader_absent(db, p, days=7):
    """The leader may be taken over after 7 days with no login, or logins but no contribution to the party (user,
    2026-10-14). Contribution = Lux earned for the party (lux_ledger). A leader appointed less than 7 days ago
    is never absent."""
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    if p.leader_appoint_at and p.leader_appoint_at > since:
        return False
    leader = db.get(User, p.leader_user_id)
    if leader is None or not leader.last_login_at or leader.last_login_at < since:
        return True
    contributed = db.query(LuxLedger).filter(LuxLedger.user_id == p.leader_user_id, LuxLedger.party_id == p.id,
                                             LuxLedger.at >= since, LuxLedger.lux > 0).count()
    return contributed == 0


def ranking_position(db, since, group, key):
    return next((r for k, _, r in ranked(lux_since(db, since, group)) if k == key), 0)
