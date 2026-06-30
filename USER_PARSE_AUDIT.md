# UserProfile::parse Audit — v1.0.1 /user Response

Verified against decompiled `libcocos2dcpp_0002.c` (arm64-v8a, v1.0.1)
and `server/src/handlers.py` `handle_user()` (line 80-139).

**Notation**: `& 0x04` = kIntFlag, `& 0x08` = kUintFlag, `& 0x10` = kStringFlag,
`& 0x20` = kUint64Flag, `type==3` = object, `type==4` = array.

JSON `0` has flags: kIntFlag(0x04), kUintFlag(0x08), kInt64Flag(0x10), kUint64Flag(0x20).
JSON `false` has flag: kFalseFlag(0x100) only. It does NOT have 0x04 or 0x08.

---

## 1. User::parse (line 13535)

**Path**: `root` (type==3) -> `"userData"` (type==3) -> `"user"` (type==3)

| # | Field              | Flag Check       | Our Value                    | Type OK? | Verdict |
|---|--------------------|------------------|------------------------------|----------|---------|
| 1 | userId             | `& 0x20` (uint64)| `uid` (int, e.g. 1)         | 0 has 0x20 | PASS |
| 2 | nativeUserId       | `& 0x20` (uint64)| `uid` (int, e.g. 1)         | 0 has 0x20 | PASS |
| 3 | platformId         | `& 0x04` (int)   | `2` (int)                    | Yes      | PASS |
| 4 | userName           | `& 0x10` (string)| `"Player"` (string)          | Yes      | PASS |
| 5 | gender             | `& 0x04` (int)   | `0` (int)                    | Yes      | PASS |
| 6 | comment            | `& 0x10` (string)| `""` (string)                | Yes      | PASS |
| 7 | deviceType         | `& 0x04` (int)   | `2` (int)                    | Yes      | PASS |
| 8 | continueLoginCount | `& 0x04` (int)   | `1` (int)                    | Yes      | PASS |
| 9 | isFleeze           | `& 0x04` (int)   | `0` (int)                    | Yes      | PASS |
|10 | fleezedDatetime    | `& 0x10` (string)| `"2000-01-01 00:00:00"`      | Yes      | PASS |

Note: `a3==0` so `nativeTagName` is NOT checked. Only checked when `a3==1`.

**Date::init** on fleezedDatetime: expects `"YYYY-MM-DD HH:MM:SS"` format. Our value uses dashes. PASS.

### Sub-parser verdict: **PASS**

---

## 2. UserDetail::parse (line 14006)

**Path**: `root` (type==3) -> `"userData"` (type==3) -> `"userDetail"` (type==3)

| # | Field                          | Flag Check       | Our Value | Type OK? | Verdict |
|---|--------------------------------|------------------|-----------|----------|---------|
| 1 | level                          | `& 0x04` (int)   | `1`       | Yes      | PASS |
| 2 | exp                            | `& 0x04` (int)   | `0`       | Yes      | PASS |
| 3 | luxRank                        | `& 0x04` (int)   | `0`       | Yes      | PASS |
| 4 | luxGetRatio                    | `& 0x04` (int)   | `100`     | Yes      | PASS |
| 5 | titleLeftId                    | `& 0x04` (int)   | `0`       | Yes      | PASS |
| 6 | titleRightId                   | `& 0x04` (int)   | `0`       | Yes      | PASS |
| 7 | titlePlateId                   | `& 0x04` (int)   | `0`       | Yes      | PASS |
| 8 | maxDeckCost                    | `& 0x04` (int)   | `30`      | Yes      | PASS |
| 9 | playTimezones                  | `type==4` (array) | `[0,0,0,0,0,0]` | Yes | PASS |
|   | (each element)                 | `& 0x04` (int)   | `0` (int) | Yes      | PASS |
|10 | playFrequently                 | `& 0x04` (int)   | `0`       | Yes      | PASS |
|11 | partyId                        | `& 0x20` (uint64)| `0`       | 0 has 0x20 | PASS |
|12 | unionId                        | `& 0x04` (int)   | `1`       | Yes      | PASS |
|13 | maxMedal                       | `& 0x04` (int)   | `100`     | Yes      | PASS |
|14 | mvpCount                       | `& 0x04` (int)   | `0`       | Yes      | PASS |
|15 | equipCoordinateNo              | `& 0x04` (int)   | `0`       | Yes      | PASS |
|16 | lastClearStageId               | `& 0x04` (int)   | `0`       | Yes      | PASS |
|17 | lastPlayNormalSphereBoardId    | `& 0x04` (int)   | `0`       | Yes      | PASS |
|18 | lastPlayStageSphereBoardId     | `& 0x04` (int)   | `0`       | Yes      | PASS |
|19 | lastPlayRaidSphereBoardId      | `& 0x04` (int)   | `0`       | Yes      | PASS |
|20 | lastPlayColosseumSphereBoardId | `& 0x04` (int)   | `0`       | Yes      | PASS |
|21 | isGuilt                        | `& 0x08` (uint)  | `0`       | 0 has 0x08 | PASS |

