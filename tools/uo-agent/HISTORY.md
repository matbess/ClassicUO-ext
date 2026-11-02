# History: working notes, 2026-10-31 to 2026-11-01

These are Claude's working notes from the sessions that built the agent bridge and sorted the first batches,
copied here from Claude's memory so nothing lives only on one machine. They're a log, not instructions:
**`AGENTS.md` and `skills/uo-sort/SKILL.md` are the current truth wherever they differ.** In particular, notes
before 2026-11-01 14:40 count chest rows from the bottom ("col 6 3rd" meant 2nd from the top), several chests and
crates have changed purpose since (see AGENTS.md), and the keep rules changed on 2026-11-01 afternoon.

## The agent bridge and the sorting

The procedure is in the user-level skill ~/.claude/skills/uo-sort/SKILL.md (written 2026-11-01). Keep that skill in step with decisions recorded here. The user wants Claude to control a character that identifies magic gear and sorts it into house chests.

Planned shape:
- A local-only bridge inside ClassicUO, off by default. It runs queued commands on the game thread: list a container, get a name, Item ID plus target, move an item to a container at a chosen x/y, walk with Pathfinder.WalkTo, read the journal, and label a container by target cursor.
- An MCP server wrapping the bridge for Claude Code.
- A fast client-side "ID and sort" routine may come later.

Labels for chests and bags live in a file on the Mac. The game can't name chests, so labelling is done by click-to-target, possibly through a `-chest <label>` client command.

