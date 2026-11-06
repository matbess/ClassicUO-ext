# uo-agent

Command-line tools for the client's agent bridge (`src/ClassicUO.Client/Game/Managers/AgentBridge.cs`).
They let an agent such as Claude look at the game and act as a character, for example to identify loot with ID
wands and sort it into a house's chests.

- **`AGENTS.md`**: how the pieces fit, the user's house and chest wall, open items and history. Start here.
- **`MINING.md`** and **`CARTO.md`**: mining (Icepick and Burgers, `mine.py`) and cartography (Clem, `carto.py`).
- **`COMBAT.md`**: Clem's fights and the tower's front door (`fight.py`, `door.py`, `fight_scenes.py`).
- **`skills/uo-sort/SKILL.md`**: the sorting procedure, safety rules, server lessons and keep rules (installed as
  the user-level Claude skill `uo-sort` by a symlink).

## Setup

1. Tick Options > Experimental > "Agent bridge: let Claude use this character (this computer only)" on the
   character that should do the work. While that character is logged in, the client writes
   `Agent/<character>.json` (port and token) next to `ClassicUO.exe`.
2. Put `Agent/rules.json` next to the client (this folder's `rules.json` is the user's house). Nothing that changes
   the game is allowed without it:

   ```jsonc
   {
     "map": 0,
     "area": [x1, y1, x2, y2],      // where the agent may work
     "z": [minZ, maxZ],
     "offLimits": ["0x40000000"],  // containers to leave alone
     "neverTouch": ["0x1766"],     // item graphics never to pick up from the floor
     "useFromBackpack": ["0x0F9E"],// tools that may be used from the backpack (scissors)
     "ignorePeople": [],           // characters that don't pause the agent
     "pacing": { "gap": [1100, 1100], "burst": 1000, "break": [1100, 1100] }  // full speed (1.1 s is the floor)
   }
   ```

3. `uo.py` looks for the bridge in `AGENT_DIR` (a Wine prefix on macOS). Change it if the client lives elsewhere.
   `~/claude/uo-agent` is a symlink to this folder.

## Commands

Run `./uo --help` for the list. Highlights:

- `uo status`, `uo nearby`, `uo item S`, `uo contents S`, `uo messages`, `uo actions`: read only, nothing is sent
- `uo open`, `uo name`, `uo walk`, `uo move` (`--at X Y`, `--amount N`), `uo equip`, `uo use`: act, paced by the bridge
- `uo label S TEXT`, `uo labels`: remember what a container is for (`labels.json`); labels work anywhere a serial does
- `uo clear` / `uo waitclear`: is anyone else in the area / wait until nobody is
- `uo resume`: carry on after the bridge stopped because the server went quiet

A sorting batch, step by step (see the skill for the details):

1. `look.py BATCHDIR`: find the loot on the floor, open every container in it, write `inv.json`, `loot.json`, `targets.txt`
2. `idall.py $(cat BATCHDIR/targets.txt)`: name everything, identify only the "magic" items, swapping ID wands
3. `plan.py BATCHDIR`: apply the keep rules and write `spec.json`
4. `sortbatch.py BATCHDIR/spec.json`: carry out the spec
5. `finish.py`: ID wand back to the spares pouch, character to the middle of the room

Other tools: `survey.py` (open every chest and record the map in `layout.json`; `--known` sends nothing and checks
labels against where chests stand), `layout.py` (print the map), `tidy.py` (re-lay a crowded chest), `moves.py` (a
list of moves at the bridge's pace), `potions.py` (potions by strength, where the server reveals it).

`labels.json`, `layout.json`, `names.json`, `rules.json` and the serials at the top of `idall.py`, `sortbatch.py`
and `finish.py` describe one particular house; change them for any other.
