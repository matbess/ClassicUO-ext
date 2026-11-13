# Lumberjacking with Icepick: the plan and the user's rules

Started 2026-11-12. This file records what the user asked for, what was tested and what was decided, so any session
can pick it up. The newest decisions are near the bottom; where an earlier note disagrees, the later one wins.
Lumberjacking reuses most of mining (MINING.md): read that first.

## Status (2026-11-12)

- Planning. Nothing tested in the game yet. Mining is parked while Icepick lumberjacks (both use him); each loop
  puts its own rules file into the client's Agent folder, as smith.py does.
- Installed client: cuo-agent31, bridge 12. No new bridge is expected to be needed (see "The bridge" below).

## The job (the user, 2026-11-12)

- **Icepick** chops trees in the same part of town as the mining route (west Britain), **always under the guards'
  protection, never outside town**. The tree area is much larger than the mining corridor; the user will show the
  boundaries.
- **Mounted**: he chops from McGee's back ("yes mounted, I'm pretty sure you can chop while mounted but we will
  verify"). If the server allows it, he never gets off, so there is no "all follow me" and no losing the horse.
- **Logs into boards**: when the logs get heavy he turns them into boards with the axe, and keeps chopping and
  converting until he's full; then he rides to Burgers and hands over the boards by trade, and Burgers banks them
  (as with the ingots).
- **Axes**: "for now he will use whatever axes I put in the blue bag, just pick one." The blue bag is 0x40766101
  (hue 3) in his backpack; on 2026-11-12 it held 2 hatchets, 2 double axes and 4 large battle axes.
- **Which trees**: not a grid (only some trees stand in rows); the route and how many trees to skip are worked out
  in the area itself.
- **Pacing**: "it might need some pacing, we'll see." Start with mining's pacing (he's out in town), quick repeat
  swings at the same tree, and adjust when the user has watched it.

## What we expect, to check in the first tests

The ore turned out to work exactly as in RunUO (8x8 blocks), so the server is probably RunUO underneath. If its
lumberjacking is RunUO's too:
- The axe must be in his hands ("The axe must be equipped for any serious wood chopping."); mining's "can't mine
  while riding" has no lumberjacking counterpart, so chopping mounted should work.
- Wood is shared in **patches of 4x3 tiles** (RunUO's bank), 20-45 logs each, 10 taken per good chop, so 2-4 good
  chops empty a patch; it comes back in 20-30 minutes. Answers: "You put some logs into your backpack.", "You hack
  at the tree for a while, but fail to produce any useable wood.", "There's not enough wood here to harvest.",
  "You have worn out your tool!" (axes have uses).
- A log weighs 2 stones, a board 1; the axe aimed at the logs in the pack turns the whole pile into boards.
- Skipping trees: one tree per patch, every patch. Trees in one patch share its wood, trees in different patches
  don't, so the "pattern" is the patch size, measured (as the ore blocks were on 2026-11-01).
- From the map files (2026-11-12): about 570 trees in the guarded town box x 1100-1215, y 1550-1897 (oak, walnut,
  cedar, willow, o'hii, plain "tree"), nearly every one in a 4x3 patch of its own; 170 of them inside the mining
  corridor. The server may add trees the map doesn't show.

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
`graphic` aims an item in his hands at a static (the tree's graphic); `/use?serial=AXE&target=LOGS` aims it at an
item. To check in the tests: whether `/use`'s 6 s wait for the server's answer (LAND_RESULT_TIMEOUT) covers a chop of
several swings, and whether `/use` with a target allows the logs in his own pack.

## Open questions

- Where Icepick and Burgers meet for the handoff (the forge spot at 1140,1849, or somewhere in the tree area).
- Burgers' room: he carries 40 spare shovels for mining (about 200 of his 390 stones), so a full load of boards
  may not fit. Leave the shovels in the bank while lumberjacking, or bank more often?
- When to convert: at a weight threshold (one conversion halves the logs' weight), measured in the tests.
