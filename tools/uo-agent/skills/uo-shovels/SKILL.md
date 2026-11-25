---
name: uo-shovels
description: Run the user's hourly shovel-buying loop in Ultima Online with Clem through the ClassicUO agent bridge - gold from his Ocllo bank box, every tinker in the Tinkers runebook bought out of shovels on each tinker's own hourly clock, home by the "skara" rune to the castle's north yard and north door, shovels into the castle tools room. Use when the user says buy shovels, shovel runs, tinkers, the Tinkers runebook, the skara rune, blocked rune spots, or asks for the shovel status, the tools room count, gold spent on shovels, or to stop or restart the shovel loop.
---

# Buying shovels with Clem

Everything is in `~/claude/ClassicUO/tools/uo-agent`. **`SHOVELS.md` has the user's rules in their words, what's
where (runes, serials, the tinkers) and everything learned; read it first.** This skill is the short version: how to
run, watch, restart and stop it, and what to tell the user. Read the `uo` skill's rules (takeover, stop and tell, the
nightly reboot) and use the `uo-team` skill before changing shared code (tools_room.py, castle.py, Clem's rules): the
castle-sorting session uses Clem too.

## The job (the user, 2026-11-24)

"We're trying to get as many shovels as possible in the tool room." Every tinker is bought out every hour (his stock
grows when he's bought out), gold from the bank as needed, until the user says stop or a blocker (out of gold). On
stop the "skara" rune and the Tinkers runebook go back into the user's chest (938 top).

## Commands

```
python3 -I shovels_test.py                 # offline checks: run after ANY change, before (re)starting
python3 -I shovels.py run                  # a new run: counts the tools room once, then the loop
python3 -I shovels.py run --keep-count     # a restart mid-run (new code, a crash, the nightly reboot): no recount
python3 -I shovels.py stop                 # the user said stop: home, shovels away, rune + book into their chest
python3 -I shovels.py status               # clocks, stock, prices, skips, totals
python3 -I shovels.py blocked              # which rune spots were blocked how often (for the user to re-mark)
```

Run `run` in the background (`run_in_background`, output to `~/claude/uo-agent-work/shovels/run.out`); the log is
`~/claude/uo-agent-work/shovels/shovels.log`.

## Watching it: quietly

The user saw the terminal busy while nothing happened and asked if tokens were being used (2026-11-24). So:
- One Monitor, **only the STATUS line and problems**:
  `tail -n 0 -F ~/claude/uo-agent-work/shovels/shovels.log | grep -E --line-buffered 'STATUS:|STOPPED|Traceback|stopped:|player in town|unexpected|reagents low|Recall reagents'`
  Re-arm it when it expires (30 minutes). Never a filter that fires on every Recall or purchase.
- End the turn after relaying; don't sit in Yield waiting (it shows as busy). The loop waits by itself.
- When the background `run` ends (task notification), read `run.out` and the log's last lines at once: a crash or a
  STOPPED needs telling, and Clem's state checked (inside? the table locked?).

## What to tell the user

**After every trip, the STATUS line** (the user: "print a status update line here showing the current count of
shovels"; "how much gold is in the bank and how much has been spent on shovels total this run"; "also show the next
scheduled times for the vendors"):

**STATUS: Tools room N shovels** · this trip: N bought (where) · this run: N bought for G gold · bank G gold · he
carries G · next due: Britain hh:mm · ...

Plus: blocked spots that keep happening (the user wants to re-mark those runes: `shovels.py blocked`), any stop and
why, and where Clem is (always inside: the north door locked, the user's table locked).

## The user's rules, short

- **Tools room counted once per run**, never between trips or hours ("i don't want you to have to inventory 50000
  shovels and slow it down"). A restart mid-run is `--keep-count`.
- **A clock per tinker**: due 61 minutes after his list was first opened in his last cycle; trips go to whoever is due.
- **Blocked spot**: again after 15, 30, 60, 120 s, then the next tinker; that one again every 10 minutes, not the next
  hour.
- **Recall reagents** (black pearl, blood moss, mandrake root): topped up from the user's entrance chest (938 2nd)
  before trips when any is below 25, straight back to the tools room (never the great hall); in town he always keeps
  3 of each for the way home.
- **Home** is the skara rune `0x406EAA74` (by serial: its name was wiped by a second Mark; `0x408E20F9` "Skara" is the
  castle FRONT) to the north yard, the north door locked behind him. Not the great hall ("we skip it").
- A player in town: home, that tinker not for 15 minutes. Takeover: stop at once, nothing sent. Blockers (no gold in
  the bank, a rune missing, a Recall landing somewhere unexpected): home, stop, tell.

## Before changing the code

`python3 -I shovels_test.py` must pass (it caught neither crash of 2026-11-24 because it didn't exist yet: a lost
function, a set indexed like a list). Add a check for whatever went wrong. Restart with `--keep-count` only while
Clem is waiting in the tools room (`waiting in the tools room:` in the log), never mid-trip. Commit and push to
`fork`; tell castle-sorting when tools_room.py, castle.py or Clem's rules change.

This skill lives at `tools/uo-agent/skills/uo-shovels/SKILL.md`, linked from `~/.claude/skills/uo-shovels/SKILL.md`.
If the link is missing: `mkdir -p ~/.claude/skills/uo-shovels && ln -sf
~/claude/ClassicUO/tools/uo-agent/skills/uo-shovels/SKILL.md ~/.claude/skills/uo-shovels/SKILL.md`.
