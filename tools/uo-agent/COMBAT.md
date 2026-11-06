# Fighting with Clem: the user's rules, the front door, and what was learned

Started 2026-11-06. Like MINING.md and CARTO.md, this records what the user asked for, what was found and what was
decided, so any session can pick it up. Newer notes win where they disagree with older ones. The tools are
`door.py` (the front door) and `fight.py` (a fight); `fight_scenes.py` checks fight.py's decisions offline.

## Why (the user, 2026-11-06)

Clem has to visit vendors in town (selling world maps, buying blanks: CARTO.md). Recalling home lands him just
outside the tower's front door, and there are usually creatures standing around there, so he has to be able to
fight. Nothing goes to town until fighting works.

## How a bard-mage fights (the user's rules)

- **Never get hit.** He runs around; he never trades blows. Standing there doing nothing is *always* the wrong
  thing: when nothing better can be done, he at least runs away from all of them, **toward the tower**. Never end up
  far from it (a little further out is fine when needed; not 100 tiles away).
- **Stay back.** Creatures come for him once they see him and he gets close. He never walks up to one. To draw one,
  only as close as it can see him.
- **Provoke them onto each other** (Provocation, skill 22): use the skill, pick the instrument (only the first time
  after a login; the tambourine in his pack), then target the two creatures. Pair creatures of similar strength.
  Several can be set on one strong one, or all on each other, just to keep them off him.
  With one following him (e.g. a dire wolf), go only as close to another (e.g. an ogre) as provoking needs, provoke
  the follower onto it, then get back away until he's sure nothing is coming after him.
- **Casters first** (they hit from a distance); then the strong ones (water elemental, troll, dire wolf); weak ones
  like a mongbat last.
- **Uneven pairs:** when one is about to die, its opponent will turn on him; cast at the stronger one so it's low or
  dead before it's freed (fight 1: the user bolted the headless one while its mongbat was dying).
- **When one dies** its opponents turn on him: provoke them onto another creature. The last one alive: keep running
  and cast at it, or provoke it onto an animal or another creature (fight 1: a llama 15 tiles off).
- **Spells while they're busy** (the user's thresholds of the target's health): Energy Bolt while it has plenty;
  Lightning below 15%; Fireball below 5%. Energy Bolt costs much more mana but does much more damage. Watch how much
  each takes off (fights.jsonl records it).
- **Meditate** when mana is low and every creature is busy fighting.
- **Hurt:** run out of their range, then heal.
- **Paralysed:** use one of the 3 trapped pouches in his pack (a little damage, frees him); re-trap them after the
  fight (Magic Trap; not automated).
- **Tired horse** ("Your mount is very fatigued." / "Your mount is too fatigued to move."): get away from all
  creatures, then dismount, say "all follow me", mount again (MINING.md, "Tired mount"). Riding back and forth a lot
  tires it.
- **Fast:** plan ahead; no stopping to think mid-fight. So the strategy lives in fight.py, not in Claude's turns.
- **Before leaving town:** restock reagents at the restock chest (the user's ']' hotkey) and Recall home (F7). The
  hotkeys needn't be pressed: doing the same actions directly is fine.
- **Speed:** the server allows about one action a second (a skill, a spell, a double-click). Answering a target
  cursor isn't an action: it can go as fast as the prompt appears (the bridge's /target, /menu and /gump don't wait
  the gap).

## Creatures (per creature: the bridge can't tell red from grey)

The bridge reports nearly every creature with notoriety **Gray** (aggressive ones are sometimes **Criminal**, e.g.
troll, water elemental, mongbat, headless one, skeleton, dire wolf), never Murderer, so whether one is "red"
(comes for him) or "grey" (leaves him alone) is kept by name in fight.py. The user (2026-11-06):
- **Leave alone** (grey; only something to provoke a red one onto): panthers (unless they attack: they don't seem
  to), timber wolves, and animals (llama, sheep, hind, great hart, jack rabbit, ...). One that does attack (war mode,
  not provoked) counts as a threat after all.
- **Deal with:** dire wolves, ogres, trolls, water elementals, skeletons, headless ones, mongbats, ratmen (they get
  random names like Chichoki, Kicchiki, Weckaki: named creatures can be monsters, not pets).
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
  the house region, steps included. Not in his rules yet; `in` stops when any are within 3 tiles of the door.

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
  30, 32, 38, 42, the trapped pouches (useFromBackpack 0x0E79), "say": ["all follow me"], and "mounts" (still
  empty: his horse's serial only shows while he's off it; until then the horse trick can't remount him).

## What the recordings showed

Fight 1 (the user by hand, 13:09-13:13; `~/claude/uo-agent-work/combat/NOTES.md`, fight1*.jsonl): six creatures at
the door (dire wolf, water elemental, troll, skeleton, headless one, mongbat), all killed, 14 damage taken.
- Provoke: "What instrument shall you play?" (first use after login) -> tambourine -> "Whom do you wish to incite?"
  -> creature -> "'You play your music, inciting anger, and it begins to look furious. Whom do you wish it to
  attack?" -> creature -> "Your music succeeds, as you start a fight." + "*looks furious*" + "You see X attacking Y!".
  Targeting a creature at the instrument prompt: "That is too far away." Out of sight: "Target cannot be seen."
- **Skills share one cooldown of about 10 s** ("You must wait a few moments to use another skill." at 7.7-9.8 s,
  fine at 10.8 s), Meditation included.
- Casting: Energy Bolt's cursor 1.7 s after the words, Fireball's 0.8 s. **Casting freezes him**: a step then gets
  "You are frozen and cannot move." Mana: Energy Bolt 20, Paralyze 14, Fireball 9, Heal 4; about 1 a second back,
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

## fight.py as it stands (2026-11-06)

Each tick (a few a second) it reads his status, every creature within 18 tiles and the new messages, then:
1. Tired horse: away from everything first (unless too tired to move), then the trick.
2. Paralysed: a pouch.
3. A free creature within 3: run away from all of them, toward the tower, never past one within 12.
4. Hurt (below 60%): get clear, then Greater Heal; poisoned and clear: Cure.
5. One coming for him: when provoke is ready and both are within 8, provoke it onto the most similar creature
   (casters first), then back off; otherwise lead it to about 7 tiles from a partner, keeping away from it; else run.
6. Clear of the fighting (8) and of anything free (10): one spell at a time at the fighting (casters, then the
   stronger of an uneven pair, else the weakest), no moving while it goes off; meditate when mana is short.
7. Nothing coming or fighting: after a fight, home once it has been quiet 5 s; before one, draw the nearest creature
   from 12 tiles (left be after 20 s if it doesn't come); nothing in sight: ride to the lookout points (south first,
   then east) and look around 3 s at each.
Home: short hops to the door, then `door.go_in`. Time up (10 min), interrupted or an error: home all the same.

## Open items

- Put his horse's serial in "mounts" (rules-Clem.json and the live copy): dismount him once inside and read it from
  `uo nearby` (his own pet).
- "remove thyself" for creatures on the front steps: add to "say", and answer its cursor with the creature.
- The creature lists (passive, tiers, casters) grow with the user's word.
- Re-trapping pouches after a fight (Magic Trap, 13) and looting are left to the user.
- fight.py hasn't yet finished a real provoke-and-kill: the next tries will tell how its leading, spells and
  thresholds work out; fights.jsonl's casts give the damage per spell.
- Town trips (selling maps, CARTO.md) come after fighting works.
