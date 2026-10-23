# KHUx private server

A replacement for the official server of Kingdom Hearts Union χ, written for the **v1.0.1 client**. The game
shut down in 2021 and no traffic from the original server was ever recorded, so every response here was worked out
from the client's own code: what each request sends, what each parser reads, and what the client checks
(`APIManager::verifyResponse`).

The client stays as it shipped; the server is ours. Where the client cannot tell us how the original server
behaved (drop rates, raid chances, campaign rules), the rule is our own and is listed in [GUESSES.md](GUESSES.md).

## What works

The v1.0.1 client plays against it without patches: the session handshake, the resource and master data
downloads, the tutorial, story quests with missions and rewards, raids, medals (enhance, evolve, skills, sell),
keyblades and decks, the Avatar Board, draws, AP, presents, serial and invitation codes, parties (unions) with chat,
colosseum, rankings, events and campaigns, login bonuses, avatars, and the in-game notice pages. Player state persists per user in SQLite (`khux.db`).

## Running

```
pip install -r requirements.txt
cp .env.example .env          # then set KHUX_DATA_DIR (and KHUX_REPO_DIR)
KHUX_VERSION_RES=1 python run.py
```

`run.py` serves plain HTTP on port 80, which is what v1.0.1 uses. `--fresh` deletes the database first (a new
account), `--port` picks another port, `--ssl` serves HTTPS on 443 for later client versions.

The client has to reach it under the game's own host names (`api.sp.kingdomhearts.com` for v1.0.1,
`psg.sqex-bridge.jp` for the handshake). The native PC build in `../recomp` redirects every name to `127.0.0.1` by
itself. On an Android device or emulator, point those names at this machine (hosts file or `dns_proxy.py`);
[SETUP.md](SETUP.md) walks through that for BlueStacks.

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `KHUX_DATA_DIR` | (required) | Game data folder: `misc.mp4`, the master data `m/`, the downloadable resources |
| `KHUX_REPO_DIR` | | Repository root, for the generated `misc.png` index |
| `KHUX_VERSION_RES` | `0` | Resource version sent at login; `1` makes a fresh client download its resources |
| `KHUX_FUNCTION_FLAGS` | `0x07` | Menu features the client shows (invitation codes, serial codes, shop benefit, ...; `0x207` adds the Facebook button) |
| `KHUX_AP` | | Fixed AP value, for testing |
| `KHUX_EVENT_NOW` | | `YYYY-MM-DD HH:MM`: fake server time for events, campaigns and login bonuses |
| `KHUX_WEEK_START` | `0` | Day the ranking week starts (0 = Monday .. 6 = Sunday) |
| `KHUX_CAMPAIGNS` | `data/campaigns.json` | Campaign schedule |
| `KHUX_BANNER_URL` | | Where the draw banner art is hosted |
| `KHUX_MISC_907` | `30` | The age-check setting; `0` shows the birthday prompt (testing) |
| `KHUX_CHAT_SECRET` | | Secret for party chat tokens |

## Data

The master data (49 tables) is served in the v1.0.1 layout. The values come from a v1.1.3 dump, the closest to the
2015 game we have; the layouts are read from the client's own parsers. `data/` holds the tables as served;
`data_113`, `data_431` and `data_501` are the sources from later versions, kept for reference. Content from later
versions is used as data only, with values recalibrated to the 1.0.1 balance.

## Code

```
run.py              starts the server
src/app.py          FastAPI app: the handshake, request decryption, routing, resources
src/handlers.py     the game API, one handler per action ID
src/state.py        per-user persistent state (medals, keyblades, decks, materials, quests, raids, flags)
src/crypto.py       request and response encryption
src/bridge.py       sqex-bridge session handshake
src/master.py       master data encoding
src/gacha.py, raid.py, party.py, chat.py, colosseum.py, ranking.py, events.py, stagemap.py, information.py
static/             notice pages and images
```

Reference notes: [GUESSES.md](GUESSES.md) (our own rules and open questions), [API_MAP.md](API_MAP.md) (action
IDs), [AUTH_FLOW.md](AUTH_FLOW.md) (the handshake and encryption), [RESPONSE_SCHEMA.md](RESPONSE_SCHEMA.md) and
[USER_PARSE_AUDIT.md](USER_PARSE_AUDIT.md) (response fields), [HTML_PAGES.md](HTML_PAGES.md) (notice pages).
`INVESTIGATION.md` is an old debugging log.

## Credits

- API encryption research: xlash123/khux-re-api
- Asset decryption: bnnm (khuxdecrypt3), thethiny

## License

MIT, see [LICENSE](LICENSE). Credit is required: keep the copyright notice in copies and derived work. Game data and assets are not covered (they belong to Square Enix).
