# Blacksmithing with Icepick: the plan and the user's rules

Started 2026-11-05. Like MINING.md and CARTO.md, this records what the user asked for, what was found and what was
decided, so any session can pick it up. Newer notes win where they disagree with older ones.

## The job (the user, 2026-11-05)

- **Icepick** trains **Blacksmithing to 100**: craft an item, smelt it straight back into ingots, put the ingots back
  on the pile, repeat. The loop is `smith.py`.
- **What to craft at each level** (the user, 2026-11-06: the levels are his **effective** Blacksmithy, the value with
  his stat bonus, not the base; `smith.py` reads `value` from `/skills`, e.g. 67.1 against a base of 63.5):

  | Blacksmithing | Item |
  |---|---|
  | 50-65 | cutlass |
  | 65-78 | kryss |
  | 78-88 | short spear |
  | 88-99 | spear |
  | 99-100 | spear, or plate gloves |

- **At 99**: try both spears and plate gloves for a while and compare how quickly the skill rises (per hour). If
  they're about the same, stay with spears: they fail less, so more items come back as ingots when smelted.
- **The pace slows near the top** (the user, 2026-11-06): progress gets slow around 97 and very slow around 99.
  At 93.8 (00:20 on 11-07) it was about 1.2 points an hour, using about 770 ingots and 6 hammers an hour.
- **Ore first**: whenever there is ore in the grey bag, smelt it into ingots before crafting.
- **Gear to smelt** (the user, 2026-11-06): a weapon or armour left loose in the grey bag is smelted into ingots for
  the pile (the first, a katana, gave 4). Later the user will bring old metal gear to smelt down.
- **No pacing**: as fast as the server allows (the user: about 1 second between actions). The bridge never goes
  below 1.1 s between actions, so `rules-Icepick-smith.json` sets 1.1-1.2 s and no breaks. Menu choices and
  target clicks go at once (`aim` 0).
- **Ingots**: the user brings them (3,000 to start). Tell the user when the bag is running low.
- **Hammers**: in a pouch in the grey bag. One sledge hammer to start; the user will add **smith's hammers** (not
  sledge hammers) from now on.
- **Hammers break** (the user, 2026-11-05), so the user keeps a bag full of them stocked. The first, a sledge
  hammer, lasted 199 uses (broke 21:13); the first smith's hammers 50 and 40. The hammers are found in any pouch or bag in the grey bag (the user swapped
  the first pouch for one of smith's hammers, 99 of them by 21:16), so swapping containers needs nothing. Icepick carries one at a
  time; when it breaks he takes the next from the pouch. The loop counts crafts per hammer (to learn how long one
  lasts) and tells the user when the pouch is getting low, and stops if none is left.
- Mining is parked while Icepick smiths (he can't do both); Burgers waits in the tower too.

## The smithy (the tower's ground floor, map 0)

- Icepick stands at **1756,1409** (z 6) by the forge, mounted on McGee (the user, 2026-11-06: by the forge, not by
  the chest; he had been seen at 1757,1408). The chest, the forge and the anvil are all within the bridge's reach of
  2 tiles from there, so he never walks (the user, 2026-11-05: no walking to the chest).
  `smith.py` has no walk at all: if he's moved out of reach, the loop stops with "too far away".
- **Forge** 0x408A3611 at 1755,1410; **anvil** 0x408A3775 at 1756,1410.
- **The ingot chest**: the bottom wooden chest 0x4074A4C1 at 1757,1407 (z 6), which holds any weight. The two chests
  stacked on it (0x4073C9D0 z 10, 0x40531814 z 14) are off limits. The chest also holds the user's own things (a
  pouch of robes and boots, raw ribs, fish steaks, gold, a loose ingot and ore): left alone.
- **The grey bag** (backpack 0x40BF2C73, hue 978) in that chest: the iron ingot stack (0x407F569C), ore to smelt
  now and then, gear to smelt, and the **hammer pouch** (0x408558AD since 2026-11-05; first 0x40421216).
- Icepick's own leftovers in his pack (six small coloured ore piles, a coloured ingot, three shovels): left alone
  (the user, 2026-11-05).
