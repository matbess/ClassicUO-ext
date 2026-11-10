# Mining with Icepick: the plan and the user's rules

Started 2026-11-01. This file records what the user asked for, what was tested and what was decided, so any session
can pick it up. The newest decisions are near the bottom; where an earlier note disagrees, the later one wins.

## Status (2026-11-05)

- **Running unattended, day and night**, `mine.py --passes 10`, since the night of 2026-11-01: 51,466 ingots
  (40,629 iron) by 2026-11-05 16:10. Installed client: build cuo-agent19, bridge 6 (from 2026-11-05 20:31).
- The pieces: the bridge, the rules files (`rules/rules-Icepick.json`, `rules/rules-Burgers.json`, copied into the
  client's `Agent/` folder), the route (`routes/route1.jsonl`, the recorded rides `routes/ride-*.jsonl`, the
  learned buildings `routes/obstacles.json`), the planner (`mining.py plan`: 92 ore blocks), the loop (`mine.py`)
  and `colours.py` (ingots by colour, from the log).
- The work folder `~/claude/uo-agent-work/mining` (not in git) holds `mine.log`, `incidents.jsonl` and
  `state.json`: `next` (the block to dig next), `totals` (with a `note` of every correction), `emptied` (blocks
  found empty, with when), `bags` (the bank's ingot, shovel and reagent bags), `shovel_bag` (the bag in Burgers'
  pack), `unreviewed` (run and hides), `fights` (creatures that hit Icepick), `town_guards` (guards found by their
  paperdolls), `bank_out_of_shovels`, `bank_shovels` and `bank_ingots` (the bank's shovels and ingots as counted on
  the last bank trip).
- Options: `--passes N`, `--from N --to M` (a stretch), `--bank` (a bank trip only), `--empty` (smelt and hand
  over only), `--incidents`, `--reviewed`, `--park`, `--stop`.
- Before starting: both characters logged in with the Agent bridge option ticked, Icepick near McGee or on him,
  Burgers by the forge with his four runes, or at the Ocllo bank (the start-up then finishes his bank trip).
- **cuo-agent19** (bridge 6) installed 2026-11-05 20:31: bridge 5's "left the area" only on leaving (below,
  2026-11-05 09:38) and bridge 6's menus, gumps and event log (SMITHING.md). cuo-agent18 was never installed.
- **Creatures** (2026-11-08, below): bridge 11 (cuo-agent28) says "Guards!" the moment Icepick or Burgers loses any
  hits (`"callGuards"` in both rules files); mine.py then steps Icepick 10 tiles off, hides him, and carries on once
  the creature is gone or after 30 s. cuo-agent28 installed 2026-11-08 (backup agent27).

## Running it from a Claude session

- **Start** it as a background task, with absolute paths: a background task may start in another folder (2026-11-05:
  `cd tools/uo-agent && python3 -I mine.py` looked for `mine.py` in the work folder and exited):
  `cd ~/claude/ClassicUO/tools/uo-agent; exec python3 -I ~/claude/ClassicUO/tools/uo-agent/mine.py --passes 10`.
  It carries on from `next` in the state.
- **Watch** the log with a Monitor (at most 30 minutes, so re-arm it at every expiry). Start each one from the
  time of the last event seen, so nothing logged while re-arming is lost (re-arming with `tail -n 0` missed a
  handoff on 2026-11-04 at 03:16). Fill in the last event's time and date (the older `$1 != date` form let lines
  from earlier days through after a long break):
  ```
  tail -n 40 -F ~/claude/uo-agent-work/mining/mine.log | awk '$1 > "YYYY-MM-DD" || ($1 == "YYYY-MM-DD" && $2 > "HH:MM:SS") { print; fflush() }' |
    grep -E --line-buffered "Reagents:|from the bank|takes the ingots|ingot bag|Gate|gate opened|McGee|retame|ALARM|alarm|STOPPED|PARKED|reagents low|left in the bank|none left|no shovels|Traceback|Error|done:|incident|run and hide|pass [0-9]+:|Icepick at|runes checked|not responding|left the area|inside the area|creature|noted:"
  ```
  Don't add a bare "shovel": every shovel that wears out logs a line.
