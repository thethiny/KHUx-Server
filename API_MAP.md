# KHUx API Endpoint Map

Extracted from decompiled libcocos2dcpp v5 (IDA9).
The client uses an Action ID enum to identify each API call.
The server URL is `api-s.kingdomhearts.com`.

## Action → Endpoint Mapping

| Action | Response Fields | Purpose |
|--------|----------------|---------|
| 1 | userData | Get/sync user data (login, session) |
| 4 | *(quest start)* | Start quest |
| 5 | *(quest end/result)* | End quest, submit results |
| 10 | *(medal equip)* | Equip medals to keyblade |
| 11 | *(medal level)* | Level up medal |
| 12 | *(medal evolve)* | Evolve medal |
| 13 | *(medal guilt)* | Apply guilt/special attack bonus |
| 15 | *(keyblade equip)* | Equip keyblade |
| 16 | userMaterials | Get user materials |
| 17 | *(case 17 from init)* | Configuration/personal key exchange |
| 18 | *(event data)* | Event quest data |
| 19 | *(multi)* | Multiplayer quest |
| 20 | *(multi/289)* | Multiplayer variant |
| 21 | *(medal unlock)* | Unlock medal subslot |
| 22 | *(skill equip)* | Equip skill to medal |
| 23 | *(shop)* | Shop purchase |
| 24 | *(avatar)* | Avatar update |
| 25 | *(colosseum)* | Colosseum battle |
| 27/256 | *(pvp)* | PvP match |
| 28/257 | *(pvp result)* | PvP result |
| 29 | resourceEv | Event resource data |
| 30 | *(present box)* | Collect presents |
| 31/300 | *(daily)* | Daily bonus/login |
| 32 | infoBody | Information/news body text |
| 33 | *(friend medal)* | Set friend medal |
| 34 | activeCampaignIds | Active campaign list |
| 35 | *(tutorial)* | Tutorial progress |
| 38 | userName | Change user name |
| 39 | *(raid start)* | Start raid |
| 40 | *(raid end)* | End raid |
| 41 | titleLeftId, titlePlateId, titleRightId | Set user title |
| 42 | *(same as 9)* | Variant |
| 43 | *(keyblade forge)* | Keyblade forging |
| 44/182/190 | *(multi variant)* | Multiplayer variants |
| 46 | deleteUserMedalIds, isSubslotUpdate | Delete medals |
| 47 | supportUser | Support medal user info |
| 49 | lastUserPresentIds, userData, userMaterials | Collect presents + refresh |
| 50 | userMaterial | Get single material |
| 51 | sellUserMedalIds | Sell medals |
| 52 | sellUserSkillIds | Sell skills |
| 53 | userKeyblade | Get keyblade data |
| 54 | userMaterials | Refresh materials |
| 55 | componentUserMedalIds | Medal component IDs |
| 56 | attachmentMedalIds | Medal attachment IDs |
| 57 | userMedal | Get single medal data |
| 58 | userSkillIds | Get skill IDs |
| 60 | checkType, closeEventSphereBoardIds | Sphere board check |
| 61 | checkTypes, closeEventSphereBoardIds | Multi sphere board check |
| 73 | userSphere | Sphere data |
| 74 | unionId | Set/join union |
| 76 | drawMedalTypeId, userData | Gacha draw |
| 83 | party, partyId, partyLeader | Party info (create/join) |
| 86 | getDetail, party, partyId | Party detail |
| 87 | partyList | List parties |
| 98 | partyUserList | Party member list |
| 101 | partyOffer | Party invitation |
| 103 | partyOffer | Accept invitation |
| 104 | partyOffer | Decline invitation |
| 109 | eventCategory | Event categories |
| 111 | supportUsers | Support user list (quest) |
| 113 | supportUsers | Support user list (event) |
| 118 | raids | Active raids |
| 122 | supportUsers | Support user list (raid) |
| 125 | getRewardRankIds | Ranking reward IDs |
| 129 | luxRankingWeekly | Weekly lux ranking |
| 130 | luxRankingMonthly | Monthly lux ranking |
| 131 | luxRankingWeeklyOwn | Own weekly lux rank |
| 132 | luxRankingMonthlyOwn | Own monthly lux rank |
| 133 | luxRanking | Overall lux ranking |
| 134 | luxRanking | Lux ranking variant |
| 135 | highscoreRanking | Highscore ranking |
| 136 | highscoreRankingOwn | Own highscore rank |
| 137 | partyRanking | Party ranking |
| 138 | partyRankingOwn | Own party rank |
| 139 | colosseumRanking | Colosseum ranking |
| 140 | colosseumRankingOwn | Own colosseum rank |
| 142 | rankingReward, userData, userMaterials | Collect ranking reward |
| 143 | campaigns | Active campaigns |
| 145 | avatarSync, pinCode | Avatar sync (data transfer) |
| 148 | avatarSync, destAccept, srcAccept | Avatar sync confirm |
| 154 | platformType | Platform type |
| 166 | matchingMemberList | Multiplayer matching |
| 168 | userMaterials | Materials refresh |
| 170 | userId | User ID lookup |
| 173 | equipCoordinateNo | Avatar coordinate equip |
| 174 | petName | Set pet name |
| 178 | luxRankingBorder | Lux ranking borders |
| 179 | highscoreRankingBorder | Highscore borders |
| 180 | colosseumRankingBorder | Colosseum borders |
| 184 | partyRankingBorder | Party ranking borders |
| 188 | userId | User ID variant |
| 200 | pvpRanking | PvP ranking |
| 201 | pvpRankingOwn | Own PvP rank |
| 202 | pvpRankingBorder | PvP ranking borders |
| 216 | boardRooms | Board game rooms |
| 217 | applicationList | Application list |
| 220 | lsiGameId, lsiGetScore | LSI game score |
| 229 | boardRooms | Board rooms variant |
| 231 | categoryIds | Category IDs |
| 289 | *(same as 20)* | Multiplayer variant |

