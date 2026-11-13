# Lumberjacking with Icepick: the plan and the user's rules

Started 2026-11-12. This file records what the user asked for, what was tested and what was decided, so any session
can pick it up. The newest decisions are near the bottom; where an earlier note disagrees, the later one wins.
Lumberjacking reuses most of mining (MINING.md): read that first.

## Status (2026-11-12)

- **`lumber.py` works** (tested 2026-11-12 22:04-22:17, below): chopping three blocks, parking, sawing, the
  handoff of boards to Burgers and his bank trip. Next: a longer stretch with the user watching, then whole laps.
- Mining is parked while Icepick lumberjacks (both use him). lumber.py puts the lumberjacking rules for both into
  the client (`rules/rules-Icepick-lumber.json`, `rules/rules-Burgers-lumber.json`); mine.py puts the mining ones back
  when it starts. lumber.py refuses to start while mine.py runs; **never start mine.py while lumber.py runs.**
- Installed client: cuo-agent31, bridge 12; no new bridge needed.
- Waiting on the user: spare axes in Burgers' bank (the bank had none on 2026-11-12 22:16), cure potions for
  Burgers (he has none to top Icepick up with).

## Running it from a Claude session

- **Start** as a background task, with absolute paths: `cd ~/claude/ClassicUO/tools/uo-agent; exec python3 -I
  ~/claude/ClassicUO/tools/uo-agent/lumber.py --laps 1` (it carries on from `next` in the state; `--from N --to M`
  for a stretch, which parks both at its end). Before starting: both logged in with the Agent bridge option,
  Icepick on McGee anywhere in the area, Burgers at the meeting spot or the Ocllo bank (the start-up finishes his
  trip), mine.py not running.
- **Watch** `~/claude/uo-agent-work/lumber/lumber.log` with a Monitor (re-arm at every expiry, from the last event's
  time, as in MINING.md), filtered to: `NEEDS YOU|UPDATE|Icepick at|runes|axes|axe|sawed|to Burgers|handed|bank|Recall|lap |ALARM|
  alarm|STOPPED|PARKED|Traceback|Error|done:|incident|creature|poison|no way|reagents low|missing|already empty`.
- **Stop** only with `python3 -I lumber.py --park` (both mounted and hidden, guards off), or `--stop` in an
  emergency (then hide them by hand). Never pkill by name.
- **Tell the user** (plain messages, no push notifications) after **every bank trip**, from the `UPDATE:` line it
  logs then (the user, 2026-11-12: "tell me the stuff that mining told me"): boards handed, in the bank and in all;
  axes (Icepick in hand and in the bag, Burgers, the bank) and the ones that broke since the last update with how
  many chops each lasted; saws (Icepick, Burgers, the bank); reagents (Burgers' and the bank bag's); cure potions;
  run and hides and fights (a creature hit him and the guards were called), new ones with who and when, and how
  many to review; the chopping since the last update and his Lumberjacking. Also alarms, incidents, stops and
  parks as they happen. Not every block.
- **"NEEDS YOU"** (the user, 2026-11-12: "if something needs my attention right away keep repeating it at each
  hand-off so I see it. Not run & hides or fights.. stuff that will end the loop (out of something)"): the handoff
  line and the update start with it while anything will end the loop unless restocked (no axes in the bank or
  axes running out, Icepick down to one cure potion (the user: 3 on him is enough; Burgers needs none), a recall reagent under 35 in the bank bag or under 20 on Burgers,
  Icepick down to one saw with none on Burgers, or no saws left in the bank). Put it first in every message, every time, until it's gone.
- **The nightly reboot** (about 04:15) stops it as it does mining ("the game is not responding"): wait for both
  bridges, hide anyone in sight, check `halted` and `resume`, then start again. Wood isn't counted like ingots, so
  there's no total to correct beyond the handoffs after the save point (state.json `totals`).

## lumber.py (2026-11-12)

- It's mine.py's `Miner` with the mining parts swapped out (a subclass, `Lumberjack`), so the safety is mining's
  unchanged: the guard and getting away from people (FLEE 50 tiles inside the lumberjacking area), "Guards!" and
  stepping away from creatures, poison and cure potions, town guards (the ones found while mining are copied over),
  McGee, the tired horse, rides planned on the map with learned buildings, lag, world saves, park and stop. It
  points mine.py's module settings at its own work folder (`~/claude/uo-agent-work/lumber`: lumber.log,
  state.json, incidents.jsonl, lumber.pid, park), the meeting spot, the runes (bank, Mining Start for Burgers'
  get-away, Lumber meet) and the three recall reagents only.
