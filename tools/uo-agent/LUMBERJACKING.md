# Lumberjacking with Icepick: the plan and the user's rules

Started 2026-11-12. This file records what the user asked for, what was tested and what was decided, so any session
can pick it up. The newest decisions are near the bottom; where an earlier note disagrees, the later one wins.
Lumberjacking reuses most of mining (MINING.md): read that first.

## Status (2026-11-12)

- Planning. The area is ridden, a tree chopped and sawn by hand (recorded), and the first bridge test passed
  (20:53, below): wood is shared by 8x8 blocks, chopping and sawing work through bridge 12. Next: the meeting spot,
  the block planner and `lumber.py`.
- Mining is parked while Icepick lumberjacks (both use him). His lumberjacking rules
  (`rules/rules-Icepick-lumber.json`) are in the client since the test; mine.py puts the mining rules back when it
  starts, and lumber.py will put its own in, as smith.py does.
- Installed client: cuo-agent31, bridge 12; no new bridge needed.

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
- **Pacing**: "it might need some pacing, we'll see." Start with mining's pacing (he's out in town), quick repeat
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

- The central meeting spot for Burgers, and his rune there.
- When to saw: at a weight threshold (sawing quarters the logs' weight), to settle in lumber.py.
