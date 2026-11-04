# Mining with Icepick: the plan and the user's rules

Started 2026-11-01. This file records what the user asked for, what was tested and what was decided, so any session
can pick it up. The newest decisions are near the bottom; where an earlier note disagrees, the later one wins.

## Status (2026-11-01, end of the evening)

- Built and tested: the bridge (installed build cuo-agent16), the rules files (`rules/rules-Icepick.json`,
  `rules/rules-Burgers.json`, copied into the client's `Agent/` folder), the route (`routes/route1.jsonl`), the
  planner (`mining.py plan`: 92 ore blocks), and the loop (`mine.py`). Tested in the game with the user watching:
  digging, smelting, trades both ways, Recall, the bank trip, Gate Travel, Hiding, the horse, and the guard
  (talk, loitering, getting away straight and past the stranger in the canyon, waiting until they've gone).
- Not yet run: a whole pass top to bottom, the gate inside the loop, the tired-horse trick inside the loop, the
  wait between passes, and anything unattended. Run the first whole pass with the user around.
- How to run: `python3 mine.py --passes 1` (from where the last run stopped; `--from N --to M` for a stretch;
  `--bank` for a bank trip only), as a background task. It logs to `~/claude/uo-agent-work/mining/mine.log` and
  stops on anything that needs the user (staff, a stolen rune, a lost horse, a bridge gone). Before starting: both
  characters logged in with the Agent bridge option ticked, Icepick near McGee, Burgers by the forge with his four
  runes.

## The job

- **Icepick** (the user's miner and blacksmith) mines a mountain range inside a town, under the guards' protection,
  starting at one end ("the top") and working to the other ("the bottom"). He never leaves the guarded area.
- When his pack gets heavy he walks to the forge, smelts the ore into ingots, and hands the ingots to **Burgers**
  through the trade window (Icepick drops them on Burgers, both accept).
- **Burgers** waits next to the forge. With the ingots he recalls to the bank (loose runes in his backpack: one for
  the bank, one for the forge), says "bank", puts the ingots in his bank box, recalls back to the forge and waits
  in place again. Then Icepick carries on mining.
- At the bottom Icepick smelts and hands off the last ingots, walks back to the top, and waits for the ore to come
  back (about an hour; to be measured), then starts again.
- The loop runs as a script without Claude (no tokens while mining or waiting). Claude is only woken when it stops.

## The route (the user's map, 2026-11-01)

- Icepick works along the foot of the mountains, following the user's red line on the world map (rotated like the
  game: north is to the top right). The forge is by the mouth of a canyon roughly in the middle of the route.
- **The canyon** runs through the mountain and leads out of the guards' protection. Icepick goes only halfway in,
  crosses to the other side of the path, and carries on mining along the other mountain face. He never follows the
  canyon out.
- The user will walk the route with Icepick while Claude records the positions (read only); the areas and the
  waypoints come from that recording.

## Shovels (the user, 2026-11-01)

- Icepick digs with shovels from his backpack and carries about 5. When they have all broken he goes back to Burgers.
- Burgers keeps the spare shovels in his bank box and brings them back from a bank trip; he gives them to Icepick
  through the trade window, the same way the ingots go the other way.
- Icepick smelts his ore every time he goes to Burgers, before handing over the ingots.
- Top-ups are fine (the user: "whatever is most efficient"): on every bank trip Burgers brings back enough shovels
  to bring Icepick back up to 5, since Icepick waits at the forge for the round trip anyway.

## More from the user (2026-11-01)

- **Hiding.** Both characters have GM Hiding. **Burgers is hidden whenever he isn't dealing with Icepick**: he hides
  again right after every trade and right after recalling back to the forge, and only shows himself (one step) to
  trade (Icepick's client can't see a hidden Burgers, so he can't drop anything on him).
- **No Meditation** for Burgers (the user: he won't recall often enough to need it).
- **The bank is relaxed** (the user, 2026-11-01): other players around the Ocllo bank are fine, and Burgers is only
  there for a few seconds, so no getting away and hiding there. He just drops off and picks up, and recalls back.
  The loop turns Burgers' guard off before recalling to the bank and on again back at the forge (and then checks
  that all four runes are still in his pack).
- **Gate.** When Icepick is far from the forge (towards the northern end), Burgers opens a Gate Travel towards the
  middle of the mountain so Icepick gets to and from the forge faster. That needs a rune marked there.
- **Always ride when not mining** (the user, 2026-11-01): Icepick gets off his horse McGee (0x00042FCB) only to dig,
  and back on before going anywhere, even a short way, so the horse is never left behind. On 2026-11-01 Claude walked
  him on foot to the bottom end and back to the forge (McGee followed, but that's not to be relied on).
- **Travel takes short cuts** (the user: following the canyon in and out to reach the forge "looks silly and wastes
  time"): mining.walk_route walks to the furthest waypoint within 15 tiles each time, so it skips the canyon loop
  (bottom end to the forge: 3 hops). Mining itself still goes along the route, canyon walls included.
- **Between nearby mining spots Icepick walks** (the user, 2026-11-01): he doesn't have to get back on McGee to move
  4-5 tiles to the next rock; the horse follows on foot. But never lose the horse: after every hop check that McGee
  is still close (he can get stuck behind a tree); if he isn't, go back to him and ride. Ride for anything longer
  (to the forge, back to the route, getting away).
- **Don't let McGee fall behind, he may go wild** (the user, 2026-11-02 23:00): if he's stuck, or more than 8 tiles
  away, Icepick goes and gets him at once, then carries on with what he was doing. `keep_mcgee` checks before every
  dig: more than 8 tiles off, out of sight, or more than 2 off and no closer for 5 seconds (stuck) means Icepick
  gets on him, rides back to his spot and gets off again. (He once stood on the rocks 6 tiles off and 13 higher
  while Icepick dug on; the check after each walk didn't see it.)
- **If McGee goes wild** (the user, 2026-11-02: he stops listening or won't let you ride), Icepick tames him again
  with Animal Taming (skill 35, in Icepick's rules; even at his low skill it works). The loop sees it when a mount
  fails ("You dont own that mount."); stops listening shows the same way, as keep_mcgee goes back and mounts. With
  bridge 3 (/skill takes `target=`, only one of the rules' mounts; build cuo-agent16) he tries up to 30 times, 10 s
  apart, until "It seems to accept you as master.", then mounts and says "all follow me". On an older bridge the loop
  stops with Icepick on foot next to McGee for the user to tame him by hand. The "yourPet" flag in /nearby isn't
  used alone: the client learns it from a status packet it may not have had since a login.
- **The bank** (the user, 2026-11-01): Burgers' bank box holds a bag with 59 shovels (take shovels from it) and a bag
  for the ingots (put ingots into it). Serials still to be read on the next bank visit.
- **Mount before hiding, always** (the user, 2026-11-01 21:37, with a screenshot of McGee standing next to a hidden
  Icepick): a riderless horse gives the hidden rider away. Every hide in the loop goes through Miner.hide(), which
  gets Icepick back on McGee first; the bridge's fallback hide mounts a horse from the rules first (cuo-agent12).
- **Tired mount.** On this server a tired mount gets its stamina back like this: dismount, say "all follow me",
  wait a second, mount again (double-click the horse). The user has it on F4 as a macro.
- **Small ore piles.** Sometimes a pile has too little ore to smelt. That's fine: leave it; it may combine with
  another small pile later (the smelt cursor also takes another pile of ore to combine with). Icepick has a few
  1-ore piles in his pack for that reason.
- Not in build cuo-agent8 yet: using the Hiding skill, dismount/mount, "all follow me" (the say list is in the
  rules file, so that part is only config), and walking through a gate.

## Safety rules (the user's, 2026-11-01, changed the same evening)

**What sets the guard off:**
1. **Talk.** Anyone other than Icepick and Burgers speaks near either of them. The user's brother counts too (he'll
   stay away; change it later if needed). Town NPCs (vendors, guards, bankers) talk too: learn the local ones first
   and leave them out.
2. **Loitering.** A player who stands near either character instead of walking or running past may be snooping or
   stealing: within 3 tiles for more than **3 seconds** (the user, 2026-11-01 21:36; first 10).
3. **Missing rune.** Either of Burgers' runes disappears from his backpack: someone stole it.
4. **Attack.** Anyone attacks either character. Also a trade window opened by anyone but the partner.

**What to do (the user, 2026-11-01): get away and hide, don't log out.** Logging out outside an inn leaves the
character standing in the world (tested 19:38: the guard's logout worked, Clem's "hi" logged both out at once, but
that's no protection). Instead:
- Remember where he was, run away from the person (staying inside the guarded area, i.e. the bridge's corridor),
  and when about 50 tiles away (30 at first; the user, 2026-11-02 23:30: 50), hide, on McGee. Don't log out.
- Wait hidden for the person to leave. If he gets revealed before they've gone, hide again.
- When they're gone, go back to where he left off and carry on.
- Claude's working definitions (tell the user; change if they want): "gone" means neither character has seen them
  for 3 minutes, and they're not in sight on the way back (if they are, get away and hide again). Burgers' area
  is only the forge, so he gets away by recalling to the Mining Start rune, hides there, and recalls back. When one
  character is getting away, the other stops work and hides where he is. A stolen rune: get away and hide, then
  stop the loop and tell the user. If the mining script isn't running, the bridge hides by itself a few seconds
  after the alarm.
- Tell the user about every incident (who, what happened), at the latest when the script next stops.

**Staff are different (the user agreed, 2026-11-01; not built yet).** If whoever speaks looks like staff (GM chat
message type, GM body 0x3DB or a GM robe, or a name/title with GM, Seer, Counselor, Admin or Staff; when unsure,
treat them as staff): stop all automation on both characters at once, don't run, hide or log out, say nothing
(Claude won't pretend to be the user to a moderator), and alert the user right away so they answer themselves.
An optional truthful away message ("my owner is away and has been notified") only if the user asks for it.

Test 2026-11-01 19:38: Clem said "hi" next to Burgers; Burgers' guard tripped at once and Icepick's followed within
the second through Agent/alarm.json; neither client reconnected by itself.

There are now a couple of other players on the server (2026-11-01), besides the user's brother.

## What was built (first plan, kept for the record)

- Bridge: rules per character (Icepick: the mountain range and the forge; Burgers: the forge spot and the bank),
  mining (use the pickaxe on a rock or mountain tile), smelting (use ore on the forge), trade (drop on a character,
  accept), casting Recall on a rune, saying only "bank", the safety watcher with a shared alarm file so both
  clients log out together, and logging out.
- Tools: read the map files to list every mineable tile in the area; the mining loop script.
- Installing a new client build needs all the user's clients closed: ask first.
- **Reagents low** (the user, 2026-11-03): after every bank trip and at the start, if any of Burgers' four
  reagents is below 20 the loop logs `reagents low: ...` with all four counts; relay it so the user can add more
  to his bank before he runs out (his bank bag ran out of black pearl that morning).
  Every handoff line ends with his four counts. If his bank had none of a recall reagent (black pearl, blood
  moss, mandrake root) and he's down to under 4 of it, or under 2 before any bank trip, the loop parks both
  and stops, so he can't get stuck at the Ocllo bank unable to recall back.
- **Stopping the loop** (the user, 2026-11-02 23:13: for an install both characters are mounted and hidden when
  the clients close, and never stopped while Icepick digs on foot):
  - `python3 -I mine.py --park` is the way: the running loop stops before its next dig (or after the step it is on), puts Icepick on McGee and
    hides him, sees Burgers hidden at his spot, turns off the guard of each one that is hidden (so the user can
    play them; the user, 2026-11-03), logs `PARKED: ...` with both and ends. The command waits for that and prints
    it. The next run starts at the next block, and its preflight turns both guards back on.
  - Out of shovels (none on Icepick, none from Burgers or the bank) parks them the same way before the loop stops
    (the user, 2026-11-03), guards off too; the STOPPED line says how they were left.
  - `python3 -I mine.py --stop` only for an emergency: ends the loop at once, nobody parked; then hide them by hand.
  - Both find the loop by `mine.pid` in the work folder and check the process has gone. Don't pkill by name: the
    loop runs as `.../MacOS/Python -I mine.py`, so `pkill -f "python3 -I mine.py"` killed only the shell around it
    and the loop ran on through a forge visit (2026-11-02 23:14). A second loop won't start while one runs.

## Tested 2026-11-01 evening (build cuo-agent8)

- Walking the route, smelting, trading both ways, digging, Recall, "bank" and depositing all work through the bridge.
- **Digging:** the shovel is used from the backpack and aimed at the rock (graphic 0 = the ground, with the land
  tile's z). Not while riding ("You can't mine while riding"): dismount first, say "all follow me" so the horse
  follows, remount to travel. Answers: "Where do you wish to dig?", then "You dig some iron ore and put it in your
  backpack" (also bronze etc.) or "You loosen some rocks but fail to find any useable ore". 5 digs on one rock by the
  forge (1143,1859) gave 5 ore; about 15 stones of ore per dig.
- **Smelting:** use the ore pile on the forge item (0x400BF6E0, at 1148,1859; reach 2, Icepick stands at 1147,1857).
  "You smelt the ore removing the impurities and put the metal in your backpack." 2 iron ore gave 4 ingots, 3 bronze
  ore 6. A 1-ore pile: "There is not enough metal-bearing ore in this pile to make an ingot." The cursor also takes
  another pile to combine with.
- **Trades:** drop on the partner opens the window; more drops on the partner go into it; both accept and it's done.
- **Recall:** Burgers' Recall costs 11 mana (40 max; he regains about 1 every 8 s), so a bank round trip is 22. Ocllo
  bank lands at 3686,2506. "bank" opens his bank box (0x4084E5F1). Bank NPCs: Roberta (0x0001EFC6) and Emo
  (0x0000D57D), both "(invulnerable)". Morgan (0x0003EC23) stood 9 tiles off with no such label: possibly a player.
- Burgers carries the spare shovels in his backpack (11 left after giving Icepick 3), not in the bank.
- Burgers' mana is the bottleneck, so Icepick hands over the ingots and goes back to mining; he only waits for
  Burgers' bank trip when he needs shovels.
- Name labels of animals coming into view (ClassicUO names them) arrive as messages; the bridge must wait for the
  server's own (system) message after a dig, not just any message (fixed in cuo-agent9).

## Pacing (the user, 2026-11-01)

The server has no moderation now, but the moderator might come back and enforce old rules without the user hearing
about it first. So nothing is ever done faster than a person might. The user first asked for 1-2 s between actions,
then found dismount / "all follow me" / dig / remount at about 1.8 s gaps (and the aim 0.1 s after the cursor) still
too fast. Now, in Icepick's and Burgers' rules:
- a random **2.5-4 s** between actions, and a **6-10 s** break after every 5;
- a random **0.7-1.5 s** between a target cursor appearing and the click (digging, smelting, Recall), from build
  cuo-agent10;
- walks wait their turn like any other action, and the next action waits a full gap after arriving (cuo-agent10;
  mining.pause() covers the build before it).
Johnny's sorting rules (rules.json) keep 1.5-2 s and 3-5 s. If the user says it's still too fast, slow the rules
files further: they apply at once, without a new build.

## Tested 2026-11-01 night (build cuo-agent9)

- Hiding: `uo skill 21`; "You have hidden yourself well." (from the character, not a system message). Any step
  reveals. Skills share a cooldown: a second use within ~10 s gets "You must wait a few moments to use another
  skill", so retry after 10 s. Hide last: step into place first, then hide.
- Dismount (double-click self) and mount (double-click McGee) work; dig on foot, then straight back on the horse.
- Burgers rides too (his mount isn't in his rules yet).
- **Gate Travel** (tested 20:35): `uo --char Burgers cast 52 0x406EC754` at the forge opens a blue moongate on
  Burgers' own tile ("You open a magical gate to another location"); the far end is at **1141,1666** (inside
  Icepick's corridor, about a third of the way down the route from the top). It uses all 40 of Burgers' mana (back
  in about 5 minutes). Burgers must step off the gate so Icepick can ride onto it, then hide again. Icepick arrives
  standing on the far gate; to come back he steps off and on again. Both ends stayed open at least 25 s.
- Burgers' mana after a gate: 0, so no Recall until it has come back (Recall needs 11).

## Ore blocks (tested 2026-11-01 20:57)

- Ore is shared by **8x8 blocks of tiles aligned to the map grid** (block = x // 8, y // 8), as in RunUO: the rock at
  1143,1859 gave 16 ore in 17 digs (about 22 that day with the earlier digs) and then "There is no metal here to
  mine"; 1143,1858 (same block) answered "no metal" at once; 1144,1860 (next block east) gave golden ore. So the loop
  digs one rock per block until it's empty, then moves to a rock in another block. Refill time: the user thinks
  about an hour (RunUO's default is 10-20 minutes); to be measured.
- Every dig that finds ore adds 12 stones (one ore). Mixed iron, bronze and now and then golden.
- **Digging strokes can be fast** (the user, 2026-11-01): only the other actions need the slow pace. Repeat digs on
  the same rock get a short gap from build cuo-agent11 on.
- **Random spots** (the user, 2026-11-01: "don't always dig in the exact same spot"): mining.plan() lists, for each
  of the 92 ore blocks along the route (in route order), every rock in the block inside the corridor and every
  walkable place within reach of it (route waypoints, or a tile one step off one that the map shows walkable).
  mining.choose() picks a random rock (rocks nearer the ground a little more often, so the server can see them)
  and a random place to stand for each pass; the block's other rocks are tried if the server won't dig the first.

## Loop decisions (the user, 2026-11-01 night)

- **Small ore piles:** a small pile (0x19B7) holding 1 ore can't be smelted; the loop skips it, and combines two
  small piles of the same metal (hue) first. Larger pile graphics smelt even with 1.
- **Banking:** Burgers banks when he holds about 300 ingots (they weigh next to nothing: 80 ingots didn't change
  his 143 stones), when he's down to fewer than 5 spare shovels, and at the end of every pass (waiting for 22 mana).
- First loop test, blocks 69-72 by the forge (21:12-21:17): 24 ore, 4 misses, 2 forge visits, 80 ingots to Burgers,
  Icepick topped up to 5 shovels; McGee fell behind once on a walk and the loop went back and rode; block 142,232
  (emptied 20:58) was still empty at 21:15; one rock up the slope gave "Target cannot be seen" (another was tried).

## Guard tests and changes (2026-11-01 21:20-21:40)

- 21:24 and 21:27: Clem said "hi" next to Icepick; his guard tripped at once, Burgers' followed through the alarm
  file, Icepick rode off and hid about 30 tiles away. The first version rode along the route and snagged once, so
  (the user) **he now rides straight away from the person**, to an open walkable spot ~30 tiles off inside his
  areas, trying the directions closest to straight away first. His rules got a "getting away" area: the open town
  east of the mountain, x 1100-1215, y 1550-1897, minus the canyon past halfway. If "You have left the protection"
  shows while running, he goes straight back and tries another direction.
- **Canyon** (the user): with the stranger at the mouth, run back towards town past them (deeper in is off limits);
  the direction search goes all the way round.
- **Burgers gets away by recalling to the Mining Start rune** (his area is only the forge), hides there and recalls
  back to the forge once the stranger has gone. Twice (21:29, 21:31, 21:34) Clem stood by the forge and Burgers
  recalled away each time he came back: correct, but costly, so the wait doubles for the same person each time
  (3, 6, 12 minutes). At start-up the loop recalls Burgers back to the forge if he isn't there.
- **Check the rune before using it** (the user, after thinking Burgers used the wrong one; he hadn't: his get-away
  goes to Mining Start on purpose): every recall and gate first single-clicks the rune and checks its name
  ("Ocllo Bank", "Mining Start", "Mining Forge", "Mining gate location"); a mismatch makes the loop look for the
  right rune by name, or stop. The bridge allows single clicks during an alarm from cuo-agent12 on.

## Travel (the user, 2026-11-01 21:46, after watching the first pass ride up along the mountain)

- Long trips go **straight with the path finder** (`Miner.travel`), not along the mountain face ("all weird and
  slow"); only if it finds no way does it fall back to long hops along the route.
- **To the top of the route: straight to Burgers at the forge, and through his gate on the Mining Start rune**
  (comes out at 1130,1544). At the start of a pass and after the bottom. Burgers needs full mana; the loop waits up
  to 4 minutes for it, then rides instead.
- Back from the forge to a block far north: through a gate to the nearer end (start or middle) if Burgers has full
  mana, else ride straight.
- **Recorded rides** (the user's idea, 2026-11-01 22:03-22:09): the user rode Icepick from the top of the route,
  from the canyon and from the bottom end, each to the forge (`routes/ride-top.jsonl`, `ride-canyon.jsonl`,
  `ride-bottom.jsonl`; spots outside Icepick's areas trimmed). A long trip follows the ride that fits best, either
  way (`mining.ride_path`: plan to the nearest point of the ride, a waypoint about every 10 tiles along it, plan
  from the point nearest the goal); other trips are planned on the map (`mining.plan_path`). The bridge rides the
  waypoints in one go (`/travel`, cuo-agent13: the next stretch starts 3 tiles before the current one ends).
- While recording, Icepick strayed out of the guards' protection twice (the canyon at 1116,1909 and the bottom end
  at 1190,1904): both past the corridor's limits, so the measured edges hold.
- **When Burgers banks** (the user, 2026-11-01 22:15: a bank trip costs 22 mana and a gate needs all 40, so banking
  mustn't cost Icepick a gate): in the south half of the route (from the middle gate spot down), when he holds about
  300 ingots; at the end of every pass, everything; in the north half only when he must (a nearly full pack).
  Shovels alone are a reason to go only once he has none left to give (the user: with 15 there's no need to go
  for 5 more); when he's at the bank anyway he tops up to 20. He carries up to 20 spare shovels (ingots weigh about a
  tenth of a stone each, so a whole pass's worth fits). Icepick keeps his small one-ore piles (no "emptying" them).
- **McGee check** (the user, 2026-11-01 22:20: "you're a little too strict"): after a walk between blocks, give the
  horse 3 seconds to catch up (the user: 2 was too short, 5 more than needed), then go back for him only if he's more than **8 tiles** away or out of sight (it was
  3 tiles, checked at once).
- **Forge trips by weight** (the user, 2026-11-01 22:23): only when the pack weighs **more than 380** (and never
  over 393): a dig adds 12, so he digs while at 380 or less. No "half-full at the start" trip (that sent him to
  the forge from the north at 237 stones).
- **Icepick carries 2 shovels** (the user, 2026-11-01 23:04; was 5): about one wears out per forge round trip and
  he's topped up at every visit, and fewer shovels leave room for more ore.
- **The wait between passes** (the user, 2026-11-01 23:13): an hour from when the pass *started* (that's when
  the top was dug), not from when Icepick gets back to the top; if the pass took longer, he starts again at once.
- **Failed smelts are tried again** (the user noticed a golden pile left over, 2026-11-01 23:27): "You burn away
  the impurities but are left with less useable metal" means the smelt failed and ate some ore (harder metals like
  golden fail more); the loop smelts what's left again, up to 4 more times.
- **Buildings the map doesn't show** (2026-11-01 23:35: Icepick rode straight into one at 1133-1151,1793-1819; the
  user: "it looks like a field on the map, it's some special addition... you have to go around"): made of items
  the server placed (walls, wooden planks, thatch roof, barred metal doors at 1145,1807 and 1148,1807, a wooden door
  at 1143,1819), so only the client knows them. The loop records every building piece the client shows
  (`routes/obstacles.json`, before every ride) and the planner keeps a tile clear of them. The client opens doors
  you walk into, which is how he got in.
- **NPCs look like players to the client.** 2026-11-01 23:57: Sacha (0x00023934, a townsperson wandering near the
  route, the user says) stood next to Icepick and set the guard off; the client only knows her as "Sacha" (no title,
  no "(invulnerable)"), so there's no telling NPCs from players by what the server sends. Known NPCs go in the
  rules' `guard.npcs` list (serials): the Ocllo bankers, and Sacha. When the guard trips on someone the user says is
  an NPC, add them.
- **NPCs by their fidget** (the user, 2026-11-02: NPCs twist their upper body when standing still, players never
  do): that's an idle animation the server sends. Build cuo-agent14 records every animation the server sends for
  characters nearby (`uo animations`) and, once the rules' `guard.fidgets` lists the fidget animation numbers,
  marks anyone doing one as an NPC for good (`Agent/npcs-learned.json`); the guard ignores them. Installed
  2026-11-02 00:05; the first animation caught was Sacha's **6** (twice), now in both rules (`"fidgets": [6]`). In
  UO, human animations 5 and 6 are the two idle fidgets; add 5 once a townsperson is seen doing it.
- **Icepick carries 3 shovels** (the user, 2026-11-02 00:30): with 2 he ran out before his pack was full.
- **No bank trip at the end of a pass** (the user, 2026-11-02 00:35): the gate to the top needs all of Burgers' mana,
  so at the end he smelts, hands over and gates Icepick up; the bank waits for the south half of the next pass
  (about 300 ingots), or for a must (no spare shovels, a nearly full pack).
- **Tired horse** (the user, 2026-11-02 00:42: "it wasn't handling it"): the server says "Your mount is very
  fatigued." (an emote, a warning) and then "Your mount is too fatigued to move." (a system message, many times a
  second while he tries to ride). The loop now acts on any "fatigued" message, and checks after every ride stretch
  (also one that stalled) and before every hop, not only on arriving.
- **Reagents** (the user, 2026-11-02 00:45): Burgers keeps **35** each of black pearl, blood moss, mandrake root and
  sulfurous ash in his pouch, topped up from a reagent bag in his bank on every bank trip; fewer than 6 (black
  pearl, blood moss, mandrake root) or 3 (sulfurous ash) makes a bank trip a must.
- **Run-and-hide incidents to review** (the user, 2026-11-02 00:56): every guard incident is kept in the state
  (`unreviewed`) until the user says they've reviewed them, and every handoff line ends "Run and hide: N to review".
  `python3 mine.py --incidents` lists them (when, who, what, where); `--reviewed` (only when the user says so) sets
  the count back to 0. The full record stays in incidents.jsonl and the bridge's alarms.log; all logs are on the
  Mac (~/claude/uo-agent-work/mining), so a server reboot doesn't lose them.
- **Server lag** (2026-11-02 02:08): a dig's "Where do you wish to dig?" came 13 s late, so the bridge (which waits
  3 s) stopped on "no answer". The server had answered, so it was lag, not a dead server: the loop now cancels the
  cursor left behind, resumes and carries on when the answer turns up within half a minute of the stop, and stops
  and tells the user if that happens three times in 10 minutes.
- **Server down** (2026-11-02 04:15): the server reset the clients' connection (RST after about 4 h 9 min); the
  clients kept trying to reconnect (the user's settings reconnect on their own). The loop stopped cleanly ("the
  game is not responding"). After a login the client knows nothing inside bags, so the loop's start-up now opens
  both backpacks and Burgers' pouch before checking his runes. Totals at the stop: 5172 ingots, 4077 iron.
- **The reboot rolled the world back** to about 04:00 (Icepick came back at the forge holding the 57 ingots of the
  04:00 smelt, Burgers with none): the ore and handoffs after 04:00 never happened, so the totals were corrected to
  4898 ingots, 3854 iron, and the loop went back to block 54. After an outage, compare the packs with the log to
  find the save point before trusting the totals.
- **The shovel bag ran out** (Burgers "took 0 shovels from the bank" at 03:56): about 59 shovels in a night, roughly
  one per forge trip. Burgers had 15 spares and Icepick 2 at 04:21; the user needs to restock the bank bag.
- **Never over the weight limit** (the user, 2026-11-02 14:20). At 13:58 one more dig took Icepick to 404/390.
  Overloaded, every step costs him stamina (7/46 after a few tiles). The horse trick doesn't help, and the ride
  stalled 45 tiles short of the forge. The cause was the weight update arriving a moment after the dig's answer: the
  loop decided on the old weight and dug once more. Now:
  - After every "You dig some", the loop waits for the new weight.
  - He stops digging once the next dig could pass **393** (a dig usually adds 12, but allow 24 for two ore; the
    allowance grows if a bigger dig is ever seen). So forge trips start at about 370.
  - If his own stamina is under a quarter on a ride, he hides on McGee until he's fresh, then rides on. That got
    him from 404 to the forge in three legs.
  - The user's rule for when he does go over: **drop an ore on the ground** at his feet and leave it (or pick it up
    on coming back). The bridge can't put things on the ground yet: `/move?serial=&ground=1&amount=` with a
    `dropOnGround` rule (ore graphics) is written in AgentBridge.cs for the next build, not built or installed (the
    user can't install now). The loop's side (drop, note where, pick it up after the forge) is still to write.
- **The new shovel bag** (the user, 2026-11-02 13:55): the loop had remembered the old empty bag's serial, so
  `bags.shovels` was cleared from the state and the next bank trip found the new bag (Burgers took 20).
- **Clem is a partner of Burgers** (2026-11-02): the user trades with Burgers as Clem; Clem standing by Burgers set off
  the loiter guard and kept re-hiding him. Take Clem out of `rules-Burgers.json` if Clem is wanted as a test stranger.
- **Guild tags look like speech**: twice (Ironhold 05:39, Nickie Deuxyeux 09:22) the talk alarm went off on a
  player's guild tag ("[title, ABBR]"), which the server sends as ordinary speech. Ignoring that shape is offered to
  the user, not done.
- **Burgers stays hidden on an alarm** (the user, 2026-11-02 14:43): a Recall shows him, so when the alarm is his own
  and he's hidden he stays put and waits it out. He recalls away (to the Mining Start rune, then back) only if he's in
  plain sight when it starts, or is revealed while waiting (detect hidden, say). Icepick hides where he is meanwhile.
- **Guild tags are not speech** (the user, 2026-11-02): an alarm whose reason is only `said "[...]"` is cleared at
  once and not counted. Someone standing close still sets off the loiter alarm. The bridge source now ignores them
  too (for the next build).
- **Burgers waits 10 tiles from the forge** (the user, 2026-11-02: people use the forge), at **1140,1849** on the grass
  at the foot of the mountain (his rules area is now [1136, 1844, 1153, 1863]). The forge rune still lands him by the
  forge, so after every Recall back he walks there and hides. Icepick smelts at the forge, then rides up to
  1141,1850 for the trade and the gate; Burgers steps beside him to show himself and goes back to his spot after.
  Through the middle gate Icepick comes out at Burgers' spot and rides on to the forge.
- **Moongates aren't buildings** (2026-11-02 16:05): the obstacle learner counts any item named with "gate" (meant for
  fence gates), so Burgers' own moongates were recorded as building tiles: at his new spot that ruled out every tile
  next to him, he had nowhere to step out to for the trade, and Icepick's give failed ("no such character nearby").
  Moongates are skipped now, the five gate tiles were taken out of obstacles.json, and Burgers' one step aside only
  checks the map (`walkable(..., learned=False)`). Icepick kept the 56 ingots for the next handoff.
- **A stranger counts as gone after 30 seconds out of sight** (the user, 2026-11-02 18:05; it was 3 minutes), doubled
  for the same person again soon after. Jake recalled in and out near the route twice (17:02, 17:59); his spell words
  set off the talk alarm each time.
- **The second shovel bag held 20** and was empty by 20:15 (2026-11-02). Burgers then banked at every handoff for
  nothing. Now:
  - When the shovel bag turns up empty, Burgers looks through the bank for another bag with shovels in it.
  - If there's none, he notes the bank as out of shovels (`bank_out_of_shovels` in the state) and doesn't go back
    for shovels for 30 minutes.
  - While he has no spares and the bank isn't known to be empty, he skips gates to keep his mana for the bank trip.
    In the north half every gate takes all his mana, so the bank trip never came.
  - When Icepick runs out, the loop stops and says the bank is empty.
