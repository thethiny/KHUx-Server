"""Events and Special Quests (101 /stage/event, MyPage openBanners, the served evStage master).

Client (1.0.1, see recomp/JOURNAL.md 2026-10-15): the quest-type screen's Events (QuestBut2) and Special Quests
(QuestBut3) buttons call 101 {eventCategory 2 / 1}. The reply lists the running events; the client reads only
`eventCategory` and `bannerUrl` from the evStage master row of each eventStageId. Which events run and when is
entirely the server's call: evStage dates/weekday flags/time slots are never checked by the client.

Schedule (ours, GUESSES E1-E5):
- Special Quests (category 1): the permanent rows (endTime 2037) on their weekday flags (Mythril on weekends, EXP
  Medals: Power on Tuesdays, ...). A server day turns over at the daily reset (12:00 server time, like the login
  bonus). Rows with a groupPattern are time slots: open for validMinute minutes at SLOT_HOURS[groupPattern].
- Events (categories 2, 3): permanent rows (Proud Quests) always; dated rows replayed every year on their original
  month/day (08:00 server time, original length). Category 3 = progressive (stages opened one by one).
  Category 4 (High Score, needs 1.1.3 score rewards) is not run.
- 2015-16 events missing from the 1.1.3 evStage dump get hand-made rows (HANDMADE, ids 9001+), dated from their
  event raid boss settings (raidSetting ids are dates: 151022000 = 2015-10-22).
Banners: the original images lived on cache.sqex-bridge.jp (gone); /event/banner/<id>.png draws one (640x140, the
size of the client's banner frame).
"""
import io
import json
import os
from datetime import datetime, timedelta

from . import party as gparty

BANNER_URL = "http://api.sp.kingdomhearts.com/event/banner/{}.png"
WEEK = ("weekMonday", "weekTuesday", "weekWednesday", "weekThursday", "weekFriday", "weekSaturday", "weekSunday")
BENEFIT = tuple("benefit" + k[4:] for k in WEEK)
PERMANENT_YEAR = "2030"           # rows ending after this are permanent (the dump has 2037)
PERMANENT_ERA_END = "2016-01-01"  # permanent rows that started later (2016 Daily Challenges, Moogle O' Glory) are off
DAY_RESET_HOUR = 12               # the server day (login bonus, daily reset): 12:00 server time
ROLLOVER_HOUR = 8                 # dated events open at 08:00 server time, like the ranking weeks
# time slots (evStage.groupPattern -> opening hour, server time); the evGroupPattern table is lost. GUESS: E3
SLOT_HOURS = {1000: 12, 1001: 18, 1002: 21,
              1003: 9, 1004: 13, 1005: 20, 1006: 10, 1007: 14, 1008: 21, 1009: 11, 1010: 15, 1011: 22}

# 2015-16 events with stages but no evStage row (GUESS: E2): (id, name, stages, start MM-DD, days)
HANDMADE = [
    (9001, "Trick or Treat", [60110, 60120, 60130], "10-22", 14),
    (9002, "Christmas Event", [60510, 60520, 60530, 60540], "12-14", 14),
    (9003, "Lure a Jack in the Box", [60610], "12-14", 14),
    (9004, "New Year's Event", [60810, 60820, 60830, 60840], "01-01", 14),
    (9005, "Storming Sheep", [60710, 60720, 60730], "01-15", 14),
    (9006, "Valentine's Event", [61110, 61120, 61130, 61140], "02-08", 14),
]

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _stage_rows():
    from .master import MASTER_JSON_DATA
    return {s["stageId"]: s for s in MASTER_JSON_DATA.get("stage", [])}


def _handmade_row(eid, name, stages, start_md, days):
    start = datetime.strptime(f"2015-{start_md} 07:00:00", "%Y-%m-%d %H:%M:%S")
    if start_md < "07":
        start = start.replace(year=2016)
    end = start + timedelta(days=days, seconds=-1)
    row = {"eventStageId": eid, "validStageId": len(stages), "stageId": (stages + [0] * 5)[:5],
           "validStageWidthId": 0, "stageStartId": 0, "stageEndId": 0, "eventCategory": 2, "eventType": 3,
           "bannerUrl": "", "mypageBanner": 6000, "startTime": f"{start:%Y-%m-%d %H:%M:%S}",
           "endTime": f"{end:%Y-%m-%d %H:%M:%S}", "boardEndTime": f"{end:%Y-%m-%d %H:%M:%S}",
           "benefitId": 0, "groupPattern": 0, "validMinute": 0, "_name": name}
    row.update({k: 1 for k in WEEK})
    row.update({k: 0 for k in BENEFIT})
    return row


