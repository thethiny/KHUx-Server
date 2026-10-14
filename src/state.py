"""Per-user inventory and progress, stored as one JSON document per user (models.UserState).

Shapes follow what the v1.0.1 client parses:
  medals:    UserMedal  {userMedalId, medalId, level, exp, attack/defense/burstUpperNumber, lock, upperCost,
                         guiltFactor, userSkills, getDatetime}
  keyblades: UserKeyblade {userKeybladeId, category, keybladeId, deckMedals, burst, totalAttack, totalDefense,
                         isFavorite, getDatetime}
  materials: {materialId: number}
  stages:    {stageId: {"clearMissionIds": [...], "luxRecord": n, "clears": n}}
  titles:    UserTitle::Title {userTitleId (uint64, IsUint64), titleId (int, IsInt)} - nothing else is read
             (hole::network::api::UserTitle::Title::init, 0x4A1620); one record per owned title master id

  spheres:   {sphereBoardId: UserSphere::Sphere} - Avatar Boards owned (see the "avatar boards" section)
  avatar_parts: [UserAvatarParts::Part {userAvatarPartsId (uint64), partsType, avatarPartsId, getDatetime}]

A new user starts from the initItem master table (category 3 = medal with equipNo = deck slot, 7 = title,
13 = keyblade, 25 = avatar board, 100 = avatar part).
"""
import json
import time

from .master import MASTER_JSON_DATA
from .models import UserState

ITEM_MEDAL = 3        # reward/item type ids (SceneUtil::setItemImageData): 3 medal, 5 material, 7 title, 13 keyblade
ITEM_MATERIAL = 5
ITEM_TITLE = 7
ITEM_KEYBLADE = 13
ITEM_AVATAR_PARTS = (18, 19, 20, 23)   # avatar set / parts (rewardId = avatarParts master id)
INIT_SPHERE = 25      # initItem category: Avatar Board owned from the start
INIT_AVATAR_PART = 100  # initItem category: avatar part owned from the start


def deck_slots(keyblade_id):
    """Medal slots of a keyblade: keyblade.validConsist (3-5). The client sizes the deck from the length of
    UserKeyblade.deckMedals (Keyblade::init, capped at 5), so a keyblade sent with [] shows no slots and cannot
    take medals; empty slots are 0."""
    row = next((k for k in MASTER_JSON_DATA.get("keyblade") or [] if k["keybladeId"] == keyblade_id), None)
    return min(max(row.get("validConsist", 3), 1), 5) if row else 3


def fit_deck(medal_ids, keyblade_id):
    """A deck list padded with 0 (or trimmed) to the keyblade's slot count."""
    n = deck_slots(keyblade_id)
    ids = [int(m) for m in medal_ids][:n]
    return ids + [0] * (n - len(ids))


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


now = _now        # server time as the client's date strings ("YYYY-MM-DD HH:MM:SS", UTC)


def new_medal(uid, medal_id):
    return {"userMedalId": uid, "medalId": medal_id, "level": 1, "exp": 0,
            "attackUpperNumber": 0, "defenseUpperNumber": 0, "burstUpperNumber": 0,
            "lock": 0, "upperCost": 0, "guiltFactor": 0, "userSkills": [], "getDatetime": _now()}


def _initial(user):
    init = MASTER_JSON_DATA.get("initItem") or []
    st = {"medals": [], "keyblades": [], "materials": {}, "stages": {}, "next_medal": 1, "next_keyblade": 1}
    deck = {}
    for row in sorted(init, key=lambda r: r["id"]):
        if row["category"] == ITEM_MEDAL:
            m = new_medal(st["next_medal"], row["itemId"])
            st["next_medal"] += 1
            st["medals"].append(m)
            if row["equipType"] == 3 and row["equipNo"]:
                deck[row["equipNo"]] = m["userMedalId"]
    for row in sorted(init, key=lambda r: r["id"]):
        if row["category"] == ITEM_KEYBLADE:
            kb = {"userKeybladeId": st["next_keyblade"], "category": 0, "keybladeId": row["itemId"],
                  "deckMedals": [deck[k] for k in sorted(deck)], "burst": 0,
                  "totalAttack": 3960, "totalDefense": 3747, "isFavorite": 1, "getDatetime": _now()}
            st["next_keyblade"] += 1
            st["keyblades"].append(kb)
    # Accounts created before this store already drew the tutorial gacha medal (KH II King Mickey) and saw
    # it equipped in slot 1; keep that so the client's view and the server agree.
    if user is not None and user.tutorial_phase >= 100:
        m = new_medal(st["next_medal"], 33043)
        st["next_medal"] += 1
        st["medals"].append(m)
        if st["keyblades"]:
            st["keyblades"][0]["deckMedals"][0] = m["userMedalId"]
    if user is not None and user.last_clear_stage_id:
        for sid in story_order():
            if sid > user.last_clear_stage_id:
                break
            st["stages"][str(sid)] = {"clearMissionIds": [], "luxRecord": 0, "clears": 1}
    return st                                  # titles: State.__enter__ -> ensure_titles


