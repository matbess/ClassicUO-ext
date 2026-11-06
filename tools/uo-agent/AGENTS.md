# The sorting agent: notes for a new session

Claude sorts the user's Ultima Online loot by playing one of their characters through the **agent bridge** built
into their ClassicUO (`src/ClassicUO.Client/Game/Managers/AgentBridge.cs`). This folder holds the tools Claude drives
it with, the house's labels and chest map, and the procedure.

**Mining** (Icepick and Burgers, from 2026-11-01): read `MINING.md` first; the loop is `mine.py`.

**Cartography** (Clem, from 2026-11-05: world maps from the map bags on the tower's second floor, outside the
vault, and trips to the map vendor): read `CARTO.md` first; the tool is `carto.py`, Clem's rules
`rules/rules-Clem.json` (no guard).

**Blacksmithing** (Icepick, from 2026-11-05: training to 100 at the forge and anvil on the tower's ground floor,
crafting and smelting back): read `SMITHING.md` first; the tool is `smith.py`, the rules
`rules/rules-Icepick-smith.json` (no guard, no pacing). Bridge 6 (build cuo-agent19) adds menus, gumps, target
cursors, skills and an event log that records what the user does by hand (`uo record`).

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
| `survey.py`, `layout.py` | | open every chest and record the map in `layout.json` (`--known` sends nothing and checks labels against positions); print the map |
| `tidy.py` | | re-lay a crowded chest's bags in one row with markers under them |
| `moves.py`, `potions.py` | | a list of moves at the bridge's pace; potions by strength (the server hides strengths) |
| `mine.py`, `carto.py` | | the mining loop (MINING.md) and Clem's cartography (CARTO.md) |

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
- By the door, a stack of six at 1758,1411: smelting 6 (bottom), 5, 1, 2, 3, 4 (top). They hold about 400 stones
  each (not locked down; the user won't lock them, since the metal gets smelted soon), roughly 55-75 metal pieces.
- Trash barrel at 1758,1410: deletes after 3 minutes, or at once on the 50th item.
- New backpacks crate at 1763,1405: empty bags for sorting, and where emptied loot bags go.
- Spares pouch for ID wands and staves inside the supplies chest (top left). 220 charges on 2026-11-01.
- Johnny ("Here's Johnny", 0x0003E672): backpack 0x4079CC26 holds the user's scissors (0x40849C45) and a dagger;
  leave both.

## Open items (2026-11-01)

- **Mining** is under way (MINING.md): the bridge now has per-character rules files (`rules/rules-<name>.json`,
  copied into the client's Agent folder), several areas, trades, casting, Hiding, mounts and the guard. For sorting
  while they're logged in, set `UO_CHAR=Johnny`: every tool then uses Johnny's bridge only (2026-11-04).
- **Bridge fix for the next client build**: in `Move`, count any message from the drop target as an answer (the
  barrel's "The trash is full! Emptying!" is spoken by the barrel, not a system message, so it causes a false stop
  that the scripts resume with `uo.resume_after_barrel_emptied`).
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
