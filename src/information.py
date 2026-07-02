"""
KHUx Private Server — HTML pages (news, notices, agreement, draw).

Uses a FastAPI APIRouter with no prefix — routes are mounted at root level.
Replicates the original Square Enix page styling from web.archive.org captures.
"""

import os as _os

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

_STATIC_DIR = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "static")


def mount_static(app: FastAPI):
    if _os.path.isdir(_STATIC_DIR):
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

router = APIRouter()

# ── Categories ────────────────────────────────────────────────────────────────

CATEGORIES = {
    1: ("IMPORTANT", "cat1"),
    2: ("UPDATE", "cat2"),
    3: ("END", "cat3"),
    4: ("MAINTENANCE", "cat4"),
    5: ("RECOVERY", "cat5"),
    6: ("CAMPAIGN", "cat6"),
    7: ("ERROR", "cat7"),
    8: ("EVENT", "cat8"),
    9: ("INFORMATION", "cat9"),
    10: ("OTHER", "cat10"),
}

# ── Notice data ───────────────────────────────────────────────────────────────

NOTICES = [
    {
        "id": 1,
        "date": "07/01",
        "cat": 9,
        "title": "Welcome to KHUx Private Server",
        "body": """
<p><span class="alert03">★ Private Server Online!</span></p>
<p>Welcome to the KHUx Private Server, a fan-operated preservation project.</p>
<p>This server aims to recreate the Kingdom Hearts Union Cross experience
after the official servers were shut down.</p>
<hr/>
<p><span class="alert01">■ Current Status</span></p>
<p><small>・ Tutorial flow is functional through Union Selection<br/>
・ Master data downloads are working for all 49 tables<br/>
・ Avatar editor and cutscenes render correctly<br/>
・ Tutorial battle is under development</small></p>
<hr/>
<p><span class="alert01">■ Known Issues</span></p>
<p><small>・ Tutorial battle may show a black screen<br/>
・ Some textures may display as white/transparent<br/>
・ Resource re-download can overwrite misc.mp4</small></p>
""",
    },
    {
        "id": 2,
        "date": "07/01",
        "cat": 2,
        "title": "Server Version 1.0.1",
        "body": """
<p><span class="alert03">★ Server Update</span></p>
<p>The private server is running version 1.0.1, matching the original KHUx client.</p>
<hr/>
<p><span class="alert01">■ Supported Features</span></p>
<p><small>・ Login and account creation<br/>
・ EULA and birthday verification<br/>
・ Master data download (49 tables)<br/>
・ Name registration<br/>
・ Avatar editor with costume parts<br/>
・ Story cutscenes<br/>
・ Union selection</small></p>
""",
    },
    {
        "id": 3,
        "date": "07/01",
        "cat": 4,
        "title": "Scheduled Maintenance Notice",
        "body": """
<p><span class="alert02">Maintenance may occur without prior notice as the server
is under active development.</span></p>
<p>Thank you for your patience and understanding.</p>
""",
    },
    {
        "id": 4,
        "date": "07/01",
        "cat": 8,
        "title": "Tutorial Battle Coming Soon",
        "body": """
<p><span class="alert03">★ Tutorial Battle</span></p>
<p>The tutorial battle system is currently under development.
Stage, enemy, and medal data are being configured to enable
the first battle experience.</p>
<p>Stay tuned for updates!</p>
""",
    },
    {
        "id": 5,
        "date": "07/01",
        "cat": 6,
        "title": "Preservation Project",
        "body": """
<p><span class="alert05">★ KHUx Preservation</span></p>
<p>This project exists to preserve Kingdom Hearts Union Cross
for historical and educational purposes. All game assets and
trademarks belong to Square Enix and Disney.</p>
<p>The original service ended on May 31, 2021. This private server
allows fans to experience the game's tutorial and early content.</p>
""",
    },
    {
        "id": 6,
        "date": "07/01",
        "cat": 1,
        "title": "Important: Private Server Disclaimer",
        "body": """
<p><span class="alert02">This is an unofficial, fan-operated private server.</span></p>
<p>It is not affiliated with, endorsed by, or connected to Square Enix,
Disney, or any of their subsidiaries.</p>
<p>Use at your own discretion. No personal data is collected.</p>
""",
    },
    {
        "id": 7,
        "date": "07/01",
        "cat": 10,
        "title": "Community Resources",
        "body": """
<p><span class="alert01">■ Useful Links</span></p>
<p><small>・ KHUx Wiki — comprehensive game database<br/>
・ Kingdom Hearts community forums<br/>
・ Game preservation archives</small></p>
""",
    },
    {
        "id": 8,
        "date": "07/01",
        "cat": 7,
        "title": "Known Connection Issues",
        "body": """
<p>If you experience connection errors, please check:</p>
<p><small>・ DNS redirect is configured correctly (hosts file or Magisk module)<br/>
・ Private server is running and accessible<br/>
・ Game client version matches server (v1.0.1)</small></p>
""",
    },
]

# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS_CATS = """
.cat1{background:#ed5b60;border-color:#eda1a4}
.cat2{background:#9dc668;border-color:#b8c7a5}
.cat3{background:#872bc4;border-color:#a067c5}
.cat4{background:#f78d14;border-color:#f7b15f}
.cat5{background:#f249dc;border-color:#f391e6}
.cat6{background:#872bc4;border-color:#a067c5}
.cat7{background:#bc3846;border-color:#bd7179}
.cat8{background:#14caf7;border-color:#5fd8f7}
.cat9{background:#4271d6;border-color:#819bd5}
.cat10{background:#7a7a7a;border-color:#a1a1a1}
"""

_CSS_BASE = """
html{background:#043654;margin:0;padding:0;color:#fff}
body{max-width:908px;
font-family:"Hiragino Kaku Gothic Pro",Meiryo,"MS PGothic",sans-serif;
font-size:85%;letter-spacing:0.05em;margin:0 auto}
ul{list-style:none;padding-left:0}
.news_cat{font-size:77%;display:block;float:left;
width:8em;text-align:center;border-style:solid;border-width:1px;
border-radius:3px;letter-spacing:0;position:relative}
""" + _CSS_CATS

_CSS_LIST = _CSS_BASE + """
body{background:#043654 url(/static/img/bg_light.png) no-repeat scroll 2% top / 60% auto;
line-height:2.0;padding:0;word-wrap:break-word}
a{color:#fff;text-decoration:none}
a:hover{background-color:rgba(0,0,0,0.3)}
.subject{font-size:93%;display:block;width:100%;height:2.3em;padding-top:0.7em;
background:rgba(0,0,0,0) url(/static/img/arrow.png) no-repeat scroll 99% center / 2% 12px;
position:relative}
.date{font-size:85%;display:block;float:left;margin:0.7em 0.5em 0;position:relative}
.news_cat{margin:0.7em 0.5em 0 0}
.container ul{margin-top:0}
.container li{border-bottom:1px dotted #fff;padding:0;clear:both;overflow:hidden}
"""

_CSS_DETAIL = _CSS_BASE + """
body{background:#043654 url(/static/img/bg_light.png) no-repeat scroll 2% top / 60% auto;
line-height:1.8;padding:1em 0.5em 9em}
a{color:#0ff;text-decoration:none}
a:hover{text-decoration:underline}
.subject{font-size:93%}
.date{font-size:85%;display:block;float:left;margin-right:0.5em}
.news_cat{margin-right:0.5em}
.container .title{border-bottom:1px dotted #fff;margin-bottom:1.0em;padding:0.7em 0 0.5em;clear:both}
.alert01{color:#00d4ed;font-weight:bold}
.alert02{color:#ffcd4a;font-weight:bold}
.alert03{color:orange;font-weight:bold}
.alert04{color:#888;font-weight:bold}
.alert05{color:violet;font-weight:bold}
.alert06{color:yellow;font-weight:bold}
.alert07{color:greenyellow;font-weight:bold}
.btn{position:fixed;left:0;bottom:0;
background:transparent url(/static/img/btn_bar.png) left top repeat-x;
width:116%;border-top:1px solid #073562;padding:0.8em 1.0em 0}
a#btn_back{border:0;height:0;padding-top:5%}
a#btn_back:hover img{opacity:0.6}
"""

_CSS_AGREEMENT = _CSS_BASE + """
body{background:#043654 url(/static/img/bg_light.png) no-repeat scroll 2% top / 60% auto;
line-height:1.8;padding:1em 0.5em 2em}
a{color:#0ff;text-decoration:none}
h1{color:#ffcd4a;font-size:18px;border-bottom:1px dotted #fff;padding-bottom:0.5em}
h2{color:#00d4ed;font-size:14px;margin-top:1.5em}
p{line-height:1.6;font-size:13px}
"""

# ── Renderers ─────────────────────────────────────────────────────────────────


def _render_list(base_url: str) -> str:
    items = []
    for n in NOTICES:
        cat_label, cat_class = CATEGORIES[n["cat"]]
        items.append(
            f'<li><span class="date">{n["date"]}</span>'
            f'<span class="news_cat {cat_class}">{cat_label}</span>'
            f'<a class="subject" href="{base_url}/detail/{n["id"]}" target="_self">'
            f'{n["title"]}</a></li>'
        )
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>INFORMATION LIST｜KINGDOM HEARTS Union χ</title>
<style>{_CSS_LIST}</style></head>
<body><div class="container"><ul>{"".join(items)}</ul></div></body></html>"""


def _render_detail(notice_id: int, base_url: str) -> str:
    notice = next((n for n in NOTICES if n["id"] == notice_id), None)
    if not notice:
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>{_CSS_DETAIL}</style></head>
<body><div class="container"><p>Notice not found.</p></div></body></html>"""

    cat_label, cat_class = CATEGORIES[notice["cat"]]
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>INFORMATION｜KINGDOM HEARTS Union χ</title>
<style>{_CSS_DETAIL}</style></head>
<body><div class="container">
<div class="title">
<span class="date">{notice["date"]}</span>
<span class="news_cat {cat_class}">{cat_label}</span>
<br/><span class="subject">{notice["title"]}</span>
</div>
<div class="page-admin">{notice["body"]}</div>
<div class="btn"><a href="{base_url}/list" target="_self" id="btn_back">
<img src="/static/img/btn_back.png" alt="Back" width="15%" border="0"/></a></div>
</div></body></html>"""


def _render_agreement() -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AGREEMENT｜KINGDOM HEARTS Union χ</title>
<style>{_CSS_AGREEMENT}</style></head>
<body>
<h1>KINGDOM HEARTS Union Cross — Terms of Service</h1>
<p>Welcome to the KHUx Private Server.</p>
<h2>1. Acceptance of Terms</h2>
<p>By tapping "Agree" you accept these terms and conditions for use of
the KHUx Private Server preservation project.</p>
<h2>2. Private Server Notice</h2>
<p>This is a fan-operated private server created for game preservation purposes.
All game assets, characters, and trademarks belong to Square Enix Co., Ltd. and
The Walt Disney Company. This project is not affiliated with or endorsed by
either company.</p>
<h2>3. No Warranty</h2>
<p>This service is provided "as-is" with no guarantees of availability,
completeness, or correctness. Features may be incomplete or under development.</p>
<h2>4. Privacy</h2>
<p>No personal data is collected, stored, or transmitted to third parties.
All game data remains on your device and the local server.</p>
<h2>5. Usage</h2>
<p>This server is intended for personal, non-commercial use only as a means
of preserving and experiencing the Kingdom Hearts Union Cross game content
after the official service ended on May 31, 2021.</p>
</body></html>"""

# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/agreement")
async def agreement_page():
    return HTMLResponse(_render_agreement())


@router.get("/information/list")
async def info_list():
    return HTMLResponse(_render_list("/information"))


@router.get("/information/detail/{notice_id:int}")
async def info_detail(notice_id: int):
    return HTMLResponse(_render_detail(notice_id, "/information"))


@router.get("/dark/information/list")
async def dark_info_list():
    return HTMLResponse(_render_list("/dark/information"))


@router.get("/dark/information/detail/{notice_id:int}")
async def dark_info_detail(notice_id: int):
    return HTMLResponse(_render_detail(notice_id, "/dark/information"))