class State:
    """with State(user, db) as st: ... - loads (or creates) the user's document and saves it on exit."""

    def __init__(self, user, db):
        self.user, self.db = user, db

    def __enter__(self):
        row = self.db.get(UserState, self.user.id) if self.user else None
        if row is None:
            self.row = UserState(user_id=self.user.id, data="{}") if self.user else None
            self.data = _initial(self.user)
        else:
            self.row = row
            self.data = json.loads(row.data)
        for kb in self.data.get("keyblades", []):          # older saves have unsized decks
            kb["deckMedals"] = fit_deck(kb.get("deckMedals", []), kb["keybladeId"])
        ensure_titles(self.data)                           # older saves have no titles
        ensure_avatar_parts(self.data)                     # older saves have no avatar parts
        self.data.setdefault("spheres", {})                # Avatar Boards: filled by sync_spheres
        ensure_coordinates(self.data, self.user)           # older saves have no outfits
        album = self.data.setdefault("album", [])          # older saves: seed the Album from the medals owned
        for m in self.data.get("medals", []):
            if m["medalId"] not in album:
                album.append(m["medalId"])
        return self.data

    def __exit__(self, *exc):
        if self.row is not None and exc[0] is None:
            self.row.data = json.dumps(self.data)
            self.db.add(self.row)
        return False


# --------------------------------------------------------------------------- outfits (UserAvatar::Coordinate)
# The Outfits screen (SceneAvatarEdit::initMyCordinateButton) keeps the userAvatars whose myCoordinateNo is 1..6 and
# selects the one equal to userDetail.equipCoordinateNo (7 is read as 1); with none it indexes an empty vector and
# throws out_of_range. Slot 1 is seeded from the avatar made in the tutorial (the User columns).
COORDINATE_SLOTS = 6
COORDINATE_KEYS = ("gender", "hairPartsId", "hairColorPartsId", "facePartsId", "bodyPartsId", "skinPartsId")


def ensure_coordinates(st, user):
    if user is None or st.get("coordinates"):
        return
    acc = [int(x) for x in user.accessories_parts_ids.split(",") if x] if user.accessories_parts_ids else []
    st["coordinates"] = [{"myCoordinateNo": 1, "gender": user.gender, "hairPartsId": user.hair_parts_id,
                          "hairColorPartsId": user.hair_color_parts_id, "facePartsId": user.face_parts_id,
                          "bodyPartsId": user.body_parts_id, "skinPartsId": user.skin_parts_id,
                          "accessoriesPartsIds": acc}]


def set_coordinate(st, c):
    """Insert or replace one outfit from an updateAvatarData entry; returns the stored record (or None)."""
    no = int(c.get("myCoordinateNo", 0))
    if not 1 <= no <= COORDINATE_SLOTS:
        return None
    rec = {"myCoordinateNo": no, **{k: int(c.get(k, 0)) for k in COORDINATE_KEYS},
           "accessoriesPartsIds": [int(x) for x in c.get("accessoriesPartsIds", [])][:5]}
    st["coordinates"] = [x for x in st.get("coordinates", []) if x["myCoordinateNo"] != no] + [rec]
    st["coordinates"].sort(key=lambda x: x["myCoordinateNo"])
    return rec


def load(user, db):
    """Snapshot for responses (a new user's seeded state is saved on first access)."""
    with State(user, db) as st:
        return st


# --------------------------------------------------------------------------- mutations
def add_medal(st, medal_id):
    m = new_medal(st["next_medal"], medal_id)
    st["next_medal"] += 1
    st["medals"].append(m)
    if medal_id not in st.setdefault("album", []):       # the Album: every medal ever owned (GUESS: A1)
        st["album"].append(medal_id)
    return m


def add_keyblade(st, keyblade_id):
    """A new keyblade with an empty deck (the player equips medals in deck edit; /user/keyblade/update)."""
    kb = {"userKeybladeId": st["next_keyblade"], "category": 0, "keybladeId": keyblade_id,
          "deckMedals": fit_deck([], keyblade_id),
          "burst": 0, "totalAttack": 0, "totalDefense": 0, "isFavorite": 0, "getDatetime": _now()}
    st["next_keyblade"] += 1
    st["keyblades"].append(kb)
    return kb


