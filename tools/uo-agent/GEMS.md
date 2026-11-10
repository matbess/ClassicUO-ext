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
- **The open graphic can also never come** (2026-11-10 00:55:31): his client's auto-open opened it ("Opening door...",
  "usable from the inside"), the door still showed shut 1 s later, and the script's use closed it again without a
  word (opening it from inside always says "That is locked, but is usable from the inside."; closing says nothing).
  `open_from_inside()` now takes a use that leaves it showing shut with no message as having shut it, and uses it
  again (up to three times). Run again from inside, it opened at once (00:57:57).
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

## Phase 2: selling to the jewelers (`gems.py sell`), the user, 2026-11-09

"There are 7 jewelers in the book who we can go sell to ... First, you recall to the npc, then you find the npc with
the jeweler title and get near them and say '____ sell' and you sell as many gems as you can, 5 at a time. The npc will
run out of money at some point and may already be out of money and refuse to buy anything. Once they are out of money
you can do a trick one time (only works once per hour I think). when they refuse to buy gems you say '____ buy' and
wait for the buy screen to open, then you close the buy screen. Once it's closed the npc will have a bit more money
available to them. Then you go back and do '____ sell' again ... until they won't buy anymore. Once they refuse to buy
again, it's time to move onto the next NPC. Now, it is possible that someone else was just selling and they will refuse
to buy even if you do the trick ... So you just go to each of the 7 NPCs and do this same thing until all of the gems are
gone or they all refuse to buy anymore then you come back to the tower (using the same logic carto did, with fighting
and stuff when needed)."

- **Recall with the flag under each rune** (the Recall button), never the book's charges (it has none: "Charges: 0").
  The book is RunUO's runebook gump: each rune's buttons are 2 + 6 x slot + (0 a charge, 1 drop the rune, 2 set
  default, **3 Recall**, 4 Gate Travel); paging (the corners, 1-8 at the bottom) is the client's own, and the bridge
  presses any rune's button without paging. The runebook is graphic 0x0EFA (as a spellbook), in his rules'
  `useFromBackpack`. Each rune's spot comes from its sextant coordinates in the book (RunUO's Sextant: the centre at
  1323,1624, 5,120 x 4,096 tiles); every landing so far was on the tile they give.
- **The book (2026-11-09)**, slot: name, spot, Recall button: 0 Britain Gems 1, 1456,1685, 5; 1 Britain Gems 2,
  1648,1650, 11; 2 Jhelom Gems, 1444,3977, 17; 3 Trinsic Gems, 1893,2803, 23; 4 Vesper Gems, 2876,717, 29; 5 Magencia
  Gems, 3658,2187, 35; 6 Nujelm Gems, 3775,1172, 41. His rules have a walking area of 25 tiles round each spot.
- **The jewelers** (titled "the jeweler" on their paperdoll): Lamar (Britain 1, 0x00004C92), Charlton (Britain 2,
  0x0002F36F), Kelia (Jhelom, 0x000095B6), Marnie (Trinsic, 0x00039AD4), Lamar (Vesper, 0x00048323), Annamarie
  (Magincia, 0x0000ACC7). Jewelers within 12 tiles of the landing are all sold to.
