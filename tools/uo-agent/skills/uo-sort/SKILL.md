---
name: uo-sort
description: Drive the user's Ultima Online character through the ClassicUO agent bridge to identify (ID) loot with ID wands and sort it into the house chest room. Use when the user asks to sort, ID or organise loot or items in UO, mentions Johnny, the chest room, ID wands or the agent bridge, or says there is more stuff to sort.
---

# Sorting loot in UO

The user plays Ultima Online, a T2A-era private server based on the UOSA server code, through ClassicUO under Wine on this Mac.
A bridge built into their ClassicUO lets Claude see the game and act as one character (currently "Here's Johnny"). The job is to identify magic gear with ID wands and sort everything into the chest room of their house.

## How the bridge runs, and what costs tokens

- The bridge lives inside the user's ClassicUO (cuo.dll). It uses no tokens, and it doesn't lag the game: it checks an empty queue each frame, notes a couple of packet kinds, and otherwise waits on 127.0.0.1.
- The user leaves it on. The setting is in Johnny's profile, so it starts whenever he logs in and stops when he logs out or the server drops him. After a server reboot it comes back by itself once he logs in again. Each login gets a new port and token, and `uo` finds them by itself.
- Its "stopped" flag only blocks Claude's actions. It lasts through a relog but not a client restart, and `uo resume` clears it without sending anything to the server.
- **What costs tokens is Claude working.** The user's "stop when done" means Claude stops: no background loops or checks left running once sorting is finished. The bridge can stay running.

## Before doing anything

