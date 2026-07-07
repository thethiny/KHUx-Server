"""
Master data table definitions, encryption, and serving logic.

Shared between app.py and handlers.py to avoid circular imports.
"""

import hashlib
import json
import os
from base64 import b64encode

from .crypto import encrypt

MASTER_TABLE_NAMES = [
    "avatarParts", "badstatus", "battleMisc", "buff", "burst",           # 0-4
    "colosseum", "colosseumStage", "drawMedalType", "enemyAttack", "enemy", # 5-9
    "evCampaign", "evMedalList", "evResource", "evScoreReward", "evStage", # 10-14
    "guiltProb", "initItem", "keyblade", "loginBonus", "material",       # 15-19
    "medal", "medalMisc", "misc", "mypageBackground", "player",         # 20-24
    "raidEnemyAttack", "raidEnemy", "raidReward", "raidSetting", "ranking", # 25-29
    "rankingReward", "reward", "serialcodeReward", "shop", "skillExp",   # 30-34
    "skill", "sphereArray", "sphere", "sphereMasu", "stage", "stamp",    # 35-40
    "title", "tutorialMisc", "world",                                     # 41-43
    "stage", "stamp", "title", "tutorialMisc", "world",                   # 44-48 (duplicates from 1.1.3)
]

MASTER_KEY_HEX = "00" * 32
MASTER_AES_KEY = MASTER_KEY_HEX[:32].encode("ascii")

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _load_json(name):
    path = os.path.join(_DATA_DIR, f"{name}.json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def _build_misc_data():
    from .enums import Misc
    entries = []
    for i in range(1, 1001):
        val = 0
        if i == Misc.PLAYER_NAME_MAX_LEN:
            val = 8
        entries.append({"miscId": i, "value": val})
    return entries


MASTER_JSON_DATA = {
    "misc": _load_json("misc") or _build_misc_data(),
    "world": _load_json("world") or [{"worldId": 1, "worldName": "Daybreak Town", "raidBackground": "", "instanceLwf": "", "instance": "", "xPos": 0, "yPos": 0, "rate": 100, "validParts": 0, "partsId": [], "xPostion": [], "yPostion": []}],
    "chapter": [{"chapterId": 1, "name": "Prologue"}],
    "battleMisc": _load_json("battleMisc") or [{"battleMiscId": i, "value": 0} for i in range(1, 101)],
    "keyblade": _load_json("keyblade") or [],
    "initItem": _load_json("initItem"),
    "enemy": _load_json("enemy") or [],
    "enemyAttack": _load_json("enemyAttack") or [],
    "medal": _load_json("medal") or [],
    "skill": _load_json("skill") or [],
    "stage": _load_json("stage") or [],
    "avatarParts": _load_json("avatarParts"),
    "avatarCombination": _load_json("avatarCombination"),
    "material": _load_json("material"),
    "medalMisc": _load_json("medalMisc"),
    "burst": _load_json("burst"),
    "tutorialMisc": _load_json("tutorialMisc"),
    "player": _load_json("player"),
    "buff": _load_json("buff"),
}


def encrypt_master_json(data: list, key: bytes = MASTER_AES_KEY) -> tuple[bytes, str]:
    """Encrypt a JSON array for master data download.
    Returns (b64_response_body, md5_hex_of_response_body)."""
    plaintext = json.dumps(data, separators=(",", ":")).encode("utf-8")
    ciphertext = encrypt(plaintext, key)
    b64_data = b64encode(ciphertext)
    md5_hex = hashlib.md5(b64_data).hexdigest()
    return b64_data, md5_hex


_master_cache: dict[str, tuple[bytes, str]] = {}


def get_master_encrypted(table_name: str) -> tuple[bytes, str]:
    """Get encrypted+base64 master data and its MD5, with caching."""
    if table_name not in _master_cache:
        data = MASTER_JSON_DATA.get(table_name, [])
        _master_cache[table_name] = encrypt_master_json(data)
    return _master_cache[table_name]