def add_material(st, material_id, n):
    k = str(material_id)
    st["materials"][k] = st["materials"].get(k, 0) + n


def materials_list(st):
    """UserMaterial::Material needs userMaterialId + materialId + number; one stack per material, so the
    material id doubles as the user material id."""
    return [{"userMaterialId": int(k), "materialId": int(k), "number": v}
            for k, v in sorted(st["materials"].items(), key=lambda x: int(x[0]))]


# --------------------------------------------------------------------------- titles
_TITLE_IDS = None


def title_ids():
    """Every title master id (title.json)."""
    global _TITLE_IDS
    if _TITLE_IDS is None:
        _TITLE_IDS = {t["titleId"] for t in MASTER_JSON_DATA.get("title") or []}
    return _TITLE_IDS


def default_title_ids():
    """Titles every player owns: the initItem category-7 rows (1001-1008), which are exactly the title master's
    category 1 / require 1 "Default Title" rows; both are taken so neither source alone can empty the picker."""
    ids = [r["itemId"] for r in sorted(MASTER_JSON_DATA.get("initItem") or [], key=lambda r: r["id"])
           if r.get("category") == ITEM_TITLE]
    ids += [t["titleId"] for t in MASTER_JSON_DATA.get("title") or [] if t.get("category") == 1]
    return list(dict.fromkeys(ids))


def owned_title_ids(st):
    return {t["titleId"] for t in st.get("titles", [])}


def add_title(st, title_id):
    """Give a title. Titles are unique per player: returns the new UserTitle record, or None when it is already
    owned or not a title master id (the picker shows master rows only)."""
    try:
        title_id = int(title_id)
    except (TypeError, ValueError):
        return None
    st.setdefault("titles", [])
    known = title_ids()
    if title_id <= 0 or title_id > 0x7FFFFFFF or (known and title_id not in known)             or title_id in owned_title_ids(st):
        return None
    uid = max(int(st.get("next_title", 1)), max((t["userTitleId"] for t in st["titles"]), default=0) + 1)
    rec = {"userTitleId": uid, "titleId": title_id}
    st["next_title"] = uid + 1
    st["titles"].append(rec)
    return rec


def title_mark(st):
    """Pass to titles_since() to get the titles granted in between (userTitleIds only grow)."""
    return int(st.get("next_title", 1))


def titles_since(st, mark):
    return [dict(t) for t in st.get("titles", []) if t["userTitleId"] >= mark]


def stage_titles(row, mission_ids=None, cleared=True):
    """Title ids a stage gives: clearGetTitle (validClearGetTitle) and first-clear items of type 7 when `cleared`,
    plus the type-7 rewards of the given missions (1-based ids)."""
    out = []
    if cleared:
        if row.get("validClearGetTitle") and row.get("clearGetTitle"):
            out.append(row["clearGetTitle"])
        types, ids = row.get("clearGetItemType") or [], row.get("clearGetItemId") or []
        for k in range(min(row.get("validClearGetItem", 0), len(types), len(ids))):
            if types[k] == ITEM_TITLE:
                out.append(ids[k])
    types, ids = row.get("submissionRewardType") or [], row.get("submissionItemId") or []
    for mid in mission_ids or []:
        k = mid - 1 if isinstance(mid, int) else -1
        if 0 <= k < min(row.get("validSubmission", 0), len(types), len(ids)) and types[k] == ITEM_TITLE:
            out.append(ids[k])
    return out


def ensure_titles(st):
    """Default titles always owned. A save from before titles existed also gets the titles of the stages and
    missions it already cleared (stage clears never granted them)."""
    if "titles" not in st:
        st["titles"], st["next_title"] = [], 1
        for tid in default_title_ids():
            add_title(st, tid)
        for sid, rec in (st.get("stages") or {}).items():
            row = stage_row(int(sid)) if str(sid).isdigit() else None
            if row:
                for tid in stage_titles(row, (rec or {}).get("clearMissionIds", [])):
                    add_title(st, tid)
    else:
        for tid in default_title_ids():
            add_title(st, tid)


# --------------------------------------------------------------------------- stages
_STORY = None


