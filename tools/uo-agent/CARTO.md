# Cartography with Clem: the plan and the user's rules

Started 2026-11-05. Like MINING.md, this records what the user asked for, what was found and what was decided, so
any session can pick it up. Newer notes win where they disagree with older ones.

## The job (the user, 2026-11-05)

- **Clem** (0x0004344A) makes **world maps** out of blank maps, in the tower (the user's house; see below).
- Bags of maps lie on the floor of the **second floor, outside the vault**. Some hold blank maps, some maps already
  drawn. The loop: find a bag of blank maps, make world maps out of them, put the world maps back into the same bag
  on the floor, go on to the next bag (how the drawn maps are stored was later left to Claude: see "Decided" below).
  Bags stay on the second floor (see "Storage" below).
- Remember which bags hold blank maps and which are done.
- **Maps get destroyed** now and then while drawing, so the supply shrinks. More come from the **map vendor**: buy all
  his blank maps, sell him the drawn maps (he then stocks the same number of blank maps), buy those back, and bring
  the blanks home in their bags.
- **The vendor's stock grows** when he is bought out: normally he sells about 20; bought out completely and left an
  hour to restock, he stocks more the next time (30, then 40, ...). Once in a while he drops back to about 10. So buy
  him out every hour, and keep the surplus in bags for later.
- **The vault** is the chest room behind the locked door on the second floor (where Johnny sorts and things are
  stored). Clem never goes in there, and bags inside it are ignored.
- **Clem's pack holds 125 items at most**, counting everything inside bags in it, like every container (the user,
  2026-11-05). The user will clear his pack to about 20 items, so he can carry one bag of about 100 maps. **Every bag
  should hold about 100 maps.**

## Blank and completed maps in separate bags (the user, 2026-11-05)

Remember what kind of maps each bag holds and keep the two apart: a bag is either **blank** (every map in it blank)
or **completed** (every map drawn: world maps, sea charts, city maps, local maps).
- Each bag's kind is in the state (`~/claude/uo-agent-work/carto/state.json`: spot, kind, count) and in its label
  (`maps: blank (Clem's bag room)` or `maps: completed (...)`, so `uo nearby` shows it).
- A map only ever goes into a bag of its own kind. The extras taken out of blank bags make new blank bags, those out
  of completed bags new completed bags.
- **The user keeps every bag pure** (2026-11-05: "I've kept the bags so they all contain the same type of map"), so
  maps are moved without single-clicking them first (`carto.py reorg --check` would, at one more action per map).
- A bag being worked holds both kinds until its last blank is drawn; then it becomes completed.
- After a vendor trip the blanks go back into the bag whose completed maps were sold, which becomes a blank bag.
- The kinds of the 46 bags found on 2026-11-05 come from two sampled maps each (30 blank, 16 completed). Working a
  bag or selling it shows what's really in it; anything else goes to a bag of its own kind.

## Bag spots on the second floor (the user, 2026-11-05)

Some second floor tiles have no bag: **leave them empty**, they make it easier to walk and move things. Bags only go
on the 45 tiles that held one on 2026-11-05 (`spots` in the state; 1752,1404 holds two). A bag that's picked up goes
back on its own spot.

## Safety (the user, 2026-11-05)

- **No guard for Clem**: he's safe inside the tower. The guard is per character already: it runs only when the
  character's rules file has a `guard` section, and the alarm file (Agent/alarm.json) is read and written only by a
  guard. Clem's `rules/rules-Clem.json` has none, so nothing Clem does can set off Icepick's or Burgers' guards.
- **No pausing for people** (the user, 2026-11-05: people walk around the tower; nothing should stop because of
  that): `"pauseForPeople": false` in his rules.
- **Full speed** (the user, 2026-11-05: pacing is for mining only; root AGENTS.md): 1.1 s between requests, no
  breaks, no waits added in scripts.
- **In town at the vendor** (the user, 2026-11-08, replacing the Invisibility idea of 11-05): a player shows up ->
  recall home at once (then deal with the creatures at the door as always), and once inside wait **15 minutes** before
  trying the vendor again.
- **The tower door** and the creatures in front of it: COMBAT.md (door.py, fight.py); coming home from town is in
  "Vendor trips" below.

## The tower (map 0)

