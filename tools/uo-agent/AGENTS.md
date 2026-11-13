# The sorting agent: notes for a new session

Claude sorts the user's Ultima Online loot by playing one of their characters through the **agent bridge** built
into their ClassicUO (`src/ClassicUO.Client/Game/Managers/AgentBridge.cs`). This folder holds the tools Claude drives
it with, the house's labels and chest map, and the procedure.

**Mining** (Icepick and Burgers, from 2026-11-01): read `MINING.md` first; the loop is `mine.py`. Bridge 11 (build
cuo-agent28) has the guard say "Guards!" the moment the character loses hits (rules `"callGuards"`; MINING.md,
"Creatures", 2026-11-08).

**Cartography** (Clem, from 2026-11-05: world maps from the map bags on the tower's second floor, outside the
vault, and trips to the map vendor): read `CARTO.md` first; the tools are `carto.py` and `trips.py` (the vendor trips,
from 2026-11-08, with bridge 12, build cuo-agent29: `/shop`, `/buy`, `/sell`), Clem's rules
`rules/rules-Clem.json` (no guard).

**Fighting** (Clem, from 2026-11-06: a bard-mage who provokes creatures onto each other and finishes them with
spells, so he can get past the creatures at the front door on trips to town): read `COMBAT.md` first; the tools
are `door.py` (out and in through the front door, which must always end locked and closed) and `fight.py`;
`fight_scenes.py` and `fight_sim.py` check fight.py's decisions offline. Bridge 7 (build cuo-agent23) adds creatures'
health, skills and spells aimed at creatures, running walks, doors and keys, and the user taking over by giving a
command themselves (`"handOver"`); only the user hands him back (`--resume`). Bridge 8 (cuo-agent24, installed
2026-11-07) casts without waiting (`/cast wait=0`): the bridge aims the cursor, the outcome comes in the messages. Never leave Clem outside or unwatched.

**Selling gems** (Clem, from 2026-11-09: the gem bag from the vault's gems chest and the Gems runebook from the
chest by the stairs, then town to sell to several NPCs and home): read `GEMS.md` first; the tool is `gems.py`
(`fetch` gets him ready; the vault door: in with the key like the front door, out without it, checked locked from
outside).

**Blacksmithing** (Icepick, from 2026-11-05: training to 100 at the forge and anvil on the tower's ground floor,
crafting and smelting back; **reached 100 on 2026-11-07**): read `SMITHING.md` first; the tool is `smith.py`, the rules
`rules/rules-Icepick-smith.json` (no guard, no pacing). Since 2026-11-07 he also smelts the junk gear in the vault's
smelting crates (`vault.py`, `rules/rules-Icepick-vault.json`; the vault door always ends locked and closed). Bridge 6 (build cuo-agent19) adds menus, gumps, target
cursors, skills and an event log that records what the user does by hand (`uo record`).

**Healing** (Burgers, from 2026-11-08: bandages from the pile on the tower floor on Isabel's ghost, one every ~10 s,
to 100): read `HEALING.md` first; the tool is `heal.py`, the rules `rules/rules-Burgers-heal.json`. Bridge 10 (build
cuo-agent27) adds `useOnGround` kinds (double-clicked where they lie) and `patients` (the user's characters `/use` may
aim at). Burgers is also mining's banker: check before running it.

**Lumberjacking** (Icepick, from 2026-11-12: chopping mounted in the guarded town around the mining route, logs
turned into boards, boards handed to Burgers to bank): read `LUMBERJACKING.md` first; the loop is `lumber.py` (mine.py's
Miner with the mining parts swapped out), the tour `lumbering.py`, the rules `rules/rules-Icepick-lumber.json` and
`rules/rules-Burgers-lumber.json`. It takes turns with mining (both use Icepick): never run both.