Requirements gathered:
- Bags inside chests.
- Per-category layout: potions piled at one spot; weapons tiled in a grid so each is visible. Use ContainerManager bounds and art sizes.
- The chests are locked down but not secured: a 125-item limit and no weight limit. Nested bag contents count toward the 125 (confirmed by the user).
- The user can put the character in the room with the chests. Locate chests by the coordinates the client already knows.
- One other player shares the world and cooperates with the user. They may be in the house and may move items in the chests. Leave other characters alone and re-check chest contents before each batch of drops.
- Chest layout: bags sit inside the chests, and below each bag (outside it) lies one marker item showing the bag's category, such as jewellery, leather, chain, plate or axes. Pair each marker with the bag above it by x position in the chest gump.
- Room: one room of the stone house has 24 chests on its wall, 6 columns wide and 4 high (stacked, so same x/y and different z). The bridge works by item ID, so stacking doesn't matter; chests can be named by column and height instead of clicking. Reach is 2 tiles, so two standing spots cover all 6 columns. The house's other room has rows of bags on the floor; their purpose is unknown, so ask before touching them.
- House coordinates (map 0): the chest wall is at x 1758-1763, y 1402, z 26/30/34/38 (bottom to top) on the z=26 floor. The house also has floors at z=6 and z=46+, so filter by floor. The green floor squares are cut cloth, hue 68. The other room (bags on the floor) is at x 1751-1756.
- Crates: 0x408AD7D5 (1763,1404, nearer the chests) is the empty ID wand/staff trash; 0x408AE270 (1763,1405) holds new backpacks. Labels are kept in ~/claude/uo-agent/labels.json (`uo label`).
- The server has a 1000 ms delay between actions ("You must wait to perform another action."). The bridge must space actions at least 1 s apart and retry on that message.
- Wall plan decisions (2026-10-31): bags by item type, with markers. No bone armour chest; the user doesn't keep bone. Helmets go with their material (plate helms in plate, coif in chain, cap in leather), not a helmets chest. Items in a bag may overlap a bit, as long as each stays visible.
- Overflow policy: when a chest is full, move its least valuable items out into overflow and tell the user so they can free up room. Potions: no potions chest. Instead there's one crate per potion kind along a wall (7 kinds by bottle colour: heal, cure, refresh, agility, strength, poison, explosion; strengths kept in separate piles inside each crate). Night Sight potions aren't kept; the user has permanent night sight. Potion crates (2026-10-31, labelled in labels.json): a stack of 6 at 1758,1404 (z 26/29/32/35/38/41 = heal, cure, refresh, agility, strength, poison) and one at 1758,1405,26 (explosion). Crates stack at most 6 high, and the user is getting more. Empty bottles, the blank scroll and cut leather and cloth go in the supplies chest. Column 5, 3rd from top (0x408FF84A, formerly spare C) became the gold chest on 2026-11-01: one merged pile, up to 60,000 per pile. Overflow crates are worked out as things fill up.
- Trash crates go along the room's short wall, for things the user doesn't keep: Night Sight potions, bone armour, and possibly plain gear.
- Incoming loot arrives in bags on the floor of the room. When a bag is emptied, it goes into the "new backpacks" crate (0x408AE270) as stock. Anything on this room's floor is incoming (to ID or just to sort): bags and loose items, except the crates, the wall chests, labelled containers and the cut cloth. The bridge deliberately has no drop-to-floor action (decided 2026-10-31): the user places queue items, overflow goes to crates, and re-sorting goes chest to chest using the backpack or a spare chest for staging. Still to add at the next rebuild: art sizes (Arts.GetRealArtBounds) and container gump bounds (ContainerManager.Get(gump).Bounds) for chest layouts. The user and co-player agreed not to set other bags down here. Limit this to the room's floor: about x 1757-1763, y 1402-1412, z near 26, because there is a floor above (items at z 46+) and below (z 6) with other bags. Confirm the bounds when the first loot bag is placed. Ignore everything outside the room (lots of bags there) and the cut cloth on the floor, which is decoration (the green squares, hue 68, plus hue 32 pieces).
- The co-player is the user's brother. Every character pauses the agent, including the user's own (Clem and others), so ignorePeople stays empty. When paused, run `uo waitclear` in the background (checks every 60 s) and resume when it exits. Only wait like this while sorting is unfinished. When everything is sorted, stop completely: no loops or background checks. The user comes back and says when there is more to sort.
- Sorting bags can be backpacks, bags or pouches; the user will drop any of them in the "new backpacks" crate. Rule: if a bag in that crate contains anything other than empty bags, move the bag whole to the "needs your decision" chest (0x409020EB, col 6 3rd) and tell the user. Never use it as a sorting bag.
- Wall chests are labelled with the plan's names in labels.json ("chest: <name> (col N row)"). Survey 2026-10-31: almost all empty. Exceptions: jewellery chest (backpack hue 154 and Recall scrolls); magic clothing chest (backpack hue 33 and blood moss); shields chest (red potion and a pouch); spare B (lockpicks x1964); and chain chest 0x408FF16B, which is the user's sample layout. That sample has 3 pouches in the top row at gump x 18/49/81, y ~108, with markers below at y ~132: bead necklace (jewellery), leather skirt (leather), chainmail coif (chain). That sample was temporary. Bags can sit closer together than in the sample, but must not overlap by default. Overlap only when the chest runs out of room, and even then each bag and its marker must stay visible and clickable. Markers must be identified items of the bag's kind, for example the first item of that kind found while sorting. The user's old sample pouches (with markers back inside) are now queue items. Lay out each slot as a bag plus its marker underneath. Size the slot from both items' art: width is the wider of the two, and height is the bag plus the marker. Long markers such as polearms, bows and staves need wider or taller slots. The bridge will need to report art sizes for this.
- Off limits: chest 0x40902338 (top of the right-hand column, 1763,1402,z38) is the co-player's personal chest until they move it. Never take from or drop into it. The other three chests in that column were empty on 2026-10-31.
- Scrolls: one chest holds 8 bags, one per spell circle. A scroll's circle comes from its graphic (spell scrolls 0x1F2D-0x1F6C in spell order, 8 per circle), so scrolls need no ID. They stack.
- The agent character is "Here's Johnny" for now. It must not be hardcoded: the bridge is enabled per character through the profile option.
- User's rule: pause sorting while any other player character is in the room, and resume once it's been empty for a short while. Enforce it in the bridge before every move. Finish or put back a held item before pausing.

Identification uses ID wands and ID staves with charges, not the skill. Facts confirmed 2026-11-01:
- Unidentified items single-click as "magic X". An ID wand can identify itself.
- Identified names look like "a wand of identification (35 charges)", "a gnarled staff of identification (75 charges)", "an accurate black staff of ruin", "a heavy crossbow of burning and ruin (18 charges)", "a wand of healing (14 charges)", "necklace of clumsiness (3 charges)", "boots of night eyes (8 charges)". Accuracy comes as an adjective and damage as "of <level>".
- The ID supply is pouch 0x4049D6B8 (labelled) in the supplies chest at 18,105. It started with 4 wands and 4 gnarled staves, 605 charges. Johnny holds wand 0x4059EB24.
- The wooden chest gump (0x49) item area is x 18-162, y 105-178. These probably have to be equipped to use.
- A labelled bag in the chests stores spare wands and staves.
- Empty ones go into a labelled bag on the floor, which the user empties later.
- If no spare is left, pause and check the storage bag again every minute.

