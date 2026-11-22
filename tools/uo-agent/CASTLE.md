# The Castle

The user's new house (2026-11-18), replacing the tower ("Outpost", 1750-1763 x 1402-1413) as home for the loot and,
in time, for Clem: "Clem doesn't need to leave the tower though, this will be home now" (he'll be parked in the
castle once the move is done). Everything here was recorded while the user walked Clem through it on 2026-11-18
(`~/claude/uo-agent-work/castle/`: `events.jsonl` what they did, `route.jsonl` where he stood, `seen.json` every item
in view).

Clem does the sorting and the move. Never act as Icepick or Burgers.

## Getting in (the user's procedure, 2026-11-18: "correct!")

Every door ends **locked and closed**, as at the tower.

1. **Recall** with Clem's "Castle" rune (`0x408E20F9`, in his red reagent bag). He lands outside the front at
   **935,2356,0**. It's wild country with creatures around: a troll, gorillas, a great hart, mountain goats and
   tropical birds were all about on 2026-11-18. The tower's outside rules apply (COMBAT.md: never leave him
   standing among creatures).
2. **Front door** `0x40913567` (west half, shut at 935,2351; the east half is `0x40913568`; open, the west half
   stands at 934,2352). The key ring `0x4093D690` hangs locked down outside, at 936,2352,23.
   1. From 935,2353, unlock the door with the key ring ("You unlock it.").
   2. Open the door, and walk in through 935,2352 to **935,2350**.
   3. From 935,2350 (the key still reaches), lock the door ("You lock it."), then close it.
3. **Entrance room** (x 935-936, y 2348-2350, between the front door and inner doors `0x4091356F`/`0x40913570` at
   2347, which stay shut). The secure **wooden box `0x405AEFB8`** stands on the table at 935,2349,12. Open it, and
   cast **Recall on the rune inside** (`0x405FCA52`, "recall rune"). He lands in the **courtyard at 935,2344,0**.
4. **Central door** `0x40913571` (west half, shut at 935,2341; the east half is `0x40913572`; open, it stands at
   934,2342). The key ring `0x408CB8EE` hangs at 936,2342,23, on the courtyard side.
   1. From 935,2343, unlock the door.
   2. Open it, and walk in through 935,2342 to **935,2340**.
   3. From 935,2340, lock the door, then close it.
5. He's now in the **great hall** (x ~930-941, y ~2326-2340: dining tables and chairs at 935-941,2334-2337, the
   thrones at 930,2335 and 930,2338).

**Getting out:** recall with the "Outpost" rune, from inside. Clem only needs to leave to fetch things from the
tower during the move.

## Getting around inside (ground floor, z 6)

The layout is odd: some places are reached by going up and down stairs.

- **West hall** (walkway x 922-923, y 2323-2348): from the great hall, go up the stairs to z 26 (932,2332 to
  928,2333, then 925,2336, 921,2331 and 924,2323), then down again to 921,2323,23 and **921,2327,6**.
- **North corridor** (y 2323, x 924-945, z 6): joins the west hall to the east hall and the forge.
- **East hall** (walkway x 948-949, y 2323-2349).
- **North doors** `0x40913573`/`0x40913575` at 934-935,2325. A key ring `0x408CB8EB` hangs at 935,2326,22.
- **South rooms**: reached along y 2349 from either hall (from 925,2348 in the west, and from 947,2349 in the east).

## The chests (180, all `wooden chest`, locked down)

They stand in stacks of 4 on one tile (z 6, 10, 14 and 18), which is 4 rows, like the tower's chest wall.

| Where | Tiles | Chests | What for (the user, 2026-11-18) |
|---|---|---|---|
| **East wall**, x 947, y 2329-2343 | 15 | 60 | **Primary loot storage.** Most loot is dumped on the east side and sorted here. |
| **West wall**, x 921, y 2329-2343 | 15 | 60 | Mirrors the east wall: extra space. Loot dumped on the west side is sorted to the west, and either side takes the other's overflow. |
| **North-east, by the forge**, x 944, y 2322 / 2326 / 2327 | 3 | 12 | Crafting supplies, and things for crafting and leveling skills. |
| **South-east row**, y 2348, x 938-942 | 5 | 20 | **The user's personal chests**, managed by Claude. |
| **South-east floor chests**, 938,2349 and 938,2350 | 2 | 2 | **Dump chests**, east side (loot to sort, like backpacks on the tower floor). |
| **South-west row**, y 2348, x 928-933 | 6 | 24 | **The user's friend's personal chests: never touch** (unless the user says otherwise). |
| **South-west floor chests**, 933,2349 and 933,2350 | 2 | 2 | **Dump chests**, west side. |

