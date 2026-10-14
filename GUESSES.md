# Guesses and open questions

The original server was never captured, so some server behaviour cannot be read from the client. This file lists
every rule we **guessed** (the client accepts it, but the original may have differed) and every **open question**.
Each entry says where the guess lives and what would confirm it. Code comments mark the same spots with `GUESS:`.

Add new entries here whenever a handler makes a choice the client does not dictate.

**Data first (user, 2026-10-14):** where the game's own data has a value, trust it over the wiki - the wiki mostly
records later changes. **Wiki check (2026-10-14):** every entry was checked against the KHUX Wiki and 2015-16 guides (sources below in
the rows; most describe EN 2016 or JP late 2015, not 1.0.1 itself). Marks: **[wiki: confirmed]**, **[wiki:
corrected, implemented]**, **[conflict]** (the wiki disagrees with the user - the user's account is kept until
settled). Rows without a mark are not documented anywhere reachable.

## Coliseum (`src/colosseum.py`, handlers 114-118, 127/128)

| # | Guess | Where | How to confirm |
|---|---|---|---|
| C1 | **[wiki: confirmed]** One row normally: the next round of the current tier ("You cannot go back to the previous round"); several rows only after a skip (C9). | `colosseum.next_stage` | luckykhuxguide.tumblr.com/post/145249009485 |
| C2 | **[wiki: corrected, implemented]** Seasons are monthly ("resets on the 1st of every month"). The master seasons are dated 2015-16, so the season served rotates by calendar month through the 11 with stage maps; progress is a new record each month. GUESS: the rotation (the client still shows the master dates). | `colosseum.current_season`, `month_key` | khuxwiki.com/wiki/Coliseum_Quests |
| C3 | **[wiki: confirmed]** Coins per round on every clear, plus a tier reward when the tier is finished. Amounts come from the master data. | `colosseum.clear`, handler 118 | khuxwiki.com/wiki/Coliseum_Quests/April_2016 |
| C4 | **[wiki: confirmed]** The last tier has 999 rounds (endless). | `colosseum.clear` | khux-guides.tumblr.com/post/130271693276 |
| C5 | Lux from a Coliseum clear is added like a quest's (`lux` in the request). | handler 118 | The original may not have counted it toward rank. |
| C6 | AP is not deducted (`useAp` is shown, but AP is ignored server-wide). | handler 116 | Server-wide decision (free to play). |
| C7 | Ranking order **[wiki: confirmed, implemented]**: tier, then round, then the earliest to get there; only this server's players; "Own" = 5 places around you. Monthly ranking rewards (1-1000 / 1001-10000 / 10001-50000 in EN Apr 2016) are not handed out yet (RK4). | `_colosseum_ranking` | luckykhuxguide.tumblr.com/post/145249009485 |
| C8 | `colosseumInfo.status` 1 = open (2 shows "This event is unavailable."). Other values unknown. | `colosseum.STATUS_OPEN` | Client code only distinguishes 1 and 2. |
| C9 | **[data: settled, implemented]** Skip: a one-turn win unlocks the tier's `excellentUnlockCount` further rounds of the *active season* (the client shows that same number in the one-turn effect, StageDirection::all1turn_start). Per season: season 2 (Aug 2015) is a flat 10 (the user's memory), Sep/Oct 2015 18/15/9/6/3/3, season 1 18/18/16/14/9/7/4/3/3/3, later seasons their own lists; guides agree ("the least you can skip is 3"). `/colosseum` lists the unlocked rounds (tutorial popup 25); clearing round k credits every round up to k with coins and locks the rest. | `colosseum.clear` | client code; khux-guides 2015-10-01; luckykhuxguide.tumblr.com/post/145249009485 |
| C10 | **[user: settled, implemented]** A skip carries into the next tier at the offset (from round 15 of a 20-round tier, a skip of 10 opens 16-20 and the next tier's 1-5). Every round credited pays its own tier's coins; every tier finished on the way pays its tier reward once. Not yet seen in the client (a list spanning two tiers). | `colosseum.clear`, `_positions` | user |

## Quests and rewards (`src/handlers.py`, `src/stagemap.py`)

| # | Guess | Where | How to confirm |
|---|---|---|---|
| Q1 | Chest and enemy drop odds are out of 100000, one cumulative roll per chest / symbol. | `stagemap.roll_stage` | User's memory of drop rates. |
| Q2 | `StageClear::Reward.rewardkind` 1 = first clear, 2 = mission. The client never reads it back, so any int works. | handler 106 | Not observable; harmless. |
| Q3 | **[implemented]** A continue costs misc 113 = 100 Jewels: the data's price block 111-114 (medal box, AP, continue, union change; 111/112/114 confirmed by client code), matching the wiki's 100. | handler 105 | khuxwiki.com/wiki/Talk:Shop |
| Q4 | **[source, implemented]** First clear of every 5th story quest: 150 Jewels + 10,000 munny to the present box (khux-guides 2015-09; the story maps have no jewel chests, so it was server-side). Existing accounts were backfilled once. | `data/campaigns.json` (quest_bonus), handler 106 | khux-guides.tumblr.com/post/129025106101 |
| Q4 | Treasure guide (tutorialMisc 17 / widget 103) is suppressed with popupFlag bit 16: with our maps it would soft-lock. | popup flags | Whether 1.0.1's launch maps had a chest in quest 1060 area 1. |

## Raids (`src/raid.py`, handlers 107-113)

| # | Guess | Where | How to confirm |
|---|---|---|---|
| R1 | **[wiki: confirmed, implemented]** A boss appears after ~70-76 defeated enemies (we roll 68-82 per cycle; "account-specific"); story quests 24, 66, 102, 183, 200, 230, 660, 715 always bring one (on first clear); quest 3 and the Coliseum never do. A type-6 raid campaign divides the count. | `raid.kills_threshold`, `ALWAYS/NEVER_SPAWN_QUESTS`, handler 106 | khuxwiki.com/wiki/Talk:Raid_Boss, luckykhuxguide 145041684770 |
| R4 | **[wiki: confirmed]** Shared with the discoverer's party (help alerts also reached some union members - not modelled); Victory to all, MVP to top damage and the host, All Points Defeated to all; boss level +1 per defeat of your own boss, reset on the 1st. **Time limit 10 minutes** (Omega 20): `bossUpTime` is in minutes (implemented; was read as hours). | `raid.py` | khuxwiki.com/wiki/Raid_Boss |
| R2 | **[client: settled, implemented]** `raidTimeStatus` (RaidClear::TimeStatus, BattleResultDialog::openRaidResult): 1 = ended in time (boss up, or beaten by you), 2 = "The Raid Boss has escaped.", 3/4 = "A party member defeated the Raid Boss!", 5 = "No available Raid Boss." (Was 2 for a defeat: the user saw "ran away".) | handler 113 | client code |
| R3 | misc 200 (3000) is not a raid gauge (the client never reads it); probably a server-only parameter. | notes only | - |
| R5 | **[implemented]** Omega bosses (raidEnemy.rare 2; the client draws Raid_Rare_Pop, 20-minute limit from rareBossUpTime). The client never reads rareUpType/Arg, so the spawn rule is ours: type 3 = the Omega replaces a discovery once the player has defeated the trigger boss `rareUpTypeArg` times this month since their last Omega (10000 on early settings = never); type 2 = 1-in-arg chance; type 1 = always; settings whose Omega is the boss itself never switch. Wiki (khwiki): "chance of appearing if the initial Raid Boss is defeated quickly enough" - an alternative reading, not used. Data: early-quest settings (x000, about 750 stages) never give one; the first Ω-capable story quests are 132 (Behemoth Ω), 161 (Guard Armor Ω), 191 (Darkside Ω), 222, 302, 351. Event Ω (e.g. Fortress Crab Ω, Aug 2016) and event raid bosses (raidSetting ids are dates: 151022000 Hocus Pocus, 151214000 Jack in the Box, 160101000...) belong to event stages (stageKind 2), parked with events. Open: whether 1.0.1-era story already had Ω (the client fully supports them; no dated source). | `raid.omega_due`, handler 106 | khwiki.com/Raid_Boss, luckykhuxguide 145041684770 |
| R6 | No cap on raid participants and no help for union members outside the party (sources mention neither a cap nor how union help was chosen; Support Alerts went to the party). | `raid.visible` | luckykhuxguide 145041684770 |
| R7 | Raid-event quests ("Lure a ..." and the stages of eventType 2 events, e.g. "Raid Level: Legendary!") always bring their boss when cleared (unless the player already has one up); a "... Ω" lure brings the Omega. | `events.is_lure_stage`, handler 106 | - |

## Daily loop and menus (`src/handlers.py`, 15 / 45 / 60 / 66 / 67)

| # | Guess | Where | How to confirm |
|---|---|---|---|
| L1 | **[settled: user]** The daily reset is 12:00 in the server's local time (the wiki's "11:00 UTC" was the EN server's own clock). | `_bonus_day` | user |
| W1 | **[settled: user, old videos + 2016 guides]** The 5-day login bonus (bonusType 1: 50/50/100/100/200 Jewels) repeats after day 5: 500 per cycle, six cycles = the 3000 Jewels a month the user remembered. Each new day (12:00 server time) gives the next day of the cycle. | handler 60 | user; levelwinner.com, touchtapplay.com (Apr 2016) |
| L2 | A missed day does not restart the 5-day cycle (not documented; the 2016 guides say "log in consecutively"). The monthly 3000 Jewels the user remembered is this bonus (6 x 500), not daily missions; daily/weekly missions and the weekly pass are later features (4.3.1 client; khuxwiki Mission / Shop). | handler 60 | old videos |
| L3 | Login bonus rewards go to the present box (the response carries no user data). | handler 60 | Memories: did bonus Jewels arrive in the present box? |
| L4 | `total` sends the milestone reached today, else the next one (display). Milestones are granted once, on their day. | handler 60 | Footage of the login bonus screen. |
| L5 | Special bonuses (bonusType 3 "Newcomer Campaign", 4 events) are date-gated by their 2015-16 dates, so none is active. Could be re-dated later. | handler 60 | Decide later. |
| M1 | **[data, implemented]** New accounts start with a 50-medal box: misc 102 = 50 sits with the box step (103 = 5) and cap (104 = 500); a 2016 report also says 50. Existing saves keep their size. | `models.User.max_medal` | data; GameFAQs 2016 (search summary) |
| P1 | **[wiki: confirmed]** AP refill = 100 Jewels (and fills the special gauges). | handler 67 | khuxwiki.com/wiki/Talk:Shop |
| A1 | **[wiki: confirmed]** The Album shows every medal obtained on the account. | `state.add_medal`, handler 15 | khuxwiki.com/wiki/Album |
| A2 | `allMedalCount` = number of medal master rows. | handler 15 | The client never computes it. |
| S1 | The support medal picked in the medal popup is the one other players see; without a pick, deck slot 1. | `_support_medal` | - |
| S2 | **[source + user, implemented]** Support list (102): up to 10 players: party members first, then your Union by closest player level (Lux rank; GameFAQs 2016: "based on your player level and the level of the other friends... only medals from players in your own Union"), ties by player id so the same people recur; other Unions only fill the list when yours has too few. Each lends their chosen support medal (45). Sora only when no other player exists. | handler 102 | gamefaqs.gamespot.com/boards/158979-kingdom-hearts-unchained-x/74255411 |
| M2 | **[client + guides: settled, implemented]** Evolving (54) resets the medal to LV 1, EXP 0 of its new cap (the Evolve screen previews LV 1/<new max>; khux-guides 2015 "Medal evolution"). Evolve is only possible at max level (client rule). | handler 54 | khux-guides.tumblr.com/post/129291918121 |

## Parties and rankings (`src/party.py`, handlers 69, 74-98, 119-129, 139)

From the client (not guesses): max 30 members (hard-coded), 5 open requests per player, 30 invitations per party, requests/invitations expire after 72 hours (screen texts), agreeType 1 not accepting / 2 approval / 3 auto-join, party rank tiers 1 Diamond .. 5 Bronze, first party joined gives misc 117 (100) Jewels, union change costs misc 114 (100) and is refused in a party, `rankingStatus` 2 = rows shown. From the user: the leader is "absent" (takeover allowed) after 7 days with no login or no contribution to the party (we count Lux earned for it).

| # | Guess | Where | How to confirm |
|---|---|---|---|
| PT2 | At most misc 802 (10) admins. | `party.max_admins` | - |
| PT4 | Creating a party is free (neither request nor response carries Jewels). | handler 74 | Memories. |
| PT6 | `failedStatus` 1 = party full / closed, 2 = too many requests (the client only checks != 0). | `party.apply/offer` | - |
| PT7 | **[wiki: corrected, implemented]** Moderators (admins) may invite, accept requests, expel, promote other members to moderator, and edit name / play style / approval / message; only the leader hands over leadership; a leader must hand over before changing union (the client refuses union changes in a party). Leaving leader -> an admin, else the longest member (GUESS). | `party.py`, handlers 75, 86-91 | chiunion.tumblr.com/post/142729520571 |
| PT9 | Party login (77) grants nothing (no reward fields). | handler 77 | - |
| PT12 | Player search (92) lists players without a party; its filters are not applied. | handler 92 | - |
| PT13 | Only the order is documented (Diamond > Platinum > Gold > Silver > Bronze); the thresholds (top 5/15/35/65%) are ours. Individual S/A/B/C ranks came from the previous week's Lux place (~top 1000 / 10000 / 20000 / 100000). | `party.party_rank` | khux-guides 153222872056; chiunion 137052050876 |
| RK1 | **[settled: user]** Ranking weeks turn over at 08:00 server local time on the server's default weekday (Monday; `KHUX_WEEK_START` 0-6 overrides), months at 08:00 on the 1st. | `party.week_start`, `month_start` | user |
| RK2 | Rankings list only this server's players; "Own" shows the 5 places around you. | ranking handlers | - |
| RK3 | Party Lux = the Lux its members earned while in it, this week. Union Lux likewise. | `party.lux_since` | - |
| RK4 | **[implemented]** Ranking periods close and pay (ranking.py): Lux = category 5 weekly (union-aware), Party = 3 weekly, Coliseum = 4 monthly. 56 raises a flag per pending result; 130 delivers only announced results and grants exactly the reward row the client picks (its own rule from the ranking / rankingReward masters); paid once. Only participants (Lux > 0 / a Coliseum record) get a result. | `ranking.py`, handlers 56, 130 | data + client code |
| RK5 | **[implemented]** Every ranking period has its own master `ranking` row (rankingId = category x 1000000 + period number, 2025-2035, appended at load): the period's dates (sent as UTC) and the reward fields of the category's 2015-16 row in rotation. Popups and ranking screens show the real week/month. Changing KHUX_WEEK_START or the server time zone changes the rows: bump master_rev. | `ranking.dated_rows`, `ranking_id_for` | - |
| RK6 | The old Lux weekly / monthly rankings (categories 1, 2: flags rankingLuxWeekly / Monthly, actions 119-122) are not run - the 1.0.1 UI has no tab for them. Party results go to players who earned Lux for the party in the period. | `ranking.py` | - |
| RK7 | Union parade (129): all 5 unions are always listed (the client indexes name_1..name_5 unchecked) and every union has a top ranker; a union nobody played for gets a placeholder ("---", starting avatar, 0 Lux). | handler 129 `_parade_placeholder` | client code (crashes without them) |
| RK8 | **[user: corrected, implemented]** The union parade (129, shown at startup whenever its list is non-empty) shows LAST week's final standings, once per player per week (the first start after the weekly rollover); empty afterwards or when nobody earned Lux last week. | handler 129 (`parade_seen`) | user: it must not pop up every boot |
| U1 | **[wiki: confirmed, implemented]** 100 Jewels every time (no free first change documented); the week's Lux is wiped ("will be reset to zero and not count towards the week's rankings"); a cooldown before joining a new party (length unknown, not modelled). | handler 69 | chiunion.tumblr.com/post/142551110401 |

## Events and Special Quests (`src/events.py`, handlers 101 / 56, served evStage)

The client never checks event dates, weekdays or time slots; it shows whatever 101 returns. Every rule below is ours. What runs is data: `data/campaigns.json` (extra events, login gifts, daily login rewards, quest bonuses, disabled evStage / evCampaign rows), loaded at startup; edit it to change the schedule.

| # | Guess | Where | How to confirm |
|---|---|---|---|
| E1 | Dated events (evStage rows from the 1.1.3 dump, 2016) replay every year on their original month/day, opening 08:00 server time for their original length. Permanent rows (endTime 2037): Special Quests on their weekday flags, Proud Quests every day. | `events.window` | - |
| E2 | 2015-16 events with stages but no evStage row get hand-made rows (ids 9001+): Trick or Treat 10-22, Christmas + Lure a Jack in the Box 12-14, New Year's 01-01, Valentine's 02-08 (dates from their event raid settings, e.g. 151022000), Storming Sheep 01-15 (no date source); all 14 days, plain quest lists (eventType 3), category 2. Not yet: Squashing Shadows, Lure a Fortress Crab, the unnamed 61310 set, Jewel Jam / Daily Challenges (2016). | `data/campaigns.json` (kind event) | user's memory / old videos |
| E3 | Time-slot Special Quests (groupPattern 1000-1011, validMinute 30/60; the evGroupPattern table is lost): each pattern opens once a day at a fixed server hour (`SLOT_HOURS`), for everyone (no player groups). All-zero weekday flags = every day. | `events.SLOT_HOURS` | - |
| E4 | The Special Quest day turns over at the daily reset (12:00 server time). | `events._server_day` | - |
| E5 | Permanent rows that started after 2015 (2016 Daily Challenges, Moogle O' Glory, Lady Luck) are off (1.0.1 era). Category 4 (High Score, needs 1.1.3 score rewards) is never run. | `data/campaigns.json` disabledEventStageIds / disabledCampaignIds | - |
| E6 | Banners: the original images (cache.sqex-bridge.jp) are gone; the server draws them (event 640x140, gacha 940x136: name on a gradient). | `events.draw_banner`, `/event/banner`, `/banner/gacha` | replace with archived art if found |
| E7 | Campaigns (131 `campaigns`, evCampaign) follow the event schedule (E1, E3, E5); rows dated before the launch (2015-09-01) are test rows and never run. A campaign covers its stageId list, else stageType 1 = story, 2/3 = event stages, others = all. The server applies type 6 (raid encounter: fewer kills needed) and type 8 (Omega encounter, 200000 = 100%); the client applies AP / Lux itself; medal drop (type 1) multiplies the odds of medal slots in the server's drop roll. | `events.campaign_*`, handlers 131 / 106 | - |
| E8 | Limited boards (sphere openId 3: event boards type 4, raid boards type 5, limited Avatar / Coliseum boards) open and close on the same yearly replay as events (`events.replay_window`); a closed board is removed (progress lost) and granted fresh next year; boards every player gets from initItem never close. Event / raid coins carry over between events. | `state.board_available`, `close_spheres`, handlers 9 / 57 | - |
| E9 | **[client: settled, implemented]** Only events whose every quest has its map in the client's archive are offered (data/stage_files.json, tools/stage_files.py): the 2016 events' maps (500xxx, 61710, 580010, the Trials 63810+) came in event packs (evResource) that we don't have, and opening such an event crashes (SceneUtil::setBossTypeImage reads stage/mappoi_stg<id>.bin unchecked). This leaves the 2015 events, Special Quests and Proud Quests; 2016 events + their boards wait for the packs (maybe in the 4.4.0 assets). | `events.playable` | - |
| E10 | Dated login gifts (present box, replayed yearly, once per window; Start Dash once per day): Start Dash 50 Jewels/login (09-03..13), 2000 Jewels + Timeless River Mickey 5* (11-18..23), KH II King Mickey + Minnie 3* (12-04..13; rarity guessed), KH Aerith 5* (12-20..27; dates guessed), Sora & Donald & Goofy 6* (03-28..04-03; the 5* 'Sora & Friends' has no row), HD Aqua 5* (06-16..23, global). | `data/campaigns.json` (login_gift / daily_login), handler 59 | 4gamer / khuxwiki HD Aqua / chiunion 2016-06-16 |

## Party chat (`src/chat.py`, action 5)

| # | Guess | Where | How to confirm |
|---|---|---|---|
| CH1 | Every player owns every valid stamp (the starting set and the `require` 1/2/3 rule are unknown). | `chat.stamp_ids` | - |
| CH2 | **[client: settled]** Chat times (createAt) are Japan time (UTC+9): the client shows them minus 9 h plus the device offset. Game API times are UTC. | `chat._fmt` | seen in the exe |
| CH3 | The chat service is ours: chatId = party id, one room per party, tagName "t_<userId>", token = userId + HMAC (KHUX_CHAT_SECRET). Reports are only logged. No system messages (join / leave markers) are sent. | `chat.py` | - |

## Purchases and the VIP pass (handlers 7, 72, 73; `events.active`)

| # | Guess | Where | How to confirm |
|---|---|---|---|
| V1 | A weekly benefit (VIP pass, shop row 30 `gp.khuxww.jewel1700`, benefitId 100, benefitResetWeek "Sunday") ends at the weekly reset the shop text promises: "until Sun. 23:59 (PDT)" = Monday 06:59:59 UTC. | `_benefit_end` | - |
| V2 | **[user: implemented]** Every purchase succeeds for free (the host's fake Google Play store always buys; 72/73 grant it): number + bonus Jewels as FREE Jewels, the row's benefit, skip tickets kept in state (not shown in userPoint yet). Repeat purchases allowed. May need limits later for the economy. | handlers 72 / 73, `recomp/host/jni.c` GooglePlayManager | - |
| V3 | Special Quests not on today's schedule but covered by their benefit (benefitId + benefit<Day>) are listed: isLock 1 (locked teaser; tap opens the VIP offer) without the benefit, 2 (playable) with it. Munny Madness (1101) is VIP-only (no weekday). | `events.active` | - |
| T1 | **[client: settled]** /tutorial/status isFinished must be 1 after the tutorial (phase 995): with 0 the battle Continue dialog offered the tutorial's free revive ("During the tutorial, you can continue without spending Jewels") at level 102. | handlers 64 / 65 | client code (StageUI::openContinueDialog) |

## Serial and invitation codes (handlers 31-33, 62/63)

| # | Guess | Where | How to confirm |
|---|---|---|---|
| SC1 | The serial code strings are ours (`data/serialcodes.json`: KHUXLAUNCH -> 1000, FAMITSUAPP -> 1001, KEYLINKAGE -> 1002); the master has rewards but no codes. Test rows 1003/1008-1010 unmapped. One use per player per reward. | `data/serialcodes.json`, handler 31 | - |
| SC2 | The master's 2015 dates are ignored (the list still shows them as "Expiration Date"); rewards go to the present box (the client's own text says so). | handlers 31/32 | - |
| IC1 | An invitation code (8 characters, ours) is redeemed at tutorial step 2; both players get misc 115 (300) Jewels in the present box (text "You'll both get %d Jewels"); the invitee joins the inviter's party when it has room (else firstReward 0, "Unable to join") and takes the inviter's union. | handlers 33, 62, 63 | - |
| IC2 | The inviter is paid for at most 10 invitees (`INVITE_CAP`); the client shows invited / (invited + remaining). misc 116 (300) is never read. | `INVITE_CAP` | - |

## Other

| # | Guess | Where | How to confirm |
|---|---|---|---|
| O1 | Rank-up gives `player.luxMedal` as Avatar Coins and refills AP (from the popup texts). | handlers (lux rank) | Seen working in game; the amounts come from master data. |
| O2 | `userSphere.notChargedSphereBoardIds` is always empty (no reader found in 1.0.1). | `_user_sphere` | - |
| O3 | `/ranking/reward/check` (130) hands out nothing: no ranking periods end on this server. | handler 130 | Decide when rankings get periods. |
| O4 | Campaign multipliers (`evCampaign`) are all x1: no campaigns are scheduled. | `_campaign_power` | Decide which campaigns to run. |
