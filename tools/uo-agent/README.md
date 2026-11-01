# uo-agent

Command-line tools for the client's agent bridge (`src/ClassicUO.Client/Game/Managers/AgentBridge.cs`).
They let an agent such as Claude look at the game and act as a character, for example to identify loot with ID
wands and sort it into a house's chests.

## Setup

1. Tick Options > Experimental > "Agent bridge: let Claude use this character (this computer only)" on the
   character that should do the work. While that character is logged in, the client writes
   `Agent/<character>.json` (port and token) next to `ClassicUO.exe`.
2. Write `Agent/rules.json` next to the client. Nothing that changes the game is allowed without it:

   ```jsonc
   {
     "map": 0,
     "area": [x1, y1, x2, y2],      // where the agent may work
     "z": [minZ, maxZ],
     "offLimits": ["0x40000000"],  // containers to leave alone
     "neverTouch": ["0x1766"],     // item graphics never to pick up
     "ignorePeople": [],           // characters that don't pause the agent
     "pacing": { "gap": [1200, 2000], "burst": 5, "break": [3000, 5000] }
   }
   ```

3. `uo.py` looks for the bridge in `AGENT_DIR` (a Wine prefix on macOS). Change it if the client lives elsewhere.

## Commands

Run `./uo --help` for the list. Highlights:

- `uo status`, `uo nearby`, `uo contents SERIAL`: read only, nothing is sent to the server
- `uo open`, `uo name`, `uo walk`, `uo move`, `uo equip`, `uo use`: act, paced by the bridge
- `uo label SERIAL TEXT`: remember what a container is for (`labels.json`); labels work anywhere a serial does
- `uo clear` / `uo waitclear`: is anyone else in the area / wait until nobody is
- `uo resume`: carry on after the bridge stopped because the server went quiet
- `idall.py SERIAL...`: identify items in a batch, swapping in a spare ID wand when one runs out
- `sortbatch.py SPEC.json`: sort a batch of loot into the chests, from a spec saying where the gear goes
- `survey.py`: open every chest once and record its bags, markers and piles in `layout.json`; `layout.py` prints that map

`labels.json`, `layout.json` and the serials at the top of `idall.py` and `sortbatch.py` describe one particular house;
change them for any other.