### Sub-parser verdict: **PASS**

---

## 3. UserPoint::parse (line 13723)

**Path**: `root` (type==3) -> `"userData"` (type==3) -> `"userPoint"` (type==3)

| # | Field               | Flag Check       | Our Value                  | Type OK? | Verdict |
|---|---------------------|------------------|----------------------------|----------|---------|
| 1 | money               | `& 0x04` (int)   | `0`                        | Yes      | PASS |
| 2 | lux                 | `& 0x20` (uint64)| `0`                        | 0 has 0x20 | PASS |
| 3 | totalLux            | `& 0x20` (uint64)| `0`                        | 0 has 0x20 | PASS |
| 4 | spherePoint         | `& 0x04` (int)   | `0`                        | Yes      | PASS |
| 5 | kizunaPoint         | `& 0x04` (int)   | `0`                        | Yes      | PASS |
| 6 | raidPoint           | `& 0x04` (int)   | `0`                        | Yes      | PASS |
| 7 | attack              | `& 0x04` (int)   | `100`                      | Yes      | PASS |
| 8 | defense             | `& 0x04` (int)   | `100`                      | Yes      | PASS |
| 9 | baseHp              | `& 0x04` (int)   | `100`                      | Yes      | PASS |
|10 | hp                  | `& 0x04` (int)   | `100`                      | Yes      | PASS |
|11 | ap                  | `& 0x04` (int)   | `50`                       | Yes      | PASS |
|12 | maxHp               | `& 0x04` (int)   | `100`                      | Yes      | PASS |
|13 | maxAp               | `& 0x04` (int)   | `50`                       | Yes      | PASS |
|14 | lastApDatetime      | `& 0x10` (string)| `"YYYY-MM-DD HH:MM:SS"`   | Yes      | PASS |
|   | (Date::init)        |                  | dash format                | Yes      | PASS |
|15 | stageSpherePoint    | `& 0x04` (int)   | `0`                        | Yes      | PASS |
|16 | raidSpherePoint     | `& 0x04` (int)   | `0`                        | Yes      | PASS |
|17 | colosseumSpherePoint| `& 0x04` (int)   | `0`                        | Yes      | PASS |
|18 | stageSkipTicket     | `& 0x04` (int)   | `0`                        | Yes      | PASS |

### Sub-parser verdict: **PASS**

---

## 4. lastActionDatetime (line 26270)

**Path**: `root` -> `"userData"` (type==3) -> `"lastActionDatetime"` (flag `& 0x10`, string)

Our value: `now` = `"YYYY-MM-DD HH:MM:SS"` (string, dash format).

The code checks:
1. `root["userData"]` must be type==3 (object) -- YES
2. `["lastActionDatetime"]` must have `& 0x10` (string flag) -- YES
3. `Date::init()` must succeed (requires dash-delimited date) -- YES