**To sort loot, follow `skills/uo-sort/SKILL.md`.** It has the procedure, the safety rules, everything learned about
the server, and the user's keep rules. It's installed as the user-level skill `uo-sort` through a symlink
(`~/.claude/skills/uo-sort/SKILL.md` -> this repo's `tools/uo-agent/skills/uo-sort/SKILL.md`), so edit it here and
commit. If the symlink is missing on a new Mac: `mkdir -p ~/.claude/skills/uo-sort && ln -sf
~/claude/ClassicUO/tools/uo-agent/skills/uo-sort/SKILL.md ~/.claude/skills/uo-sort/SKILL.md`.

This file is the background: how the pieces fit, the house, open items and history.

## How it fits together

```
user's ClassicUO (Wine)                       this Mac
  AgentBridge.cs  <-- HTTP 127.0.0.1:7780-7789, bearer token -->  uo.py / uo  <--  the batch scripts  <--  Claude
     reads Agent/rules.json, writes Agent/<character>.json (port + token) on login
```

- **The bridge** runs inside the client when the character's profile has Options > Experimental > "Agent bridge"
  ticked (profile key `agent_bridge`; currently only on "Here's Johnny"). It starts on login and stops on logout or
  disconnect, so it survives server reboots without any setup. It costs no tokens and doesn't lag the game.
- **Requests run on the game thread, one at a time, paced** by the character's rules file: full speed (1.1 s, the
  bridge's floor, no breaks) for everything but mining (the user, 2026-11-05; root AGENTS.md, "Pacing is for mining
  only"),
  and are refused when unsafe: outside the rules area, out of reach (2 tiles, 12 for a wand target), someone else in
  the room (409 "paused"), double-clicking anything but a container or the item in the hands. If the server ever
  doesn't answer, the bridge stops (423) until `uo resume`. It holds actions during world saves.
- **Endpoints.** Read only (nothing sent to the server): `GET /status`, `/nearby?range=&containers=`,
  `/item?serial=`, `/contents?serial=&depth=` (with the container's gump and item area, and each item's art box),
  `/messages`, `/rules`, `/actions` (the send log). Acting: `POST /open`, `/close`, `/name` (single-click, a comma
  list), `/walk?x=&y=` or `?to=&distance=`, `/move?serial=&to=&x=&y=&amount=` (amount splits a stack: the moved part
  keeps the serial), `/equip`, `/use?serial=&target=`, `/cancel`, `/resume`. Errors: 404 unknown item, 403 not
  allowed, 409 paused/too far/refused, 423 stopped.
- **`Agent/rules.json`** sits in the client folder (`<prefix>/drive_c/ClassicUO/Agent/`). A copy of the house's is
  in this folder (`rules.json`); restore it from here if it's lost.
- **The tools** (all Python 3, standard library only; `~/claude/uo-agent` is a symlink to this folder):

| Tool | Step | What |
|---|---|---|
| `uo` / `uo.py` | any | the command line and the importable library: every endpoint, labels, `move()` that walks and carries, world-save and barrel helpers; remembers every item name in `names.json` |
| `look.py BATCHDIR` | 1 | find the floor loot, open every container (nested too), write `inv.json`, `loot.json`, `targets.txt` |
| `idall.py $(cat BATCHDIR/targets.txt)` | 2 | name each item, wand only the "magic" ones, wands and staves first, swap ID wands as they run out |
| `plan.py BATCHDIR` | 3 | apply the keep rules and write `spec.json`; lists what goes to "needs your decision" |
| `sortbatch.py BATCHDIR/spec.json` | 4 | do it: new bags and markers, gear into bags, GM sets, trash to the barrel, smelting crates, cutting, scrolls, reagents, gems, potions, supplies; empty loot bags back to the crate; records the chest map |
| `finish.py` | 5 | ID wand back to the spares pouch, Johnny to the middle of the room |
| `inventory.py`, `vault/` | 6 | the vault's full inventory (`vault/inventory.json`) for the shared page "The Vault" (`vault/index.html`, published at https://claude.ai/artifact/5nsmouJoGEEEMFdaffrXLP), updated after every sort |
| `survey.py`, `layout.py` | | open every chest and record the map in `layout.json` (`--known` sends nothing and checks labels against positions); print the map |
| `tidy.py` | | re-lay a crowded chest's bags in one row with markers under them |
| `moves.py`, `potions.py` | | a list of moves at the bridge's pace; potions by strength (the server hides strengths) |
| `mine.py`, `carto.py`, `smith.py`, `vault.py` | | the mining loop (MINING.md), Clem's cartography (CARTO.md), Icepick's smithing and his smelting of the vault's junk gear (SMITHING.md) |
| `heal.py` | | Healing with bandages on a ghost (HEALING.md): Burgers on Isabel |
| `trips.py`, `drawing.py` | | Clem's trips to the mapmaker in Ocllo (CARTO.md, "Vendor trips"): buy him out, then sell drawn maps and buy them back; home by Recall straight into fight.py's front-of-the-tower mode. Once every drawn map is sold, drawing.py draws world maps on all the blanks, then back to selling |
| `restock.py`, `door.py`, `fight.py`, `fight_scenes.py`, `fight_sim.py` | | Clem's reagents before he leaves (below 25: restock at the chest), the front door, his fights, and offline checks of the fight decisions (COMBAT.md) |
| `blackbox.py` | | read-only recorder: copies every client's bridge event log (what was sent after Razor, messages) to `~/claude/uo-agent-work/blackbox/<Character>-<date>.jsonl`, across client restarts; `--show N`. Started 2026-11-06 for Razor's jammed drag queue (a pick-up the server took with no drop after it: Razor holds every later pick-up and double-click for up to 2 minutes; its "Drop What You are Currently Holding" hotkey frees it) |

Batch working files go in `~/claude/uo-agent-work/batchN/`. They're scratch: nothing there is needed later.

## The house (map 0)

The chest room is on the second floor (z 26) of the user's stone house: x 1758-1763, y 1402-1412 (the rules area;
floors above at z 46+ and below at z 6 hold other things, so filter by height). The green squares on the floor are cut
cloth (decoration; never touched). The other room, with rows of bags on the floor, is at x 1750-1756: Clem's map bags (CARTO.md), not
Johnny's.

