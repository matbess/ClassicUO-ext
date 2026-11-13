# Lumberjacking with Icepick: the plan and the user's rules

Started 2026-11-12. This file records what the user asked for, what was tested and what was decided, so any session
can pick it up. The newest decisions are near the bottom; where an earlier note disagrees, the later one wins.
Lumberjacking reuses most of mining (MINING.md): read that first.

## Status (2026-11-12)

- Planning. The area is ridden and a tree chopped and its logs sawn into boards by hand (recorded, below). Mining
  is parked while Icepick lumberjacks (both use him); each loop puts its own rules file into the client's Agent
  folder, as smith.py does.
- Installed client: cuo-agent31, bridge 12. No new bridge is expected to be needed (see "The bridge" below).

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

Bridge 12 (cuo-agent31) seems to have what's needed: `/equip` puts an axe in his hands; `/use` with `x`, `y`, `z`,
`graphic` aims an item in his hands at a static (the tree's graphic) and waits up to 6 s for the server's answer
(enough: chops answered in 2-4 s); the saw is a tool used from the backpack (`useFromBackpack` 0x1034) whose menus
are answered with `/menu`, as smith.py does with the hammer.

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

## Open questions

- Where Icepick and Burgers meet for the handoff (the forge spot at 1140,1849, or somewhere in the tree area).
- When to convert: at a weight threshold (one conversion halves the logs' weight), measured in the tests.