A T2A Tower multi (0x7A) centred on 1756,1408; floors at z 6, 26 and 46, the roof at 66. Read from `multi.mul` and the
doors the client sees (the bridge's /tiles leaves multi pieces out).

- Ground floor (z 6): the front double door at 1756-1757,1414; a hall along y 1410-1413; the west room (x 1750-1753)
  with the stairs up at x 1750-1751, y 1406 (z 6) to 1403 (z 21). A door at 1759,1406.
- **Second floor (z 26): the bag room** is x 1750-1756, y 1402-1413, split by a wall along y 1409 with a gap at
  x 1753-1754. The stairs up are at x 1755-1756, y 1406 (z 26) to 1403 (z 41). The ground floor stairwell is open at
  x 1750-1751, y 1402-1408. **The vault** is x 1758-1763 behind the door at 1757,1412 (wall along x 1757).
- Third floor (z 46): the west part x 1750-1756 (stairs to the roof at x 1750-1751), a door at 1757,1412 to the room
  above the vault (not Clem's: storage is the second floor only, the user 2026-11-05). Bags already up there: 0x409167C1
  (1752,1402), 0x409167C0 (1753,1402), 0x407B195A (1758,1410).
- Walking between floors: the path finder ends a walk at the goal's x,y on whatever floor it reaches first, so go
  onto the stairs first (top step at 1751,1403 z 23 from the ground floor), then to a tile on the next floor.
- Clem's areas (`rules/rules-Clem.json`): the ground floor hall and stairs room, the bag room, and the third
  floor's west side as overflow only. Not the vault, not the vault door's column, not the room above the vault. The gold chest downstairs will need adding when the user shows it.

## What's there (the look on 2026-11-05 17:10)

- 46 bags (backpacks) in the bag room, 4,958 maps, all graphic 0x14EB, hue 0, 1 stone each (a bag of 120 is 120
  stones). The server names a **blank map "map"**; drawn ones are "city map", "sea chart", "world map", or a local map
  with a name ("map of Britain to Skara Brae").
- **30 bags of blank maps: 3,606** (mostly 120 each), in the north half (y 1402-1408) and the east of the south half.
- **16 bags of drawn maps: 1,352**, sea charts and city maps, in the south-west (x 1750-1754, y 1410-1413).
- No world maps yet.
- Bags with 120 or more: 32. Bringing them to 100 moves 634 maps (about 7 new bags).
- Only two maps per bag were single-clicked, so a bag could be mixed; working a bag finds out anyway.
- A key ring hangs at 1756,1410 (z 38): not touched.
- On the third floor (west side) two older bags already held blank maps: 0x409167C0 (1753,1402) 85 and
  0x409167C1 (1752,1402) 48 (two sampled each). They count as overflow.
- Files: `~/claude/uo-agent-work/carto/look1.json` (every bag and its maps), `names1.json` (the samples).

## The plan (2026-11-05, with the user's answers)

One loop, no phases. Each time round, the first of these that applies:

1. **The vendor is due** (his hour is up): a vendor trip.
2. **A bag holds blank maps**: pick it up, make world maps until no blank is left, put it back on its spot, mark it
   done (with how many maps it lost).
3. **Nothing left to draw**: a vendor trip now, if there are drawn maps to sell; otherwise wait for the vendor.

**Buy out first, then sell** (the user, 2026-11-05, and again 2026-11-08 after Claude got it backwards; see "Vendor
trips" below: "sell first, then buy" is only the order *within* a sell trip; it's part of the trick; if he isn't bought out first, he won't
stock as many blank maps after you sell him the completed ones). With the 125-item limit that takes separate trips:
- **Buy trip** (first thing after each restock): Clem goes with an empty pack (about 105 free places) and buys every
  blank map the vendor has. More than fit (his stock grows by about 10 an hour): more buy trips, all before any sell
  trip. The buyout must be complete before his next restock or the growth stops.
- **Sell trips** (once he's bought out): Clem takes one bag of about 100 completed maps, sells them, buys back the
  blanks they restock, brings them home into the same bag (now a blank bag). One trip per completed bag.
- **On every arrival he opens the buy list first.** Blank maps in stock mean the vendor has restocked since the
  buyout: never sell then; take the bag home and make a buy trip.
- Bought maps land loose in his pack; putting them into a bag is one move per map, done at home in the tower, not in
  town.
- **A finished map lands loose in his backpack** (the user, 2026-11-05), so working a bag costs one move per map as
  well (each new map into the bag right after it's drawn keeps the bag's count of blanks and losses straight).
- **Drawing takes the blank from inside a bag in his pack** (the user, 2026-11-05): no need to take blanks out.

## Decided: maps in play stay loose, bags are storage (2026-11-05)

The user left it to Claude ("whatever is most efficient"). Every completed map is sold sooner or later anyway, so the
number of sell trips is the same either way; storing in bags only adds moves (about 200 per 100 maps, roughly 9
minutes). So:
- **Drawing**: Clem picks up a blank bag (one move) and draws from it; the finished maps stay loose in his pack.
- **No blanks left in his pack**: if the vendor has been bought out since his restock, a **sell trip** with the
  loose completed maps as they are; the blanks bought back come home loose and he draws those next. No moves.
- **A sell trip isn't possible** (the restock is due and the buyout comes first, or too little mana): the loose
  completed maps go into the empty bag (one move each) and down as a completed bag; he picks up the next blank bag.
- **Before each buy trip his pack is emptied**: whatever he holds goes down in bags of its kind.
- **Storage**: the blank bags are the reserve (losses, and the vendor dropping back to 10); the buyout's surplus goes
  into new blank bags; the completed bags are sold on sell trips as time allows.
- **Loose maps of both kinds look alike to the client**, so the loop tracks every map by where it came from: one that
  appears after a draw is completed, one that appears after a buy is blank. That keeps the bags pure when loose maps
  are put away. At the vendor, sell only completed maps (the sell list names them), never blanks.
- The reorganisation is still needed: a bag he picks up must hold no more than about 104 maps.
- **The vendor's sell list includes maps inside bags in his pack** (the user, 2026-11-05), so selling a completed bag
  costs no moves: pick it up, sell what's in it, buy back, and the emptied bag comes home for storage. The list covers
  everything in his pack, blanks too if the vendor buys them: sell only the drawn kinds by name, never "map".
- Every trip is two Recalls (22 mana; Clem has 100).
- Log the vendor's stock at every visit (time, count, price) to learn when he restocks and how the growth and the
  resets go.
- Blanks brought back are topped up into blank bags with room (up to 100 each).

**First, the reorganisation** (the user, 2026-11-05: there isn't room for 7 more bags on the second floor; use the
third floor as overflow, but work back to the second floor only; combining the completed maps frees space):
1. **Completed maps**: 1,352 fit in 14 bags. The two smallest completed bags (43 and 60) are emptied into the others
   with room, and the two over 100 (125, 103) trimmed to 100: 131 moves, 2 bags and their second-floor spots freed.
2. **Blank maps**: the 606 over 100 in the 30 blank bags go into 7 bags: the 2 freed ones (back on their spots, now
   blank), Clem's **working bag** (in his pack; drawing starts there) and **4 overflow bags on the third floor**
   (west side). Clem takes a bag into his pack, walks round moving the extras straight into it (the bag in his pack
   is always in reach), and puts it down where it goes.
3. **Back to the second floor**: Clem draws from the working bag, then the overflow bags, before any other; an
   emptied overflow bag doesn't go back up. Destroyed maps bring the total down (258 more than the second floor's 46
   bags of 100 plus his working bag). Until the overflow is gone, storage counts as full: no buyouts.

Needs: Clem's pack cleared to about 20 items, and 5 empty bags on the third floor (4 overflow, 1 working bag).
737 moves; without single-clicks about 3.3 s a map at the indoor pace (breaks included). Emptied overflow bags are left upstairs for the user.

## Progress

- 2026-11-05 18:11, paused for the user to play Clem: the completed maps are done (16 bags down to 14, none over
  100; 0x409167B7 and 0x409167BC emptied and now blank bags on their spots). The blanks were started: 3 blank bags
  trimmed to 100, 0x409167B7 holds 72 (back on its spot at 1753,1411). Clem's pack: his 17 items plus the empty working
  bag 0x4098F2E7. To carry on: `python3 -I carto.py reorg` (it works the rest out from the bags).
- 2026-11-05 evening: everything committed before another agent starts on other automation; the reorg resumed.
  The user cleared Clem's pack and swapped the working bag: it's now **0x4098F2E4** (0x4098F2E7, the old one, is
  the user's again, downstairs).
- **2026-11-05 20:15: the reorganisation is done.** No bag holds more than 100. Second floor: 46 bags, 4,552 maps
  (14 completed bags with 1,352; 32 blank bags with 3,200). Third floor overflow: 0x4045BFF9 (77) at 1752,1405,
  0x405AE5DC (77) at 1753,1405, 0x409397D1 (76) at 1752,1404, 0x40832F5B (76) at 1753,1404. The working bag
  0x4098F2E4 holds 100 blanks in Clem's pack (120 items in all). 4,958 maps, as at the start. 0x409397A3
  (1752,1403,46) is still empty upstairs. Clem is standing in the gap in the wall (1753,1409).
- **2026-11-05 21:58 to 2026-11-06 11:44: every blank map drawn.** 3,739 blanks (the 3,606 in the bags plus the two
  older bags upstairs, 85 and 48) made about **3,200 world maps**; about 535 were ruined. **Cartography 84.2 -> 95.3**
  (95.7 with his bonus). Success rose with the skill: about 73% at 84, 84% overall, 90-96% a bag at 94-95. Now every
  map bag holds completed maps: 46 on the second floor, 6 on the third (the four overflow bags' results and the two
  older bags'), and 0x409167C0 (78 world maps) in Clem's pack. Nothing was sold: the user, 2026-11-06, "make sure
  you don't try to [sell in town] yet ... only work on drawing on all the blank maps and then pause". Clem stands on
  the third floor at 1753,1402.
- The five bags on the raised strip (x 1752, y 1404-1408, see below) ended on the tiles beside it at x 1753: 1753,1403
  holds three bags, 1753,1407 and 1753,1408 two each. The strip itself is empty now.
- The nightly reboot (04:15) rolled the world back to about 03:58: Clem was holding the bag he'd had before the 04:10
  swap again, with 39 blanks and 54 drawn loose. The state was put right by hand and the loop went on at 04:20.
- **2026-11-10 03:06: Cartography 100, the goal.** The vendor loop (trips.py) had sold every drawn map by 2026-11-09
  16:37 (Cartography 98.5), buying them back as blanks; from then on he only drew (99.3 at 18:53, 100 at 03:06).
  `put_away_at_gm` then filled 0x4045BFF2 and 0x409167BC to 100 and put 20 into 0x409167C1 (25), put the bag in
  his pack (0x40836C28, 6 blanks) back at 1752,1402,46, and parked him in the safe zone (1756,1411), both door
  halves shut. The state is `mode: done` (with `stay_in`): 3,769 blanks and 1,138 drawn maps in the bags.
- Twice the user wanted every map in one bag so they could play Clem (2026-11-09). You don't need to sort that bag:
  the server takes blanks from inside any bag in his pack and the drawn maps land loose; count that bag's blanks as
  "maps in it minus the drawn ones" and put the drawn maps back in at the end (done with a small wrapper around
  trips.py that replaced `drawing.blanks` for that one bag).
- Before any more vendor trips: the user took his 300 gold out (2026-11-10 01:10), and the Ocllo Maps rune
  (0x408F827E) is no longer in his reagent bag, where an unmarked rune (0x408F8282) lies instead. `find_runes` stops
  trips.py at startup without it, even when he only draws.

## Running it (carto.py)

- `python3 -I carto.py bags` lists the bags in the state; `python3 -I carto.py reorg [--dry] [--check]` does the
  reorganisation. It only ever uses Clem's bridge (`CHAR = 'Clem'`), so it can't act as Johnny, Icepick or Burgers.
- From a Claude session, run it in the background: `cd ~/claude/uo-agent && python3 -I carto.py reorg >
  ~/claude/uo-agent-work/carto/reorg.out 2>&1`, and watch `carto.log` (one line per bag; `reorg.out` also has the
  bridge's send lines). At the old 1.5-2 s pace it took about 3.3 s a map; he now runs at full speed (1.1 s).
- **Files** (`~/claude/uo-agent-work/carto/`, outside the repo): `state.json` holds every bag (spot, kind, count),
  the 45 bag spots, and the reorg's plan (`empties` upstairs, `freed` bags, the `working` bag, and `home`: the spot
  each bag picked up goes back to). If it's lost, `labels.json` (committed) still has every bag's kind, and the
  reorg works the counts out again from the bags. `look1.json` and `names1.json` are the first look.
- **To hand Clem to the user mid-run**: stop the process by its pid (never `pkill` by name: the mining loop runs
  too), then put a bag that's in his pack back on its home spot, so nothing is left half done:
  `python3 -I -c "import sys; sys.path.insert(0, '.'); import carto, uo; carto.info = uo.find_bridge('Clem'); s =
  carto.load_state(); carto.put_down(BAG, s['reorg']['home'][BAG])"` (the working bag stays in his pack). Then
  start it again later as above.
- Someone else in his areas (the user's other characters too) pauses the bridge (409 "paused"); `act()` waits,
  checking every 20 s, and world saves are waited out. The nightly 04:15 reboot rolls back to the last save: just
  run it again, since it counts the bags afresh.

## Learned on the way (2026-11-05)

- The **125-item limit** counts everything inside bags in the pack too. Spell icons in the pack listing (serials
  from 0x7F000000) aren't items and don't count (`pack_items()`).
- **Changing floors**: the path finder only checks a walk's goal by x,y, so it stops at that x,y on whatever floor it
  reaches first. Walk onto the stairs first (`go_to_floor()` uses the bottom and top steps at x 1755, y 1406/1403,
  and from the ground floor 1751,1407, 1751,1403, then 1752,1402; walks on those stairs often stop a tile short, so
  it tries again), then to the tile. `/walk` checks the rules area at the height he's at.
- **Walking on a floor**: the ground floor stairs come up into the bag room at 1751,1403, so a long walk across the
  room can go down them and end under the bag (2026-11-05: he stood at 1752,1409 on the ground floor, the server
  said "I can't reach that" to the double-click). `walk()` goes in hops of at most 3 tiles (down and back up is
  always longer), through the gap in the wall (1753,1408 / 1753,1410), never aims a hop at the stairwell or the
  stairs up, and checks the floor after every hop. Only `go_to_floor()` uses a plain walk (`stride()`).
- **"I can't reach that"** isn't an answer to the bridge (cuo-agent17): it stops (423) as if the server had gone
  quiet. And `uo.wait_out_world_save` takes any stop for a world save while a save's messages are among the last 15,
  so it resumed and the same double-click went out 12 times. `carto.act()` now treats a stop within two minutes of
  a save as something else and quits with the last messages.
- **Putting a bag down**: `/move ground=1` drops it at his own feet only (and only the `dropOnGround` graphics), so
  `put_down()` walks onto the spot first.
- **A bag nobody has opened** shows no contents in the client: `contents()` opens it first (not with `--dry`).
- Moving a map from a bag on the floor into the bag in his pack needs only the floor bag in reach (the pack is
  always in reach); `move()` walks to it first.
- The Mac's python3 is 3.9: no f-strings that reuse the outer quote inside `{}`.
- **The raised strip** (2026-11-06): on the second floor the tiles x 1752, y 1404-1408 (beside the ground floor
  stairwell) have something about 5 higher than the floor under the bags (they lie at z 31-32). Clem can't step up
  onto them, and a walk to one went for the ground floor's tile by the stairs instead (the floor check stopped him on
  the top step). He can pick bags up from beside them, but the bridge drops a bag only at his feet, so nothing goes
  back onto those tiles: a bag from there goes down on a neighbouring bag's tile (work.py, `standable()`).
- **After the nightly reboot** (04:15, rollback to about 15 minutes before): the client logs back in by itself (about
  04:19) and knows nothing inside bags. Before starting again: check `halted`, open his working bag through the
  bridge (Razor queued that first double-click for 5 s after the login, which halted the bridge once: `uo resume`,
  the open had gone through), see which bag is really in his pack and how many blanks and loose maps there are, and
  put the state right (`reorg.working`, both bags' kind, count and spot). A swap after the save point is undone.
  On 2026-11-09 Razor's login queue double-clicked the reagent bag, the working bag, Clem and his backpack exactly
  1 s apart (04:19:13-16), then said "Finished 5 queued actions in 4.0 seconds": the bridge records that as a
  takeover, so trips.py refuses to start. Check the event log (`GET /events`) for that pattern before using
  `--resume`; anything else is the user. For drawing, `drawing.bag` and both bags' kind and spot in state.json are
  what to put right (the rollback undid the 04:13 swap: the old bag back in his pack with 20 loose drawn maps).

## Drawing a map (recorded 2026-11-05 21:58, the user by hand; `~/claude/uo-agent-work/carto/draw1.jsonl`)

1. Use the skill Cartography (skill 12; `"skills": [12]` in his rules). No target cursor: the server shows a menu,
   **"What do you want to make?"**: 1 local map, 2 city map, 3 sea chart, **4 world map**, each "1 Blank Maps or
   Scrolls". It takes the blank from the bag in his pack.
2. Choose world map (by name, not number). About 6 s later the server says either **"With great care, thou dost make
   a chart of the geography."** (a world map lands loose in his pack) or **"Thy trembling hand results in an unusable
   map."** (the blank is used up, nothing made). Either way one blank goes, so the pack's item count doesn't change.
3. Again at once: about 10.8 s a map, most of it the server's (and the bridge's /skill wait, below). Now and then
   (26 times in 3,700) the server answers the skill with "You must wait a few moments to use another skill.": just
   use it again.
- Cartography was 84.2 (85.6 with a bonus), cap 100, on 2026-11-05 22:00.
- The loop is in `~/claude/uo-agent-work/carto/` for now (outside the repo while the other agent works on the code;
  to go into carto.py): `draw.py` draws from the working bag until it's empty and logs each go to `draws.jsonl`;
  `work.py` goes bag after bag: draw the working bag, put the loose drawn maps into it, set it down on the next blank
  bag's tile (the completed bag goes down before the blank one is picked up, for the 125-item limit), pick that one
  up. Third floor overflow first, then the second floor by row, the raised strip last. It stops when no blank bag is
  left, and never leaves the tower (his rules allow no spells).
- `/skill` waits for a system message or a cursor, and a menu is neither, so it returns only after its timeout (about
  3 s) each time. For a later build: count a menu as the skill's answer.

## Vendor trips (2026-11-08, trips.py, bridge 12)

The user, 2026-11-08: "It's time to do that." Answers, in their words where it matters:
- **Ocllo**: "I put a rune to ocllo maps in clems bag": 0x408F8282, loose in his reagent bag. The tower rune
  0x406EDAD9 lands him at 1757,1419, just outside the front door.
- **The mapmaker**: "there will be more than 1 npc in the building and you need to find the vendor with the title
  called 'mapmaker' and go near them and say their name followed by buy/sell. For example 'Cador buy' 'Cador sell'."
- **The trick** (the user, correcting Claude: "I told you a bunch of times, there's a trick to this"): "You BUY all
  his blank maps first (to make him have 0 maps). After that is when you sell all of your drawn maps. These should be
  split up into separate trips because he might be selling a lot of blanks. So you take 1 (or more ...) trip(s) with
  an empty bag to buy all of the blank maps (20-95 of them at a time). Bring them back, put them away. Then take up
  to 95 drawn maps to the same npc who now has 0 blank maps and you sell all of the drawn ones. When you are done
  selling the NPC will stock all of those drawn maps as new blank maps ... Now you buy all those blank maps back ...
  Then you can do it again but the 2nd time you don't have to go to buy because you already know the npc is empty
  and has no blank maps (he won't get more for about an hour) ... But each time you start this process over you
  have to begin the process by going to the npc and buying out all blank maps first."
- **Reagents**: "Always check that you are full of reagents (at least 20 of each) before leaving to the npc"
  (restock.py: any below 25 -> restock to full).
- **Gold**: "Clem should carry 300 gold when he goes to town. I put 5000 gold in the top left chest next to the stairs
  (bottom level)": 0x4058ABA9 at 1752,1402,14 (the chest wall by the stairs, 1752-1753 x z 6/10/14; the restock chest
  0x40746D31 is the one under it).
- **How many**: "not more than X number of maps at a time (how ever many he can fit, his limit is 125 items ...)".
  With his own 22 items, his gold and the bag, 100 drawn maps fit and all 100 come back as blanks.
- **Players in town**: "just recall home (then deal with the mobs) and when you're in the tower wait 15 minutes
  before trying to go back to the npc again."
- **Coming home**: "When you recall back you will immediately have to be running code that looks for enemies and
  provokes them onto each other. You should handle all of the enemies until there are no more in front of the tower
  before you attempt to enter the tower ... The code that does the fighting will need to be part of the same code
  that recalls back to the tower so there's no delay": trips.py runs fight.py's Fight (front mode, COMBAT.md) the
  moment the Recall lands, in the same process.
- **Looting**: "You don't have to loot anything except for the gold outside of the tower. Only loot the gold."
- **Empty bags** for bought-out blanks: "we have more empty bags. I can put more bags up there if it's needed":
  trips.py takes any empty bag on the 3rd floor's west side as a blank bag (0x409397A3 at 1752,1403,46 was the first)
  and stops with "empty bags needed" when there's no room left for a buyout.

- **When every drawn map is sold, straight on to drawing** (the user, 2026-11-08: "once all of the drawn maps are
  sold then you should return to drawing maps to raise his cartography skill", and "Don't stop once every drawn map
  is sold ... draw maps on all of them"): trips.py has two modes, kept in state.json (`mode`, `drawing`): selling
  (trips, with the buyouts) until no completed bag is left, then drawing (drawing.py, draw.py and work.py of
  2026-11-05/06 brought into the repo) until no blank bag is left, then selling again. drawing.py picks up a blank bag
  (the 3rd floor first, then the 2nd by row, tiles he can't stand on last), draws world maps until it's empty, puts
  the drawn maps into it and sets it down on the next blank bag's tile before picking that one up; the last goes on
  the spot the first left empty. No vendor trips while drawing.
- **Drawing never leaves the tower, and 100 ends it** (the user, 2026-11-08: "when you are done buying/selling and
  switch to drawing, do not go to the npc to buy more blanks yet, youll simply be drawing and you will not leave the
  tower. This is because I wont be as available to closely watch you fight"; "If you do make it to 100 you should stop
  and just park Clem safe inside the tower. That's all we're trying to do here is reach 100 cartography skill"): at
  100.0 the loose drawn maps go into a bag with room, the working bag back on its spot, he parks in the safe zone,
  and trips.py ends (mode "done").
- **Walking in the tower runs** (the user, 2026-11-08: "why does he walk up and down the stairs so weird. Can't you
  walk up and down them fast?"): carto.py's walks and stair steps go with run=1 (mounted, about twice the pace); the
  short hops and the floor check after each stay (the path finder takes the stairwell otherwise).

**trips.py** (`python3 -I trips.py run [--trips N] [--buyout]`, `trips.py status`; state in
~/claude/uo-agent-work/carto: vendor.json, visits.jsonl, trips.log):
- A buyout is due when the vendor isn't known to be empty, or 55 minutes after his last buyout (his hour); else a
  sell trip. `--buyout` forces one.
- Inside first: a sell trip picks up the next completed bag (3rd floor overflow first), then on the ground floor:
  gold made up to 300, restock.py, door.retrap(), a heal if hurt, meditation to 90 mana, mounted.
- Recall to Ocllo. Anyone human in sight who isn't known to be an NPC is single-clicked once: a title ("the
  mapmaker", "the guard") makes them an NPC (kept in vendor.json; the bridge's learned fidgeters and yellow,
  invulnerable ones count too); anyone else is a player: home, and 15 minutes inside.
- At the mapmaker (walked up to within 2): "<name> buy" first every time. A buy trip buys every blank that fits in
  the pack, the gold covers and the bags at home have room for; all of them bought means he's bought out (the time
  is kept). A sell trip with blanks in his stock means he restocked early: nothing is sold, the bag goes home and a
  buyout comes next. Otherwise "<name> sell" every drawn map (by name, never a blank), "<name> buy" them all back.
  Every visit is logged (stock, prices, bought, sold, gold).
- Magic Reflection, Recall home, fight (front mode), in through the door, parked; the blanks into the bag he sold
  from (a blank bag now, back on its spot) or into blank bags with room; gold back to 300.
- Bridge 12 (cuo-agent29): `/shop?vendor=&mode=buy|sell` says "<his name> buy|sell" to a vendor whose single-click
  title the rules allow ("vendors": ["mapmaker"]) and returns his window; `GET /shop`; `/buy` and `/sell` with
  `items=SERIAL:AMOUNT,...`, only the rules' "goods" (0x14EB) and at most "spend" gold; none of them halts the bridge
  when nobody answers (that would strand him in town), and neither does single-clicking a person.

**Learned on the first trips (2026-11-08 18:48-19:20):**
- The runes are found by name at the start: the Ocllo Maps rune is 0x408F827E ("a recall rune for Ocllo Maps"); his
  tower rune is "Outpost" (0x406EDAD9); 0x408F8282 is unmarked ("That rune is not yet marked." on the first try).
  After a login the reagent bag (where they are) has to be opened first.
- The rune lands him at 3637,2633 in the shop. NPCs about: Cador, Cora, Lady Melva the town crier, Thurston the
  shepherd, Emanuel the Harbor Master, Ayela the artist (vendor.json keeps them).
- **A single click shows only an NPC's name here** ("Cador"); the title is in the **paperdoll** ("Cador the
  mapmaker"; a player's reads "Bob" or "The Glorious Lord Bob, Grandmaster Mage"). The bridge's `/paperdoll` asks
  for it with a plain double-click on the person (the client's paperdoll flag 0x80000000 makes this server show the
  character's own) and closes it again. The client forgets the title once he leaves Ocllo, so it's looked at again
  every visit (the bridge deals only with a vendor whose title it knows).
- **The server sells only 5 items at a time** ("You may only sell 5 items at a time!"; the user: "sell over and
  over"): "Cador sell", 5 maps, again, until he has none (about 40 s for 55). Cador wanders about the shop: Clem walks
  back up to him before every request.
- Prices: blank maps 3 gold to buy, drawn maps 3 gold to sell. **The trick works**: 55 drawn maps sold, his stock
  of blanks went from 0 to 55, all bought back (19:20). He also sells 10 each of many drawn local maps ("Map Of
  Britain", "Map Of The World", ...): left alone. The first buyout (18:58) found 20 blanks.
- **His restocks** (bought out each time): 20 blanks (18:58), 29 (19:54), 38 (20:46): growing by about 9 an hour,
  as the user said. The 20:46 restock came about 52 minutes after the 19:54 buyout, before trips.py's 55: the sell
  trip's look at his buy list caught it (nothing sold, the bag went home, a buyout next).
- **Razor clicks taken for the user**: Razor's AutoSearch double-clicks every bag that lands in his pack, and its
  AutoOpenCorpses a corpse he lands next to (sent before the client knows the corpse, so the bridge's "a corpse isn't
  the user" check misses it). The user keeps both on (AutoSearch feeds their counters): `fight.razor_click` resumes
  exactly those (the one command sent since is that double-click: on a corpse, or on the bag just dropped into his
  pack within a second); anything else waits for the user.

## What the bridge can't do yet (for the next client build, together with the miners' bridge 5)

Bridge 6 (cuo-agent19, 2026-11-05) has menus, gumps, the target cursor, skills and an event log (`uo record`): the
gump recorder and the cartography menu are done. Still to come:

- ~~Vendors~~: bridge 12 (2026-11-08, above).
- Count the server's "I can't reach that." (and other refusals spoken by the character) as an answer, not silence.
- ~~Doors~~: bridge 7 (COMBAT.md).
- Maybe the runebook's gump (the vendor runes are in "Map Makers and Ships"); loose runes work with /cast today.
- Belt and braces: a guard that hears another bridge's alarm should act on it only if that character is a partner.

## Storage and the goal (the user, 2026-11-05)

- **The goal is Clem's Cartography skill.** Make as many maps an hour as the loop can; vendor trips are there to keep
  blanks coming.
- **Storage is the second floor only**: not the third floor, the room above the vault or the roof ("all those bags on
  the second floor should be plenty of maps"). Up to 100 maps a bag; blanks brought back are topped up into blank bags
  with room.
- **When the second floor's bags are full, skip the buyout.** Then the vendor isn't bought out when Clem comes to
  sell, and he restocks fewer blanks after the sale. Claude's plan (told to the user): sell anyway and buy back all he
  has; if that loses maps, storage gets room again and the buyouts resume.

## The user's other answers (2026-11-05)

- **Drawing a map shows gumps and messages.** The user will draw one by hand while the bridge records the gumps, the
  buttons pressed and the messages, so the steps come from what really happens (needs the new build).
- **The vendor's rune** and **Clem's gold** are in a chest downstairs on the main floor; the user will show them when
  we're ready.
- **The restock**: not known whether it comes an hour after the buyout or on the vendor's own clock. The visit log
  will show.

## Questions still open

- The way home: where the tower rune lands, which key opens the front door, and whether it also opens the vault.
- Whether to start the bridge additions above (asked 2026-11-05, no answer yet). Plan: build them in a separate git
  worktree together with the miners' pending bridge 5, and install only with the user's go-ahead while the clients
  are closed.

## Next steps (in order)

0. **Done 2026-11-10: Cartography 100** (Progress). Clem is parked; nothing is running for cartography.
1. Done 2026-11-06: every blank drawn (Progress). Clem is paused until the user says what's next.
2. Fold draw.py and work.py into carto.py once the other agent is done with the code.
3. 2026-11-08: vendor trips written (trips.py, bridge 12, above). First runs watched closely: where the Ocllo rune
   lands (then narrow his Ocllo area to the shop), the shop's NPCs and their titles, the names in the buy and sell
   windows, prices, and the first fight at the door coming home.