- **What to tell the user** (they follow on the phone through Remote Control: plain messages, no push
  notifications):
  - every forge trip, in a few lines: the ingots handed over (and how many iron), the shovels given, the iron in
    the bank, the run and hides and the fights to review, all four of Burgers' reagents, and the shovels: Burgers' spares and the
    bank's (counted on his last bank trip; the handoff line has both from 2026-11-08);
  - the iron in the bank rather than the total ever mined (the user, 2026-11-08: "I'd rather know how many are in
    the bank than the total we've ever mined"). Burgers counts the uncoloured ingots in the bank's ingot bag on
    every bank trip, after putting his in (`Burgers emptied his pack into the ingot bag; the bank has N iron
    ingots`, kept as `bank_ingots` in `state.json`); the handoff line shows that count and the iron he's carrying
    to the bank next. `totals` is still kept in `state.json`, just not shown;
  - bank trips (the shovels and reagents taken), McGee (tired, stuck, gone wild, retamed), every alarm and incident,
    every creature that hits him or turns grey near him (`creature:` and `noted:` lines),
    `reagents low` (any of the four under 20), a new pass, stops, parks and reboots;
  - not worn-out shovels or a ride that replans and carries on.
- **What the user's words mean:**
  - "park it" (to play Burgers or Icepick, or for an install): `python3 -I mine.py --park` at once.
  - "I'm done with Burgers", "he's ready", "I restocked": check both statuses, then start the loop and the Monitor
    again. Bags they swapped in the bank are found on the next bank trip (by what's in them), and Burgers at the
    bank finishes his trip at the start; if they ask for a check, read the bank with `/contents`.
  - "I've reviewed it": `python3 -I mine.py --reviewed`.
  - The totals of each ore colour: `python3 -I colours.py` (estimates; see its docstring).
- **Out of shovels**, the loop parks both and stops. When the user restocks within 30 minutes of the bank being
  found empty, set `bank_out_of_shovels` to null in the state first, or Burgers won't go back for them until the
  30 minutes are up.
- **The nightly reboot** (about 04:15; the server rolls the world back to its last save, about 15 minutes before).
  The loop stops with "the game is not responding". Then:
  1. Wait until both bridges answer again (about 04:19; the clients log back in on their own).
  2. Anyone in sight is hidden at once (`uo --char Icepick skill 21`; a second try 10 s later if it fails).
     Icepick on foot gets on McGee first (`uo --char Icepick mount 0x00042FCB`).
  3. Don't open packs or bags by hand (it halted Icepick's bridge on 2026-11-04): the start-up does that. Check
     `halted` in both statuses, and `uo --char NAME resume` where it's set.
  4. Find the save point: the ingots Burgers holds match one handoff line in the log, the last one before the save
     (Icepick's ore and ingots should agree).
  5. Back up `state.json`, then take the later handoffs off `totals` (ingots and iron) and say so in `totals.note`;
     set `next` to the block Icepick was on at the save; drop the `emptied` entries dated after it. If a bank
     trip came after the save, set `bank_ingots` and `bank_shovels` back to the bank trip before it.
  6. Start the loop and the Monitor again, add the reboot to this file and its window to `ROLLED_BACK` in
     `colours.py`, and tell the user.

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
  that all four runes are still in his pack). A run that starts with him at the bank leaves his guard off until
  that trip brings him back (2026-11-04: turned on at the bank, it raised an alarm over Sharri there).
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

**Staff get the normal guard** (the user, 2026-11-04). Until then a staff alarm (GM chat, a GM body or robe, a
staff title in the name) made both characters stand still and the loop stop until the user answered; that was
taken out of the bridge (version 4, build cuo-agent17) and the loop, so a staff member near or talking is one more
stranger: get away, hide, wait until they've gone, carry on, and the incident goes on the review list.

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

**Only mining is paced** (the user, 2026-11-05): everything else, the bank included (mine.py's quick bank pacing) and
everything inside the tower or house, runs at full speed (1.1 s between requests, no breaks; root AGENTS.md).

The server has no moderation now, but the moderator might come back and enforce old rules without the user hearing
about it first. So nothing is ever done faster than a person might. The user first asked for 1-2 s between actions,
then found dismount / "all follow me" / dig / remount at about 1.8 s gaps (and the aim 0.1 s after the cursor) still
too fast. Now, in Icepick's and Burgers' rules:
- a random **2.5-4 s** between actions, and a **6-10 s** break after every 5;
- a random **0.7-1.5 s** between a target cursor appearing and the click (digging, smelting, Recall), from build
  cuo-agent10;
- walks wait their turn like any other action, and the next action waits a full gap after arriving (cuo-agent10;
  mining.pause() covers the build before it).
Johnny's sorting rules (rules.json) run at full speed since 2026-11-05. If the user says it's still too fast, slow the rules
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
  pearl, blood moss, mandrake root) or 3 (sulfurous ash) makes a bank trip a must. Not for a reagent the bank had
  none of on the last visit (`bank_short` in state.json; 2026-11-09, the user said go ahead): those trips only used up
  the last blood moss. Ordinary trips still look again; when the user restocks, set `bank_short` to [].
- **Run-and-hide incidents to review** (the user, 2026-11-02 00:56): every guard incident is kept in the state
  (`unreviewed`) until the user says they've reviewed them, and every handoff line ends "Run and hide: N to review".
  From 2026-11-09 fights (a creature hit Icepick) are counted apart, in `fights` ("Fights: N to review" after the run
  and hides; the user: "report how many fights you engage in along with the run & hides"); `--incidents` lists
  both and `--reviewed` clears both.
  `python3 mine.py --incidents` lists them (when, who, what, where); `--reviewed` (only when the user says so) sets
  the count back to 0. The full record stays in incidents.jsonl and the bridge's alarms.log; all logs are on the
  Mac (~/claude/uo-agent-work/mining), so a server reboot doesn't lose them.
- **Server lag** (2026-11-02 02:08): a dig's "Where do you wish to dig?" came 13 s late, so the bridge (which waits
  3 s) stopped on "no answer". The server had answered, so it was lag, not a dead server: the loop now cancels the
  cursor left behind, resumes and carries on when the answer turns up within half a minute of the stop, and stops
  and tells the user if that happens three times in 10 minutes.