## Common Response Fields

These fields appear in many/all responses:

| Field | Description |
|-------|-------------|
| userData | Full user state (medals, currency, progress) |
| userMaterials | Materials inventory |
| userMedal | Single medal data |
| userKeyblade | Keyblade configuration |
| party | Party/guild info |
| raids | Active raid bosses |
| campaigns | Active events/campaigns |
| rankingReward | Ranking reward data |
| supportUsers | Available support medals from friends |

## Request Construction

The client constructs requests via `sub_3E4A08(output, json_payload, action_id, endpoint_name, ...)`.
All requests are encrypted: `JSON → gzip → base64 → AES-256-CBC → base64`.
The `sharedSecurityKey` from the session is the AES key.

## Sources

- Decompiled from `libcocos2dcpp_0002.c` lines 34380-46500 (v5/IDA9)
- Cross-referenced with xlash123/khux-re-api

## Complete Request Field Names (172 unique)

Extracted from all API request builders in the decompiled code.

### User/Account
`userId`, `userIds`, `userName`, `deviceType`, `deviceToken`, `platformType`, `platformId`, `platformIds`, `accessToken`, `pinCode`, `serialCode`, `adUniqueId`, `pushType`, `tutorial`, `resoMode`, `platform`

### Quest/Battle
`stageId`, `stageCount`, `rank`, `userKeybladeId`, `burst`, `isSkip`, `enemyDeadNumber`, `mimicDeadNumber`, `maximumDamage`, `guiltBurstMaximumDamage`, `lux`, `exp`, `money`, `getPoint`, `getMaterials`, `getEnemyDropItems`, `getTreasures`, `timeMissions`, `challengeId`, `resultType`

### Medal System
`medals`, `userDeckId`, `userDecks`, `petBaseSlotMedal`, `componentUserMedalIds`, `attachmentMedalIds`, `sellUserMedalIds`, `deleteUserMedalIds`, `isSubslotUpdate`, `subslotUserMedalIds`, `subslotMedals`, `updateKeybladeSubslots`, `keybladeSubslotId`, `keybladeIds`, `removeUserMedalId`, `userSkillIds`, `sellUserSkillIds`

### Gacha/Draw
`drawMedalTypeId`, `drawPetTypeId`, `count`

### Party/Social
`partyId`, `partyApplicantId`, `partyOfferId`, `name`, `message`, `playStyle`, `agreeType`, `memberCount`, `memberNum`, `appointId`, `dismissId`, `expelId`, `playTimezones`, `playFrequently`, `earnLuxRank`, `getDetail`, `level`, `supportUserId`

### Raid
`raidId`, `raidEnemyId`, `partsId`, `hp`, `damage`, `parts`, `totalDamage`, `rescueCount`, `memberList`

### Multiplayer
`multiId`, `multiRoomId`, `multiStageId`, `prevMultiRoomId`, `roomCreateUserId`, `isSteal`, `matchingMemberList`

### Avatar
`myCoordinateNo`, `defaultFlag`, `accessoryMask`, `accessoryHat`, `earPartsId`, `facePartsId`, `accessoryNecklace`, `legPartsId`, `accessoryBackpack`, `bodyPartsId`, `tailPartsId`, `accessorySpecial`, `accessoryMouth`, `updatePetCoordinateData`, `petName`, `equipCoordinateNo`

### Sphere Board
`sphereBoardId`, `releaseMasuId`, `allOpen`, `checkType`, `checkTypes`, `boardTypes`, `closeEventSphereBoardIds`

### Ranking
`rank`, `luxRanking`, `luxRankingBorder`, `highscoreRanking`, `highscoreRankingBorder`, `partyRanking`, `partyRankingBorder`, `colosseumRanking`, `colosseumRankingBorder`, `pvpRanking`, `pvpRankingBorder`, `getRewardRankIds`

### Shop/IAP
`productId`, `priceLocale`, `priceAmount`, `bridgeTransId`, `transactionId`, `receiptData`, `purchaseData`, `dataSignature`, `amazonUserId`, `amazonMarketplace`, `amazonBridgeTransId`, `shopPoint`

### Events/Campaigns
`eventCategory`, `activeCampaignIds`, `campaigns`, `resourceEv`, `receiveMissionIds`, `receivePresentIds`, `lastUserPresentIds`

### Dark Road
`bp`, `key1`, `key2`, `drawTicket`, `amulet`, `darkUserAsset`, `darkUserCards`, `darkUserMaterials`, `darkEnemyData`, `darkEnemyGroupHash`, `darkRewardItem`, `darkRewardItems`, `killedEnemyNum`, `killedEnemyBp`, `isUnlockMaterialEquipNumber`, `rewardType`, `rewardId`, `rewardNum`, `mapId`, `bgmBattle`, `enemyId`, `enemyType`

### Chat/Board
`chatId`, `roomName`, `thumbnailId`, `categoryId`, `categoryIds`, `bgmId`, `thresholdTime`, `boardRooms`, `applicationList`

### Settings/Notifications
`isNoticeAp`, `isNoticeHelp`, `isNoticeEvent`, `isNoticeLuxUp`, `isNoticePet`, `isTwitterThumbnail`, `viewedTheaterIds`

### Transfer/Sync
`avatarSync`, `destAccept`, `srcAccept`

### Misc
`infoId`, `infoBody`, `type`, `year`, `month`, `day`, `num`, `number`, `materialId`, `userMaterial`, `userMaterials`, `unionId`, `vsUserId`, `lsiGameId`, `lsiGetScore`, `__request_interval_order__`