### Sub-parser verdict: **PASS**

---

## 5. UserMedal::parse (line 15136)

**Path**: `root` (type==3) -> `"userMedals"` (type==4, array)

Our value: `[]` (empty array).

**Critical analysis of empty array behavior** (lines 15178-15206):

```
v15 = v5;          // v5 = array length = 0
if ( v5 ) {        // 0 is falsy, so the loop body is SKIPPED entirely
  ...
}
v10 = v7 == v15;   // v7 = 0 (initialized before the if), v15 = 0 => true
if ( !v10 ) {      // false, so we do NOT null out v3
  v3 = 0;
}
```

With an empty array: `v5 = 0`, the loop is skipped, `v7 = 0`, `v15 = 0`,
so `v7 == v15` is **true**, and the parser returns the allocated (valid) object.

**Empty array does NOT return null.** It returns a valid UserMedal with 0 entries.

### Sub-parser verdict: **PASS**

---

## 6. UserSkill::parse (line 15424)

**Path**: `root` (type==3) -> `"userSkills"` (type==4, array)

Our value: `[]` (empty array).

Same structure as UserMedal::parse (lines 15467-15496):

```
v15 = v5;          // v5 = 0 (array length)
if ( v5 ) {        // skipped
  ...
}
v10 = v7 == v15;   // v7=0, v15=0 => true
if ( !v10 ) {      // not taken
  v3 = 0;
}
```

**Empty array does NOT return null.** Returns valid UserSkill with 0 entries.

### Sub-parser verdict: **PASS**

---

## 7. UserAvatar::parse (line 14554) -> Coordinate::init (line 14455)

**Path**: `root` (type==3) -> `"userAvatar"` (type==3) -> Coordinate::init

| # | Field                | Flag Check       | Our Value | Type OK? | Verdict |
|---|----------------------|------------------|-----------|----------|---------|
| 1 | myCoordinateNo       | `& 0x04` (int)   | `0`       | Yes      | PASS |
| 2 | gender               | `& 0x04` (int)   | `0`       | Yes      | PASS |
| 3 | hairPartsId          | `& 0x04` (int)   | `0`       | Yes      | PASS |
| 4 | hairColorPartsId     | `& 0x04` (int)   | `0`       | Yes      | PASS |
| 5 | facePartsId          | `& 0x04` (int)   | `0`       | Yes      | PASS |
| 6 | bodyPartsId          | `& 0x04` (int)   | `0`       | Yes      | PASS |
| 7 | skinPartsId          | `& 0x04` (int)   | `0`       | Yes      | PASS |
| 8 | accessoriesPartsIds  | `type==4` (array) | `[]`     | Yes      | PASS |

Empty `accessoriesPartsIds` array: length is 0, the while loop is skipped (`v14 = 0`,
the `if (v14)` at line 14526 is false), and `v4 = 1` (success) at line 14525 is returned.

### Sub-parser verdict: **PASS**

---

## 8. UserKeyblade::Keyblade::init (line 15764)

**Path**: `root` -> `"userKeyblade"` (type==3 checked at line 26329-26330)

| # | Field           | Flag Check        | Our Value                   | Type OK? | Verdict |
|---|-----------------|-------------------|-----------------------------|----------|---------|
| 1 | userKeybladeId  | `& 0x20` (uint64) | `1`                        | 1 has 0x20 | PASS |
| 2 | category        | `& 0x04` (int)    | `0`                        | Yes      | PASS |
| 3 | keybladeId      | `& 0x04` (int)    | `1`                        | Yes      | PASS |
| 4 | deckMedals      | `type==4` (array)  | `[]`                      | Yes      | PASS |
|   | (each element)  | `& 0x20` (uint64)  | (none, empty)             | N/A      | PASS |
| 5 | burst           | `& 0x04` (int)    | `0`                        | Yes      | PASS |
| 6 | totalAttack     | `& 0x04` (int)    | `0`                        | Yes      | PASS |
| 7 | totalDefense    | `& 0x04` (int)    | `0`                        | Yes      | PASS |
| 8 | isFavorite      | `& 0x04` (int)    | `0`                        | Yes      | PASS |
| 9 | getDatetime     | `& 0x10` (string)  | `"2000-01-01 00:00:00"`   | Yes      | PASS |