- The ground floor is also the way in for Clem (cartography) and the other characters; Icepick doesn't pause for
  people, and he has no guard here (safe inside, as with Clem).

## Rules file

`rules/rules-Icepick-smith.json`: one small area round the forge, anvil and chest, no guard, no pausing, the ore and
hammer graphics usable from the pack, and the quick pace. `smith.py` copies it into the client's
`Agent/rules-Icepick.json` every time it starts; `mine.py` copies the mining rules (`rules-Icepick.json`) back in its
preflight, so starting the mining loop again needs nothing by hand. The mining planner reads the repo's
`rules-Icepick.json`, which is unchanged.

## Done so far

- 2026-11-05 20:16: the 137 iron ore in the grey bag smelted (6 loads of 25, through `smith.py ore`): 137 ingots,
  the bag now 3,309. These piles (graphic 0x19B8) give one ingot per ore (the large piles Icepick digs give two).
  Smelting works mounted.

## The bridge (version 6, build cuo-agent19)

Crafting needs what the bridge couldn't do before: answering the server's menus or gumps and reading skills. Bridge 6
(`AgentBridgeDialogs.cs`) adds, for any character:
- `GET /skills`: value, base, cap and lock of every skill, and the total (for the skill cap).
- `GET /gumps`: the menus (the old picture and text menus, packet 0x7C) and gumps (0xB0/0xDD) open now, with their
  items, buttons (with the text beside each), switches and texts.
- `POST /use?serial=` with no target: double-click an allowed tool (the hammer) and return what the server showed.
- `POST /menu`, `POST /gump`, `POST /target`: choose a menu item, press a gump button, answer a target cursor.
- `GET /events`: one log of everything: messages, menus and gumps shown, target cursors, skill changes, and what the
  client sent (double-clicks, menu choices, gump buttons, targets, picks, drops), whoever sent it. Only a fixed list
  of packets is read on the way out, never their typed text and never the login.
- `uo record FILE` follows the event log into a file: for recording a task the user does by hand.

## How this server does it (recorded from the user, 2026-11-05 20:33)

cuo-agent19 was installed at 20:31; the user crafted a cutlass and smelted it by hand while `uo record` ran
(`~/claude/uo-agent-work/smith/record1-events.json`). Picture menus (packet 0x7C), not gumps:
1. Double-click the hammer: the **"Blacksmithy Options"** menu: 1 Repair, 2 Smelt, 3 Shields, 4 Armor, 5 Weapons, and
   6 **Make Last Item** once something has been made (it survives a smelt in between).
2. Weapons: "What materials would you like to work with?" and a target cursor: target the ingots (in his pack).
3. "What type of item do you want to craft?": 1 Bladed, 2 Axes, 3 Polearms, 4 Bashing.
4. "What do you want to make?" (Bladed): broadsword 10 ingots, **cutlass 8**, dagger 3, **kryss 8**, longsword 12,
   scimitar 10, viking sword 14. Polearms (seen 2026-11-06 05:53, at 78): bardiche 18, halberd 20, **short spear 6**,
   **spear 12**, war fork 12. The menu's serial changes every time; its id is always 0.
5. About 4.5 s later: "You create the item." or "You failed to create the item, and some of your materials are
   lost." (a failed cutlass lost 4 ingots).
6. **Make Last Item** crafts at once: no materials cursor, no further menus.
7. Smelt: "Target an item to recycle.", target the item: "You melt the item down into ingots." at once. **A cutlass
   gave all 8 ingots back**, so only failures cost metal.

Skills (2026-11-05 20:33): Blacksmithy 57.8 (base 53.2), the total of all base skills 404.7, so no skill cap problem.
Crafting goes by the 57.8. Hiding and Mining are locked at 100; Blacksmithy, Carpentry, Magery, Tailoring and
Tinkering are set to rise, the rest to fall.

## The loop (`smith.py run`, from 2026-11-05 20:39)

