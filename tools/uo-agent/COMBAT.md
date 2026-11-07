# Fighting with Clem: the user's rules, the front door, and what was learned

Started 2026-11-06. Like MINING.md and CARTO.md, this records what the user asked for, what was found and what was
decided, so any session can pick it up. Newer notes win where they disagree with older ones. The tools are
`restock.py` (reagents, before he leaves), `door.py` (the front door) and `fight.py` (a fight); `fight_scenes.py`
and `fight_sim.py` check fight.py's decisions offline.

## Why (the user, 2026-11-06)

Clem has to visit vendors in town (selling world maps, buying blanks: CARTO.md). Recalling home lands him just
outside the tower's front door, and there are usually creatures standing around there, so he has to be able to
fight. Nothing goes to town until fighting works.

## How a bard-mage fights (the user's rules)

- **#1 priority, always: keep distance between him and the creatures** (the user, 2026-11-06, after he was left
  standing next to a dire wolf: "That's the worst thing to do"). Anything free within 3 tiles: get away before
  anything else, the door steps, looting, healing and "remove thyself" included (the way in breaks off between steps
  when a creature comes near). **No spell with anything close**: it closes in during the words, hits him and ruins
  the spell; a full getaway first, then cast with every free creature 6+ tiles off.
- **Keep the front yard clear** (the user, 2026-11-06): don't leave creatures at the front door; lead them away from
  it and kill them there. Getting away prefers spots 10-25 tiles from the door (out of the yard, near the tower).
- **Drawing**: get a bit closer (4 tiles) and wait a bit longer (30 s) for it to attack.
- **Never get hit.** He runs around; he never trades blows. Standing there doing nothing is *always* the wrong
  thing: when nothing better can be done, he at least runs away from all of them, **toward the tower**. Never end up
  far from it (a little further out is fine when needed; not 100 tiles away).
- **Stay back.** Creatures come for him once they see him and he gets close. He never stands next to one.
- **Drawing a creature** (the user, 2026-11-06, showing it with an ogre): ride up to about **5 tiles** from it and
  wait for it to target him and come at him; then lead it off. Not from 12 tiles, and no wiggling back and forth
  (it tires the horse).
- **Ignore creatures trapped inside buildings** (the ogre at about 1733,1468 is shut inside the castle south-west of
  the tower): a wall is between them, so it never comes. One that doesn't come at him from 5 tiles is left be.
- **Provoke them onto each other** (Provocation, skill 22): use the skill, pick the instrument (only the first time
  after a login; the tambourine in his pack), then target the two creatures. Pair creatures of similar strength.
  Several can be set on one strong one, or all on each other, just to keep them off him.
  With one following him (e.g. a dire wolf), go only as close to another (e.g. an ogre) as provoking needs, provoke
  the follower onto it, then get back away until he's sure nothing is coming after him. **Bringing two together**
  (the user, 2026-11-06): stay far enough from both not to get hit, never right next to either; start trying to
  provoke before getting close to either; circle round them, about 3 tiles from any of them. fight.py circles the
  other one at about 5 tiles, always the same way round, every ride at least 3 from every creature and 5 from the
  follower (it closes in meanwhile), and provokes as soon as both are within 8 of him and within 9 of each other.
- **Casters first** (they hit from a distance); then the strong ones (water elemental, troll, dire wolf); weak ones
  like a mongbat last.
- **Uneven pairs:** when one is about to die, its opponent will turn on him; cast at the stronger one so it's low or
  dead before it's freed (fight 1: the user bolted the headless one while its mongbat was dying).
- **When one dies** its opponents turn on him: provoke them onto another creature. The last one alive: keep running
  and cast at it, or provoke it onto an animal or another creature (fight 1: a llama 15 tiles off).
