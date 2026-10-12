"""Per-user inventory and progress, stored as one JSON document per user (models.UserState).

Shapes follow what the v1.0.1 client parses:
  medals:    UserMedal  {userMedalId, medalId, level, exp, attack/defense/burstUpperNumber, lock, upperCost,
                         guiltFactor, userSkills, getDatetime}
  keyblades: UserKeyblade {userKeybladeId, category, keybladeId, deckMedals, burst, totalAttack, totalDefense,
                         isFavorite, getDatetime}
  materials: {materialId: number}
  stages:    {stageId: {"clearMissionIds": [...], "luxRecord": n, "clears": n}}

A new user starts from the initItem master table (category 3 = medal with equipNo = deck slot, 13 = keyblade).
"""
import json
import time

from .master import MASTER_JSON_DATA
from .models import UserState

ITEM_MEDAL = 3        # reward/item type ids (SceneUtil::setItemImageData): 3 medal, 5 material, 13 keyblade
ITEM_MATERIAL = 5
ITEM_KEYBLADE = 13


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
    return st


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
        return self.data

    def __exit__(self, *exc):
        if self.row is not None and exc[0] is None:
            self.row.data = json.dumps(self.data)
            self.db.add(self.row)
        return False


def load(user, db):
    """Snapshot for responses (a new user's seeded state is saved on first access)."""
    with State(user, db) as st:
        return st


# --------------------------------------------------------------------------- mutations
def add_medal(st, medal_id):
    m = new_medal(st["next_medal"], medal_id)
    st["next_medal"] += 1
    st["medals"].append(m)
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
