"""Private-server gacha: banners from data/banners.json, medal pools rebuilt from the medal table.

The original per-banner medal lists (drawMedalList) were server-only and are lost, so the pools are ours:
  standard     - regular character medals (medalId series 1x-3x, medal.type 1), by rarity
  illustrated  - the 6-star specials of series 4x / 14x ("Illustrated", "SP", ...)
  organization - the 6-star Organization XIII medals (series 13x)
  [ids]        - an explicit list; a single id makes the banner a store item (always that medal)
The 9x series (Moogle / Huey / Louie / Dewey / Chip & Dale) are fusion/EXP medals from quests and never drawn.
GachaList::Gacha::init needs validAdd, drawMedalTypeId, drawType, sortId, payType, price, lotCount,
isDayLimited, userLimitedCount, name, description, bannerUrl - the list is entirely server-defined.
"""
import json
import logging
import os
import random
from typing import Optional

logger = logging.getLogger(__name__)

_DATA = os.path.join(os.path.dirname(__file__), "..", "data", "banners.json")
# image hosting for banners (Cloudflare Pages later); the client tolerates an unreachable image
BANNER_BASE_URL = os.environ.get("KHUX_BANNER_URL", "http://api.sp.kingdomhearts.com/static/banner")

_banners: Optional[list] = None
_pools: dict = {}


def banners() -> list:
    global _banners
    if _banners is None:
        with open(_DATA, encoding="utf-8") as f:
            _banners = json.load(f)["banners"]
    return _banners


def banner(banner_id: int) -> Optional[dict]:
    return next((b for b in banners() if b["id"] == banner_id), None)


def _series(medal_id: int) -> int:
    return medal_id // 10000


def pool(name, rare: int) -> list:
    """Medal ids of a pool at one rarity."""
    if isinstance(name, list):
        return list(name)
    key = (name, rare)
    if key not in _pools:
        from .master import MASTER_JSON_DATA
        medals = MASTER_JSON_DATA.get("medal", [])
        series = {"standard": {1, 2, 3}, "illustrated": {4, 14}, "organization": {13}}[name]
        _pools[key] = [m["medalId"] for m in medals
                       if m.get("type") == 1 and m.get("rare") == rare and _series(m["medalId"]) in series]
    return _pools[key]


def unlocked(b: dict, quests_cleared: int) -> bool:
    return quests_cleared >= b.get("unlockQuests", 0)


def lot_count(b: dict) -> int:
    return sum(lot["count"] for lot in b["lots"])


def list_entry(b: dict) -> dict:
    return {
        "validAdd": 0, "drawMedalTypeId": b["id"], "drawType": 1, "sortId": b.get("sortId", b["id"]),
        "payType": b.get("payType", 1), "price": b["price"], "lotCount": lot_count(b),
        "isDayLimited": int(b.get("isDayLimited", 0)), "userLimitedCount": 0,
        "name": b["name"], "description": b["description"],
        "bannerUrl": b.get("bannerUrl") or f"{BANNER_BASE_URL}/{b['id']}.png",
    }


def draw(b: dict) -> list:
    """Medal ids for one purchase of banner b."""
    if isinstance(b["pool"], list) and len(b["pool"]) == 1:
        return [b["pool"][0]] * lot_count(b)
    out = []
    for lot in b["lots"]:
        rates = {int(r): w for r, w in lot["rates"].items() if pool(b["pool"], int(r))}
        for _ in range(lot["count"]):
            rare = random.choices(list(rates), weights=list(rates.values()))[0]
            out.append(random.choice(pool(b["pool"], rare)))
    return out