The 4 dump chests are next to the "window" by the main entrance.

**Spare backpacks** (the user, 2026-11-18): the emptied loot bags, as the tower's backpacks crate. Once it holds 125,
further empty bags go in the trash. Since version 2, one chest by the forge (944,2327, floor), not one on each wall.

**The user's words** (2026-11-18):
- **East storage** is the east wall, **west storage** the west wall. **"My vault"** is the user's personal chests
  (south-east, behind their table); **"his vault"** is the friend's (south-west).
- The 4 floor chests by the entrance are the **intake** or **dump chests**: 2 east (938,2349 and 938,2350), 2 west
  (933,2349 and 933,2350).
- **"Sort the east side"** sorts the east dump chests into east storage. **"Sort the west side"** sorts the west dump
  chests into west storage. **"Sort all"** (or "all the dump chests") does both, each into its own side.
- The west dump chests are **exempt** from the friend's side: Clem goes over there to sort them ("Clem should be
  able to go over there and sort those into the westside chests"). Everything else on the friend's side stays off
  limits.
- **The friend's tables are gone** (the user, 2026-11-18 01:46: "I removed the tables that were blocking his vault
  so he (and you) can access his vault now"). Both south-west tables (0x40908E5D and 0x40909037) were taken up into
  Clem's pack; the walkway along y 2349 is open from the west hall to the west intake chests. The south-east table
  (the user's) stays.
- **Trash barrel**: the barrel in the forge corner, 949,2322 ("yes that's the trash barrel").
- **Smelting**: the 4 chests by the forge ("yes that's ok. If they ever get full then we'll figure out how to adjust
  it").
- **The banked ingots** (about 12,600 with Burgers) stay in the bank until someone puts them in an intake chest.

**Secure chests** (the user, 2026-11-18): 28 more can be made ("I wish to secure this" on a locked-down chest).
They hold at most about 400 stones each ("either 395 or 400"): plan for 395. 8 of them are the friend's: the two
stacks at the west end of their row (x 928 and 929, y 2348), which Clem secures for them (the user: "yes, Clem can
secure those 8 chests"; for that job only, his rules let him at them). Gold goes behind the user's table, never in a
secure: too heavy.
**All 21 made secure on 2026-11-18** (`castle_plan.py secure`): the 13 on the east wall and the friend's 8, each
answering "locked down & secure". No window asks for an access level: the house makes them friends-level (the user:
"I'm pretty sure everything is locked down as friends. I've never seen a window come up to pick"), which is what the
user wants for now: the friend is a co-owner, and every alt can open them. 7 secures are left for the west wall.

The draft of what goes where is the page "Castle Storage Plan"
(https://claude.ai/artifact/FMom8XXRnpNF2zyWtoETVe, `castle/plan.html`). The keep rules stay as they are for now (the
user, 2026-11-18: "Let's just keep what we have planned for now").

The forge corner also has the forges (946-947,2322), bellows (945 and 948,2322), the anvil (948,2323) and a barrel
(949,2322).

**Forge columns (2026-11-21):** 944,2326 top to floor: ingots, boards & logs, cloth & leather, cooking (one chest each:
they stack into single piles). 944,2327: the friend's personal chest (off limits in Clem's rules), the user's personal
chest, tools, free. Nothing is sorted into the personal chests.

**Undyed forge chests (2026-11-21):** the 12 grey-dyed chests by the forge were swapped for plain wooden chests
(`forge_swap.py`; the user turned and placed most of them, since a chest's facing can't be changed by Clem). Same
places, same kinds; the serials in the data files were renamed (`forge_swap.py remap`). The grey chests go to the great
hall (the user).

**Clem's reagents (2026-11-21):** from the user's own chest, 938 2nd (`restock.CASTLE_CHEST`): on the way in through
the window from the entrance room (`castle.restock_at_window`, standing at 936,2349), else the long way round past the
tables (`castle.restock_inside`, the table locked down as he comes out). The tower's restock chest is empty.

### The secure south rooms

Each south room is shut off by a **locked-down table** across the walkway on y 2349:

- **South-east table** `0x408793A4` at **943,2349,6**. **It stays.** It has to be released and moved to get in,
  then moved back and locked down again every time.
- **South-west table** `0x40908E5D`: removed by the user on 2026-11-18; the friend's side is open.

The user's friend has no owner commands, so the tables are for the owner side. The user, 2026-11-18, "correct!":

1. **Open:** stand next to the table (944,2349 for the south-east one). Say **"I wish to release this"**, and target
   the table ("(no longer locked down)"). Pick it up and drop it one tile aside (the user put it at 945,2350).
2. **Close:** put it back on 943,2349. Say **"I wish to lock this down"**, and target the table. Check that a single
   click says "locked down".

## Version 2 of the plan (the user, 2026-11-19)

- **For now: the east side, the user's vault (south-east) and the forge only** ("just don't make any secure chests
  yet. We'll figure out the west and southwest & secures later. For now we'll do just the east and southeast and
  forge"). The west intake chests aren't sorted (`castle_site.SIDES`), and no new chest is made secure. The east
  wall's 13 secures stay. The friend's 8 go back to plain locked-down chests ("yes plan for them to be non-secure";
  `castle_plan.py unsecure`, listed in `castle/secured-friend-2026-11-18.json`).
- **The west wall** is free, unassigned and not secure: "Don't mirror the east side ... leave everything empty for
  now".
- **Crafting by the forge:** "All the ingots, boards and logs and other things for crafting should be moved up to the
  chests closest to the forge". Every ingot, board and log goes to the forge chests, the big piles too (ingots and
  "ingots 2", "boards & logs" and "boards & logs 2", with smelting, cloth & leather, tools and cooking); the 8 chests
  in the user's vault that were for them (938 and 939) are free.
- **Gems and house deeds in the user's vault**, next to the gold (942: house deeds 3rd, gems floor): "Gems can be down
  by the intake in the southeast, like the gold is, so can house deeds (house deeds are separate from other types of
  deeds, house deeds can be traded in for gold and act like gold kind of)". A house deed is named "deed to a ..."
  (`plan.HOUSE_DEED`); other deeds stay in the east wall's deeds chests. The old gems chest (east 2337, top) is free,
  and still secure.
- **Spare backpacks:** one chest by the forge (944,2327, floor): "I want the chest with backpacks to be in the forge
  area so it's not behind the tables".
- **The forge gate (an idea, not decided):** the user may move their tables up to the forge corner, locked down
  across the east hall walkway, to cut off the whole east side (the east wall, the user's vault and the east intake
  chests) from the forge ("the tables will be moved so they separate the forge and the east wall (and the southeast
  area)"). Proposed: 948,2328 and 949,2328, just north of the first wall chests and south of the forge chests; a
  third on 947,2328 if that's open floor. Clem would get through by releasing one table, as with the south-east table
  now; `castle.py table` and `castle_site.py` (the table's place, and the zone it guards) change to match when they
  stand. Then the east wall wouldn't need secures (`castle_plan.py unsecure`, with the 13 listed in
  `castle/secured-east-2026-11-18.json`), but that's for the user to decide later.

## Sorting (from 2026-11-19)

The sorting tools work in the castle when Clem is inside it: the same steps as the tower (the uo-sort skill,
"Sorting in the castle"), with `--side east|west` on look.py. **`castle_site.py`** holds what's castle-only:
- which chest takes each kind on each side, with the overflow order (own wall, then the other; secures always the
  east wall's, then "valuables overflow" behind the user's table; gold always behind the table);
- the walks: zones (east hall, forge corner, north corridor, west hall, south-west walkway, south-east rooms behind
  the table, great hall) joined by the user's own routes from 2026-11-18, walked waypoint by waypoint, since long
  walks stop short and the great hall reaches the west hall only over the stairs;
- the user's table, opened on the way behind it and closed at the end of every tool (`Mover.close_up`);
- room left in a chest: a single click says "(N items, M stones)"; 125 items, and 395 stones for a secure.
`python3 -I castle_site.py test` checks the tables offline. **Not yet run in the game** (2026-11-19): the first
castle sort is watched by the user.

## The move (done 2026-11-19, 20:09-22:53)

`castle_move.py run` carried everything in the tower vault to the castle in 30 trips: each trip into the vault
(gems.py's door), as much as his pack takes, Recall to the castle (the castle-front fight, both doors), every piece
into its castle chest at its tower spot, back by castle.py out. What was learned on the way, now in the code:
- **Weight:** a pile is weighed by lifting it; one too heavy is split to what fits, and he's never left over his
  most (overloaded he can't move). A bag heavier than he can ever carry (the scroll pouches, 600-900 stones) goes
  over in parts: its contents wait loose in its castle chest (`move-pending.json`) and go back in when it comes.
  His pack also holds only 125 things (potions don't stack).
- **False stops:** Razor's AutoSearch opens every bag that lands in his pack, and the bridge takes that double-click
  for the user (`razor_opened`, checked on every request); a pile dropped onto its kind merges and its serial is
  gone, so the bridge stops waiting for it (taken as landed when it's gone from his pack); a split pile's rest gets
  a new serial (found again by graphic and amount).
- **Walking:** the user's own route (rec2, turn points only) ridden with /travel; the two ramps stepped tile by tile
  on the recorded tiles; each stretch checked to end on its floor (two floors share x,y round the stairs); castle
  chests worked from their standing spots, within reach.
- **Reagents:** checked before every trip out; restocked in the tower, or from the castle's reagents chest; when a
  chest is out of one, on with none under 20 (the tower's ran out of mandrake root and black pearl, 2026-11-19).
- Loose crafting things went to the forge (cloth & leather, tools, boards & logs, ingots), not where they lay.
- The **user's table** never had to move: the y 2350 row runs round it to the user's vault (the user was told).

## The tables (from 2026-11-20)

The user moved their two tables to the west end of the forge corner: locked down across the corridor at 943,2323
and 943,2324 ("the forge area is blocked off now too"; at 948-949,2328 the east wall's 2329 stack could be reached
over them). Behind them: the forge chests, the east wall, the user's vault and the east intake chests. In front: the
great hall and the rest. Clem moves only the one at 943,2323 (`castle.TABLE`, 0x405E7C85), on his route's row,
aside to 942,2324, from 941,2323 in front or 944,2323 behind, and puts it back from either; the one at 943,2324
(0x408793A4) is checked locked down. Clem's rules allow the tables' graphics (0x0B34, 0x0B35) on the ground. Loot to
sort goes on the forge room floor; a sort keeps the table aside from its first walk past it to `finish.py`, which
parks him in the middle of the great hall (933,2336, the square the user chose, 2026-11-20) and locks the table down from behind.

**938's top 3 are the user's own, secure** (2026-11-20: they can reach them through the window from the castle
entrance, so secure; "we're also going to use them for supplies that I need to refill when I'm adventuring, like
reagents"). The user's three chests from the tower moved there from 942 exactly as they lay (`tower_down.py relay`).
938 floor (not secure) holds the spare backpacks since 2026-11-20 (moved from the forge's 2327 floor, which is free
now): "I'm also going to need empty backpacks when I'm adventuring". Leaving, Clem locks the table down as he passes
it (`Mover.leave_to`), never from the great hall and back.

## The tower's ground floor (from 2026-11-20)

What's left in the tower after the vault: 6 chests by the stairs, 9 in the bedroom, 3 by the forge. The user decides
where each goes; 2 are the friend's (they'll say which).

- **The user's own 3** (the stack at 1752,1402 by the stairs: z 14, 10, 6) went to **942** in their vault, same heights
  (2nd, 3rd, floor), then on to **938's top 3** (secure), moved exactly as they were: "i want the items placed in the chests exactly the same so when i
  open the chests it looks the same as it does here in the tower". `tower_down.py record` writes every piece's x,y in
  its chest and the server's order (the drawing order); `carry` takes them whole (a bag's contents keep their places
  when the bag moves: the user, "you don't have to record those") and puts each back at its x,y in that order, then
  checks the spots and the order. 42 of 42 matched. The middle one was Clem's reagent restock chest; he restocks
  from the castle's reagents chest now. The gem bag went from 942 floor to 939 floor, and 939 took 942's old
  slots (valuables overflow, house deeds, gems).
- Razor's AutoSearch also opens the bags inside a bag that lands in his pack: `castle_move.razor_opened` counts
  those clicks as Razor's too (2026-11-20 18:15).
- The bedroom (x 1754-1763, y 1402-1409) isn't in Clem's rules areas yet.

## Known so far, not yet done

- **`castle.py`** (2026-11-18, the user: "that should be a skill or something. We're going to need to do this a lot
  with the UO automation, not just for moving"): `in`, `out`, `table open`, `table close` and `where`, so every job
  gets in and out the same way. **Not yet tried in the game**: the first runs are watched by the user.
- Clem's rules (`rules/rules-Clem.json`) have the castle (2026-11-18): its rooms as areas (not the south-west rooms),
  both doors and their key rings, the two house phrases, the table in "dropOnGround", and the friend's 24
  south-west chests and their table in "offLimits".
- The table is picked up and put down beside him, from 944,2349 (bridge 15, the user, 2026-11-18: "change the
  bridge so you can set down items anywhere near you"). Installed 2026-11-18 (cuo-agent34).
- Step 3: the courtyard rune **stays in the box; Clem never carries one** (the user, 2026-11-18: "That's a security
  concern"). Bridge 14 (build cuo-agent33) casts Recall on **any recall rune within reach**, wherever it lies (a box,
  a chest, the bank), not only carried ones ("You should be able to recall from any rune"). Installed 2026-11-18.
- The layout of the east wall and the forge chests (which category goes where) is to be drafted on a map page for
  the user, then the move from the tower.