Empty `deckMedals`: length is 0, `v24 = 0`, the `if (v24)` at line 15828 is false,
loop is skipped, continues to `burst` field. PASS.

### Sub-parser verdict: **PASS**

---

## 9. Record::init (line 26336)

**Called as**: `hole::network::api::Record::init(v2 + 34)`

This function takes only ONE argument (the destination struct pointer). It does NOT
receive any JSON value -- it is a pure initialization function that sets defaults.
The JSON check is done separately at lines 26332-26335:

```c
*(_DWORD *)(rapidjson::...::operator[](a2, "userRecord") + 12) == 3
```

This only checks that `root["userRecord"]` is type==3 (an object). No fields are read.

Our value: `{}` (empty object). Type is 3 (object). PASS.

Record::init with one arg always returns 1.

### Sub-parser verdict: **PASS**

---

## 10. Ranking::init (line 22913)

**Path**: `root` -> `"userRanking"` (type==3, checked at line 26339-26340)

| # | Field | Flag Check        | Our Value | Type OK? | Verdict |
|---|-------|-------------------|-----------|----------|---------|
| 1 | lux   | `& 0x20` (uint64) | `0`       | 0 has 0x20 | PASS |
| 2 | rank  | `& 0x04` (int)    | `0`       | Yes      | PASS |

### Sub-parser verdict: **PASS**

---

## 11. Party conditional (line 26342-26347)

The code reads `partyId` from UserDetail (offset 40, which is the uint64 partyId field).
If partyId == 0, the party check is SKIPPED (short-circuit OR: `!*(_QWORD *)v45`).

Our `partyId` is `0`, so the `!*(_QWORD *)v45` evaluates to true, and the
`Party::init` branch is never entered.

We do NOT need a `"party"` key in the response. PASS.

### Sub-parser verdict: **PASS**

---

## 12. linkPlatformId (line 26348-26351)

**Path**: `root` -> `"linkPlatformId"` (flag `& 0x10`, string)

Our value: `""` (empty string). This is a JSON string, so it has the 0x10 string flag.

### Sub-parser verdict: **PASS**

---

## Overall Result: ALL 12 SUB-PARSERS PASS

No bugs found. The `/user` response structure from `handle_user()` correctly satisfies
every type check, field name, and navigation path expected by `UserProfile::parse`.

### Key findings:

1. **Empty arrays are safe**: Both `UserMedal::parse` and `UserSkill::parse` correctly
   handle empty arrays (`[]`). The loop count check `v7 == v15` passes when both are 0.

2. **`Record::init` does not read JSON**: It only initializes the struct with defaults.
   The only JSON requirement is that `root["userRecord"]` exists and is type==3 (object).
   Our `{}` satisfies this.

3. **Party is safely skipped**: Since `partyId == 0`, the party parser is never invoked.
   No `"party"` key is needed.

4. **`isGuilt` uses `& 0x08` (kUintFlag)**: Not `& 0x04`. JSON `0` has both flags, so
   this is fine. But if someone ever sent `false` here, it would FAIL (bool lacks 0x08).

5. **`isFleeze` uses `& 0x04` (kIntFlag)**: We send `0` (int). If someone sent `false`,
   it would FAIL (bool lacks 0x04).

6. **`isFavorite` uses `& 0x04` (kIntFlag)**: We send `0` (int). Same bool warning.

7. **Date fields**: All use dash-delimited format `"YYYY-MM-DD HH:MM:SS"` as required.