- Each time round: the hammer (the next from the pouch when the last broke), the pack's ingots topped up to 150 from
  the bag when under 40, then one attempt (Make Last Item when the last item is the one wanted, else the menus),
  and every item made smelted at once. Every 50 crafts (and at the start) it looks for ore in the bag and smelts it
  first, then any gear lying loose in the bag: one piece at a time into his pack, Smelt, the ingots back onto the
  bag's stack (logged "smelted katana ... from the bag: 4 ingots"). Something that won't smelt goes back in the bag
  and is left alone (`not_smeltable` in the state). Gear ingots count as added in the supplies line ("N of them
  from M pieces of gear smelted"). `smith.py ore` does both without the loop.
- The item comes from the user's table by Blacksmithy's value; `--item NAME` makes one kind regardless (for the
  trial at 99). Items not where expected (short spear and spear are under Polearms, checked at 78) are looked for under the other
  kinds, and the log says so.
- **Clicks in Icepick's client** while the loop runs can take its menu or cursor (2026-11-05 20:45: a click on the
  ground used up the Smelt cursor and the loop stopped). It now tries the step again, and stops only after five
  interruptions in a row ("is someone playing Icepick?"). At the start it smelts any crafted item left in his pack.
- **World saves** (2026-11-05 21:33): the save notices can come where a craft's result should, and just after one
  the server may answer "You must wait to perform another action". The loop leaves the notices out, waits up to a
  minute for the real result, doesn't count a refused attempt, and smelts any crafted item it finds lying in his
  pack every time round.
- **A world save can hold the server's answers back** (2026-11-06 20:32: the hammer's menu came 8 s after the save
  notice, and the loop stopped). It now waits up to 30 s for a menu, a target cursor or a smelted item to go, and
  double-clicks the hammer again if no menu comes; at the start it cancels a Blacksmithy menu left open.
- **Server lag** (2026-11-07 02:30: the hammer's menu came 22 s late, no world save): the bridge stops (423, "the
  server went quiet"). The loop then waits up to 5 minutes for the server to show it's answering (a late menu, a
  target cursor or a new message), resumes, cancels the late menu and tries the step again ("the server lagged" /
  "the server answered again" in the log). More than 5 in an hour, or no sign of the server in 5 minutes, and it
  stops as before.
- **Stops and the counts**: the state is saved at the end of each cycle, so a stop partway through loses that one
  cycle's craft and ingots; the item it made is smelted at the next start and the two cancel out. (Until 2026-11-06
  20:36 the start took the leftover's ingots off "used" as well, which undercounted by 12; corrected in the state.)
  A hammer's minutes leave out the time the loop was stopped.
- It stops by itself at 99 ("time for the spear / plate gloves trial"), when the hammers or ingots run out, or on
  anything it doesn't understand.
