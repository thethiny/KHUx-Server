# KHUx Server

Private server reimplementation for Kingdom Hearts Union Cross.

## Goal

Reimplement the game's REST API so the original v5.0.1 client can connect
and play. The client communicates via HTTPS REST with AES-256-CBC encrypted
JSON payloads.

## Architecture

```
Client (v5.0.1 APK on emulator)
    │
    ├── DNS redirect: api-s.kingdomhearts.com → localhost
    ├── DNS redirect: psg.sqex-bridge.jp → localhost
    │
    └── HTTPS REST (AES-256-CBC + gzip + base64)
            │
            ▼
    Server (Python/FastAPI)
        ├── Auth: UUID-based session + sharedSecurityKey generation
        ├── API: Game endpoints (quest, medal, battle, etc.)
        ├── Data: Master tables from extracted m*.jpg files
        └── Assets: BGAD containers re-served as mode 0
```

## Status

- [ ] API endpoint map (in progress)
- [ ] Auth flow documentation (in progress)
- [ ] Server scaffold
- [ ] Asset re-packaging pipeline (mode 3 → mode 0)

## Docs

- `API_MAP.md` — complete list of client-expected endpoints
- `AUTH_FLOW.md` — session establishment and encryption details

## Credits

- API encryption research: xlash123/khux-re-api
- Asset decryption: bnnm (khuxdecrypt3), thethiny
- Game data extraction: KHUx Tools (../khux/)
