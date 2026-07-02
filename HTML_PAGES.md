# KHUx HTML Pages Reference

All HTML pages served by the private server, their original URLs, and web archive sources.

## Page Types

### 1. Agreement / EULA
- **Local**: `GET /agreement`
- **Original**: `http://api.sp.kingdomhearts.com/` (loaded in `SceneAgreement` webview)
- **Game reference**: `need/url` response `agreement` field
- **Notes**: Game's native UI provides Agree/Disagree buttons — the HTML is content only.

### 2. Information List
- **Local (light)**: `GET /information/list`
- **Local (dark)**: `GET /dark/information/list`
- **Original (light)**: `http://api.sp.kingdomhearts.com/information/list`
- **Original (dark)**: `https://api.sp.kingdomhearts.com/dark/information/list`
- **Web archive (light)**: `https://web.archive.org/web/20210610101101/https://api.sp.kingdomhearts.com/information/list`
- **Web archive (dark)**: `https://web.archive.org/web/20210625000652/https://api.sp.kingdomhearts.com/dark/information/list`
- **Notes**: List of news items with date, category badge, and title. Each item links to a detail page. Dark variant used by the in-game webview (dark background matches the game UI).

### 3. Information Detail
- **Local (light)**: `GET /information/detail/{id}`
- **Local (dark)**: `GET /dark/information/detail/{id}`
- **Original**: `http://api.sp.kingdomhearts.com/information/detail/{id}`
- **Web archive**: `https://web.archive.org/web/20210610101101/http://api.sp.kingdomhearts.com/information/detail/77506`
- **Notes**: Individual notice with title bar (date + category badge), HTML body content, and a fixed "Back" button bar at the bottom. The body uses alert classes for colored text (alert01=cyan, alert02=gold, alert03=orange, etc.).

### 4. Draw Probabilities
- **Local**: Not yet implemented
- **Original**: `http://api.sp.kingdomhearts.com/information/draw/{id}`
- **Web archive**: `https://web.archive.org/web/20180913051738/http://api.sp.kingdomhearts.com/information/draw/1004`
- **Web archive (2)**: `https://web.archive.org/web/20180811070948/http://api.sp.kingdomhearts.com/information/draw/556#medal_1808112`
- **Notes**: Gacha medal draw probability tables. Uses the detail page CSS plus table styles (.tr1/.tr2 alternating rows, .td1/.td2 columns). The `[General]` links are anchor jumps (`#medal_XXXXXXX`) to sections on the same page, not separate pages. Shows rarity breakdown (3-7 star) and per-medal probabilities.

## Categories

| ID | Class | EN Label | JP Label | Background | Border |
|----|-------|----------|----------|------------|--------|
| 1 | cat1 | IMPORTANT | 重要なお知らせ | #ed5b60 | #eda1a4 |
| 2 | cat2 | UPDATE | アップデート | #9dc668 | #b8c7a5 |
| 3 | cat3 | END | 終了 | #872bc4 | #a067c5 |
| 4 | cat4 | MAINTENANCE | メンテナンス | #f78d14 | #f7b15f |
| 5 | cat5 | RECOVERY | 復旧 | #f249dc | #f391e6 |
| 6 | cat6 | CAMPAIGN | キャンペーン | #872bc4 | #a067c5 |
| 7 | cat7 | ERROR | 障害 | #bc3846 | #bd7179 |
| 8 | cat8 | EVENT | イベント | #14caf7 | #5fd8f7 |
| 9 | cat9 | INFORMATION | お知らせ | #4271d6 | #819bd5 |
| 10 | cat10 | OTHER | その他 | #7a7a7a | #a1a1a1 |

## Alert Text Classes (used in detail/draw page content)

| Class | Color | Use |
|-------|-------|-----|
| alert01 | #00d4ed (cyan) | Section headers |
| alert02 | #ffcd4a (gold) | Highlights, quest numbers |
| alert03 | orange | Star headlines |
| alert04 | #888 (gray) | Muted text |
| alert05 | violet | Special highlights |
| alert06 | yellow | Warnings |
| alert07 | greenyellow | Positive notes |
| alert_pow | #ff4a74 | Power attribute |
| alert_spe | #5cd94a | Speed attribute |
| alert_mag | #62a7ff | Magic attribute |

## Static Assets

Located in `server/static/img/`:

| File | Source | Description |
|------|--------|-------------|
| bg_light.png | `cache.sqex-bridge.jp/img/7JzqN464T` | Light theme background (KH artwork, 277KB) |
| bg_dark.png | `cache.sqex-bridge.jp/img/9efqNF9vA` | Dark theme background (232KB) |
| btn_back.png | `cache.sqex-bridge.jp/img/oUpJN3GJ8` | "Back" button image (9KB) |
| btn_bar.png | `cache.sqex-bridge.jp/img/7JzjNmCER` | Bottom bar gradient background (282B) |
| arrow.png | `cache.sqex-bridge.jp/img/7JzyN8Yjp` | List item arrow indicator (393B) |

All fetched from `web.archive.org` captures of the original CDN.

## API Handlers (JSON, not HTML)

The game also requests notice data via the encrypted API:
- **Action 28** (`/system/information/list`) — returns `{informations: [...]}` JSON
- **Action 29** (`/system/information/list/151203`) — same as 28
- **Action 30** (`/system/information/detail`) — returns `{information: {url: "..."}}` with the webview URL

These are in `handlers.py`, not `information.py`.

## Implementation

All HTML routes are in `server/src/information.py` using a FastAPI `APIRouter` (no prefix).
The router is included in `app.py` via `app.include_router(html_router)`.