def story_order():
    """Story quest stage ids in play order: stage master rows with stageKind 1, by their `id` (quest No.)."""
    global _STORY
    if _STORY is None:
        rows = [s for s in MASTER_JSON_DATA.get("stage") or [] if s.get("stageKind") == 1]
        _STORY = [s["stageId"] for s in sorted(rows, key=lambda s: s["id"])]
    return _STORY


def stage_row(stage_id):
    return next((s for s in MASTER_JSON_DATA.get("stage") or [] if s["stageId"] == stage_id), None)


# --------------------------------------------------------------------------- avatar parts
_PARTS = None
_LEGACY_PARTS = (30001, 30002, 20001, 20002, 40001, 40002)   # what /user/avatar/parts served before this store


def parts_master():
    global _PARTS
    if _PARTS is None:
        _PARTS = {r["avatarPartsId"]: r for r in MASTER_JSON_DATA.get("avatarParts") or []}
    return _PARTS


def add_avatar_part(st, parts_id):
    """Give an avatar part (or outfit set; both are avatarParts master rows). Unique per player: returns the new
    UserAvatarParts::Part record, or None when already owned / not an avatarParts id."""
    try:
        parts_id = int(parts_id)
    except (TypeError, ValueError):
        return None
    st.setdefault("avatar_parts", [])
    master = parts_master()
    if parts_id <= 0 or parts_id > 0x7FFFFFFF or (master and parts_id not in master) \
            or any(p["avatarPartsId"] == parts_id for p in st["avatar_parts"]):
        return None
    uid = max(int(st.get("next_avatar_part", 1)), max((p["userAvatarPartsId"] for p in st["avatar_parts"]), default=0) + 1)
    rec = {"userAvatarPartsId": uid, "partsType": int((master.get(parts_id) or {}).get("partsType", 0)),
           "avatarPartsId": parts_id, "getDatetime": _now()}
    st["next_avatar_part"] = uid + 1
    st["avatar_parts"].append(rec)
    return rec


def ensure_avatar_parts(st):
    """Avatar parts owned from the start: the initItem category-100 rows (falls back to the six parts the
    server used to hard-code when initItem has none)."""
    if "avatar_parts" in st:
        return
    st["avatar_parts"], st["next_avatar_part"] = [], 1
    ids = [r["itemId"] for r in sorted(MASTER_JSON_DATA.get("initItem") or [], key=lambda r: r["id"])
           if r.get("category") == INIT_AVATAR_PART] or list(_LEGACY_PARTS)
    for pid in ids:
        add_avatar_part(st, pid)


# --------------------------------------------------------------------------- avatar boards (sphere)
# Client side (v1.0.1): hole::network::api::UserSphere::Sphere::init (0x4A5AEC) reads one owned board as
#   {userSphereBoardId: int, sphereBoardId: int, isBuy: int (!= 0), status: int, unlockMasuIds: [int],
#    getDatetime: "YYYY-MM-DD HH:MM:SS"}
# and UserSphere::parse keeps them in a map keyed by sphereBoardId. SceneSphereBoardSelect::initSphereBoardList
# lists ONLY master boards present in that map (filtered by board type for the coin mode), so a board the server
# never sends cannot be opened. Type-2 boards are listed with a Jewel price until isBuy != 0 (the tap opens
# openBoardBuyDialog -> /user/sphere/buy). status 3 = completed (ConnectingSphere::get_user_data; every other
# value means "not finished"; 1 / 2 are our own new / in progress).
# The board grid is sphereArray.spCol0..4 (5 x 9 cells): 1..998 are node ("masu") numbers n, whose cost and reward
# are sphereMasu.<field>[n - 1]; >= 999 are paths / decorations. Node 23 is not on the grid: it is the
# completion reward (SphereUI::openPopUpIncentiveComp shows masu index 22 once every grid node is open).
SPHERE_NEW, SPHERE_STARTED, SPHERE_COMPLETE = 1, 2, 3
SPHERE_COMPLETE_MASU = 23
# board type (sphere.type) -> User column of the coin it costs (SceneSphereBoardSelect / ConnectingSphere read
# UserPoint +24 spherePoint for types 1/2, +80 colosseumSpherePoint for 3, +72 stageSpherePoint for 4 and
# +76 raidSpherePoint for 5; TextData 103400001/2/3/27 Avatar / Coliseum / Event / Raid Coins)
SPHERE_COIN = {1: "sphere_point", 2: "sphere_point", 3: "colosseum_sphere_point", 4: "stage_sphere_point",
               5: "raid_sphere_point"}
SPHERE_BUY_TYPE = 2    # boards bought with Jewels (sphere.price)

_SPHERE = _ARRAY = _MASU = None