1. Read `~/claude/ClassicUO/tools/uo-agent/AGENTS.md` (how the pieces fit, the house and its chest wall, open items, history), `~/claude/uo-agent/labels.json` (what every container is for), and the chest map with `python3 ~/claude/uo-agent/layout.py` (every chest's bags, their kinds and markers, and loose piles, as last seen). This skill file lives in the same repository (`tools/uo-agent/skills/uo-sort/SKILL.md`, linked from `~/.claude/skills/uo-sort/`): when the user decides something new, write it here and commit.
2. **Use Johnny's bridge:** `export UO_CHAR=Johnny` first (or put `UO_CHAR=Johnny` in front of every command). Icepick and Burgers have bridges too when mining, and with more than one running, every tool stops with "several bridges are running" unless it knows which character to use. Never act as Icepick or Burgers while sorting.
   Then run `~/claude/uo-agent/uo status`.
   - If it says STOPPED, check the messages first (`uo messages`).
     - If a world save was going on ("The world will save…", "world save complete"), it was the save. Resume and carry on, after checking whether the interrupted move went through.
     - If the cause was the bridge's own and the evidence shows the server answered (for example a drop into a container not opened since login, where the weight changed), resume and tell the user why.
     - Otherwise, tell the user what the server last said and wait for them before resuming.
   - If it says no bridge is running, ask the user to log the character in and tick Options > Experimental > "Agent bridge".
3. Run `uo clear`. If anyone is in the room, run `uo waitclear` in the background and continue when it exits.
4. Look first with no clicks (`uo nearby 14`; reading what the client knows sends nothing to the server). Compare it with the chest map (`layout.py`) before opening things.

## Tools (in ~/claude/uo-agent, a link to ~/claude/ClassicUO/tools/uo-agent in the git repository; run them from there)

| Command | What it does |
|---|---|
| `uo status`, `uo nearby [range] [--containers]`, `uo item S`, `uo contents S [--depth N]`, `uo messages` | Read only; nothing is sent to the server |
| `uo open S`, `uo close S` | Open a container (walks within reach first) and close its window |
| `uo name S[,S...]` | Single-click for the server's name. Unidentified gear says "magic X". |
| `uo walk X Y`, `uo walk --to S [--distance N]` | Walk inside the room |
| `uo move S TO [--at X Y]` | Move into a container or onto a same-kind stack. Carries the item via the backpack when it can't reach both ends. |
| `uo equip S`, `uo use WAND TARGET` | Equip; use what's in the hands on a target |
| `uo label S TEXT`, `uo labels` | Remember what a container is for. Labels work anywhere a serial does. |
| `uo clear`, `uo waitclear`, `uo resume`, `uo rules` | Check the room is empty, wait for it, resume after a stop, show rules |
| `python3 look.py BATCHDIR` | Batch step 1: find the floor loot, open every container in it (nested too), write `inv.json`, `loot.json` and `targets.txt` |
| `python3 idall.py S [S...]` | Batch step 2: identify with automatic ID-wand swaps (`$(cat BATCHDIR/targets.txt)`). Run it in the background. |
| `python3 plan.py BATCHDIR` | Batch step 3: apply the keep rules below and write `spec.json`; prints every decision and what needs the user |
| `python3 sortbatch.py BATCHDIR/spec.json` | Batch step 4: carry out the spec. Run it in the background. |
| `python3 layout.py` | Print the chest map from `layout.json`. Reads a file only. |
| `python3 finish.py` | End of sorting: ID wand from his hands back to the spares pouch, walk to the middle of the room, and say whether loot is still on the floor. |
| `python3 inventory.py [--known]` | The whole vault's contents for The Vault page (`vault/inventory.json`): opens every chest, bag and the potion and backpacks crates. `--known` reads only what the client knows. |
| `python3 tidy.py CHEST BAG:MARKER ...` | Re-lay a chest's bags in one evenly spaced row, each marker under its bag, in the order given. Use it when a chest gets crowded and markers end up beside their bags. `--dry` only prints. |
| `python3 survey.py [S...]` | Open every chest (or the ones named) once and re-record the map: 24 opens, under a minute. `--known` records from what the client already knows and sends nothing. |
| `python3 moves.py PLAN.json` | Carry out a list of moves `["S", "TO", x, y, amount]` at the bridge's pace; stops at the first failure and says where |
| `python3 potions.py CONTAINER...` | Name every potion, then pile each by strength in its kind's crate (Night Sight to trash) |
| `uo move S TO --amount N` | Split a stack: the part moved keeps the serial, the rest stays as a new item |

`uo.py` can be imported for scripts (see idall.py). It keeps every item name it sees in `names.json`, so identified names survive client restarts.
Batch working files go in `~/claude/uo-agent-work/batchN` (scratch, not needed later). `uo.py` raises `BridgeError` with `.code`: 409 means paused, too far or refused; 423 means stopped.

## Safety rules (these matter more than speed)

- Sorting runs at **full speed** (the user, 2026-11-05: pacing is for mining only): the bridge's floor of 1.1 s between actions and no breaks (`rules.json`). Don't add waits in scripts, and never go around the bridge.
  - This came from 2026-10-31, when about 55 fast opens came just before the server stalled for everyone.
  - Pacing is set in `rules.json` and has a floor of 1.1 s.
- Long batches still take a while, so use background tasks for them and keep requests to a few dozen actions.
- If the bridge stops because the server didn't answer, find out why before anything else. Never retry blindly.
  - World saves freeze the server for several seconds. They are routine. The bridge holds new actions while it knows a save is running, but an action already sent when the save starts can still stop it. Then wait for "world save complete", check whether the interrupted action went through, and carry on without asking. The scripts do this themselves (`uo.wait_out_world_save`).
  - A false stop with a clear cause, where the server did answer (see "Drops into a container not opened since login" below): resume and tell the user.
  - Any other silence: stop and tell the user.
- Johnny pauses whenever any other character is in the room, including the user's own characters such as Clem. Wait with `uo waitclear` in the background, checking once a minute.
- When all sorting is done, stop completely. No loops or background checks keep running. The user comes back when there's more.
- The bridge only acts inside the room in `rules.json`. It never picks up the cut cloth on the floor (decoration), never drops anything on the floor, and only double-clicks containers and the item in the hands, so no potion gets drunk by mistake.
- The user can tell Claude to stop at any time. Stop at once and stop any background task.

## Things learned about this server and client

- **The client forgets container contents when it restarts.** After every restart, open each container before moving things into or out of it, including containers nested in chests (such as the ID spares pouch). Otherwise the bridge answers 404 "no such item nearby".
- **Reopening a container can bring only its contents.** If the server still counts the container as open (closing a window is never sent to the server), it sends the contents without the "show window" message. The bridge counts either as an answer.
- **The action delay also runs from drops.** "You must wait" can still show up now and then. The bridge retries once, which is harmless. The gap is 1.1 s in `rules.json`.
- **Drops into a container not opened since login get no reply.** The server only reports a container's contents to someone who has opened it, so the bridge hears nothing and stops (2026-11-01, putting the wand in the spares pouch after a restart). `uo.move` now opens a target the client knows nothing about first. If it happens anyway, the weight change and empty hands show the drop worked.
- **The trash barrel** (0x4068E2BB, by the door at 1758,1410; added 2026-11-01) deletes what goes in after three minutes, or at once when the 50th item goes in. Then the barrel itself says "The trash is full! Emptying!" and the item just dropped is deleted too. The bridge only counts system messages as an answer, so it stops ("no answer after dropping"). That's a known false stop: resume and carry on (`uo.resume_after_barrel_emptied`; sortbatch and idall do it themselves). Never put anything in the barrel the user might still want.
- **Server-wide announcements can make a move look failed.** A broadcast ("The tournament is now over…") arriving just as a drop is answered counts as the server's reply, and the bridge reports the move as not done although the item went where it should (2026-11-04). sortbatch now checks where the item really is before calling a move failed (`landed_in`). If a script still stops with "did not go into", check `uo item S` before anything else.
- **Moving a bag makes the client forget what's in it.** After picking a bag up and dropping it, open it again before moving anything out of it, or the bridge answers 404.
- **Weights:** a bag's single-click label shows "(N items, M stones)".
- **Cut cloth looks like the floor decoration.** Cutting makes "cut cloth" of the same kind (0x1766) as the green floor squares. `neverTouch` only applies to items lying on the floor, so cloth in containers can be moved while the floor squares stay protected.

## Order of work (Claude decides the order; ask the user about policy only)

1. **Look:** `python3 look.py ~/claude/uo-agent-work/batchN`, with N the next unused number (`ls ~/claude/uo-agent-work`). Anything on the room floor except the chests, crates, barrel, labelled containers and cut cloth is the queue. Loose items not in a bag are listed; sort those by hand. Only loot bags go on this floor, so a labelled bag lying there has been reused as a loot bag: look.py drops its label, treats it as loot, and it goes to the backpacks crate at the end. The forge in the room is labelled and stays. Key rings are never opened, as using one asks "What do you want to unlock?" instead of showing its keys (2026-11-11). look.py treats them as items, and they're kept in the miscellaneous chest (below).
2. **Identify, but never spend a charge without checking first** (the user's rule, 2026-11-01): `python3 idall.py $(cat BATCHDIR/targets.txt)` in the background.
   - It names each item first: one single-click, or none if names.json already knows the name.
   - Only items the server calls "magic X" ("a magic chainmail coif", "magic wand") get the wand.
   - Already identified items ("of guarding", "(18 charges)"), plain items and GM items ("exceptional ... crafted by") are skipped.
   - Wands and staves go first (the user's rule), so any ID wands among them add their charges to the batch. idall.py swaps to found ID wands like any spare, fewest charges first; used-up ones go in the barrel.
3. **Plan:** `python3 plan.py BATCHDIR` applies the keep rules below and writes `spec.json`. Read its report. Show the user the plan before the first layout of an empty chest, and tell them what's going to "needs your decision". If a rule doesn't fit, edit the spec by hand (the format is at the top of sortbatch.py) and fix plan.py and this skill.
4. **Sort:** `python3 sortbatch.py BATCHDIR/spec.json` in the background. It also handles everything that needs no decision: scrolls by circle, reagents, gems into the gem bag, potions into their crates, supplies, hides (cut), gold (to needs your decision) and iron ore (to smelting), and sends emptied loot bags back to the backpacks crate.
   - If it stops part-way, fix the cause, then run a copy of the spec without the parts already done (new bags already made are found by their labels).
5. Run `python3 finish.py` (the user's rules, 2026-11-01): it puts the ID wand or staff from Johnny's hands back in the spares pouch, after a single-click so names.json has its real charges, so the user can play him. Then it walks him to the middle of the room (1760,1407, the centre of the rules area). Next time idall.py starts with empty hands and takes the spare with the fewest charges. Last it checks the floor: **MORE LOOT ON THE FLOOR** means the user brought a bag while the batch ran (2026-11-08: Clem dropped one 11 s after look.py had looked, and it was missed). Sort it as the next batch before reporting; "the floor is clear" means done.
6. **Update The Vault page** (the user, 2026-11-10: "each time you finish sorting"): the shared inventory at **https://claude.ai/artifact/5nsmouJoGEEEMFdaffrXLP** (title "The Vault"). Run `python3 inventory.py` in the background (about 2 minutes: Johnny opens every chest, bag, potion crate and the backpacks crate; not the smelting crates or the barrel, the user's choice) to write `vault/inventory.json` and the same data into the page itself (`window.VAULT` in `vault/index.html`: on 2026-11-10 the user's phone showed no chests while the page fetched a separate data file). Then publish with the Artifact tool: `file_path` `~/claude/ClassicUO/tools/uo-agent/vault/index.html` and `url` the link above (no other files). The user has shared it with anyone who has the link, and viewers see each update at once. On phones the wall turns into tiles in wall order, each showing its column and row. In a new conversation, read the artifact first (`action: "read"` on the link), or the publish is refused; never publish without `url`, which would make a second page. The page also shows what the gem bag sells for (the user, 2026-11-11), from `GEM_PRICES` in inventory.py (Clem's jeweler prices in GEMS.md); the marker gem under the bag counts too, as the user sells it with the bag (2026-11-11; sortbatch lays a new one). If Clem reports new prices, update `GEM_PRICES`. Commit `vault/inventory.json` with the batch. Give the user the link in the report.
7. If anything changed (a new decision, open item or lesson), write it into this skill or `AGENTS.md` and commit. Make sure no background task is still running. Then report what was done (kept, smelted, cut, trashed, anything for the user to decide, ID charges left, the pieces waiting to be smelted, the page updated) and stop.

## What to keep (the user's decisions, 2026-11-01; ask about anything new)

Emetah's keep list (another player's advice) is the rule, except where the user decided otherwise (marked
**user's exception**). On 2026-11-01 the user said to follow Emetah's rule going forward, keeping those exceptions.

| Group | Keep | Reject |
|---|---|---|
| Weapons | Force or power (accuracy and tactics are a bonus), except daggers, knives and crooks. Staves without charges count as weapons: a plain, accurate or "of ruin/might" staff goes in the barrel (wood). Charged "of daemon's breath", "of dragon's breath", "of thunder" or "of ghoul's touch" even if nothing else is good. **User's exceptions:** anything of vanquishing, whatever the weapon, even a dagger or knife; crossbows only if power or vanquishing. **All hatchets and pickaxes**, plain, magic or GM (the user, 2026-11-07 and 11-08: hatchets for lumberjacking, pickaxes for mining): in a "hatchets" bag and a "pickaxes" bag in the axes chest. | Everything else |
| Wands and staves | Identification, greater healing, fireball, lightning | Everything else, including healing, harming and curses |
| Armour, keepers | Chain fortification or invulnerability; plate or ringmail hardening and up | |
| Metal armour the user doesn't mind losing (**user's exception**) | Chain, ringmail and plate guarding or hardening, at most 2 of each piece type; "of defense" (to the plain gear chest), at most 2 of each type | Extras beyond 2, and any with a curse ("of defense and night eyes": 2026-11-09). A keeper (fortification, hardening and up) with a curse goes to needs your decision. |
| Shields | Invulnerability only (2026-11-01: with both hands full you can't drink potions, so shields are rarely worth it) | Everything else: metal to smelting, wooden to trash |
| Leather and studded | Invulnerability only (2026-11-01; everything kept before that was cut the same day) | Everything else is cut |
| Jewellery and clothes | Invisibility, magic reflection, teleport; all magic rings (they're teleport or invisibility) except a curse | Everything else, including blessings and protection (rarely used: the slots go to teleport, reflect and invisibility; the user rejected them 2026-11-01), stat boosts (agility, strength, cunning: the charges wear off fast) and clumsiness, feeblemind, weakness and night eyes |
| Other | Crystal balls, cheese (wedges and wheels, matched by graphic 0x097C-0x097E) and key rings (the user, 2026-11-11: "keep the keyrings"), loose in the miscellaneous chest (column 5, 3rd from top), the home for anything the user keeps that has no other place (2026-11-04). Add new kinds to `MISC` in plan.py when the user says to keep them. | Night Sight potions; torches (the user, 2026-11-04); jugs of cider and bread loaves (2026-11-07) |
| Bone armour | Only really good bone (the user, 2026-11-01): hardening, fortification or invulnerability, like plate's keepers, and any daemon bone. No "gear I don't mind losing" bone. It goes in a bag in the bone armour chest (column 2, bottom). Bone has AR 32 per piece against plate's 30, needs 40 strength, but lasts half as long (25-30 hits). | Rejected bone goes in the trash barrel: it can't be smelted or cut (the user, 2026-11-01) |
| Left in the loot by accident | Gold goes to the needs-your-decision chest (the user wants to see it); iron ore goes to smelting. sortbatch does both. | |
| Feathers | Supplies (they make arrows); sortbatch piles them there. | |
| Scissors | Spare pairs go loose in the supplies chest as Johnny's backup (the user, 2026-11-11). The pair in his backpack stays there. | |
| Hides (piles skinned from animals) | Cut into leather (one scissors use per pile) and put on the cut up leather pile in supplies. sortbatch does it (works: tested 2026-11-01, one cut per pile). | |
| Logs | Made into boards (the user, 2026-11-09) with the **saw the user keeps in Johnny's backpack; it stays there**. The saw's menu: "Other", then "board", turns a whole pile into boards at once ("You create the item."; no Carpentry needed). sortbatch does it and puts the boards on their pile in the supplies chest. Johnny's rules.json lets him use saws from his backpack (`useFromBackpack`). With no saw, sortbatch says NO SAW and leaves the logs in their loot bags. Boards that come in as boards go straight to the supplies pile. | |
| GM crafted ("exceptional ... crafted by NAME"), **user's exception** | Always kept, armour and weapons. Not magic, so the wand only wastes a charge on them. | |

**GM armour sets (the user's list, 2026-11-01):** ringmail gloves, ringmail sleeves, chainmail leggings, chainmail tunic, platemail gorget, and a helm: plate helm, close helm, norse helm or helmet. Those four have the same armour (base AR 30, needs 40 strength); the plate helm only lasts a little longer (50-65 hits against 45-60). Bascinets (AR 18), chainmail coifs (23) and orc helms (20) are weaker and don't count. These are T2A numbers from another shard's table (uolostlands.com/armor), not checked on this server. GM set pieces are kept apart so whole sets are easy to grab.

**Where GM items go (decided 2026-11-01):**
- **Set pieces:** the "GM armour sets" chest (column 6 top, formerly treasure maps; the user keeps maps downstairs for now). One bag per set and no markers. Each piece goes into the first set bag missing a GM piece of that kind, and a new bag is started when none is. Only GM pieces count: sets 2 and 3 have plain gorgets, so the first GM gorgets replace those, and sortbatch sends the replaced plain pieces to smelting. List the pieces under `sets` in the sortbatch spec (plan.py does); sortbatch does the rest and labels new bags "GM set N".
- **Other GM armour** (a GM plate tunic, say): its material chest, in an "exceptional" bag with a marker.
- **GM weapons:** their weapon chest, in an "exceptional" bag with a marker.
- **Magic gear stays out of the sets.** Most kept magic armour is low-level gear the user doesn't mind losing, so mixed sets would be uneven. If the user wants a full best suit, build one on request from the chest map.

**Where rejects go:**
- **Metal armour and metal weapons:** the smelting crates by the door, for Icepick (the user's miner/blacksmith). Only what a blacksmith makes melts. **Never smelting** (the user, 2026-11-07: 31 pieces came back with "You can't melt that down into ingots."): skinning knives, butcher knives, cleavers, pickaxes, pitchforks, hatchets (tinker-made tools; hatchets and pickaxes are all kept now anyway) and orc helms. They go in the trash barrel; plan.py's `NO_SMELT` does it. A magic one the keep rules keep (vanquishing, GM, an orc helm of defense or guarding under the 2-per-type limit) is still kept.
- **Leather and studded armour, cloth clothes, hats and boots:** Johnny cuts them himself (list them under `cut`); no Tailoring is needed. Cutting only works in his backpack, with the user's scissors there (sortbatch finds any pair by graphic). The user plays Johnny too and may take them (2026-11-08: scissors and dagger gone): then sortbatch says NO SCISSORS and leaves the items to cut in their loot bags on the floor; ask the user to put a pair back, and cut them then (a spec with only `loot` and `cut`). The "cut up leather" and "cut cloth" go on their piles in the supplies chest. The old "for cutting" chest became the helms chest on 2026-11-01.
- **Trash barrel by the door** (the user's rule, 2026-11-01: trash goes in the barrel unless they say otherwise): wood (staves, bows, crossbows), the tools and orc helms that won't melt (above), wands, jewellery, empty ID wands, Night Sight potions, and anything else that can't be smelted or cut. List them under `trash` in the spec; sortbatch and idall drop them in the barrel.
- **Smelting:** only the six crates stacked by the door, "smelting 1" to "smelting 6", filled in that order (the user's rule, 2026-11-01: all smelting in one place). There is no smelting chest any more; the old one (column 2, bottom) holds bone armour now. List metal rejects under `smelt`. The crates hold about 400 stones each ("That container cannot hold more weight"), so they fill at roughly 55-75 metal pieces, not 125; sortbatch moves on to the next crate when one is full. **Nobody smelts during sorting** (the user, 2026-11-08): Icepick is the smith and is on the same account as Johnny, so he can't be logged in while Johnny sorts; Johnny has no hammer and Blacksmithy 6. The pieces stay in the crates. finish.py opens every smelting crate and prints `SMELTING: N pieces waiting to be smelted`: **put that number in every end-of-sort report.** The user won't lock them down (2026-11-01): the metal gets smelted soon.
- sortbatch carries trash and smelting in loads (up to 30 items, stopping 20 stones short of Johnny's limit) and moves on to the next crate when one holds 125 items or the server says it can't hold more.
- More crates may replace these chests later.

**Not sure where something goes:** put it in the "needs your decision" chest and tell the user.

**ID wands and staves** go in the spares pouch in the "supplies & ID wands" chest. Use the one with the fewest charges first, and put the one in hand back in the pouch when sorting is done. When one is empty it goes in the trash barrel. If no spares are left, idall.py waits and checks the pouch once a minute: tell the user.

**A bag left with nothing in it** after rejects are moved out goes back to the backpacks crate. Its kind gets a new bag and marker when a keeper turns up.

**Possible later additions:** Icepick smelting at the downstairs forge (the bridge would need a second area and crafting-menu support). The user plans mining, then smelting, next.

## Layout conventions

- Chest labels give the column (1-6, left to right) and the row counted from the top: "top", "2nd from top", "3rd from top", "bottom". When telling the user where a chest is, use that wording. The chest at z 38 is the top and z 26 the bottom.
  - Before telling the user where a chest is, trust the label only if the survey's label check is clean. `survey.py --known` (sends nothing) works out every chest's column and row from where it stands and prints `LABEL CHECK` for any label that disagrees. Run it after the user moves or adds chests.
- **The map is saved, and the game is the truth.** `layout.json` keeps every chest's bags, kinds, markers and loose piles. sortbatch.py re-records each chest it opened at the end of a batch, and labels new bags. Still open a chest before moving into it: the user may have taken things out, and the server only reports drops into containers opened since login.
- Every bag inside a chest is labelled `bag: KIND (CHEST chest)`, for example `bag: plate tunics (plate chest)`, so a spec can name it with `resolve('bag: plate tunics')`.
- All 8 scroll circles have markers (circles 1 and 2 got theirs 2026-11-01: a Heal and an Agility scroll).
- Inside each chest are bags of one kind each. Under each bag sits one marker: an identified item of that kind, usually the first one found.
- A bag and its marker form a slot: as wide as the wider of the two, and as tall as both together.
- Bags don't overlap unless the chest runs out of room. When it does, overlap is fine (the user confirmed this for the scrolls chest), as long as every bag and marker stays visible and clickable.
- In weapon and armour bags, items are laid out in a grid with the best first (damage, then accuracy, then durability; protection, then durability). Some overlap is fine if needed. Potions go in piles; stackables (scrolls, reagents, gems) are dropped onto their stack.
- Use the item `art` sizes and the container `area` from `uo --json contents`. A wooden chest's area is x 18-162, y 105-178, and an item is placed by the top left of its art.
- Chests hold 125 items, counting bags, markers and everything inside the bags; there's no weight limit. When one fills, move its least valuable items to overflow and tell the user.
- Bags for sorting come from the backpacks crate. Check each is empty first. A bag holding anything except empty bags goes whole to "needs your decision", and tell the user.
- **Scrolls:** one chest with 8 circle bags in a row, circles 1-8 from left to right, with markers underneath overlapping by about a third. A marker is a single scroll of that circle; split one off a stack with `--amount` if needed.
  - Circle and place come from the graphic: spell scrolls run 0x1F2D-0x1F6C in spell order. The circle is `(g - 0x1F2D) // 8 + 1`, and the spell's place in its circle (`(g - 0x1F2D) % 8`) sets its spot in the bag: 2 rows of 4.
  - Circle bags can be any bags or pouches.
- **Reagents:** stacks without bags, in a fixed order with empty gaps kept for missing kinds, two rows of four: black pearl, blood moss, garlic, ginseng / mandrake root, nightshade, spider's silk, sulfurous ash. Smaller stacks merge onto the big one. **Gems** are stacks inside the gem bag (see below), in the order amber, amethyst, citrine, diamond, emerald, ruby, sapphire, star sapphire, tourmaline.
- **Gems chest** (column 5, bottom): every gem pile lives in ONE bag ("bag: gems", top left, a gem marker under it) so the user can grab the bag to sell. sortbatch stacks new gems inside it. The rest of the chest is free for other uses.
  - **The user takes the whole gem bag to sell the gems, then reuses the empty bag as a loot bag** (2026-11-07). So the gem bag being gone from the chest is normal: sortbatch starts a new one from the backpacks crate at the top left the next time gems come in, labels it, and splits one gem under it as the marker (unless the old marker is still lying there). The old bag, back on the floor with loot, is just loot (see step 1).
- **Spare chests:** the old shields chest (column 4, 3rd from top) is now "spare + invulnerability shields", and the gems chest has free room. Offer these first when a new kind of item needs a home.
- **Supplies chest:** the ID spares pouch at the top left, then lockpicks, empty bottles and blank scrolls in a row.
- **Miscellaneous chest** (column 5, 3rd from top; the gold chest until 2026-11-04): loose things the user keeps that have no other home, such as crystal balls. Loot gold goes to the needs-your-decision chest.
- **Potion crates:** one crate per kind (by bottle colour). The server doesn't reveal strength: a single click says "an unknown red potion" or just "Blue Potion". So for now each crate holds one mixed pile. If the user finds a way to learn strengths (for example Taste Identification), potions.py already piles them left to right: lesser, regular, greater (total refresh), deadly.
- **Marker choice:** the least valuable item of its kind; among equals, the one with the smallest picture. That keeps markers small so more bags fit.
- **Sizes:** a backpack shows about 15x20 visible pixels, a pouch 10x14, a cloth bag 13x16. Most item art is 44 pixels wide with the visible part inside it (see `art.visible`). Staves are 86x67 and too tall to go under a bag, so they go beside it.
- **Containers emptied while sorting** (loot bags and pouches) become sorting bags or go back into the backpacks crate.

## Changing the bridge

The source is `~/claude/ClassicUO/src/ClassicUO.Client/Game/Managers/AgentBridge.cs`, on branch `extensions` of github.com/matbess/ClassicUO-ext. Build, smoke test and install with the scripts in `tools/build` (see its README); the repository's root `AGENTS.md` describes the whole fork.

- Never install, smoke test or run `wineserver -k` while the user's clients are running, and ask before installing.
- `install.sh` backs up the installed `cuo.dll` and `cuo.pdb` first.
- Commit bridge and tool changes (including labels.json, layout.json and names.json) to `extensions` and push to the `fork` remote when asked, or after a session's changes settle.