- **A creature already fighting something else is the chance to attack it** (the user, 2026-11-06: he stood waiting
  for a dire wolf to come at him while it was fighting a bear; "when it's fighting something else is your chance to
  attack it and lower its HP"). fight.py counts one as busy, whoever started the fight, when it has been within a
  tile of another creature for 2 s (the wolf and the bear stood a tile apart, still, for 34 s) or is losing health
  he didn't take; a busy one isn't drawn or waited for: he bolts it from within spell range, keeping 4 tiles off.
- **Spells while they're busy** (the user's thresholds of the target's health): Energy Bolt while it has plenty;
  Lightning below 15%; Fireball below 5%. Energy Bolt costs much more mana but does much more damage. Watch how much
  each takes off (fights.jsonl records it).
- **Fighting one with spells** (when there's nothing to provoke it onto): don't go half way (the user,
  2026-11-06: "just try to kill it all the way quickly"). fight.py: the next spell as soon as the last has landed,
  until it's dead; between spells only a short hop when it's right on him. (Before, he got away and waited for it to
  be 10 tiles off each time: two bolts 24 s apart at a skeleton.)
- **Mana sparingly; provoke is the first line of defence** (the user, 2026-11-06, after he spent nearly all his mana
  killing one ettin: fine for one, but no mana left for the next). "It's ok to provoke 2 creatures and wait for them
  to do damage to each other for a while (while maybe you are meditating) before you use any mana." fight.py: at a
  pair fighting, spells only at a caster, at the stronger of an uneven pair before it's freed, or at one already
  down to 40% (CAST_WHEN); otherwise he meditates (mana not full) or waits. Killing with spells all the way is for
  a lone one with nothing to set it on.
- **Loot** the corpses if he's able to (the user, 2026-11-06; they took everything: a war hammer, a white potion,
  gold, with the client's grid loot). fight.py, once the fight is over and nothing is coming: every corpse that fell
  during the fight within 10 tiles, never a person's ("corpse of ..."): ride next to it, open it, move everything
  into his backpack.
- **Meditate** when mana is low and every creature is busy fighting.
- **Hurt:** run out of their range, then heal.
- **Paralysed:** use one of the 3 trapped pouches in his pack (a little damage, frees him); re-trap them after the
  fight (Magic Trap; not automated).
- **Tired horse** ("Your mount is very fatigued." / "Your mount is too fatigued to move."): get away from all
  creatures, then dismount, say "all follow me", mount again (MINING.md, "Tired mount"). Riding back and forth a lot
  tires it.
- **Fast:** plan ahead; no stopping to think mid-fight. So the strategy lives in fight.py, not in Claude's turns.
- **Before leaving the tower** (the user, 2026-11-06): always make sure he has enough reagents; if any is below 25,
  restock first. The user does it with Razor's restock-agent-1 (their macro 'restock-clem') at the wooden chest
  0x40746D31 in the ground floor stairs room (1752,1402,10): Razor asks "Target a container to restock from, or
  target yourself to use your bank box.", then moves each reagent from the chest into his reagent bag 0x40677564,
  one a second, and it's done at "Finished N queued actions in N seconds." (recorded in combat/restock1.jsonl). It
  tops them up to garlic, spider's silk, ginseng 35; mandrake root, nightshade, black pearl 45; sulfurous ash, blood
  moss 40. `restock.py` does the same through the bridge (onto his stacks, so they merge), and `door.py out` runs it
  first every time. The bag is opened before counting: once the client had lost two of its stacks (ash and moss
  didn't show, so the bag looked out of them).
- **Before leaving town:** restock reagents at the restock chest (the user's ']' hotkey) and Recall home (F7). The
  hotkeys needn't be pressed: doing the same actions directly is fine.
- **Speed:** the server allows about one action a second (a skill, a spell, a double-click). Answering a target
  cursor isn't an action: it can go as fast as the prompt appears (the bridge's /target, /menu and /gump don't wait
  the gap).

## Creatures

**A creature coming at him turns Criminal** (the user, 2026-11-06: "I can see the creature turn completely grey
when they target me, that means they're going to come at me. And they stay grey"). Clem's client shows notoriety
Criminal in a grey (criminal_hue 946), other than the colour of the ordinary attackable creatures (notoriety Gray).
The gargoyle that day: Gray at 18 tiles, Criminal at 14 (16:01:27), then straight at him, 14 to 5 tiles in 7 s;
**war mode never came on**, so it tells nothing. The earlier recordings agree: the ones that fought him (troll,
water elemental, mongbat, headless one, skeleton, dire wolf, the ratman Chichoki) were Criminal at times; the
trapped ogre and the panthers never. fight.py: coming = Criminal.

Which creatures to bother with at all is kept by name in fight.py (the bridge shows them all Gray until they turn).
The user (2026-11-06):
- **Leave alone** (grey; only something to provoke a red one onto): panthers (unless they attack: they don't seem
  to), timber wolves, and animals (llama, sheep, hind, great hart, jack rabbit, ...). One that does attack (war mode,
  not provoked) counts as a threat after all.
- **Deal with:** dire wolves, ogres, trolls, water elementals, skeletons, headless ones, mongbats, ratmen (they get
  random names like Chichoki, Kicchiki, Weckaki: named creatures can be monsters, not pets).
- **Trapped inside buildings: ignore** (the ogre and a gargoyle inside the castle south-west of the tower, about
  1733-1745, 1467-1483: a wall is between them). One that doesn't turn on him within 15 s of his being 5 tiles off
  is left be.
- Strength tiers for pairing (fight.py WEAK / STRONG; anything else middling) and casters (CASTERS) are first guesses
  from T2A: the user corrects them as they go.

## The front door

**It must always stay locked and closed** (the user, 2026-11-06). The doors: 0x408AEA54 (west half, the one used;
shut at 1756,1414, open at 1755,1415) and 0x408AEA55 (east half, 1757,1414). The key ring 0x4040A302 is locked down
outside at 1758,1415,22; it reaches the door from outside (1756,1416) and the doorway (1756,1414), not from inside
(1756,1413: "I can't reach that."). It turns the lock either way: "You unlock it." / "You lock it." (said by the
door, not the server).

- **Out** (`door.py out`): no key. From inside the locked door opens for him ("That is locked, but is usable from
  the inside."): open it, step out to 1756,1416, close it. Then **check**: from right in front (1756,1415) try to get
  back in; it must say "That is locked." and stay shut. Only if it opens (someone forgot to lock it last time) does
  the key come out: lock it, close it. The user checks by walking into the door; his client then sends "open door"
  (auto_open_doors), the same as using it, and its path walker treats a shut door as a wall (smooth_doors off), so
  door.py uses the door instead.
- **In** (`door.py in`, also fight.py's way home): from 1756,1416 unlock with the key, open, step into the doorway
  (1756,1414), lock with the key, step in (1756,1413), close.
- **Creatures on the front steps:** the house command "remove thyself" and a click on the creature ejects it from
  the house region, steps included (in his rules' "say"; fight.py uses it on one within 3 of the door before going
  in); `door.py in` stops when any are within 3 tiles of the door.

## Safety rules (the user, 2026-11-06)

- **The user can take over at any time.** With `"handOver": true` in his rules, any command the user gives Clem
  themselves (a step, a spell, a skill, a door, a double-click, a target, war mode, an attack; not lifts and drops,
  which Razor's scavenger does, single clicks or double-clicks on corpses) makes the bridge refuse every action until
  /resume. **Only the user hands him back**: door.py and fight.py refuse while he's taken over and need `--resume`,
  passed only when the user says so ("try it again").
- **Never stop watching him while he's outside** (unless the user is controlling him): keep a monitor on the run and
  on his health and the nearest creatures (`~/claude/uo-agent-work/combat/watch.py` snapshots).
- **Always park him back inside** with the door locked: never leave him outside the front door, more creatures come
  along. fight.py only ends by going home (or the user taking over).
- **Never just stop a fight**: an error or a vanished creature mustn't end the script with him standing there; it
  carries on and goes home.
- A halted bridge (423 "stopped because the server went quiet") is a safety stop: Claude Code's permission check
  may refuse a `uo resume` for it; tell the user, who can run it (`! … uo.py --char Clem resume`).

## Bridge 7 (builds cuo-agent20-22; installed cuo-agent22, 2026-11-06 23:27)

- `/nearby`: each creature's `hits`/`hitsMax` (scaled by the server: out of 25 here; the share is what counts),
  `warMode`, `paralyzed`, `poisoned`. `/status`: `paralyzed`, `poisoned`, `takenOver`.
- Rules `"fight": true`: `/target` and `/cast` may aim at creatures anybody may attack (Gray, Criminal, Enemy,
  Murderer), never a person or a pet, within 12 tiles, and `/cast` at the character himself. A fight's aim never
  halts the bridge.
- `/skill?id=&cursor=1` leaves a skill's cursor up for `/target` (Provocation: instrument, then two creatures).
- `/cast?spell=&target=CREATURE|SELF` aims the moment the cursor shows and comes back (`aimed`, `hits`, `mana`).
- `/walk?run=1` runs; `wait=0` (fight rules only) comes back at once, so the next walk can turn him.
- Rules `"doors"` and `"keys"`: `/use` opens or closes a door (waits for it to move) or uses a key ring where it
  hangs; `/target` aims the key at the door. A message from what was aimed at counts as the answer (cuo-agent22;
  before it, "You unlock it." from the door looked like no answer and halted the bridge with Clem outside and the
  door unlocked, 2026-11-06 15:21).
- Rules `"handOver": true`: the takeover above.
- Clem's rules (`rules/rules-Clem.json`): the tower areas plus "outside" (x 1715-1810, y 1414-1485), fight,
  handOver, the doors and key, skills 12 (Cartography), 22 (Provocation), 46 (Meditation), spells 4, 11, 18, 29,
  30, 32, 38, 42, the trapped pouches (useFromBackpack 0x0E79), "say": ["all follow me"], and "mounts": his
  horse, "a horse" 0x00043254 (his own pet: never a target).

## What the recordings showed

Fight 1 (the user by hand, 13:09-13:13; `~/claude/uo-agent-work/combat/NOTES.md`, fight1*.jsonl): six creatures at
the door (dire wolf, water elemental, troll, skeleton, headless one, mongbat), all killed, 14 damage taken.
- Provoke: "What instrument shall you play?" (first use after login) -> tambourine -> "Whom do you wish to incite?"
  -> creature -> "'You play your music, inciting anger, and it begins to look furious. Whom do you wish it to
  attack?" -> creature -> "Your music succeeds, as you start a fight." + "*looks furious*" + "You see X attacking Y!".
  Targeting a creature at the instrument prompt: "That is too far away." Out of sight: "Target cannot be seen."
  **The two must be close to each other**: "The creatures you are trying to provoke are too far away from each other
  for your music to have an effect." (an orc 15 tiles from a panther, 2026-11-06). So he leads the follower right
  past the other one first (the user: "You have to lead 2 creatures to be close enough together to provoke them")."
- **Skills share one cooldown of about 10 s** ("You must wait a few moments to use another skill." at 7.7-9.8 s,
  fine at 10.8 s), Meditation included.
- **Spell range is about 10 tiles**: "That is too far away." at 11 (Energy Bolt, 2026-11-06).
- **Provoking worked with the two 8 tiles apart** (a dire wolf onto a grizzly bear, 2026-11-06 16:31).
- Casting: Energy Bolt's cursor 1.7 s after the words, Fireball's 0.8 s. **Casting freezes him**: a step then gets
  "You are frozen and cannot move." That includes the rest of a ride still under way when the words are said: the
  bridge's /cast then comes back on that message before the cursor, the cursor goes unanswered and the next cast
  gets "You must wait for that spell to have an effect." (2026-11-06 16:13). So: only cast standing still. Hit while
  casting: "Your concentration is disturbed, thus ruining thy spell." Mana: Energy Bolt 20, Paralyze 14, Fireball 9, Heal 4; about 1 a second back,
  2 a second meditating ("You enter a meditative trance." ... "You are at peace.").
- Reagents are in bag 0x40677564 (Razor's restock and scavenger hot bag). After a login the client knows nothing in
  bags: open it once; after that the counts stay current while it's closed (checked). Black pearls run out first
  (Recall, Fireball, Energy Bolt).
- Razor's scavenger loots into that bag by itself (its pick-ups take action slots); the user loots corpses with grid
  loot.

The scripted tries (fight.log, fights.jsonl, fight2-4*.jsonl), and what each changed:
- **14:38**: rode 17 tiles straight into a pack of four ratmen and stood still trying to provoke one it couldn't see;
  Claude stopped it there (misreading ratmen names as pets), and the restart cleared the user's takeover. He went to
  29 health. -> keep away from everything, watch continuously, never resume a takeover, never just stop.
- **15:21**: the yard was empty; the bridge halted on the key's answer with the door unlocked. -> cuo-agent22.
- **15:33**: provoked a cougar onto an ogre, cast back to back (moving while casting cut the bridge's wait for the
  cursor short), crashed when the cougar vanished, couldn't path home from 1810,1415 and exited next to the ogre and
  a dire wolf; the user saved him at 37 health. -> the rewrite below.
- **15:44**: went back and forth between two panthers 14 tiles either side (drawing whichever was nearer), and tired
  the horse out. -> one creature drawn at a time, fewer walks, the horse trick, panthers left alone.
- **16:50** (cuo-agent23): a dire wolf by the tower never turned on him in 15 s, so it was left be (and wrongly
  written into trapped.json for good); nothing else anywhere, so home; the wolf was at the front door, he went back
  and forth trying to get in, it turned on him there, and being "left be" it was also left out of the "anything near
  him?" check, so at 54 health he cast Greater Heal with it next to him (frozen) and went to 33; the user took over.
  -> every free creature counts as near, whatever; one that didn't come is left be for that run only (trapped.json
  only for ones behind a wall, by hand); a creature within 3 of the door gets the house command "remove thyself"
  (in his rules' "say") before he goes for the door, and he never goes for the door with one there.
- **16:42**: drew an ettin (it came at him: Criminal at 5 tiles) and, with nothing to set it on, killed it with
  spells all the way: five Energy Bolts in 12 s (25 -> 21 -> 16 -> 9 -> 4 -> dead), one hit taken (84). Then the
  client opened the ettin's corpse by itself (auto_open_corpses, range 2) and the bridge took that double-click for
  the user taking over. -> bridge (cuo-agent23): a double-click on a corpse the client opened itself
  (PlayerMobile.AutoOpenedCorpses) never counts as the user.
- **16:37**: the best run so far. Drew the castle ogre once more (-> trapped.json: never drawn again), then a grizzly
  bear (never came); a dire wolf came and, with the bear wrongly left out as a partner (it had "never come"), he
  killed it with spells all the way: Energy Bolt, Energy Bolt, Lightning in 7 s, no damage taken. Then he drew an
  ettin and provoked it onto a panther ("You see a panther attacking an ettin!") and bolted it while it was busy
  (the user: "when it's fighting something else is your chance to attack it and lower its HP") - and Claude, going
  by alerts that arrived late, stopped the run there and took him home. door.py in went straight in. -> creatures
  that just don't attack stay partners (only ones behind a wall are left out); a spell kill counts as a fight (home
  afterwards); check the latest state before stopping a run.
- **16:31**: the restock check passed (35-45 each); drew the castle ogre again (it never came: left be after 15 s;
  trapped ones aren't remembered between runs yet), then a grizzly bear; a dire wolf turned Criminal 13-17 tiles off
  and he circled round the bear though nothing was attacking him yet (the user: "Stop running around in a circle
  when nothing is even attacking you ... wasting stamina"); provoked the dire wolf onto the bear (about 8 apart:
  worked); then Energy Bolt after Energy Bolt from 11 tiles: "That is too far away." (spell range is about 10; the
  user: "get closer to cast if it says 'that is too far away'"). Claude stopped it and brought him home; going in,
  the step into the doorway caught diagonally on the frame. -> circling only for a follower within 8; spells only
  within 10, riding to 8 first (and after "too far away"); keep 6 from fights; door.py in steps straight north via
  1756,1415.
- **16:23**: a skeleton was Criminal by the door as he came out; he got away from it, no wiggling, and bolted it
  twice standing still (25 -> 12) but 24 s apart, and it reached him in between. Black pearls ran down to 2 (Razor:
  "Warning: Black Pearl amount is now 3!") and the reagent bag had no sulfurous ash or blood moss left (no Lightning,
  no Recall). The user took over. -> killing all the way; spells chosen by the reagents he has (REAGENTS; the bag
  read every 3 s); a fight out of spell range: ride back to 10 tiles to cast.
- **16:13**: drew an orc (Ulmragha) from 5 tiles, standing still: it turned Criminal and came, good. The provoke onto
  a panther 15 tiles from it failed ("too far away from each other"), the word "far" dropped the panther as a partner,
  so he cast at the orc on the move (ruined, frozen, a lost cursor); the user took over at 84 health. -> pairs within
  7 of each other, lead the follower past the partner, cast only standing still, a late cursor still aimed.
- **16:06**: drew a gargoyle (it turned Criminal from far off), tried to set it on the ogre shut in the castle
  ("Target cannot be seen."), then wiggled between leading toward the ogre and keeping away from the gargoyle; the
  user said stop, Claude stopped the script and sent him toward the tower, the gargoyle caught him (down to 46)
  and the user took over. -> the Mover (one spot at a time), casters drawn from 11 and kept off, out-of-sight
  creatures left out, a lone pursuer cast at from 8 tiles, fight_sim.py.
- **15:58**: drew the ogre from 12 tiles; it wandered a tile nearer, which counted as "coming", so he tried to lead
  it to a panther 4 tiles from him and wiggled between two tiles. The ogre was shut inside the castle. The user then
  showed how: ride to about 5 tiles and wait for it to target him (a gargoyle there turned Criminal and came). ->
  coming = Criminal; draw from 5 tiles, left be after 15 s; a picked spot is kept (no re-picking every moment).

## fight.py as it stands (2026-11-06, evening)

**Moving (the user: "Stop wiggling!!"; it tires the horse).** With nothing coming at him there's no reason to go
back and forth or circle at all (the user, 2026-11-06: "sometimes you have to go back if a mob is actually coming at
you. You DONT need to go back when no mobs are even coming at you"): then no ride may turn back the way the last one
went within 5 s (NO_TURN_BACK); with something coming at him, any way he needs. Every ride is logged with its
reason in fight.log ("ride X -> Y (why)"). After a provoke he steps back only out of 6 tiles, staying within spell
range, so he doesn't ride away and back in to cast. Standing still is the default. He moves only for a
reason (drawing a creature, getting away from one, getting a partner into provoke range), and then rides straight to
one spot, picked once and kept until he's there (the Mover); a getaway is ridden to the end. The old way picked the
best spot afresh several times a second, and as creatures moved the best spot flipped: that was the wiggling, twice.

Each tick (a few a second) it reads his status, every creature within 18 tiles and the new messages, then:
1. Tired horse: away from everything first (unless too tired to move), then the trick. Paralysed: a pouch.
2. A free creature within 3: get away, away from all of them, toward the tower, never past one within 12.
3. Hurt (below 60%): get clear, then Greater Heal; poisoned and clear: Cure.
4. One coming at him (turned Criminal; casters first): provoke it onto something as soon as both are within 8 (the
   most similar creature; never one out of sight or left be); with the partner further off, ride to about 7 tiles
   from it on his side (never toward the follower); closer than 5 (casters 7): get away, toward a partner if any;
   nothing anywhere to set it on: cast at it once a getaway has left it 8 tiles behind; otherwise stand still and
   let it come.
5. Keep 8 from creatures fighting each other; with nothing loose within 10: one spell at a time at the fighting
   (casters, then the stronger of an uneven pair, else the weakest), no moving while it goes off; meditate when
   mana is short.
6. Nothing coming or fighting: after a fight, home once it has been quiet 5 s; before one, draw the nearest creature:
   ride straight to 5 tiles from it (casters 11: they notice him from far off), stand still and wait for it to turn
   Criminal (left be after 15 s); nothing in sight: ride to the lookout points (south first, then east) and look
   around 3 s at each.
"Target cannot be seen." leaves that creature out for a minute (the ogre shut in the castle). Home: hops of 8 to the
door (each kept until reached), then `door.go_in`. Time up (10 min), interrupted or an error: home all the same.

`fight_scenes.py` checks single decisions; `fight_sim.py` runs them over time in a made-up world (Clem riding to his
spot, creatures coming once they've turned) and counts his walks and reversals: run both after changing fight.py.

## Open items

- "remove thyself" for creatures on the front steps: add to "say", and answer its cursor with the creature.
- The creature lists (passive, tiers, casters) grow with the user's word.
- Re-trapping pouches after a fight (Magic Trap, 13) and looting are left to the user.
- fight.py hasn't yet finished a real provoke-and-kill: the next tries will tell how its leading, spells and
  thresholds work out; fights.jsonl's casts give the damage per spell.
- Town trips (selling maps, CARTO.md) come after fighting works.
