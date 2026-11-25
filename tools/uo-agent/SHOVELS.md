# Buying shovels with Clem

The short version (commands, watching, what to tell the user) is the skill `skills/uo-shovels/SKILL.md`. Offline
checks: `python3 -I shovels_test.py` (run after any change, before restarting the loop).

Started 2026-11-24. The tool is `shovels.py`; its log is `~/claude/uo-agent-work/shovels/shovels.log`, its state
`state.json` there (the round under way, every tinker's last stock and price, the bank's gold), `visits.jsonl` (every
tinker visit) and `vendors.json` (the NPCs and players seen). Newer notes win where they disagree with older ones.

## The job (the user, 2026-11-24)

"We're trying to get as many shovels as possible in the tool room." In their words:

- "When you go buy shovels you'll do the following each hour: go to the bank (ocllo bank rune), get gold (however much
  you think this shovel run will take based on how many shovels you think the vendors currently have, each hour some
  of them still start to sell more shovels, like 9 more I think). Go to all of the vendors in the tinkers runebook &
  buy all of their shovels, as many as you can, until you're weight is filled up. Then take them back and put them in
  the tool room. It will take many trips to the vendors and back to the castle. if gold gets low you go to the bank to
  get more. You dont' stop until you have bought all the shovels, and then you go to the castle tool room and wait for
  the next hour mark. When the next hour mark comes you do it again ... Keep doing it until I tell you to stop or you
  encounter a blocker (like you ran out of gold)."
- **The courtyard rune** ("skara"): "it comes to my castle courtyard ... When you recall here you should go into the
  door i'm next to to enter the castle (be sure to lock it, double check that it's locked) ... The reason you'll use
  the skara rune is to avoid having to fight, there are no monsters in the castle courtyard. You don't have to use the
  fighting logic."
- **The rune and the Tinkers runebook** "will be kept in my personal chest when we're not buying shovels and you'll
  have to retreive it and put it back when we stop buyig shovels. The personal chest is the top left chest of mine,
  near the window at the entrace of the caste in the southeast area. It's a secure chest" (938 top, `0x406E70A6`,
  "yours: runes and bags"). "When i say stop then put the rune & the tinerks runebook back in my chest."

## What's where