def _sphere_tables():
    global _SPHERE, _ARRAY, _MASU
    if _SPHERE is None:
        _SPHERE = {r["sphereBoardId"]: r for r in MASTER_JSON_DATA.get("sphere") or []}
        _ARRAY = {r["arryId"]: r for r in MASTER_JSON_DATA.get("sphereArray") or []}
        _MASU = {r["masuId"]: r for r in MASTER_JSON_DATA.get("sphereMasu") or []}
    return _SPHERE, _ARRAY, _MASU


def sphere_row(board_id):
    return _sphere_tables()[0].get(board_id)


def sphere_masu(row):
    """The sphereMasu row (node costs / rewards) of a board."""
    return _sphere_tables()[2].get(row.get("masuId")) if row else None


def sphere_nodes(row):
    """Node numbers placed on a board's grid (sphereArray spCol0..4 values 1..22)."""
    arr = _sphere_tables()[1].get(row.get("arryId")) if row else None
    nodes = set()
    for k in ("spCol0", "spCol1", "spCol2", "spCol3", "spCol4"):
        for v in (arr or {}).get(k) or []:
            if isinstance(v, int) and 1 <= v < SPHERE_COMPLETE_MASU:
                nodes.add(v)
    return nodes


def board_available(row, lux_rank, now):
    """sphere.openId: 1 always, 2 from Lux rank (player level) openParam, 3 between startDatetime and
    endDatetime (event / limited boards). Server rule, the client has no unlock logic of its own."""
    open_id = row.get("openId")
    if open_id == 1:
        return True
    if open_id == 2:
        return lux_rank >= row.get("openParam", 0)
    if open_id == 3:
        return str(row.get("startDatetime", "")) <= now <= str(row.get("endDatetime", ""))
    return False


def new_sphere(st, row, bought):
    uid = max(int(st.get("next_sphere", 1)),
              max((s["userSphereBoardId"] for s in st["spheres"].values()), default=0) + 1)
    rec = {"userSphereBoardId": uid, "sphereBoardId": row["sphereBoardId"], "isBuy": 1 if bought else 0,
           "status": SPHERE_NEW, "unlockMasuIds": [], "getDatetime": _now()}
    st["next_sphere"] = uid + 1
    st["spheres"][str(row["sphereBoardId"])] = rec
    return rec


def sync_spheres(st, lux_rank, now=None):
    """Give every board the player qualifies for and does not own yet: the initItem category-25 boards, then
    each master board whose open rule passes. Jewel boards (type 2 with a price) arrive unbought. Returns the
    new records (the client flags them NEW when they come from /user/sphere/check)."""
    now = now or _now()
    st.setdefault("spheres", {})
    added = []
    for r in sorted(MASTER_JSON_DATA.get("initItem") or [], key=lambda r: r["id"]):
        row = sphere_row(r.get("itemId")) if r.get("category") == INIT_SPHERE else None
        if row and str(row["sphereBoardId"]) not in st["spheres"]:
            added.append(new_sphere(st, row, not needs_buying(row)))
    for bid, row in sorted(_sphere_tables()[0].items()):
        if str(bid) in st["spheres"] or row.get("type") not in SPHERE_COIN:
            continue
        if board_available(row, lux_rank, now):
            added.append(new_sphere(st, row, not needs_buying(row)))
    return added


def needs_buying(row):
    """A Jewel board (type 2 with a price) is given unbought: listed with its price until /user/sphere/buy.
    (initItem category 25 also lists the 1.1.3 Jewel boards 2500002-2500009, i.e. every player sees them.)"""
    return row.get("type") == SPHERE_BUY_TYPE and row.get("price", 0) > 0


def close_spheres(st, now=None):
    """Remove limited boards (openId 3) whose period is over, except Jewel boards already bought. Returns the
    removed sphereBoardIds (/user/sphere/check closeEventSphereBoardIds -> UserSphere::removeSphere)."""
    now = now or _now()
    closed = []
    for key, rec in list(st.get("spheres", {}).items()):
        row = sphere_row(rec["sphereBoardId"])
        if not row or row.get("openId") != 3 or now <= str(row.get("endDatetime", "")):
            continue
        if row.get("type") == SPHERE_BUY_TYPE and rec.get("isBuy"):
            continue
        del st["spheres"][key]
        closed.append(rec["sphereBoardId"])
    return closed


def sphere_list(st):
    return [dict(s, unlockMasuIds=list(s["unlockMasuIds"]))
            for s in sorted(st.get("spheres", {}).values(), key=lambda s: s["userSphereBoardId"])]
