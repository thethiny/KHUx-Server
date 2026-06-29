# KHUx API Response Schema

Complete JSON response field names extracted from v1.2.3 decompiled client.
1123 field reads identified across 7 files.

## Response Envelope (every response)

| Field | Type | Description |
|-------|------|-------------|
| ret | int | Return code (0 = success) |
| isMaintenance | bool | Server maintenance flag |
| sessionTO | ? | Session timeout |
| isNewDayPeriod | bool | Daily reset flag |
| versionApp | string | Required app version |
| versionRes | string | Resource version |
| versionDat | string | Data version |
| functionFlags | ? | Feature flags |
| serverTime | int64 | Server timestamp |
| error | object | Error details |
| viewUrl | string | Redirect URL |
| nativeToken | string | Native session token |

## User Data (Action 1: userData)

### Identity
userId, nativeUserId, platformId, userName, gender, comment,
deviceType, continueLoginCount, isFleeze, fleezedDatetime,
nativeTagName, birthday

### Currency
money, lux, totalLux, spherePoint, kizunaPoint, raidPoint,
specialPoint, vipPoint, freeStone, payStone, stageSkipTicket,
superSkipTicket

### Stats
attack, defense, baseHp, hp, ap, maxHp, maxAp, lastApDatetime,
level, exp, luxRank, luxGetRatio, maxDeckCost, maxMedal,
mvpCount, equipCoordinateNo, lastClearStageId, isGuilt,
earnLuxRank, guiltBurstLv

### Titles
titleLeftId, titleRightId, titlePlateId

## Avatar

myCoordinateNo, gender, hairPartsId, hairColorPartsId,
facePartsId, bodyPartsId, skinPartsId, accessoriesPartsIds,
userAvatar, userAvatars, userAvatarPartsId, partsType,
avatarPartsId, userAvatarParts, isChangeCoordinate, backgroundId

## Medals

userMedalId, medalId, number, level, exp, attackUpperNumber,
defenseUpperNumber, burstUpperNumber, lock, upperCost,
guiltFactor, userSkills, userMedals, userMedal, getDatetime,
userSkillId, skillId, beforeEnhanceUserMedal, afterEnhanceUserMedal,
enhanceEffect, overwriteSkills, successOverwrite,
guiltBurstFirstLv, guiltBurstMaxLv, beforeEvolveUserMedal,
afterEvolveUserMedal

## Keyblades/Decks

userKeybladeId, userDeckId, category, keybladeId, deckMedals,
burst, totalAttack, totalDefense, isFavorite, userKeyblades, userDecks

## Materials

userMaterialId, materialId, number, userMaterials

## Raids

raidEnemyId, partsId, hp, attribute, rare, raidId, useAp,
timeLeft, feverFlag, feverTime, stageId, parts, damage,
cooperators, discovererUserId, mvpUserId, discoverer, mvp,
mvpTotalDamage, subdueId, mvpId, partAllId, raidRewards,
raid, raidStatus, raidTimeStatus, reliefFlag, user, players,
startRaidData, vitalsLog, partsLog

## Quests/Stages

score, clearMissionIds, stages, stageSkip, eventId, highScore,
campaign, userRandomEnemies, userEnemyDropItems, userTreasures,
startStageData, campaigns, luxMagnifications,
stageRewardUserMedalIds, highScoreReward, firstClearFlag,
newStageId, isLock, getHighscore, getHighscoreRewardIds

## Events

eventStageId, showIcon, bannerUrl, eventType, endTime, status,
message, stories, events

## Party

partyId, unionId, rank, name, playStyle, agreeType, memberCount,
leaderUserId, adminUserIds, leaderAppointDate, newcomerDate,
chatId, chatEndpointUrl, userParty, isJoin, isLeader, isAdmin,
flagFirstReward, joinDate, party, firstReward, partyApplicant,
partyApplicants, partyList, partyLeader, hasNewOffer, isApply,
hasNewApplicant, isNewLeader, newcomerUsers, isAbsenceLeader,
failedStatus, partyOfferId, partyOffers, offerDate

## Gacha

validAdd, drawMedalTypeId, drawType, sortId, payType, price,
lotCount, isDayLimited, userLimitedCount, userWarrantDisplayOfTime,
warrantMedalId, description, bannerUrl, gachaList, gachaBonus,
addType, userMedalIds, firstGetUserMedalIds

## Rankings

rankingDatas, rankingStatus, rankingTermStart, rankingTermEnd,
lastRank, updateTime, nextUpdateTime, arrivalTime, lastRankingId,
lastUnionRank, lastRankingResults, rankingRewardIds,
openRankingIds, rankingRewards, rankingColosseum, rankingParty,
rankingLuxWeekly, rankingLuxMonthly, rankingLux, rankingHighScore,
unionParade, rankingUnionResult, rankingUnionTopRanker

## Colosseum

colosseumStageId, colosseumStatus, colosseumInfo, colosseumStages,
userColosseum, userRank, userStageCount, userStageTotalCount,
stageCount, startColosseumData, clearColosseums, userColosseumRanking

## Sphere Board

userSphereBoardId, sphereBoardId, isBuy, status, unlockMasuIds,
userSphere, userSphereDatas, notChargedSphereBoardIds

## Present Box

userPresentId, resourceType, resourceId, number, limitDatetime,
message, created, userPresent, userPresentDatas, presentCount,
presentCountMax, userPresentCount

## Login

login, newcomer, tutorial, acquirableLoginBonus, progression,
data, loginBonusId, dayCount, loginBonus, continue, total, specials

## Chat

userChat, userId, tagName, userEndpointUrl, authToken, userToken, stampIds

## Payment

paymentInfo, cesaLimitAge, chargeMoneyThisMonth, lastchargeMoneyThisMonth

## Notifications

adminMypageTexts, openBanners, type, priority, text, id, limitDate

## Sources

Extracted from libcocos2dcpp.armebi_0002.c (v1.2.3 response parsing)
and libcocos2dcpp.armebi_0003.c (v1.2.3 request building)