- Each block: a random tree and spot to chop from (lumbering.choose), ridden to mounted; chopped until "not enough
  wood" (another tree of the block if the server won't let him chop the first). The block and when it ran dry go
  in state.json `emptied`.
- Weight: before every chop, if another good chop (20 stones) could take him past 393 he saws; if he's still over
  340 after sawing he's full, and goes to Burgers. A full load is about 500 boards (250 stones).
- Axes: the one in his hands; when it breaks ("You broke your axe.") the next from the blue bag. Every axe's chops
  are counted (state.json `axe_uses`) and a broken one's life is logged and kept (`axe_life`): the user wants to know
  how long they last. Out of axes: to Burgers for more.
- At Burgers: saw, trade the boards (and any logs) for spare axes (Icepick back up to 4 in the blue bag; the user:
  "just like mining") and cure potions (up to 3); Burgers then banks the boards (every handoff: a load is most of
  what he can carry), takes axes from an axe bag in his bank (up to 2; the user: "burgers only needs like 2 extras"; more go back), restocks his recall reagents to 35, recalls
  back on "Lumber meet" and hides. Icepick waits hidden by the meeting spot meanwhile. Out of axes everywhere: both
  parked, the loop stops.
- Saws (2026-11-13): Icepick keeps 3, topped up by Burgers at the handoff; Burgers carries 1 spare from the bank's
  saws (the user keeps about 20 there, in a bag the loop finds by what's in it). A saw lasts about 70 sawings (75,
  70, 69), 6-7 a load.
- Boards go into a bag in the bank that has boards in it, else loose in the bank box as one pile (the user,
  2026-11-12: "I don't mind it if there's 1 stack of all the boards in the bank box"; a pile holds up to 60,000).

## Tested 2026-11-12 (the user watching)

- 22:04-22:07, `--from 0 --to 2`: start-up (rules in, guards on, runes checked by name, Burgers to his spot and
  hidden), 3 blocks chopped until empty in 4 minutes: 47 chops, 10 good (100 logs), 34 misses, 3 empties;
  Lumberjacking 25.6 -> 28.4. Parked both, mounted and hidden.
- **The first hatchet broke** at 22:05:13 ("You broke your axe.", with the logs of that chop) after about 80 chops
  counting misses (it may have been used before); the loop took the next one from the blue bag. At ~15 chops a
  block for now, an axe lasts about 5 blocks: many axes (the user will get more).
- 22:15-22:17, `--unload`: 100 logs sawn (337 -> 187 stones: **a board is half a stone, confirmed**), 210 boards
  handed to Burgers, his bank trip (no bag with boards yet, so loose in the bank box: 210 there), no axes in the
  bank, 5 black pearl, 6 blood moss, 6 mandrake root restocked, back on Lumber meet, both parked hidden. 1.5 minutes.