def master_rows():
    """The served evStage table: the 1.1.3 dump (unused stageId slots zeroed - they held garbage) + HANDMADE,
    every bannerUrl pointing at our banner route."""
    try:
        rows = json.load(open(os.path.join(_DATA, "evStage.json"), encoding="utf-8"))
    except (OSError, ValueError):
        rows = []
    out = []
    for r in rows:
        r = dict(r)
        n = max(0, min(int(r.get("validStageId", 0)), 5))
        r["stageId"] = list(r.get("stageId", []))[:n] + [0] * (5 - n)
        out.append(r)
    out += [_handmade_row(*h) for h in HANDMADE]
    for r in out:
        r["bannerUrl"] = BANNER_URL.format(r["eventStageId"])
    return out


_ROWS = None


def rows():
    global _ROWS
    if _ROWS is None:
        from .master import MASTER_JSON_DATA
        _ROWS = {r["eventStageId"]: r for r in MASTER_JSON_DATA.get("evStage", [])}
    return _ROWS


def row(eid):
    return rows().get(eid)


# --------------------------------------------------------------------------- schedule
def now_local():
    """Server-local now (KHUX_EVENT_NOW="YYYY-MM-DD HH:MM" overrides it for testing)."""
    fake = os.environ.get("KHUX_EVENT_NOW")
    return datetime.strptime(fake, "%Y-%m-%d %H:%M") if fake else datetime.now()


def _server_day(now):
    """(weekday 0=Mon, day start) of the server day containing `now` (turns over at DAY_RESET_HOUR)."""
    start = (now - timedelta(hours=DAY_RESET_HOUR)).replace(hour=DAY_RESET_HOUR, minute=0, second=0, microsecond=0)
    return start.weekday(), start


def window(r, now=None):
    """(start, end) of the row's current opening (server-local), or None when it is not running now."""
    now = now or now_local()
    if r.get("eventCategory") == 4:
        return None
    permanent = r["endTime"] >= PERMANENT_YEAR
    if permanent and r["startTime"] >= PERMANENT_ERA_END:     # added later than the 1.0.1 era (GUESS: E5)
        return None
    if permanent:
        flags = [r.get(k, 0) for k in WEEK]
        if r.get("groupPattern"):
            hour = SLOT_HOURS.get(r["groupPattern"])
            if hour is None:
                return None
            for day in (now.date(), now.date() - timedelta(days=1)):
                start = datetime.combine(day, datetime.min.time()).replace(hour=hour)
                end = start + timedelta(minutes=max(int(r.get("validMinute") or 30), 1))
                if start <= now < end and (not any(flags) or flags[start.weekday()]):
                    return start, end
            return None
        if r.get("eventCategory") == 1:
            wd, start = _server_day(now)
            return (start, start + timedelta(days=1)) if flags[wd] else None
        return _server_day(now)[1], _server_day(now)[1] + timedelta(days=1)
    # dated: replayed every year on its original month/day
    return replay_window(r["startTime"], r["endTime"], now)


