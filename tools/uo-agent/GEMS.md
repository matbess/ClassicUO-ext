# Selling the gems with Clem

Started 2026-11-09. Like CARTO.md and COMBAT.md, this records what the user asked for, what was found and what was
decided, so any session can pick it up. Newer notes win where they disagree with older ones. The tool is `gems.py`;
its log is `~/claude/uo-agent-work/gems/gems.log` and its state `state.json` there.

## The job (the user, 2026-11-09)

Clem takes the gem bag to town and sells the gems to several NPCs (sell only, nothing bought), then comes home to the
tower. Going to town and coming home work as on the map trips (CARTO.md, "Vendor trips"; COMBAT.md, "Home from
town"): Recall out from inside, a player in town means home at once and 15 minutes inside, and coming home Recall
lands him outside the front door with fight.py's front-of-the-tower mode taking over at once.

## Phase 1: getting ready (`gems.py fetch`), every trip

The user's steps, "this is what you'll need to repeat every single time you go sell gems":
1. **The gems** are in the vault (the locked room on the tower's second floor), in the **column 5, bottom chest**
   (0x408FE3A0, 1762,1402,26). There's a gem bag there and **one loose gem beside it, which shows what's in the
   bag**: that gem goes into the bag (onto its own kind's stack), then the whole bag into his pack.
2. **The Gems runebook** is downstairs in the **top left chest by the stairs** (0x4058ABA9, 1752,1402,14, right above
   the reagents chest): into his pack. That chest also holds the gold and three other runebooks (unnamed, "Map Makers
   and Ships", "Tinkers"); the Gems one is 0x4067FDD7, "Gems ... crafted by ScribeMaster", found by its name.
3. **Reagents**: restock if any is below 25 (restock.py, from the chest right below it).
Then he's ready to go; `fetch` parks him in the safe zone.

The first full run (2026-11-09 20:58:28-20:59:36, 68 s): in, the loose amber onto its stack, the bag (268 gems: 39
citrine, 34 sapphire, 29 diamond, 35 star sapphire, 30 ruby, 23 emerald, 23 amethyst, 30 tourmaline, 25 amber) into
his pack, out, the door checked locked, the runebook, reagents topped up, parked. 34 items in his pack, 111/390
stones. Each step is skipped when already done (the bag or the runebook in his pack, or he's already in the vault).

Clem's rules (`rules/rules-Clem.json`) cover the vault, its door's tile, the vault door and its key ring for this
only; his maps never go in there (CARTO.md).

## The vault door (the user, 2026-11-09)

The vault door 0x408AEA59 (metal, 1757,1412, z 26) stays on its tile: shut graphic 0x0681, open 0x0682. Its key ring
0x404099E0 is locked down in the bag room at 1756,1410 (z 38). **It always ends locked and closed.**
- **In, exactly like coming in the front door**: at 1756,1412 unlock with the key ("You unlock it."), open, step into
  the doorway (1757,1412), lock with the key ("You lock it."), step in (1758,1412), close.
- **Out, no key**: "Once you are in the room the door will already be locked, then I want you to leave the room
  without trying to lock it again (because it's already locked)". The locked door opens from inside ("That is locked,
  but is usable from the inside.") and stays locked: through the doorway to 1756,1412 and close it behind him. **The
  key would do harm here**: it turns the lock either way, so on the locked door it unlocks it; and from inside the
  vault it can't be reached anyway ("I can't reach that.": the wall is between).
- **Then stop and check it from outside** ("that's important"): use the door from 1756,1412; it must say "That is
  locked." and stay shut. Only if it opens (it wasn't locked) does the key come out: lock, close, check again.
- **His client opens the door by itself** as he walks up to it (auto_open_doors: "Opening door..." and the server's
  "That is locked, but is usable from the inside."), and the open graphic can come a moment after the words. The
  first try (20:48:03) read it as still shut, used it, and so shut it again, then went for the key. `out_of_vault()`
  now waits for the graphic when those words have come, and only uses the door if it's really still shut.
- After anything going wrong at the door, `lock_up()` closes it, and uses the key only when the door is known to be
  unlocked (between "You unlock it." and "You lock it." on the way in).
- Tested on its own with `gems.py vault-test` (20:55, in and straight out, stops at the door in the bag room).

## Running it

- `python3 -I gems.py fetch [--resume]`: phase 1. `vault-test`: in and out of the vault only. `runebook`: only the
  runebook. `vault-out`: out of the vault only (he's in it).
- Only the user hands Clem back: it refuses to start while he's taken over (`--resume` only when they say so).
- Razor's AutoSearch double-clicks the gem bag as it lands in his pack, which the bridge takes for the user taking
  over: `trips.pick_up` resumes exactly that (as on the map trips).
- Johnny's rules pause his bridge while anyone else is in the vault: Clem's visit holds up a running sort for about a
  minute. When the gem bag is gone, Johnny's sorting starts a new one (skill uo-sort, "Gems chest").

## Next

- Phase 2: the selling itself (the user to say: the runebook's spots, which NPCs, where the gold goes, what to do with
  anything unsold). The runebook needs the bridge to work its gump (bridge 6 has gumps; loose runes work with /cast
  today).