- 22:37-22:58, `--to 32` (blocks 3-22): Burgers started at the bank (the user put him there with spare axes) and
  the start-up finished his trip: 8 axes taken from an axe bag in the bank (2 left), reagents counted (bank bag:
  black pearl 90, blood moss 118, mandrake root 99). Then 20 blocks in 19 minutes: 217 chops, 53 good (530 logs),
  144 misses, one block already empty (148,224: someone else's chopping), 7 saws; Lumberjacking 28.4 -> 31.5; no
  axe broke. A full load came at about 20 minutes: 530 boards.
- **Burgers too heavy to recall** (22:58): the 530 boards (265 stones) on top of his 8 spare axes (about 8 stones
  each) took him to 404/390, and his Recall to the bank answered "Thou art too encumbered to move."; the loop
  stopped with both hidden at the meeting spot. Fixed: the handoff gives only what Burgers can carry and still keep
  8 stones under his most (Icepick keeps the rest for the next handoff), a full load is now 320 stones after sawing
  (about 480 boards), and before any recall a Burgers who is too heavy hands boards back to Icepick first (a step
  shows each of them for the trade). Recovered with `--unload` at 22:59: 54 boards back, Burgers 377/390, banked:
  686 boards in the bank.
- The update at 23:00 said the bank had no axes: its axe bag was counted without being opened (after a trip away
  the client knows nothing inside a bag until it's shown). Every bag the loop uses is opened first now.
- 23:01-23:09, blocks 23-32: 10 blocks in 9 minutes, 98 chops, 31 good (310 logs), 56 misses (better as his skill
  rises), 2 saws; parked at 1135,1771. **The second hatchet broke after 262 chops** (counted by the loop from new;
  the first one's ~80 had probably been used before, as the user thought). Then a double axe.
- 2026-11-13 00:33, the first run and hide: Bert stood within 3 tiles of Icepick on his way to Burgers; his paperdoll
  said "Bert the beggar". Icepick rode 49 tiles off, hid, waited 30 s, carried on at 00:35:47. From then on any
  lower-case job title counts as a townsperson, like the guards (MINING.md, "Townspeople too").
- 2026-11-13 01:35, a world save began as Burgers cast Recall at the start of a bank trip: the cursor came 8 s later,
  after "world save complete", and the loop stopped with him in sight holding 520 boards (cursor cancelled and hidden
  by hand at 01:35:44, then `--unload`). mine.py's recall now waits a save out and casts again.
- 01:47, **the first saw wore out** ("You have worn out your tool!") after about 75 sawings; the loop logs each one.
- 01:54, 'a bull said "*looks furious*"': the guard took a creature's emote for talk and Icepick rode off twice (the
  second time the bull was "back in sight"). Creatures are only dealt with when they hit him (the user, 2026-11-08),
  so a creature's noise is now ignored and creatures aren't watched for coming back (mine.py, shared with mining).
- Pacing off from 00:43 (pacing.py): loads of ~520 boards every 8-11 minutes, about 2,800-3,500 boards an hour;
  Lumberjacking 41 -> 50.8 by 01:53. Double axes and large battle axes last 108-122 chops.
- 02:25, Burgers' Recall home from the bank answered on "It begins to rain." before its cursor came: the loop
  stopped with him at the bank, cursor up (aimed at the rune by hand). mine.py's recall now aims a late cursor itself.
- 03:40 and 03:48, two blocks by the castle (x ~1280) skipped: the ride stalled short of the spot and the tree was 3
  tiles off. The loop now walks closer once before giving a tree up.
- **The nightly reboot, 2026-11-13 04:15** (as in mining): the loop stopped ("the game is not responding"), both back
  at 04:19, Icepick mounted but in sight (hidden at once). Rolled back to about 04:00: Icepick held 160 boards, 120
  logs and the axe taken at 03:58 (3 axes in the bag), which fits only the moment between his 03:58:28 and
  04:00:14 sawings. So the handoffs of 04:03 and 04:12 never happened (bank 12,790, not 13,850): state.json backed
  up (state.before-reboot-fix.json), `next` back to 406 (the block on at the save), `emptied` after 04:00 dropped,
  totals -1060 (noted), the 04:08 broken axe taken off `axe_life`. How to find the save point after a reboot: what
  Icepick holds (boards, logs, the axe in hand and the count in the blue bag) against the log's sawings, handoffs
  and axe changes.
- **The first full lap finished 2026-11-13 05:58** (blocks 0-594, from 2026-11-12 22:04, pacing off from 00:43):
  **19,130 boards in the bank**; Lumberjacking 25.6 -> 71.1; 34 axes broken (double axes and large battle axes
  about 119 chops on average), 3 saws worn out (75, 70, 69 sawings); 6 run and hides to review (Bert the beggar, a
  bull five times before creature noises were ignored), 1 fight (a snake at 05:19: "Guards!", killed at once, not
  poisoned). At full speed a load of ~520 boards came every 7-10 minutes. Both parked at the meeting spot,
  Icepick holding the last ~200 stones of the lap. The bank bag's black pearl (16) and mandrake root (25) were
  running low.
- So far a block takes about a minute and a load about 20 minutes, so a lap of 595 blocks is about 10-11 hours
  with the handoffs (each about 1.5 minutes).

## The job (the user, 2026-11-12)

- **Icepick** chops trees in the same part of town as the mining route (west Britain), **always under the guards'
  protection, never outside town**. The tree area is much larger than the mining corridor; the user will show the
  boundaries.
- **Mounted**: he chops from McGee's back ("yes mounted, I'm pretty sure you can chop while mounted but we will
  verify"). If the server allows it, he never gets off, so there is no "all follow me" and no losing the horse.
- **Logs into boards**: when the logs get heavy he turns them into boards (with a saw: see below), and keeps
  chopping and converting until he's full; then he rides to Burgers and hands over the boards by trade, and Burgers
  banks them (as with the ingots).
- **Axes**: "for now he will use whatever axes I put in the blue bag, just pick one." The blue bag is 0x40766101
  (hue 3) in his backpack; on 2026-11-12 it held 2 hatchets, 2 double axes and 4 large battle axes.
- **Which trees**: not a grid (only some trees stand in rows); the route and how many trees to skip are worked out
  in the area itself.
- **Pacing**: off since 2026-11-13, for lumberjacking and mining alike, behind a flag (`pacing.py on|off`; MINING.md,
  "Pacing"). Before that: "it might need some pacing, we'll see." Start with mining's pacing (he's out in town), quick repeat
  swings at the same tree, and adjust when the user has watched it.

## Chopping, recorded (the user by hand, 2026-11-12 20:27-20:31; `uo record`, ~/claude/uo-agent-work/lumber/chop1.jsonl)

- **The axe must be in his hands**: used from the bag, the hatchet's cursor came up ("What do you want to use this
  item on?") and the tree answered "The axe must be equipped for any serious wood chopping." Equipped (layer 2, two
  hands), a double-click gives a ground cursor at once, no message.
