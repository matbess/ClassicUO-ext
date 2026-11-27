---
name: uo-burgers
description: Top up Burgers with shovels and reagents in Ultima Online - Clem takes bags of 50 shovels from the castle tools room and Burgers' four reagents (black pearl, blood moss, mandrake root, sulfurous ash) to the Ocllo bank, trades them to Burgers (2 bags into his bank, the 3rd in his pack for Icepick), brings the empty backpacks home. Use when the mining agent or the user says Burgers needs shovels or reagents, Burgers is out of shovels, or asks to restock or top up Burgers' bank.
---

# Shovels and reagents for Burgers

Everything is in `~/claude/ClassicUO/tools/uo-agent`. **Read `BURGERS.md` first** (the user's rules in their words,
what's where). Read the `uo` skill's rules (takeover, stop and tell, nightly reboot) and the `uo-team` skill: this job
drives Burgers, who is the mining session's, and Clem, whom the shovel loop and castle-sorting use.

## When it's asked for

1. **Who asked.** Usually the mining session messages "Burgers needs shovels" (maybe with reagent numbers). The user
   asking is the handback for Clem (and Burgers): `uo --char NAME handback` if one shows `takenOver`.
   **When the mining session asks, do it on your own: no asking the user** (2026-11-26: "when I'm done playing him I
   want you to automatically give shovels to burgers when the mining agent asks you for some"). The one exception is
   Clem showing `takenOver` because the user is playing him. Then tell the user that mining needs shovels, and start
   once they hand him back.
2. **Burgers must be free.** The mining session stops its loop and parks him first (its message says so). Check
   `ps -axo command | grep -E '[m]ine\.py|[l]umber\.py|[h]eal\.py'`: anything running, message the mining session
   and wait (`notify_when_idle`). Never drive Burgers while its loop runs.
3. **The shovel loop.** If `shovels.py run|resume` is running: `shovels.py pause`, say so, wait for it to exit
   (`waiting in the tools room` / its task ends), stop its Monitor.
4. `python3 -I burgers_test.py`, then run in the background:
   `python3 -I burgers.py run [--reagents '...'] > ~/claude/uo-agent-work/burgers/run.out 2>&1`
   and a Monitor: `tail -n 0 -F ~/claude/uo-agent-work/burgers/burgers.log | grep -E --line-buffered 'trip [0-9]|FINAL:|STOPPED|Traceback|TOPUP:|needs:'`
5. When it ends: read `run.out` and the log's tail. Then:
   - the shovel loop resumed if it was paused (`shovels.py resume` in the background, its Monitor again);
   - **tell whoever asked, only them**: the mining session if it asked ("shovels and reagents topped up: ...", the
     FINAL line, Burgers hidden at the bank with his guard off, his rules put back), or the user if they asked.

## Rules, short

- Burgers' pack to 50 and his bank to 250 of each of the four reagents unless the asker gives numbers (`--reagents`).
- 3 bags: the first 2 into his bank whole, the 3rd stays in his pack for Icepick.
- He must have 253 stones free before each bag trip; if not it stops: tell the user ("he can't hold a bag").
- The bags first (bag trips carry only the bag), then the reagents on trips of their own; Clem never over his max less 10.
- Empty backpacks from his bank and pack (never mine.py's spare-shovel bag) go home to the spare backpacks chest.
- Clem ends in the tools room with the user's table locked; the skara rune back in the user's chest unless it's the
  shovel loop's kit. Problems: stop, Clem home, tell.

This skill lives at `tools/uo-agent/skills/uo-burgers/SKILL.md`, linked from `~/.claude/skills/uo-burgers/SKILL.md`.