- **The courtyard rune is `0x406EAA74`**, in Clem's reagent bag, known by its serial only. The user marked it at
  15:53:55, named it "skara", then cast Mark on it again (15:54:50), which wiped the name: it reads "a recall rune for
  an unknown location". It lands him in the **north yard at 935,2328** (z 0), the "courtyard" the user means. **`0x408E20F9` is named "a recall rune for Skara"** but is the user's
  recall-home rune to the castle *front* (935,2356, outside, among creatures; the user's Razor macro 'recall-home'
  uses it; CASTLE.md's "Castle" rune). The first trip home (16:12:21) picked the rune by name and landed at the front:
  nothing was there, and Clem came in by the front door and the courtyard box rune (`castle.py in`). Now the serial is
  pinned, and a landing at the front goes in through the front door with the fight logic, then stops the loop.
- **The Ocllo Bank rune** `0x408F827E` ("a recall rune for Ocllo Bank"; it was the Ocllo Maps rune) lands at
  3686,2505. "bank" opens Clem's bank box `0x40951010`: **92,689 gold** on 2026-11-24 16:11.
- **The Tinkers runebook** `0x407B4809` (hue 1121), 7 runes, Recall flag under each (gems.recall_to; no charges):
  Britain Tinker 1424,1661; Jhelom 1395,3808; Minoc 2464,453; Trinsic 1841,2675; Vesper 2901,786; Magencia (Magincia)
  3714,2122; Serpents (Serpent's Hold) 2942,3510. Every landing so far on the spot the book gives. Clem's rules have
  25 tiles round each as an area (`tinker: ...`).
- **Clem's rules** (2026-11-24): "tinker" among the vendors, shovels (`0x0F39`, `0x0F3A`) among the goods, "bank"
  among the words.

## The tinkers (2026-11-24, the first round)

| Rune | Tinker (shovels) | Others there | Stock (first visit) | Price |
|---|---|---|---|---|
| Britain | Merele the tinker | Prentice the tinker guildmaster: no buy window ("Ah, 'tis Clem") | 19 | 14 |
| Jhelom | Joanna the tinker | Nadia the tinker guildmistress: no buy window | 19 | 14 |
| Minoc | Elad the tinker | Raven the tinker guildmistress | 19 | 14 |

- A shovel weighs 5 stones (90 stones for 19, less the gold paid). Clem's max is 390; with his own things (about 80
  stones), ~55 shovels fill him, before the gold's weight (50 coins a stone).
- "<name> buy" sometimes goes unanswered once; asked again it works (trips.shop).

## How it runs (shovels.py)

- `python3 -I shovels.py run [--now] [--once]`: from anywhere (the north yard or the courtyard: in; town or the front:
  home first). Fetches the rune and the book from the user's chest if they're not in his pack.
- **A clock per tinker** (the user, 2026-11-24, asking how to keep the vendors refreshing when a run takes 10 minutes,
  or 20 with blocked spots: "yes, do that"). A vendor restocks when his buy list is asked for an hour or more after his
  last restock. So a tinker's cycle starts the first time his list is opened after he was bought out, and he's due
  again 61 minutes later (`RESTOCK`); until he's bought out he stays due. Trips go to whoever is due, earliest first;
  between trips Clem waits at the tools room's stand until the next one is due. A slow trip only delays the tinkers
  still in it, and each keeps his own hour. (The first round, 16:11-16:19, used one clock for all: its first opens
  became the clocks.)
- **Recall reagents** (the user, 2026-11-24: "you'll have to watch the reagent count for the 2 reagents used by the
  recall spell and top up using the reagent chest when it gets low"): black pearl, blood moss and mandrake root. Every
  trip starts with castle.reagents_ok(), which tops every reagent up from the user's entrance reagent chest (938 2nd)
  when any is below 25 (to 45/40/45); a trip needs at most ~12 Recalls. If the chest can't give 12 of each, the loop
  stops (the chest is running out). In town, before every Recall on, he must still have 2 of each, else home.
- **A trip**: reagents (as above), healed, mana; the bank when
  his gold can't cover what the due tinkers are likely to have, up to a full load (gold for at most 2 full loads, since
  gold weighs); then the due tinkers in turn: every tinker within 12 tiles of the landing (paperdoll "the tinker"),
  every shovel that fits (weight less 10 stones, 125 items) and the gold covers. Gold running out at a tinker with room
  left: the bank and back. Full: home.
- **Home**: the courtyard ("skara") rune lands him in the **north yard** (935,2328, grass, walled off from the great
  hall: the user, "you don't go to the gret hall for shovel runs ... You go inside the side door that he's next to"):
  the north door (`0x40913575`, shut at 935,2325; key ring `0x408CB8EB` at 935,2326 on the yard side, in his rules
  since 2026-11-24): from 935,2327 unlock, open, in to 935,2324 (the north corridor), lock ("You lock it."), close;
  shovels.py checks it stands shut. Then the tools room (`tools_room.put(['shovels'], leave=False)`: every bag
  recounted, new backpacks from the spare backpacks chest as bags fill), the user's table locked again from behind
  it, and he waits at the stand (945,2346). First done 16:22:35-16:22:42.
- **Blocked spot** ("That location is blocked.", someone standing on the rune's spot; Magincia, 16:18): again after
  15, 30, 60 and 120 s (the user: "Do an exponential backoff up to 2 minutes. If it doesn't unblock, then move on ...
  We don't want to wait too long or the vendors won't be refreshed after 1 hour"), then on to the next due tinker;
  that one is tried again every 10 minutes (the user: "re-schedule the ones that were blocked to try them again each
  10 minutes").
- **A player in town** (the user, 2026-11-24, after Clem left Jhelom for someone 15 tiles off: "I don't want you to do
  this. We're in town and not carrying much. You should only do this if the player gets within 1 tile of you and
  doesn't leave (they stay within 5 tiles). Then leave and come back 10 min later"): only a stranger who comes within 1
  tile and is still within 5 tiles 10 s later sends him home; that town again in 10 minutes. Anyone else is ignored. A tinker who can't be
  reached (no answer three times, no path, another floor): not for 5 minutes, noted in his `skipped`.
- **Blockers stop the loop, with him home**: no gold left in the bank, a rune or the book missing, a Recall that lands
  somewhere unexpected (at the castle front he comes in by the front door with the fight logic first), reagents short,
  three trips in a row that buy nothing, anything the castle tools refuse.
- `python3 -I shovels.py stop` (the user says stop): finishes the tinker he's at, home, the shovels away, the rune and
  the book into the user's chest (938 top), waits in the tools room. `cleanup` and `fetch` do just those steps.
  `status` prints the state (each tinker's clock, stock, price, skips; the totals).
- Watch: `tail -F ~/claude/uo-agent-work/shovels/shovels.log` for "bought", "bank", "Recall", "trip", "put away",
  "STOPPED", "player", "blocked", "skipped", "waiting".

- **The tools room is counted once per run** (the user, 2026-11-24: "just assume no one is taking them out while
  you're doing a run. You only inventory it at the start of a run"; "You don't even inventory between each hour or
  whenever, i don't want you to have to inventory 50000 shovels and slow it down"): `shovels.py run` opens every bag
  once at its start (`count_room`), then sets `tools_room.TRUST_CACHE`: each put-away opens only the bags with room
  and adds to the count. The log's "TOOLS ROOM: N shovels" lines carry the running count.
- **Blocked spots are logged** (the user, 2026-11-24: "try to remember which locations are blocked frequently so I can
  improve the rune locations for those"): every blocked try in `blocked.jsonl` (time, rune, spot, try number);
  `python3 -I shovels.py blocked` sums them per rune. Magincia's was blocked 16:18-16:19 and again from 16:25 (the
  first, before the log).
- **Pause** (the user, 2026-11-24: "I'd like to pause it so I can fix the runes and use clem for a while. The pause
  ability should understand how to adjust the schedule when I pause/unpause"): `shovels.py pause` finishes the step
  (in town: that tinker, home), puts the shovels away and exits, the rune and book staying in his pack;
  `shovels.py resume` hands him back, comes home from wherever he is, re-reads the runebook (re-marked runes: the
  rules' tinker areas follow, `sync_areas`), forgets the blocked skips, and goes on. A vendor's restock clock runs
  through a pause, so nothing is shifted: whoever came due meanwhile is due at once. First paused 16:58 (Clem in
  the tools room; the user fixing the Trinsic and Magincia runes).
- **Blocked Recalls cost reagents**: 16:25-16:28 Magincia's blocked spot took black pearl, blood moss and mandrake
  from 22 to 17 (gems.recall_to cast three times per try). Now one cast per try (`recall_once`), and no try in town
  without 3 of each left.

## The tools room filling up

- **The next row** (the user, 2026-11-24): "When you fill up those 4 columns completely full of bags and shovels then
  you'll go to the next 'row' of 4 spots on the floor" (y 2346, x 944-947); the axe stacks on the west wall are on
  hold ("we're not going to do axes right now, we're goign to do shovels instead, so put the axe stacks on hold for
  now, we might find another place for them"). Not built yet: 4 stacks x 20 bags x 50 = 4,000 shovels first ("Do the
  second row when we get to it"); tools_room.py stops and asks when all 4 are 20 high. Then: the 4 spots at y 2346
  as shovel stacks, filled only once the first row is full, and Clem's stand moved off 945,2346 (945,2347 reaches
  both rows).

## What to tell the user

**A status line in the chat after every trip home** (the user, 2026-11-24: "print a status update line here showing
the current count of shovels"): the tools room's running count, what the trip bought and where, what's due next.


Per trip: bought N (where), put away, the tools room's total. Per round: shovels and gold, trips, tinkers skipped and
why, the bank's gold left. Any stop: why, and where Clem is (always inside, both doors locked).
