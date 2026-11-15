# Carpentry: Icepick to 100 (from 2026-11-14)

The user, 2026-11-14: raise Icepick's Carpentry to 100 (GM), crafting from the boards on the chest-room floor and
throwing everything made into the trash barrel next to him. Keep the loop going until 100.

## The user's table (by the displayed value, not the base)

| Carpentry | Item | Materials |
|---|---|---|
| 30 - 37 | small crate | 8 boards |
| 37 - 47 | medium crate | 15 boards |
| 47 - 55 | ballot box deeds | ? |
| 55 - 68.4 | wooden shields | ? |
| 68.4 - 74 | fishing poles (need Tailoring 40.0 displayed) | 5 boards + 5 cloth |
| 74 - 80 | quarter staff | ? |
| 80 - 100 | gnarled staff | ? |

At the start: Carpentry 40.2 (base 23.1: his stats add about 17), Tailoring 40.1 (base 31.9, just over the 40 the
fishing poles need).

## Where everything is (chest room, z 26)

- Icepick stands at 1759,1410, mounted. Everything is within reach, so he never walks.
- Boards: two piles on the floor, 1760,1409 and 1760,1410 (79k on 2026-11-14). Half a stone each; he carries up to
  500 (the user).
- Cloth: a pile at 1759,1408 (1,750 from 35 bolts: **a bolt cuts into 50 cloth**, checked 2026-11-14). Estimated use
  for the fishing poles: about 3,600 (950 crafts; a failure loses about half the materials), the user is getting 5,000.
- Saws: his pack, then any container in his corner (1758-1761, 1408-1410): the small crate at 1760,1408 and three crates at 1761,1408-1410 (2026-11-14). About 51 crafts a saw at first (79, 57, 19).
- Trash barrel at 1758,1410.
- Rules: `rules/rules-Icepick-carp.json`, an area of just that corner. The house's green decoration is cut cloth too,
  so cut cloth isn't in "neverTouch" here; the small box keeps him off the decoration.

## How this server does it (2026-11-14)

- Double-click the saw: "What type of item do you want to craft?": Other, Furniture, Containers, Misc. Add-Ons (more
  as the skill rises). Then "What do you want to make?" ("medium crate: 15 Boards or Logs"). Each menu only lists
  what he can make now. **No Make Last Item**, so every craft goes through both menus (about 8 s a craft).
- "You create the item." or "You failed to create the item, and some of your materials are lost." A crate also gets
  "Your tinker skill was sufficient to make the item lockable." and a key inside.
- **Razor's "Auto search new containers"** double-clicked the first crate 2 ms after it was made, and the bridge took
  it for the user taking Icepick over. The user turned it off in Icepick's Razor profile (2026-11-14).
- Moving boards from the floor onto his stack gets no answer from the server, so the bridge stops as if the server
  went quiet; `carp.py` checks his count went up and resumes.

## The loop (`carp.py`)

- `python3 -I carp.py run` (background task), `stop`, `report`, `rules`. Log and state in
  `~/claude/uo-agent-work/carp` (`carp.log`, `state.json`).
- Each time round: a saw (the next from the crate when one wears out), boards topped up to 500 when under 40 (400 plus
  300 cloth for fishing poles), the item for the current value through both menus (the category is found once and
  remembered in `places`), the result, and anything new in his pack into the barrel. Leftovers named exactly like a
  crafted item are binned at the start.
- Out of saws, boards or cloth: logs "WAITING: ..." and looks every minute without sending anything, then carries on.
- Stops on the user taking over, at 100, or on anything it doesn't understand (an item on none of the menus: a
  different name on this server).
- Watch: `tail -n 0 -F ~/claude/uo-agent-work/carp/carp.log | grep -E --line-buffered "start:|now making|is under|STOPPED|WAITING|back \(|wore out|took saw|saws low|supplies:|interrupted|lagged|answered again|Carpentry [0-9.]+ -> [0-9]+(\.0)? after|Traceback|Error"`.

## Progress

- 2026-11-14 16:00: started at 40.2 on medium crates.