- **Chopping mounted works** (he stayed on McGee throughout).
- The cursor is answered with the tree's tile (x, y, z and the static's graphic). The leaves work as well as the
  trunk (0x0CE1 walnut leaves, 0x0CD1 and 0x0CDB leaves were all chopped). The ground (graphic 0) and **o'hii trees
  (0x0C9E)** answer "You can't use an axe on that.": o'hii trees are out.
- Answers come 2-4 s after the aim (several swings), inside the bridge's 6 s: "You put some logs into your
  backpack." (a good chop), "You hack at the tree for a while, but fail to produce any useable wood." (a miss),
  "There's not enough wood here to harvest." (empty, at once). A skill gain message often comes first.
- **A good chop gives 10 logs; a log weighs 2 stones** (60 logs took him from 76 to 196 stones).
- **His Lumberjacking is low**: 20.3 at the start, 23.6 after 19 chops (base 4.6; the rest is a stat bonus); 6 of
  the 19 found wood. He'll miss a lot at first and get better as he goes.
- **Wood is shared by 8x8 blocks of the map grid, like the ore** (the user: "chopping a tree makes the trees near it
  have less or zero wood"; RunUO's own lumberjacking would use 4x3 patches, which doesn't fit):

  | tree | what it gave | 8x8 block |
  |---|---|---|
  | 1129,1549 | 1 good chop, then empty | 141,193 |
  | 1128,1554 | 6 misses, 3 good chops, then empty | 141,194 |
  | 1128,1557 | empty at the first try, never chopped | 141,194 (the same block) |
  | 1124,1557 | 2 misses, 1 good chop, then empty | 140,194 |
  | 1124,1560 | 4 misses, 1 good chop, then empty | 140,195 |

  So the "pattern" is mining's: one tree per 8x8 block, chopped until empty, then on to the next block. One check
  through the bridge still to do: empty a block, then try another tree in it and one just over the line.
- **A block gave only 1-3 good chops** (10-30 logs). These may have been chopped before; to measure on fresh blocks.
- From the map files: 1,269 choppable trees in the area (o'hii left out) in **572 8x8 blocks**; 195 blocks hold one
  tree, the rest 2-6.

## Boards, recorded (the user by hand, 2026-11-12 20:34-20:38; boards1.jsonl)

- **Not with the axe**: the hatchet aimed at the logs answered "You can't use an axe on that."
- **With a saw** (0x1034; the user put 5 in his pack, 0x4088EAE8-0x4088EAF5) and his Carpentry (39.8, base 22.6):
  double-click the saw, a menu "What type of item do you want to craft?" (1 Other, 2 Furniture, 3 Containers, 4
  Misc. Add-Ons): **1**; then "What do you want to make?" (1 board: 1 Logs, 2 barrel staves, 3 barrel lid): **1**;
  about 6 s later "You create the item." **All 60 logs became 60 boards in one go** (one log per board).
- **Boards are much lighter than logs**: he went from 196 to 116 stones. With the 5 saws added at the same time (2
  stones each if as in RunUO) that makes a board about half a stone, a quarter of a log; to confirm at the next
  conversion. So sawing early and often keeps him light: a full load is mostly boards.
- Saws probably wear out like the axes ("worn out"): to watch.

## The plan

**Phase 1: learn, in the tree area**
1. **Boundaries**: the user rides Icepick round the edge of the area while Claude records his positions (read only,
   `record_route.py`); any "You have left the protection" marks a guard edge. That gives the rules' areas.
2. **One tree by hand**: the user chops a tree and converts logs to boards while Claude records (`uo record`): the
   prompts and messages, the axe in hand or not, chopping mounted, logs and stones per chop, the board step, axe
   wear.
3. **Patch size**: chop one tree until it's empty, then try the trees 1, 2, 3, 4... tiles away in each direction;
   the ones that come back empty share its wood.
4. **Regrowth**: back to the first tree later to time the wood's return; it sets how long a lap may be.

**Phase 2: plan, offline**
5. **Tree map**: every tree in the area from the map files, checked against what the client shows there (server-
   placed trees, buildings: `routes/obstacles.json`), drawn on a map image for the user.
6. **Route**: the trees grouped into patches, one per patch, a random tree and spot to chop from each time (as the
   rocks), in an order that tours the area. The user checks it on the map.

**Phase 3: build**
7. **Rules**: `rules/rules-Icepick-lumber.json`: the area, the axes (in hand), mining's pacing with quick repeats,
   the same guard as mining (callGuards, town guards as NPCs).
8. **`lumber.py`** on top of mine.py's `Miner` (a subclass, so mine.py barely changes): all of mining's safety is
   reused (getting away and hiding from people, "Guards!" and stepping away from creatures, cure potions, town
   guards, McGee, the tired horse, travel and learned buildings, park/stop, the nightly reboot, lag). New: the tree
   route, chopping (axe in hand, chop until the patch is empty, swap a worn axe from the blue bag), logs to boards
   when heavy, the weight limit with boards, and the handoff of boards to Burgers.
9. **Tests**: a few patches, the whole route, then unattended with a Monitor and updates, as for mining.

## The bridge

Bridge 12 (cuo-agent31) has what's needed (tested 2026-11-12 20:53): `/equip` puts an axe in his hands; `/use` with
`x`, `y`, `z`, `graphic` aims the axe in his hands at a tree (its static's graphic, `reach=2`) and waits for the
server's answer (2-4 s, inside its 6 s); `/walk?x=&y=&distance=2` rides him next to a tree; the saw is a tool used
from the backpack (`useFromBackpack` 0x1034) whose menus are answered with `/menu`, as smith.py does with the hammer.

## The first bridge test (2026-11-12 20:53-20:54, the user watching; scratch `test1.py`, `test1.log`)

Icepick's lumberjacking rules put in the client, his guard on, mounted the whole time, mining's pacing:

| tree | 8x8 block | answers |
|---|---|---|
| A 1128,1572 (fresh block) | 141,196 | miss, LOGS, LOGS, LOGS, miss, LOGS, empty: 40 logs |
| B 1132,1575, same block | 141,196 | **empty at the first chop**: the block's wood was gone |
| C 1124,1575, 4 tiles west over the line | 140,196 | LOGS, empty: 10 logs |

- **Confirmed: wood is shared by the 8x8 blocks of the map grid**, as the ore is. The rule is one tree per block,
  chopped until "not enough wood", then the next block.
- A block's wood varies: 1-4 good chops so far (10-40 logs) over six blocks.
- **A board weighs half a stone**: 50 logs (100 stones) sawn into 50 boards took him from 216 to 141. Sawing
  quarters the weight; one saw use did all 50 in one go, "You create the item." about 6 s after the last menu.
- 5 good chops and the sawing took 70 s in all, riding included. Lumberjacking 23.6 -> 25.6.

## The handoff (the user, 2026-11-12)

- **Burgers meets Icepick somewhere central in the tree area**, not at the forge.
- **The spot** (the user, 2026-11-12 21:0x, standing both there): "a little bit over by this building so they're
  not next to the main road". **Burgers waits at 1200,1716, Icepick comes to 1200,1714**, beside a building to the
  north-west (wooden doors at 1199,1711 and 1194,1713). About 25 tiles west of the middle of the trees (1230,1715),
  off the dirt road through 1223-1227,1708. Inside Icepick's area.
- **His rune**: the user marked "Lumber meet" on his spot (2026-11-12): 0x406EAA75 in Burgers' pack ("a recall rune
  for Lumber meet"). Still to make: his rules for this job (his spot and the bank).

## The tour (`lumbering.py`, 2026-11-12)

- `lumbering.py plan` lists every choppable tree inside Icepick's area from the map files (o'hii left out), keeps
  those with a walkable tile inside the area within 2 tiles to chop from, and groups them by 8x8 block: **595
  blocks, 1,332 trees**. It orders the blocks into one loop (nearest neighbour, then 2-opt), measuring each hop
  along walkable ground (so nothing cuts across the mountain), starting at the block nearest the meeting spot.
  The order is saved in `routes/lumber-tour.json` (only the block order: the trees and stand spots come from the
  map each time), so the loop's place in it keeps its meaning; plan again only on purpose.
- A lap is about **4,500 tiles of riding** between blocks, hops of 8 tiles on average and 29 at most. It runs south
  from the meeting spot through the south-west lobe, east along the south, up the east side by the castle, across
  the north and back down the west side to the meeting spot. `lumbering.py draw OUT.png` draws it.
- Each visit picks a random tree of the block and a random spot within reach to chop from (`choose`, as mining's).

## Burgers (the user, 2026-11-12)

- He doesn't carry shovels while lumberjacking (so a load of boards fits); he may carry spare axes later, depending
  on how long they last.

## The area (the user's ride, 2026-11-12 20:02-20:06)

- The user rode Icepick round the edge from the top of the mining route (1131,1544): down the mountain range, east
  along the south edge, north up the east side (by the castle moat), and west back to the start. Recorded in
  `~/claude/uo-agent-work/lumber/bounds.jsonl` (not in git); the picture is `area.png` there (scratch script
  `area_map.py`).
- Inside the ride: about 60,000 tiles, x 1091-1338, y 1529-1912. The map files show **1,339 trees** in it (422
  "tree", 249 oak, 247 walnut, 221 cedar, 130 willow, 70 o'hii), in 1,294 different 4x3 patches: if the patches
  are RunUO's 4x3, nearly every tree has its own wood and none need skipping.
- Guard edges the user touched on purpose ("left the protection" / "now under the protection"): north by the
  start (out at 1138,1536, in at 1132,1543), west (out at 1091,1624, in at 1100,1645), south (out at 1195,1911, in
  by 1195,1904) and north-east by the castle (out at 1285,1529, in at 1285,1549). Mounted, the message arrives a
  few tiles late, so the rules' edges keep a margin inside these (as mining's do).
- The dark brown rectangles on the map look like fields; the one Icepick rode into while mining was a building the
  server placed there (MINING.md, "Buildings the map doesn't show"). To check on the spot.
- The horse got tired twice on the ride (the user's remount macro); the loop's tired-horse handling covers it.

- **The rules' area** (`lumber_area.py`, 2026-11-12): everything inside the ride in bands of 3 rows (130 boxes),
  less what's past the guard edges (mining_area.py's x 1100, y 1898 and the canyon, and y 1543 in the north), plus
  mining's corridor and getting-away boxes: the user rode along the foot of the mountain, and the trees between the
  ride and the rock (chopped by hand at 1124,1557 and 1124,1560) lay just outside the loop. 180 boxes in all.

## Open questions

- How long axes last (the loop logs each one's chops), and so how many Burgers should carry.
- How long the wood takes to come back (state.json `emptied` has when each block ran dry; a lap is likely most of a
  day, far longer).
- (Pacing: settled 2026-11-13, off; see "Pacing" in the job.)
