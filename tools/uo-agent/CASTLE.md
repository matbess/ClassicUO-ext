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

**Spare backpacks** (the user, 2026-11-18): on each wall, the **floor chest at the north end** (947,2329,6 and
921,2329,6) holds the emptied loot bags, as the tower's backpacks crate does. Once it holds 125, further empty bags
go in the trash.

The draft of what goes where is the page "Castle Storage Plan"
(https://claude.ai/artifact/FMom8XXRnpNF2zyWtoETVe, `castle/plan.html`). The keep rules stay as they are for now (the
user, 2026-11-18: "Let's just keep what we have planned for now").

The forge corner also has the forges (946-947,2322), bellows (945 and 948,2322), the anvil (948,2323) and a barrel
(949,2322).

### The secure south rooms

Each south room is shut off by a **locked-down table** across the walkway on y 2349:

- **South-east table** `0x408793A4` at **943,2349,6**. **It stays.** It has to be released and moved to get in,
  then moved back and locked down again every time.
- **South-west table** `0x40908E5D` at **927,2349,6**. This is the friend's side: it may go away. Never touch it.

The user's friend has no owner commands, so the tables are for the owner side. The user, 2026-11-18, "correct!":

1. **Open:** stand next to the table (944,2349 for the south-east one). Say **"I wish to release this"**, and target
   the table ("(no longer locked down)"). Pick it up and drop it one tile aside (the user put it at 945,2350).
2. **Close:** put it back on 943,2349. Say **"I wish to lock this down"**, and target the table. Check that a single
   click says "locked down".

## Known so far, not yet done

- **`castle.py`** (2026-11-18, the user: "that should be a skill or something. We're going to need to do this a lot
  with the UO automation, not just for moving"): `in`, `out`, `table open`, `table close` and `where`, so every job
  gets in and out the same way. **Not yet tried in the game**: the first runs are watched by the user.
- Clem's rules (`rules/rules-Clem.json`) have the castle (2026-11-18): its rooms as areas (not the south-west rooms),
  both doors and their key rings, the two house phrases, the table in "dropOnGround", and the friend's 24
  south-west chests and their table in "offLimits".
- The table is picked up and put down beside him, from 944,2349 (bridge 15, the user, 2026-11-18: "change the
  bridge so you can set down items anywhere near you"). Installed 2026-11-18 (cuo-agent34).
- Open question: the west dump chests (933,2349 and 933,2350) are behind the friend's table, which Clem never
  touches. How should loot dumped there be reached?
- Step 3: the courtyard rune **stays in the box; Clem never carries one** (the user, 2026-11-18: "That's a security
  concern"). Bridge 14 (build cuo-agent33) casts Recall on **any recall rune within reach**, wherever it lies (a box,
  a chest, the bank), not only carried ones ("You should be able to recall from any rune"). Installed 2026-11-18.
- The layout of the east wall and the forge chests (which category goes where) is to be drafted on a map page for
  the user, then the move from the tower.