- **What they say**: out of money: "You have nothing I would be interested in." and no sell window; short of money
  for a sale: "Sorry, I cannot afford but 203 gold at this time." (what he can still pay: the next offer fits within it,
  then single gems); the trick: "Greetings. Have a look around." and his buy window (22 items), closed at once (closing
  the window sends nothing: it's asking that gives him money). Lamar and Charlton bought nothing before the trick and
  about 2,000 gold after; every jeweler bought after it.
- **Prices** (2026-11-09): diamond 120, star sapphire 75, sapphire, emerald, amethyst 60, ruby, tourmaline 45, citrine,
  amber 30 (a gold less now and then as he runs low). Sold the most valuable first, 5 of one kind a sale.
- **Trinsic, Marnie upstairs** (the user: "you can't talk to Marnie without coming up the stairs"; "Go in the room with
  marnie"): she's in a room on the upper floor (z 20) behind a door (0x4000FCF3 at 1896,2806, in his rules' doors);
  from beside her wall she doesn't hear "Marnie sell". The way in (`SHOP_ROOMS` in gems.py): the shop's stairs at x
  1891 from 1891,2808 up to 1891,2803, then 1893,2804, 1895,2806, open her door if shut, 1897,2805. A walk straight to
  her from the top of the stairs went back down them, over and over (the path finder ends a walk at the goal's x,y on
  whatever floor it reaches first).
- **Marnie isn't always upstairs** (2026-11-10 01:01): she was downstairs, 2 tiles from the landing; he went up to
  her room anyway and called down to her, unheard, while she walked about below, and used her trick for nothing.
  Now he goes up only when she's on the room's floor (her z), and comes back down (the way in, reversed) when she's
  below and he's up. Not yet tried.
- **The trick only for a jeweler who heard him**: "no answer" three times (another floor, a wall) isn't a refusal,
  and "<name> buy" won't reach him either; the trick is kept for when he can hear.
- **Vesper**: "no path to there" to Lamar 4 tiles from the landing, at 2 tiles and at 3 (2026-11-09 and 11-10). The
  map files (uomap.py) show why: the rune lands in a room (x 2872-2878, y 712-718) north of the shop; a plaster wall
  along y 719 has one gap, at **2875,719**, most likely a shut door; Lamar walks about behind it (2874-2876,
  721-723), west of his counter (x 2877). These vendors don't hear through walls (Marnie), so he has to open that
  door: its serial is needed for his rules' doors (read it with him there).
- **A player in town**: home at once and 15 minutes inside, then on (the map trips' rule); the user's own characters
  and yellow (invulnerable) vendors aren't strangers; someone whose paperdoll doesn't come back (walked off: the
  bridge's 404 ended the first try in Britain) is asked again next look, and counts as a player after three.
- **The gold** (the user, after the first tour ended at 389 of 390 stones): "As soon as he gets to within 10 stones of
  his max weight then recall home and put the gold in the bottom chest next to the forge ... then you can go back to the
  tour starting by returning to the same vendor you were in the middle of talking to." Gold weighs a stone per 50
  coins. Before every sale he checks the sale fits under his max less 10 stones, and before Recalling on to the next
  jeweler that he has room for at least 750 gold more; otherwise Magic Reflection, Recall home, the front-door fight,
  in, and the gold onto the stack in the **bottom chest of the three stacked by the forge** (0x4074A4C1 at 1757,1407;
  the forge is 0x408A3611 at 1755,1410; Icepick's ingot chest, his rules' "smithy (the gold chest)" area), then ready
  again and back to the same jeweler. At the end of a tour the gold goes there too. 24,900 gold there after the first
  tour (the 15,517 added onto 9,383).
- In town, anything unforeseen (a bug too) or a bridge stop that isn't the user sends him home; only the user taking
  over leaves him where he is. `gems.py sell` started while he's at one of the book's jewelers carries on from there.
- Logs: `gems.log`; `visits.jsonl` (every jeweler: sold, gold, prices, the trick, what was said); `vendors.json` (the
  NPCs seen, players, when each jeweler's trick was last used).

**The first tour (2026-11-09 21:28-21:41)**: all 268 gems for **15,517 gold**: Lamar 21 for 1,995, Charlton 20 for
2,010, Kelia 58 for 3,992, Marnie 64 for 3,600, Vesper's Lamar none (no path), Annamarie 105 for 3,920; Nujel'm not
needed. Home: the front clear, in, locked, parked; the gold into the chest by the forge.

**The second tour (2026-11-10 00:55-01:04, the user: "go sell the gems again please")**: 134 gems (no loose gem in
the chest this time), all sold for **7,785 gold** in 5 minutes: Lamar 21 for 1,995, Charlton 30 for 1,995, Kelia 36
for 1,995 (every one bought nothing before the trick), Marnie none (downstairs while he was up: see above), Vesper's
Lamar none (the door), Annamarie the last 47 for 1,800. The 7,785 went into the chest by the forge as a new pile (the
24,900 from the first tour had been taken out). Fetch, sell and cleanup took 9 minutes in all.

## Phase 3: cleanup (`gems.py cleanup`, and the end of every `sell`), the user, 2026-11-09

"The last part is the cleanup. You should go put the runebook back and put the gembag back. That will be the logic
whether or not there are any gems left over, you just put them back in The Vault."
- The Gems runebook back into the top left chest by the stairs (where `fetch` noted it was; else beside the other
  runebooks), the gem bag, gems left in it or not, back into the vault's gems chest where it was (18,105 the first
  time), the vault door as in phase 1 (in with the key, out without it, checked "That is locked." from the bag room),
  parked. 21:50-21:51 the first time: 35 s.
- **The chest by the stairs from the ground floor only**: a walk to "next to the chest" from the hall ended on the top
  step of the stairs beside it (1751,1403, z 23), 9 above the chest: "I can't reach that.", which the bridge takes for
  silence and halts on. Now he walks 1752,1407, then 1752,1403, and checks he's on the ground floor. From the smithy
  (by the gold chest) he goes through the hall first (a hop straight for the stairs room crossed tiles outside his
  areas).

The whole job from inside the tower: `gems.py fetch`, then `gems.py sell` (which ends with the cleanup).

## Next

- Vesper's jeweler: the door at 2875,719 (its serial into his rules' doors, then a way in like Marnie's).
- Marnie downstairs: the new floor check.
- A gold run in a real tour (tested offline only so far).
