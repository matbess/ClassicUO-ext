# Mining with Icepick: the plan and the user's rules

Started 2026-11-01. This is the next project after sorting (see AGENTS.md). Nothing here is built yet; this file
records what the user asked for so any session can pick it up.

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
- **The bank** (the user, 2026-11-01): Burgers' bank box holds a bag with 59 shovels (take shovels from it) and a bag
  for the ingots (put ingots into it). Serials still to be read on the next bank visit.
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
   stealing. Starting numbers: within 3 tiles for more than 10 seconds.
3. **Missing rune.** Either of Burgers' runes disappears from his backpack: someone stole it.
4. **Attack.** Anyone attacks either character. Also a trade window opened by anyone but the partner.

**What to do (the user, 2026-11-01): get away and hide, don't log out.** Logging out outside an inn leaves the
character standing in the world (tested 19:38: the guard's logout worked, Clem's "hi" logged both out at once, but
that's no protection). Instead:
- Remember where he was, run away from the person (staying inside the guarded area, i.e. the bridge's corridor),
  and when about 30 tiles away, hide. Don't log out.
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

## What has to be built

- Bridge: rules per character (Icepick: the mountain range and the forge; Burgers: the forge spot and the bank),
  mining (use the pickaxe on a rock or mountain tile), smelting (use ore on the forge), trade (drop on a character,
  accept), casting Recall on a rune, saying only "bank", the safety watcher with a shared alarm file so both
  clients log out together, and logging out.
- Tools: read the map files to list every mineable tile in the area; the mining loop script.
- Installing a new client build needs all the user's clients closed: ask first.

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
