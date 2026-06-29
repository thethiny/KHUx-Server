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

## Next steps
- Try using Frida to hook the callback function and log the StatusCode
- Check if the response content-type header has extra parameters
- Try matching the exact response format from xlash123/khux-re-api
- Check if the game expects cookies (Set-Cookie headers) from the server