- Pace, measured: dclick to menu 75 ms; the bridge answers a menu about 1 s after it shows (the 300 ms settle and
  the game thread's ticks); the server crafts in 4.4-6.7 s; the next action waits at least 1.1 s. A failed attempt
  takes about 7 s, a made-and-smelted one about 12: roughly 300-400 attempts an hour. The next build can skip the
  settle when a menu or cursor is the answer (about a second a cycle).
- The work folder `~/claude/uo-agent-work/smith` (not in git): `smith.log`, `state.json` (totals, crafts per hammer,
  the last item, the item being made), `smith.pid`.

## Running it from a Claude session

- **Start** as a background task, with absolute paths:
  `cd ~/claude/ClassicUO/tools/uo-agent; exec python3 -I ~/claude/ClassicUO/tools/uo-agent/smith.py run`.
  It needs Icepick logged in with the Agent bridge ticked, at his spot with the chest in reach.
- **Watch** the log with a Monitor (30 minutes at most, re-arm at each expiry):
  `tail -n 0 -F ~/claude/uo-agent-work/smith/smith.log | grep -E --line-buffered "start:|now making|STOPPED|-> [0-9]+ after|broke|supplies|low|instead|not under|craft [0-9]+|ore smelted|interrupted|from the bag|couldn't|no Blacksmithy menu|cancelled|lagged|answered again|trial|Traceback|Error"`.
  Every 0.1 gained logs a "Blacksmithy A -> B" line (several a minute at first), so the filter takes only whole
  points ("-> 59 after").
- **Stop**: `python3 -I smith.py stop` (after the craft it's on; waits for the loop to end). No hiding needed indoors.
- **Tell the user**: every whole skill point (with the rate an hour) and the supplies line that follows it, item
  changes, hammers breaking (and how many uses one lasted), `hammers low`, `ingots low`, ore and gear smelted, and every stop.
- **Supplies** (the user, 2026-11-05: keep track of how many hammers break and how many hammers and ingots are
  left): a `supplies:` line at the start, after every hammer that breaks and at every whole skill point: the
  ingots in the grey bag and in his pack, the spare hammers, the hammers broken so far. Also in `smith.py report`
  (with the average uses per hammer) and `supplies`/`broken` in the state.
- **How long the hammers last** (the user, 2026-11-05): every break logs the hammer's uses and minutes and the
  seconds a use; the supplies line gives the spare hammers in hours (average uses of the smith's hammers broken so
  far times the loop's own seconds a craft, leaving out gaps over a minute). First measures: smith's hammers 50, 40,
  70, 71, 66 uses (about 59), 10.5-10.7 s a use (a craft, and its smelt when made), about 10.5 minutes a hammer:
  94 spares were about 16 hours at 22:09.
- **Ingots used** (the user, 2026-11-05: "based on how many we started with and how many are remaining"): started
  with 3,309 plus every addition since, minus what's left in the grey bag and his pack. Additions (the user's, and
  ore smelted) are found as any rise in bag + pack beyond what he used, which the loop counts in his pack round each
  craft and smelt (`ingots_spent`, `ingots_returned`, `ingots_used` in the totals; state `ingots`). The first 442
  are exact (to 21:16); the 258 from 21:16 to 21:38, while the user was adding, are estimated from the failures
  (4.97 lost a failure).
- **Totals**: `python3 -I smith.py report`.
- **The nightly reboot** (about 04:15; the world rolls back to the save about 15 minutes before; MINING.md): the loop
  stops with "the game is not responding". Then:
  1. Back up `state.json`; wait until `uo --char Icepick status` answers (about 04:19); `uo --char Icepick resume`
     if it shows `halted`.
  2. Find the save point: his Blacksmithy (`uo skills`) matches one "A -> B" line in the log; a hammer the log says
     broke after the save is back in his pack; his pack's ingots match a supplies line.
  3. Correct the state: ingots used = started with minus what's really left now (bag + pack); take the hammers that
     broke after the save out of `broken` (the one back in his pack gets its uses at the save; one taken after it is
     back in the pouch, so out of `hammers`); set crafts, made, failed and the item counts back to the last skill line
     before the save; say so in `totals.note`.
  4. Start the loop and the Monitor again, and tell the user.
  2026-11-06: back at 04:19:19, rolled back to about 04:00:30 (76.2 -> 75.8; hammer 0x40860DDD, broken at 04:06:35,
  back in his pack; 133 ingots returned), the loop running again at 04:20:15.
  2026-11-07: stopped 04:15:17, back at 04:19:03, rolled back to about 04:00 (Blacksmithy 96.1 kept; hammer
  0x4094AC9F, broken at 04:07:18, back in his pack; no save notice survives the relog, so the save point came from
  the ingots: bag and pack matched the top-up at 03:56, and 20 of the 150 were gone), running again at 04:20:14.

## The trial at 99 (`smith.py run --trial MINUTES`)

- The loop stops at 99. Then `run --trial 60` makes spears and plate gloves in turns of 60 minutes and keeps, for
  each, the time smithing, the skill gained, crafts, failures and ingots used (state `trial`), until 100. At each
  turn it logs "trial: spear -> plate gloves; so far spear: +0.2 in 1.00 h (0.20 an hour) ...". Gains come 0.1 at
  a time and slowly at 99, so it takes several turns before the two can be told apart; if they're about the same,
  spears (the user).
- Where plate gloves are (found 2026-11-07 10:42): **Armor → Platemail → "platemail gloves: 12 Ingots"** (index
  2; the kinds are Ringmail, Chainmail, Platemail, Helmets; Platemail also has arms 18, gorget 10, legs 20, tunic 25,
  female 20). The item is called "platemail gloves"; names match loosely, so "plate gloves" finds it.
- Started 2026-11-07 10:42 at 99.0, plate gloves first (seeded in the state's `trial`), turns of 60 minutes.

## Questions still open

- How the trial comes out.
