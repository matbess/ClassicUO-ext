# Healing: bandages on a ghost

The user's way to train Healing (2026-11-08): a character stands next to another of their characters who is a ghost
and bandages them over and over. Each bandage is a resurrection attempt, and each one is a chance to gain. The first was
Burgers (Healing 98.4, Anatomy 100), with Isabel's ghost a tile south of him on the tower's ground floor and the pile of
clean bandages (0x408DD58F, 4,770) on the floor a tile east. The goal is 100.0. The tool is `heal.py`, and it works for
any character and patient (`--char`, `--patient`, `--bandages`), with a `rules/rules-<char>-heal.json` for each.

## How this server does it

Recorded from the user doing it by hand with a Razor macro (blackbox, 2026-11-08 01:17):

1. Double-click the bandages (they can lie on the floor within reach): "Who will you use the bandages on?" and a
   target cursor.
2. Aim at the ghost: "You begin applying the bandages."
3. About 9.5-9.9 s later: "You are able to resurrect your patient." or "You are unable to resurrect your patient."
   Each attempt uses one bandage. "Able" sends the ghost a resurrection offer; **don't accept it on her client**, or
   she comes back to life and there's nothing left to train on (heal.py stops if she's alive).
4. **A new bandage before the last one ends cancels it**, and nothing is learned. The user's first six, 6-8 s apart,
   gave no result at all. So heal.py starts the next one the moment one ends, about every 10 s (the user: "every 10
   seconds"); a fixed 10 s timer would sometimes cut one off just short.

Burgers' first run: one bandage every 10.0 s, results after 9.5-9.8 s.

## The bridge (bridge 10, build cuo-agent27, installed 2026-11-08)

Before bridge 10 the bridge only double-clicked an item in the hands, a tool from the pack or the door's key ring, and
never aimed a cursor at a person. Two rules entries were added:

- `"useOnGround": ["0x0E21"]`: kinds the character may double-click where they lie, inside the area and within reach
  (2 tiles). 0x0E21 is clean bandages.
- `"patients": ["0x000431CC"]`: the user's own characters (serial or name) that `/use?serial=&target=` may aim an
  item's cursor at, within 2 tiles (a bandage reaches 1 on this era's server). Isabel is named by serial only, so
  nobody else called Isabel can be aimed at.

`/use` on a patient answers once "You begin applying the bandages." comes, with the patient's state (`patient`: dead,
hits, distance). The result comes ~10 s later in the messages; heal.py reads them.

## The rules: `rules/rules-Burgers-heal.json`

A small box round where he stands (1755-1758, 1407-1410, z 0-25); the three chests there are off limits; no guard
and no pausing (inside the locked tower); full speed; `handOver`: anything the user does with Burgers themselves stops
the loop until they hand him back (`python3 -I uo.py --char Burgers resume`, then run again). heal.py copies it into
the client's `Agent/rules-Burgers.json` and puts his mining rules back when it ends; mine.py writes the mining ones at
its start anyway.

**Burgers is also the mining loop's banker, and maybe lumberjacking's.** Check with the user (and any other session
using him) before running heal.py with him, and stop it with `heal.py stop` before mining or lumberjacking needs him.

## Running it

```
cd ~/claude/ClassicUO/tools/uo-agent
python3 -I heal.py run                 # Burgers on Isabel with the floor pile, until Healing 100.0
python3 -I heal.py stop                # ends after the bandage under way
python3 -I heal.py report              # bandages, results, gains
```

Run it in the background from a Claude session. It sends nothing between bandages and only reads (messages, skills),
so it costs no tokens while it runs. Log: `~/claude/uo-agent-work/heal/heal.log` (one line a bandage, with the skill
and any gain); state in `state.json` there.

It stops by itself when the skill reaches the target or cap (DONE). It also stops (STOPPED) when:
- the patient is alive, out of sight, or more than a tile away;
- the bandages are gone;
- the user took the character over;
- the server goes quiet more than 5 times in an hour (a world save, or a lag the server answers after, is waited out
  and resumed);
- the client doesn't come back within 30 minutes of losing the server (the nightly reboot at about 04:15 is waited
  out: the clients log back in by themselves about 4 minutes later).

## Progress

- 2026-11-08 01:35: started, Burgers Healing 98.4 base (98.6 shown), 4,770 bandages.
- 2026-11-08 04:15: 99.2 after 930 bandages (2 h 40 m; a +0.1 every 1-55 minutes, slower near 99: 98.9 to 99.0 took
  32 min, 99.1 to 99.2 took 56). The nightly server reboot dropped the client and heal.py stopped on the lost
  bridge; it now waits for the client to log back in (up to 30 minutes) and carries on. The reboot rolls the world
  back about 15 minutes, so a gain just before 04:15 can be lost.
