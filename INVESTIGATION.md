# Server Error Investigation

## Status
The v1.0.1 client connects, authenticates, and proceeds through the startup
sequence but shows "Server Error" after the last API call in the chain.

## Working endpoints
1. PUT /system/status — status check with encrypted server URL
2. GET /login/token — returns bridge URL
3. POST /bridge — session establishment (32-char hex key)
4. POST /login — login response with newcomer/tutorial flags
5. GET /system/need/url — 10 URL strings
6. GET /system/coppa — age restriction values

## Failing point
- With newcomer=false: fails after GET /user (action 1)
- With newcomer=true: fails after POST /tutorial/user/create (action 61)

In both cases:
- Server returns 200 with valid-looking JSON
- Client accepts (no retry loop)
- "Server Error" dialog appears
- No further API requests made

## Response format
Both plain JSON (application/json) and encrypted (application/encoded-json
with URL-encoded base64 AES) have been tried. Same result.

## Key findings from decompile
- Response detection: searches HTTP response headers for content-type strings
  "application/json" (plain) and "application/encoded-json" (encrypted)
- Ret::parse requires: isMaintenance (bool), sessionTO (bool), isNewDayPeriod (int),
  versionApp (string), versionRes (int), versionDat (int), functionFlags (int),
  serverTime (string date "YYYY-MM-DD HH:MM:SS")
- Login::parse requires: login.newcomer (bool), login.tutorial (bool),
  login.acquirableLoginBonus (bool), login.progression (int)
- TutorialProgress::parse requires: tutorial.userTutorialId (int64),
  tutorial.progression (int), tutorial.name (string), tutorial.inviteCode (string)
- User::parse requires userData.user with 10 fields, plus UserDetail, UserPoint,
  lastActionDatetime, userMedals[], userSkills[], userAvatar, userKeyblade,
  userRecord{}, userRanking, linkPlatformId

## Theories remaining
1. The action-specific parser callback returns an error StatusCode even though
   the response JSON appears valid. Possible causes:
   - A type mismatch not caught by analysis (e.g., field needs uint64 not int64)
   - A field value that's invalid (e.g., keybladeId=1 doesn't exist in master data)
   - The callback checks additional conditions beyond just parsing
2. The game logic after successful parsing fails due to missing master data,
   resources, or game state (e.g., trying to load tutorial assets that don't exist)
3. The response content-type is being sent with extra params (e.g., charset=utf-8)
   that cause the pattern search to fail

## verifyResponse analysis (from assembly 4BB4C5.asm)

The function uses a jump table with action_id - 1 as index.

Key mappings (CONFIRMED from assembly):
- Case 23 (action 24 = /system/coppa): calls SystemNeedUrl::parse, checks [this+0x54]
- Case 24 (action 25 = /system/master): calls SystemCoppa::parse, checks parse result at [SP+0x458]
- Case 25 (action 26 = /system/resource): calls MasterDataManager::update, returns its result
- Case 26 (action 27 = /system/resourceEv): calls ResourceDataManager::update, returns its result

The blocker: case 24 calls SystemCoppa::parse on the /system/master response.
The parse result at SP+0x458 (shared_ptr data pointer) is checked. If null → returns 0.

Our response includes misc.{"116":13,"900":0,...} but SystemCoppa::parse still returns null.
Need to investigate WHY the parse fails on valid-looking data.

MasterDataManager::update (called for /system/resource) returns 1 as long as
master.revision and master.count are valid ints, regardless of count value.

Binary patching was attempted but libhoudini ARM translation crashes on
modified function prologues.

## Next steps
- Investigate SystemCoppa::parse failure: the decompile at line 21727 might
  have issues with the decompiler output. Read the ASSEMBLY for SystemCoppa::parse
  instead of trusting the decompile.
- Check if the `& 8` check (uint) actually corresponds to a different flag
  in this rapidjson version.
- Try sending all coppa values as unsigned (use large positive values instead of 0)
- Alternatively, find the exact rapidjson flag layout used by this build