- **Lag on a Recall** (2026-11-08 22:38): Burgers' Recall home from the bank got its "Select Marked item." 2 s after
  the bridge stopped, but under his own name rather than "System", so the lag check missed it and the loop stopped
  with Burgers at the bank and Icepick in sight at the forge. Icepick was hidden, Burgers' bridge resumed and the
  cursor cancelled, and the restart finished the bank trip. The lag check now takes an answer under the
  character's own name too (in use from the next start after commit "Mining: a late answer under the character's
  own name is lag too").
- **Server down** (2026-11-02 04:15): the server reset the clients' connection (RST after about 4 h 9 min); the
  clients kept trying to reconnect (the user's settings reconnect on their own). The loop stopped cleanly ("the
  game is not responding"). After a login the client knows nothing inside bags, so the loop's start-up now opens
  both backpacks and Burgers' pouch before checking his runes. Totals at the stop: 5172 ingots, 4077 iron.
- **The reboot rolled the world back** to about 04:00 (Icepick came back at the forge holding the 57 ingots of the
  04:00 smelt, Burgers with none): the ore and handoffs after 04:00 never happened, so the totals were corrected to
  4898 ingots, 3854 iron, and the loop went back to block 54. After an outage, compare the packs with the log to
  find the save point before trusting the totals.
- **Again 2026-11-04 04:15** (a nightly reboot, it seems): both clients back at 04:19, rolled back to about 04:00
  (Icepick at the forge with his ore half smelted, Burgers holding the 55 ingots of the 03:57:55 handoff). Icepick
  came back in sight and was hidden at once. Totals 29567 / 23357 corrected to 29301 / 23155, the blocks marked
  empty after 04:00 dropped from the state, and the loop went back to block 69. Opening Icepick's pack by hand
  30 s after the login got no answer and halted his bridge (the first restart stopped on it): leave the opening to
  the loop's start-up, and check `halted` in both statuses (then `uo resume`) before restarting.
- **And 2026-11-05 04:15** (so it is nightly, at about 04:15): back at 04:19, rolled back to about 03:59. Icepick
  came back on foot and in sight while digging: put on McGee (`uo mount`) and hidden at once (Hiding needed a
  second try). Burgers held exactly the last handoff before the save (54 ingots, 38 iron, 03:58:05), which dated
  it. Totals 44173 / 34898 corrected to 43907 / 34698, back to block 53.
- **And 2026-11-09 04:15**: back at 04:19, rolled back to about 04:00. Icepick came back mounted but in sight at
  1166,1805 with a full pack (379), riding to the forge, which only fits 03:59:45 to 04:00:09 in the log; hidden at
  once. The handoffs from 04:01:09 on (212 ingots, 166 iron) and the 04:05 bank trip never happened: totals 62382 /
  49250 corrected to 62170 / 49084, back to block 29, and `bank_ingots` / `bank_shovels` set back to the 03:41 count
  (6079 iron, 12700 in all; 36 shovels). With the bank counts in the state, a rolled-back bank trip has to be
  taken off them too (the next bank trip counts afresh anyway).
  The first restart (04:20) stopped: the server was still slow, and the name of a rune came as a Label 28 s
  after the bridge gave up, which the lag check didn't count. It now takes a late Label for the serial whose name
  was asked; the second restart, a minute later, went through.
- **Server down 2026-11-09 06:41** (not the nightly reboot): the server reset the connection after 2 h 22 min and
  refused new ones for about 4 minutes; the loop stopped with "the game is not responding". Back at 06:45 with no
  rollback: Icepick on foot and in sight where he had been digging (mounted and hidden at once, Hiding on the
  second try), Burgers with the shovels and the 39 iron of the last handoff. The loop picked up at block 36 with
  nothing to correct.
- **And 2026-11-10 04:15** (the nightly reboot): back at 04:19, rolled back to about 03:59:50. Burgers came back
  at the Ocllo bank with an empty pack (the 03:59:47 bank trip had been saved, so `bank_ingots` and
  `bank_shovels` stood); Icepick mounted but in sight at 1141,1850, just off the forge after the 03:59:02 handoff
  with 3 shovels and his 3 cure potions (hidden at once, first try). The handoffs from 04:02:44 on (270 ingots,
  231 iron) never happened: totals 80085 / 63238 corrected to 79815 / 63007, back to block 65.
- **A tile outside the area** (2026-11-05 09:38): on the long straight stretch to waypoint 31 (1101,1594 to
  1101,1649, along the area's west edge at x 1100) the client's path finder stepped Icepick to 1099,1649. The
  bridge stops every walk the moment it sees him outside the area, even one heading back in, so the replans and
  hops all failed and the loop stopped (he was left mounted but in sight; hidden by hand). The loop now steps him
  back onto a walkable tile inside, a tile at a time, whenever a ride stops with "left the area". **Bridge 5**
  (build cuo-agent18, the user asked for it the same day): "left the area" counts only when a walk or ride takes
  him from inside to outside; one that starts outside may take up to 4 steps outside on its way back in.
- **The user swaps whole bags in Burgers' bank** (2026-11-04: easier than emptying them; ingots, shovels or
  reagents). At each bank trip the loop drops a remembered bag that's gone, finds the new one by what's in it,
  labels it, and removes the labels of bags no longer in the bank.
- **Burgers' spare shovels are in a bag in his pack** (the user, 2026-11-04: they put them there from now on,
  not loose). The loop counts and hands out shovels loose or in any bag in his pack, puts the ones from the bank
  into that bag, and remembers the bag (`shovel_bag` in the state) for when it's empty.
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
    on coming back). The bridge can do it since cuo-agent16 (`/move?serial=&ground=1&amount=`, allowed only for
    the graphics in a `dropOnGround` rule), but Icepick's rules have no `dropOnGround` yet and the loop's side
    (drop, note where, pick it up after the forge) isn't written: the weight limit above has kept him under 393
    since, so it hasn't been needed.
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
  once and not counted. Someone standing close still sets off the loiter alarm. The bridge ignores them too, from
  build cuo-agent16.
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
- **Burgers carries 40 spare shovels** (the user, 2026-11-05 18:50, bringing 60 to the bank after the third bag
  ran out: "put 40 in his pack"; it was 20). Each bank trip tops him up to 40. A shovel weighs about 5 stones, so
  that's about 200 of his 390. The third bag gave 57 shovels from 14:43 to 18:49, about one every 4 minutes
  counting the first top-up.