def replay_window(start_str, end_str, now=None):
    """A dated 2015-16 period replayed every year: (start, end) when `now` is inside this year's (or last
    year's, for periods over New Year) copy - start on the original month/day at ROLLOVER_HOUR (the original
    hour-of-day offset kept, so a board opening 3 days after its event still does), original length - else
    None. Shared by events, campaigns and the limited (openId 3) Avatar / event / raid boards."""
    now = now or now_local()
    try:
        s0 = datetime.strptime(str(start_str), "%Y-%m-%d %H:%M:%S")
        e0 = datetime.strptime(str(end_str), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    length = e0 - s0 + timedelta(seconds=1)
    for year in (now.year, now.year - 1):
        try:
            start = s0.replace(year=year, hour=ROLLOVER_HOUR, minute=0, second=0)
        except ValueError:                      # 29 February
            start = s0.replace(year=year, day=28, hour=ROLLOVER_HOUR, minute=0, second=0)
        if start <= now < start + length:
            return start, start + length
    return None


def active(category, now=None):
    """[(row, start, end)] running now for a 101 request category (1 Special Quests, 2 Events)."""
    now = now or now_local()
    want = (1,) if category == 1 else (2, 3)
    out = []
    for r in rows().values():
        if r.get("eventCategory") in want:
            w = window(r, now)
            if w and playable(r):
                out.append((r, w[0], w[1]))
    out.sort(key=lambda t: (t[0].get("validMinute", 0) == 0, t[1], t[0]["eventStageId"]))
    return out


_STAGE_FILES = None


def stage_has_map(stage_id):
    """Whether the client's archive has the stage's map (data/stage_files.json; no list = assume yes)."""
    global _STAGE_FILES
    if _STAGE_FILES is None:
        try:
            _STAGE_FILES = set(json.load(open(os.path.join(_DATA, "stage_files.json"), encoding="utf-8"))["stageIds"])
        except (OSError, ValueError, KeyError):
            _STAGE_FILES = set()
    return not _STAGE_FILES or stage_id in _STAGE_FILES


def playable(r):
    """An event the client can open: it has stages and every one has its map in the archive (the 2016 event maps
    came in event packs we don't have; SceneUtil::setBossTypeImage crashes on a missing map)."""
    ids = stage_ids(r)
    return bool(ids) and all(stage_has_map(sid) for sid in ids)


def stage_ids(r):
    if r.get("validStageWidthId"):
        lo, hi = r.get("stageStartId", 0), r.get("stageEndId", 0)
        return sorted(sid for sid, s in _stage_rows().items() if lo <= sid <= hi and s.get("stageKind") == 2)
    st = _stage_rows()
    return [sid for sid in r.get("stageId", [])[:r.get("validStageId", 0)] if sid in st]


def name(r):
    if r.get("_name"):
        return r["_name"]
    ids = stage_ids(r)
    n = (_stage_rows().get(ids[0], {}).get("name") or "") if ids else ""
    return n.split(":")[0].strip() or "Event"


def entry(r, end, clears):
    """StageEvent::Event for 101. clears: {stageId: {"luxRecord", "clearMissionIds"}} of the player."""
    st = _stage_rows()
    ids = stage_ids(r)
    if r.get("eventCategory") == 3:              # progressive: cleared ones + the next
        shown = []
        for sid in ids:
            shown.append(sid)
            if str(sid) not in clears:
                break
        ids = shown
    new_id = next((sid for sid in ids if str(sid) not in clears), ids[-1] if ids else 0)
    stages = [{"stageId": sid, "useAp": st[sid].get("useAp", 0),
               "score": (clears.get(str(sid)) or {}).get("luxRecord", 0),
               "clearMissionIds": (clears.get(str(sid)) or {}).get("clearMissionIds", [])} for sid in ids]
    return {"stages": stages, "eventStageId": r["eventStageId"], "showIcon": 0, "bannerUrl": r["bannerUrl"],
            "eventType": r.get("eventType", 3) if r.get("eventType") in (1, 2, 3) else 3, "status": 1,
            "endTime": gparty.fmt_local(end - timedelta(seconds=1)), "newStageId": new_id, "isLock": 0}


def is_lure_stage(stage_id):
    """Raid-event quests ("Lure a ..." and the stages of eventType 2 events): their point is the boss."""
    st = _stage_rows().get(stage_id) or {}
    if st.get("stageKind") != 2 or not st.get("raidBoss"):
        return False
    if (st.get("name") or "").startswith("Lure a"):
        return True
    return any(r.get("eventType") == 2 and stage_id in stage_ids(r) for r in rows().values())


def is_event_stage(stage_id):
    return (_stage_rows().get(stage_id) or {}).get("stageKind") == 2


# --------------------------------------------------------------------------- banners
_FONT_CANDIDATES = [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_COLORS = {1: ((24, 70, 140), (90, 170, 230)), 2: ((110, 30, 120), (230, 120, 60)), 3: ((20, 100, 70), (120, 210, 120))}
_banner_cache = {}


def _font(size):
    from PIL import ImageFont
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def draw_banner(title, sub, size=(640, 140), colors=((110, 30, 120), (230, 120, 60))):
    """A banner PNG: a vertical gradient, a gold frame, the title and a subtitle."""
    from PIL import Image, ImageDraw
    title, sub = (t.replace("★", "*") if t else t for t in (title, sub))   # Arial has no star glyph
    w, h = size
    top, bottom = colors
    im = Image.new("RGB", size)
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / (h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    d.rectangle([3, 3, w - 4, h - 4], outline=(255, 230, 150), width=3)
    fs = int(h * 0.33)
    f = _font(fs)
    while d.textlength(title, font=f) > w - 50 and fs > 16:
        fs -= 2
        f = _font(fs)
    d.text((w // 2 + 2, int(h * 0.41) + 2), title, font=f, fill=(0, 0, 0), anchor="mm")
    d.text((w // 2, int(h * 0.41)), title, font=f, fill=(255, 255, 255), anchor="mm")
    if sub:
        d.text((w // 2, int(h * 0.8)), sub, font=_font(int(h * 0.16)), fill=(255, 240, 200), anchor="mm")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def banner_png(eid):
    """A 640x140 banner for an evStage row: the event's name on a gradient (category colours)."""
    if eid not in _banner_cache:
        r = row(eid) or {"eventCategory": 2}
        title = name(r) if r.get("eventStageId") else "Event"
        sub = {1: "Special Quest", 3: "Event - new quests unlock as you clear"}.get(r.get("eventCategory"), "Event")
        _banner_cache[eid] = draw_banner(title, sub, (640, 140), _COLORS.get(r.get("eventCategory"), _COLORS[2]))
    return _banner_cache[eid]


# --------------------------------------------------------------------------- campaigns (131 /campaign)
LAUNCH = "2015-09-01"            # campaign rows dated before the launch are test rows (GUESS: E7)


def campaign_rows():
    from .master import MASTER_JSON_DATA
    return MASTER_JSON_DATA.get("evCampaign") or []


def campaign_window(r, now=None):
    """Like window() for an evCampaign row (no categories): permanent rows by weekday / time slot, dated rows on
    their anniversary; rows dated before the launch never run."""
    if r.get("startTime", "") < LAUNCH:
        return None
    now = now or now_local()
    if r["endTime"] >= PERMANENT_YEAR:
        if r["startTime"] >= PERMANENT_ERA_END:          # permanent, but added after the 1.0.1 era (E5)
            return None
        flags = [r.get(k, 0) for k in WEEK]
        if r.get("groupPattern"):
            hour = SLOT_HOURS.get(r["groupPattern"])
            if hour is None:
                return None
            for day in (now.date(), now.date() - timedelta(days=1)):
                start = datetime.combine(day, datetime.min.time()).replace(hour=hour)
                end = start + timedelta(minutes=max(int(r.get("validMinute") or 30), 1))
                if start <= now < end and (not any(flags) or flags[start.weekday()]):
                    return start, end
            return None
        wd, start = _server_day(now)
        return (start, start + timedelta(days=1)) if not any(flags) or flags[wd] else None
    return window(dict(r, eventCategory=2), now)


def active_campaigns(now=None):
    return [r for r in campaign_rows() if campaign_window(r, now)]


def campaign_applies(r, stage_id):
    """Whether a campaign covers a stage: its stageId list when it has one, else by stageType (1 story, 2 and 3
    event stages, others every stage) - GUESS: E7."""
    n = int(r.get("validStageId") or 0)
    if n:
        return stage_id in r.get("stageId", [])[:n]
    kind = (_stage_rows().get(stage_id) or {}).get("stageKind")
    st = r.get("stageType")
    if st == 1:
        return kind == 1
    if st in (2, 3):
        return kind == 2
    return True


def campaign_power(ctype, stage_id=None, now=None):
    """Combined power (10000 = x1) of the running campaigns of a type that cover the stage."""
    power = 10000
    for r in active_campaigns(now):
        if r.get("type") == ctype and (stage_id is None or campaign_applies(r, stage_id)):
            power = power * int(r.get("power") or 10000) // 10000
    return power