The sorting rules will be worked out together once the bridge can see the room and actually identify and move items.

Step 1 (read-only bridge) built and installed 2026-10-31 (previous frame build backed up in ~/Games/backups/classicuo-1.1.0.347-buffframe/); not committed yet. Patch: ~/Games/patches/classicuo-agent-bridge-step1.diff.
- Game/Managers/AgentBridge.cs, profile key agent_bridge, on the Options > Experimental page.
- Listens on 127.0.0.1:7780-7789 with a bearer token. It writes C:\ClassicUO\Agent\<character>.json and refuses requests carrying Origin or Sec-Fetch headers.
- Endpoints: GET /status, /nearby, /item, /contents, /messages; POST /open (containers only, not corpses) and /name (single click).
- Terminal helper: ~/claude/uo-agent/uo (status, nearby, item, contents, open, name, messages; --char, --json).
- Build: ~/claude/builds/cuo-agent1.

Step 2 built and installed 2026-10-31 (~/claude/builds/cuo-agent2; step-1 build backed up in ~/Games/backups/classicuo-1.1.0.347-agent1/). Tested in game 2026-10-31: walk, open/close of the 7 potion crates (all empty), moving the hatchet to the backpack and equipping it again, and refusals for cloth, the off-limits chest, items outside the area and walking outside it. Wand use is not yet tested (needs ID wands). Not committed.
- New POST endpoints: /walk (x, y or to=serial, distance; Pathfinder.WalkTo), /move (lift, then drop into a container or onto a same-kind stack; x/y default 0xFFFF), /equip, /use (only an item in the hands; double-click, then target), /close, /cancel. New GET: /rules.
- Pacing: 1100 ms between uses and lifts, with one retry on "You must wait".
- Every action is checked against C:\ClassicUO\Agent\rules.json (JSON with comments): map 0, area [1758,1402,1763,1412], z [26,45], offLimits, neverTouch [0x1766,0x1767], ignorePeople. Actions refuse with 409 "paused" while any other human or ghost is in the area.
- The uo helper resolves labels in place of serials (`uo move X "potions: heal"`).

