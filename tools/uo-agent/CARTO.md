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
- **In town at the vendor** (only briefly): if anyone who isn't a known NPC is about, cast **Invisibility** on himself,
  then work out while invisible whether they're an NPC (the fidget animations the guard already learns NPCs by) or a
  player. An NPC: carry on. A player: recall back to the tower and go inside.
- **The tower door**: unlocking and re-locking it, and what to do about a monster near it, are still to be worked out
  with the user.

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

**Buy out first, then sell** (the user, 2026-11-05: it's part of the trick; if he isn't bought out first, he won't
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

## Running it (carto.py)

- `python3 -I carto.py bags` lists the bags in the state; `python3 -I carto.py reorg [--dry] [--check]` does the
  reorganisation. It only ever uses Clem's bridge (`CHAR = 'Clem'`), so it can't act as Johnny, Icepick or Burgers.
- From a Claude session, run it in the background: `cd ~/claude/uo-agent && python3 -I carto.py reorg >
  ~/claude/uo-agent-work/carto/reorg.out 2>&1`, and watch `carto.log` (one line per bag; `reorg.out` also has the
  bridge's send lines). It takes about 3.3 s a map at Clem's pace.
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

## What the bridge can't do yet (for the next client build, together with the miners' bridge 5)

- **Vendors**: read the buy and sell windows, buy, sell (the client already has the packets: Send_BuyRequest,
  Send_SellRequest).
- **A gump recorder**: every gump the server shows (layout and text), the button the player presses, and the
  messages around them, so the user can draw a map by hand while Claude watches.
- **Cartography**: reading and pressing the gumps it shows (Send_GumpResponse). Steps from the recording.
- **Invisibility on himself**: /cast only aims at things the character carries.
- Count the server's "I can't reach that." (and other refusals spoken by the character) as an answer, not silence.
- **Doors**: open and close, lock and unlock with a key.
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

1. Add the two older third floor blank bags (0x409167C0: 85 at 1753,1402; 0x409167C1: 48 at 1752,1402; the client
   has forgotten their contents, so open them first) to the state as overflow blank bags. The reorganisation itself
   is done.
2. The bridge additions (vendor, gumps and the recorder, Invisibility on himself, doors), with the user's go-ahead.
3. With the new build: record the user drawing a map by hand; the user shows the vendor rune, the gold chest and the
   door; then write the drawing and vendor loop in `carto.py`.