**The chest wall** at y 1402: 6 columns (x 1758 to 1763, left to right) by 4 high (z 38 top, 34, 30, 26 bottom).
Labels say "(col N, ROW)" with rows counted from the top.

| | col 1 (1758) | col 2 (1759) | col 3 (1760) | col 4 (1761) | col 5 (1762) | col 6 (1763) |
|---|---|---|---|---|---|---|
| top | swords | fencing | plate | jewellery | scrolls | GM armour sets |
| 2nd | axes | archery | chain & ring + coifs | magic clothing | reagents | needs your decision |
| 3rd | maces & staves | magic wands | leather + caps | spare + invulnerability shields | miscellaneous | supplies & ID wands |
| bottom | polearms | bone armour | studded | helms | gems | plain gear |

Every chest and every bag inside one is labelled in `labels.json`; `python3 layout.py` prints what each chest holds.
Each bag has a marker item under it showing its kind (except GM set bags). Empty as of 2026-11-01: leather + caps
and studded (they'll take invulnerability leather and studded, the only kind kept now), bone armour, the spare in
column 4, miscellaneous (crystal balls and other odds and ends); the gems chest is mostly free.

**Crates and the rest:**
- Potion crates: a stack of six at 1758,1404 (z 26 up: heal, cure, refresh, agility, strength, poison) and
  explosion at 1758,1405. One mixed pile each (strengths are hidden).
- By the door, a stack of six at 1758,1411: smelting 6 (bottom), 1, 3, 4, 5, 2 (top) since 2026-11-08 (the user
  restacked them). They hold about 400 stones
  each (not locked down; the user won't lock them, since the metal gets smelted soon), roughly 55-75 metal pieces.
- Trash barrel at 1758,1410: deletes after 3 minutes, or at once on the 50th item.
- New backpacks crate at 1763,1405: empty bags for sorting, and where emptied loot bags go.
- Spares pouch for ID wands and staves inside the supplies chest (top left). 220 charges on 2026-11-01.
- Johnny ("Here's Johnny", 0x0003E672): backpack 0x4079CC26 holds the user's scissors (for cutting), a saw (logs
  into boards, from 2026-11-09) and a dagger; leave all three. The user plays Johnny too: on 2026-11-08 both were gone, so cutting waited (the skill, "Where rejects go").

## Open items (2026-11-01)

- **Mining** is under way (MINING.md): the bridge now has per-character rules files (`rules/rules-<name>.json`,
  copied into the client's Agent folder), several areas, trades, casting, Hiding, mounts and the guard. For sorting
  while they're logged in, set `UO_CHAR=Johnny`: every tool then uses Johnny's bridge only (2026-11-04).
- **Bridge fix for the next client build**: in `Move`, count any message from the drop target as an answer (the
  barrel's "The trash is full! Emptying!" is spoken by the barrel, not a system message, so it causes a false stop
  that the scripts resume with `uo.resume_after_barrel_emptied`). The vault's barrel also says "The item will be
  deleted in three minutes." after every drop (2026-11-07), so each drop there stops the bridge.
- **`uo.wait_out_world_save` is too trusting** (found 2026-11-05 by the cartography session): it takes any 423 stop
  for a world save while a save's messages are among the last 15, so a real stop shortly after a save gets resumed
  and the action re-sent (12 double-clicks in a row for Clem). Fix: only count save messages newer than the stop.
  It's shared with `mine.py`, so it wasn't changed while the mining loop runs; `carto.py` guards against it itself.
- **GM sets 2 and 3** have plain (non-GM) gorgets. sortbatch puts the next GM gorgets into those sets and sends the
  plain ones to smelting.
- The effect recorder can be dropped from the client once the user is happy with the buff tracker.
- Not built: an MCP server wrapping the bridge, and an in-client "sort now" button (the user prefers asking Claude).

## History

The full working notes from those first two days are in `HISTORY.md` (a log; this file and the skill win where
they differ). Summary:

- 2026-10-31: bridge built in steps (read only, then actions, pacing, art sizes). Around 23:00 the server stalled for
  everyone just after a burst of about 55 fast opens; it wasn't the bridge, but that's why the pacing and the
  stop-on-silence rule exist.
- 2026-11-01: first sort and a re-sort under Emetah's keep list; batches 2-6 (about 1,300 items); the chest survey and
  map; GM sets; the trash barrel; crate groups; shields, leather and studded cut back to invulnerability only; the
  smelting chest replaced by crates; chest labels fixed to count rows from the top. Installed client: build cuo-agent7.