Incident 2026-10-31 around 23:00: the server stopped carrying out actions for everyone (the user's brother too), and logins hung on "Entering Britannia". It wasn't caused by the bridge, but just before it Claude had sent about 55 opens in 2.5 min at the server's minimum spacing, several of them out of reach. The user asked for safer pacing:
- Step 3 (~/claude/builds/cuo-agent3, installed 2026-10-31; step-2 build backed up in ~/Games/backups/classicuo-1.1.0.347-agent2/): every action, including single clicks, waits a random 1.2-2 s, plus a 3-5 s break after every 5. This is configurable as "pacing" in rules.json, with a floor of 1.1 s.
- The bridge refuses anything out of reach before sending (reach 2, wand target 12). This server ignores out-of-reach double-clicks silently.
- If the server ever doesn't answer, the bridge halts (423) until POST /resume (`uo resume`); `uo status` shows STOPPED.
- `uo move` carries the item in the backpack when it can't reach both the item and the destination.
- Never run long batches; stop at the first unanswered action.

Possible server rollback after the 23:00 outage (the server owner may restore an earlier save). First thing after logging back in: work out what state the world is in. Start with no-click reads (uo status, uo nearby), then a few paced opens. Known checkpoints (2026-10-31, local time):
- ~21:25: crates 0x408AD7D5 (wand trash) and 0x408AE270 (backpacks) placed, each holding a copper key.
- ~22:15: the 7 potion crates placed at 1758,1404/1405, all empty.
- 22:39: the brother's chest (0x40902338) was still full (5 coloured backpacks, 2 pouches, spellbook, Mark/Gate scrolls, 859 gold). Other chests held: jewellery (backpack hue 154, Recall), magic clothing (backpack hue 33, blood moss), shields (red potion, pouch), spare B (lockpicks x1964), chain (sample pouches and markers).
- ~22:58: all 24 chests empty; the backpacks crate held 15 backpacks with 5 more nested inside; 9 containers on the floor (pouches 0x4092B7CC/BF/D2/BB, backpack hue 33 0x407B195C, backpack hue 154 0x4087FCC6, bag 0x4086BE0E, backpack 0x40832F6B, pouch 0x4049D6B8). Johnny: weight 72/257, hatchet in hand.

Committed and pushed 2026-11-01 to github.com/matbess/ClassicUO-ext branch extensions:
- 787060f: the bridge, including step 4.
- 2842717: tools. The tools now live in ~/claude/ClassicUO/tools/uo-agent, and ~/claude/uo-agent is a symlink to it. labels.json changes as work goes on; commit it now and then.

Step 4 (~/claude/builds/cuo-agent4, installed 2026-11-01; step-3 build backed up in ~/Games/backups/classicuo-1.1.0.347-agent3/): items report art {w,h,visible[x,y,w,h]}; /contents reports the container's gump and area [x1,y1,x2,y2]. An item at (x,y) is drawn with its art's top left corner there. Tools: ~/claude/uo-agent/idall.py (batch identify with automatic wand swaps; run it in the background). uo.py is importable, raises BridgeError, and has a 600 s timeout because paced batches are slow.

Server quirks learned on 2026-11-01:
- The one-action-per-second delay also counts from a drop. Lift-to-lift gaps of 1.2 s still produced "You must wait" during moves.
- Reopening a container the server still counts as open (closing a window client-side isn't sent) can bring only its contents (0x3C) without the "show window" message (0x24).
- The server queues early actions ("Ignoring action request (already queued)").

Step 5 (~/claude/builds/cuo-agent5, installed 2026-11-01 01:01; step-4 build backed up in ~/Games/backups/classicuo-1.1.0.347-agent4/; committed as 46963b0): /move takes an amount to split stacks; an open counts as answered on 0x24 or 0x3C (AgentBridge.OnPacket hooked in PacketHandlers); pacing restarts from each drop or equip.

Re-sort under the new keep rules finished 2026-11-01 at 01:41:
- Smelting chest: butcher knife, pickaxe, silver dagger.
- Cutting chest: boots of cunning, tunic of strength.
- Trash crate: now 28 items plus 2 used ID tools.
- New markers: lightning (9) for attack wands; greater healing for the healing wands bag.
- 9 bags went back to the backpacks crate. The swords, axes, maces, fencing, archery, jewellery and magic clothing chests are now empty.
- Johnny's backpack holds the user's scissors and dagger; leave them. The dagger isn't needed.
- moves.py now waits out world saves (uo.wait_out_world_save); not committed yet.
- Step 6 (~/claude/builds/cuo-agent6, installed 2026-11-01 01:51; step-5 build backed up in ~/Games/backups/classicuo-1.1.0.347-agent5/):
  - Holds actions and stops answer clocks during world saves.
  - "useFromBackpack" in rules.json allows scissors 0x0F9E/0x0F9F (already in rules.json).
  - LIFT_WAIT is now 1000 ms between pick-up and drop.
  - GET /actions gives the send log; `uo actions` shows it next to the server's "must wait" messages.
- Scissors tested 2026-11-01: boots of cunning gave cut up leather; tunic of strength gave cut cloth x2. Both are in the supplies chest (second row) and the cutting chest is empty.
  - Floor cloth is now protected by serial in offLimits (the old rules are saved in ~/claude/uo-agent-work/rules.before-cloth.json).
  - Steps 6 and 7 committed and pushed 2026-11-01 (9acf7c7 bridge, 2189d9e tools).
  - Step 7 (~/claude/builds/cuo-agent7, installed 2026-11-01 02:07; step-6 build backed up in ~/Games/backups/classicuo-1.1.0.347-agent6/). rules.json is back to neverTouch [0x1766, 0x1767] with offLimits empty. neverTouch applies only to floor items, and a target disappearing counts as the answer to a use, so cutting no longer falsely stops. After installing, neverTouch [0x1766, 0x1767] can return.
- Later: the user will bring a trash barrel into the room and ask Johnny to empty the trash crate into it.

First sort finished 2026-11-01 at 01:18:
- The floor queue and Johnny's backpack are empty.
- 20 bags with markers sit in 11 chests; the plan_layout.py layout is in use.
- Gems, supplies and reagents are laid out as stacks. The scrolls chest has 8 circle bags: c1 the loot backpack, c2 the loot bag, c3-c6 pouches, c7 the hue-33 backpack, c8 the hue-154 backpack.
- Potions are one pile per crate (the server hides strengths).
- The backpacks crate is now empty: all 20 spares were used, so the user needs to bring more.
- Trash crate: 15 items plus 2 empty ID tools.
- ID supply: Johnny holds a staff with 29 charges; the spares pouch has 4 wands, 4 staves and a wand from the loot.
- Step-5 bridge and tool changes were committed and pushed 2026-11-01 (46963b0 bridge, 7b070ad tools).

Proposed order (2026-10-31):
1. Read-only "eyes": a localhost bridge with a token, enabled by a per-character option. It reports position, nearby items and characters, container contents with names, and the journal. Double-click is allowed only on containers. Use curl first and add MCP later.
2. "Hands": move or drop at an x/y, equip, use a wand and target, label by target, walk, the pause rule, and the wand workflow.
3. Sorting rules and layouts.

Working agreement (2026-11-01): Claude decides the order of work and how to be efficient. Ask the user only about policy: what to keep, what to trash, and procedure.
- Trash: anything "of clumsiness", "of night eyes", "of clumsy", "of feeblemind"/"feeblemindedness" or "of weakness" (decided 2026-11-01).
- The trash crate is 0x408AD7D5 (the former wand-trash crate), moved by the user next to the door at 1758,1411,26. Everything to throw away goes there, including empty ID wands. More trash crates may come later.
- Armour "of defense" (the lowest level) goes to the plain gear chest, keeping only 1-2 of each type (e.g. 2 studded leggings). Extras beyond that go to trash. Better levels (guarding and up) go to the material chests.
- Pickaxe goes to axes and butcher knife to swords (Claude's call). Lockpicks go to supplies.
- 2026-11-01: the user is adopting a keep list from another player (Emetah), with changes:
  - Weapons: keep anything of vanquishing, whatever the type (user, 2026-11-01). Keep force or power, except daggers, knives and crooks, plus charged "daemon's breath", "thunder" and "ghoul's touch". Crossbows only if really good; the user doesn't expect to use them.
  - Wands and staves: keep ID, greater healing, fireball and lightning.
  - Armour: keep chain fortification and invulnerability, and plate or ring hardening and up. Guarding and hardening is "gear I don't mind losing": keep at most 2 per piece type.
  - Jewellery and clothes: keep invisibility, magic reflection and teleport, and all magic rings.
  - Rejected metal and armour goes to a crafters' area, not trash: Icepick (the user's miner/blacksmith) smelts it, and leather or cloth gets cut. The area isn't chosen yet.
  - Settled: "of defense" stays, at most 2 per type. Stat clothes and jewellery are rejected (the charges wear off fast).
  - The crafters' areas are spare A (now "for smelting - Icepick", col 2 bottom) and spare B ("for cutting", col 4 bottom) until the user gets more crates.
  - Plate "of guarding" counts as gear the user doesn't mind losing (at most 2 per type).
  - The full keep table is in the uo-sort skill.
  - Scissors aren't supported yet; Johnny can probably cut without Tailoring, but that is untested.
- Plan: identify everything first (superseded 2026-11-01: name each item first and only use a charge on ones the server calls "magic X"; see the uo-sort skill). Then add art sizes to the bridge (one client restart) and plan the whole wall's layout. Then sort by carrying whole loot bags in the backpack and moving items straight into the chests, with potions last.
- 2026-11-01 10:34: chest survey (24 opens, no warnings). The map is now saved in tools/uo-agent/layout.json (print with `python3 layout.py`), and all 27 bags inside chests are labelled "bag: KIND (CHEST chest)". Empty chests: axes, maces & staves, polearms, fencing, archery, jewellery, gold, treasure maps, for cutting. The circle 1 and 2 scroll bags are empty, with no markers yet. The wand from Johnny's hand (2 charges) went back into the spares pouch, so Johnny's hands are empty for the user to play him.
- 2026-11-01: GM-crafted ("exceptional ... crafted by") items are always kept. The treasure maps chest (0x40902338, col 6 top) is now "GM armour sets"; the user keeps treasure maps downstairs for now and may bring them up later. Set = ringmail gloves, ringmail sleeves, chainmail leggings, chainmail tunic, platemail gorget, and a plate/close/norse helm or helmet. sortbatch's `sets` builds them; details in the uo-sort skill.
- 2026-11-01 batch 5 done (12:00-14:14): 10 backpacks, 728 items. 586 identified (all ID charges but 229 used; two ID staves found in the loot were used up too). Kept about 100: 16 attack/healing wands, 15 weapons (first bags in the axes, fencing, maces, polearms, archery and swords chests), plate/ringmail/helm keepers, and disposable pieces up to 2 per type. 11 to needs your decision (blessings, protection, fortification on shields/leather/studded). 182 trash, 138 smelting, 169 cut, 122 potions. Five new crates by the door (stack at 1758,1411): trash 1 (bottom, old trash crate), trash 2, smelting 1-4. After the batch: smelting chest full (125), smelting 1 has 28, trash 1 full (125), trash 2 has 109, so about 16 trash spaces left. Plate + helms and chain & ring chests are crowded: some markers sit beside their bags, not under them. Spares: 156 + 73 = 229 charges.
- 2026-11-01 14:31: the "for cutting" chest (0x408FC111, col 4 bottom) is now "chest: helms" holding the helms bag; the plate + helms chest (0x408FD7CF) is now "chest: plate". Plate (5 bags) and chain & ring (4 bags) were re-laid in one row each with tidy.py, every marker under its bag.
- 2026-11-01 14:40: chest labels now count rows from the top ("col 6, 2nd from top"). The old labels' "2nd" and "3rd" counted from the bottom, so "needs your decision (col 6 3rd)" was really 2nd from top, and I sent the user to the supplies chest by mistake. Older notes that say "2nd" or "3rd" for a chest use the old counting.
- Bridge fix for the next client build (not urgent): in Move, count any message from the drop target (for example the trash barrel's "The trash is full! Emptying!") as an answer, not only system messages. Until then the barrel's 50th item causes a false stop that the scripts resume.
- 2026-11-01 15:20: the user put a trash barrel in the room and said to empty the trash crates into it. They follow Emetah's rule going forward: shields and leather/studded invulnerability only; blessings and protection rejected. All kept shields below invulnerability were cleared out, but they are held in the trash and smelting crates (not the barrel) while the user asks the brother if he wants them.
- 2026-11-01: the user wants all gems in ONE bag in the gems chest (col 5, bottom) so they can grab it to sell; gem bag goes top-left with its marker so the rest of the chest stays free. The user noted the gems chest has room for other uses too. The shields chest (col 4, 3rd from top) is free after the shield clear-out; both can be dual-purpose when a new kind of item needs a home.
- 2026-11-01 15:45: user decisions: trash goes straight into the trash barrel unless they say otherwise; all kept leather/studded below invulnerability cut; gold accidentally left in loot bags goes to needs your decision (the gold chest is now a spare) and iron ore to smelting. The trash crates hold only the brother's possible shields; once he answers, all six door crates are for smelting.
- 2026-11-01 16:12: brother didn't want the shields (7 wooden went in the barrel); trash 1/2 crates relabelled smelting 6/5, so the smelting group is the chest + smelting 1-6 and all trash goes in the barrel. Batch 6 (5 bags, 86 things): 3 GM armour sets came as pouches and went whole into the GM chest as GM set 1-3 (sets 2 and 3 have plain, non-GM gorgets); exceptional katana and double axe got 'exceptional' bags; ring of teleporting started a 'rings' bag in the jewellery chest; 460 scrolls (circles 1 and 2 now have markers), gems into the gem bag, hides cut (works), feathers to supplies. 9 charges used; spares 156 + 64 = 220. finish.py's wand step worked live.
- 2026-11-01 16:15: no smelting chest: smelting uses only the six crates by the door (smelting 1-6). The old smelting chest's 125 items were carried to the crates; the chest (0x408FFDD1, col 2, bottom) is a spare.

**Why:** the user now plays on a private server based on the UOSA server code. Someone else hosts it on another machine; that person no longer plays. The only other player is the cooperating one. Shard automation rules are not a concern; don't look them up or raise them.
**How to apply:** pick up this design rather than starting over. Write up the plan before changing any code. See the section below.

## The Mac, Wine and the client builds

User plays UO on an Intel MacBook Pro via Sikarugir wrappers in ~/Applications/Sikarugir/. Originally this was the public UOSA shard (uosecondage.com). As of 2026-10-31 the game points at a private server based on the UOSA server code, hosted elsewhere by someone who no longer plays; one other cooperating player shares that world. See the section above.
- UOSecondAge.app: original UOSA launcher/ClassicUOSA client. Leave it untouched (read/copy only).
- ClassicUO-Wine10.app: main setup. ClassicUO 1.1.0.347 (commit ee79d7e) + Razor CE in C:\ClassicUO; Play.bat starts multiple clients sharing one settings.json. ClassicUO.app is the older Wine 9 copy.
- Razor lives in ~/Games/Razor (shared by both ClassicUO wrappers).

Installed patches (as of 2026-10-21, backups in ~/Games/backups/, diffs in ~/Games/patches/):
- cuo.dll rebuilt with a forgiving item pick-up option (profile key forgiving_pick_up_range); source clone at ~/claude/ClassicUO.
- 2026-10-31: cuo.dll rebuilt again adding an info bar "one item per line" option (profile key info_bar_vertical, values aligned left in a column). Previous pick-up-only DLL backed up in ~/Games/backups/classicuo-1.1.0.347-forgiving-pickup/.
- 2026-10-31: installed a build adding an effect recorder (Options > Experimental, profile key record_effects) that logs buff/debuff-related server packets to C:\ClassicUO\Logs\Effects. Goal: learn what UOSA sends (it has no 0xDF buff packets) and then build a client-side buff/debuff tracker feeding ClassicUO's BuffGump. Previous info-bar build backed up in ~/Games/backups/classicuo-1.1.0.347-infobar/.
- 2026-10-31: wrote Game/Managers/BuffTracker.cs (profile key track_buffs, default on) that fills ClassicUO's buff bar from UOSA's stat changes, flags, light, body, spell sounds/effects, words and system messages. Verified by replaying recorder logs (~/claude/effects-tools/tracker-replay, decoder ~/claude/effects-tools/decode.py). Installed 2026-10-31 (previous recorder-only build backed up in ~/Games/backups/classicuo-1.1.0.347-recorder/). Recorder still included; remove it once the user is happy with the tracker.
- 2026-10-31: added a buff bar frame option (profile key buff_bar_frame, default on; off hides the frame and rotate gem, and only the icons catch the mouse). Installed 2026-10-31 (built from commit 0309411 on branch extensions; previous tracker build backed up in ~/Games/backups/classicuo-1.1.0.347-bufftracker/).
- 2026-10-31: all ClassicUO changes committed (one commit per feature: pick-up, info bar, buff tracker, buff bar frame, effect recorder last so it can be dropped) on branch `extensions` off ee79d7e, pushed to the user's fork github.com/matbess/ClassicUO-ext (remote `fork`; `origin` is upstream ClassicUO). Push access is a repo-only deploy key ~/.ssh/github_classicuo via ssh host alias github-classicuo. Commit identity set repo-locally: matbess <1884731+matbess@users.noreply.github.com>. No gh CLI/brew on this Mac. ~/claude/effects-tools/split_commits.py was the one-off splitter.
- Cross-build toolchain (zig lld-link, xwin MSVC/SDK libs, lld-link wrapper, w10-wine helpers) lives in ~/claude/buildtools; outputs in ~/claude/builds.
- Razor.exe IL-patched to fix the PacketReader dangling-pointer crash in compressed gumps (runebooks).
- WINEDEBUG set to fixme-all (the +seh logging I had enabled caused crashes); Debug Mode still on.

**Why:** Context for future crash investigations and client changes.
**How to apply:** Never change the running game without asking; the user often plays while I investigate. "Crashes" have also turned out to be server-side disconnects; check the macOS log (tcp_connection_summary) before assuming a client crash. See AGENTS.md.