## Creatures (the user, 2026-11-08)

At 17:10 something hit Icepick in town (100 to 96, then 90) while he went to fetch McGee at 1104,1589. A grizzly bear
and a water elemental were close by; the water elemental is the likely one (a caster: fight.py's CASTERS). It was the
first creature in a week of mining. The guard took it for a person: it rode him 68 tiles off, hid him and waited 30 s.
The user stopped the loop ("stop": `--stop`, Icepick then hidden by hand) and set the rules:

- **Watch his health all the time and say "Guards!" the moment he loses any hits.** The guards only come for a
  creature once it has hit someone ("They have to hit you first before the guards will attack them. So you have to
  wait until you actually get hit."), and then a guard kills it at once. So nothing is said before a hit: a creature
  turning grey (Criminal: it has gone after someone, COMBAT.md "Creatures") is only noted in the log (`noted:`,
  within 14 tiles of Icepick, once per creature), not acted on (the user chose "only react to hits").
- **Then only step away**: "He should only step away like 10 tiles and hide for 30 seconds or until the guards have
  killed it." Not the 50-tile getaway that's for people.

How it works:
- The bridge's guard checks his hits every 250 ms (hits lost set off the alarm before too). From bridge 11
  (cuo-agent28), with `"callGuards": "Guards!"` in the guard rules it says the words at once, as ordinary
  speech (how a player calls the guards), then again at most every 2 s while he keeps losing hits, whatever else
  is going on. Burgers' rules have it too. The alarm names the attacker: the nearest creature in sight that has
  turned Criminal (or Murderer, Enemy), else the nearest stranger within 12.
- mine.py (`creature_attack`): an alarm of Icepick's own that is hits lost, blamed on a creature or on nobody in sight,
  is a creature: he rides `CREATURE_FLEE` (10) tiles straight away from it, hides, and waits until it's gone from
  sight (killed) or `CREATURE_WAIT` (30) s have passed; then the alarms are cleared and he carries on with the block.
  A person who hits him still gets the 50-tile getaway and the wait until they've gone.
- Safety: below half his hits he stays hidden until he has half back before digging on, and a third creature attack
  within 10 minutes (`CREATURE_STRIKES`) leaves both hidden and stops the loop for the user (no guards there, or
  something the guards don't kill).
- **Tested for real at 17:30:58, the first run on cuo-agent28**: the same water elemental hit Icepick (100 to 93) at
  1101,1649. In the same instant he said "Guards!" and the guard James came, "You see James attacking a water
  elemental!", "Thou hast suffered thy punishment, scoundrel." He rode 9 tiles off and hid; the elemental was gone
  at the first look, and he carried on at 17:31:28 with 94/100.
- **Poison** (the user, 2026-11-09, after a snake bit Icepick at 23:08: "make sure you aren't poisoned, especially
  from snakes"; he wasn't). After every creature attack, and whenever the guard check sees it (bridge status
  `poisoned`), `check_poison` drinks a cure potion (orange, 0x0F07, allowed in his rules' `useFromBackpack`) if he
  carries one; with none he waits hidden for it to wear off. Still poisoned after `POISON_WAIT` (90) s, or under
  half his hits: both are parked and the loop stops for the user. The user puts cure potions on Burgers (2026-11-10:
  "yes, he should. I will put some on burgers"); at every handoff Burgers tops Icepick up to `CURES_WANTED` (3) in
  the trade, and the handoff line ends with both counts (`Cure potions: Icepick N, Burgers N`).
- **Town guards are not strangers** (the user, 2026-11-09: "You are running from the guard, Olinda is the guard who
  killed the snake"). The guard who came for the snake stood by Icepick, and the loiter alarm sent him on two
  50-tile getaways. Now, before a getaway from a person, `town_guard` asks for their paperdoll (bridge 12's
  `/paperdoll`; a single click shows only the name here): a title ending "guard" ("Olinda the guard") makes them a
  town guard, kept in state.json `town_guards` and added to both characters' rules `npcs` (`with_guards`, when the
  rules are written), so the bridges leave them alone; no incident, and he carries on. Every title asked is logged
  (`paperdoll of ...`). Olinda (0x00041A9D) was added by hand from the user's word; the title check itself is not
  yet seen working on a guard.
- Not used for mining: bridge 11 can also raise the alarm when a creature within `"creatures"` tiles turns grey, or
  for an `"avoid"` list of kinds. The user turned that down (an early getaway means it never hits him, so the guards
  never kill it and it keeps wandering about the route); both are left out of the rules.

## Off the gate toward the next spot (2026-11-08)

The user saw Icepick come out of the middle gate (1141,1666) and go straight back through it to the forge. It was
old: about one middle-gate trip in four since 2026-11-01 (30 of 111) ended "stopped at" a tile by the forge. He
always stepped one tile south-east off the gate, and a ride west from there went back over the gate tile (the
planner keeps its waypoints off an open gate, but the client's path finder rides between them). Now `off_the_gate`
walks him from the gate tile two tiles straight toward the next dig spot (west: 1139,1666; south: 1141,1668), so
the ride starts on the far side. The Mining Start gate keeps the old south-east step (to_start doesn't know the
next spot; no returns were seen there).
