---
name: uo
description: Help the user automate something in Ultima Online through their patched ClassicUO's agent bridge (Claude plays one of their characters - Clem, Icepick, Burgers, Johnny - from scripts in ~/claude/ClassicUO/tools/uo-agent). Use when the user types /uo with a task, asks to automate, script, train, gather, craft, sell or run something in UO, or asks to start, resume, pause or change one of the existing UO loops (mining, lumberjacking, carpentry, cartography, gems, healing, fighting).
argument-hint: <what to automate or run in UO>
---

# Automating Ultima Online through the agent bridge

The user's request: **$ARGUMENTS**

The user plays Ultima Online (a private, T2A-era server based on the UOSA code) in their own fork of ClassicUO under
Wine on this Mac. The fork has an **agent bridge**: a local HTTP API inside each client that lets Claude see the game
and act as that character. Claude automates things by writing Python loops in `tools/uo-agent/` that drive the
bridge, then running and watching them. Everything learned is written in the repo, not in Claude's memory.

Repo: `~/claude/ClassicUO` (github.com/matbess/ClassicUO-ext, branch `extensions`; `~/claude/uo-agent` is a
symlink to `tools/uo-agent`). This skill lives at `tools/uo-agent/skills/uo/SKILL.md` and is linked from
`~/.claude/skills/uo/SKILL.md`: when something about *how to work* changes, edit it here and commit.

## 1. Get oriented (every session, before touching a character)

1. Read `~/claude/ClassicUO/AGENTS.md` (the Mac/Wine setup, the user's rules, pacing, building) and
   `tools/uo-agent/AGENTS.md` (how the bridge and tools fit, the takeover rules, the house, every project).
2. Find out whether the request is an **existing project** and read its doc in full before acting:

   | Project | Character(s) | Doc | Tool |
   |---|---|---|---|
   | Sorting loot in the chest room | Johnny (Clem when Johnny is offline) | `skills/uo-sort/SKILL.md` | look/idall/plan/sortbatch/finish |
   | Mining in town, banking | Icepick + Burgers | `MINING.md` | `mine.py` |
   | Lumberjacking in town | Icepick + Burgers | `LUMBERJACKING.md` | `lumber.py` |
   | Carpentry to 100 | Icepick | `CARPENTRY.md` | `carp.py`, `chests.py` |
   | Blacksmithing, smelting vault junk | Icepick | `SMITHING.md` | `smith.py`, `vault.py` |
   | Cartography, map vendor trips | Clem | `CARTO.md` | `carto.py`, `trips.py`, `drawing.py` |
   | Selling gems to jewelers | Clem | `GEMS.md` | `gems.py` |
   | Fighting, the tower's front door | Clem | `COMBAT.md` | `fight.py`, `door.py`, `restock.py` |
   | Healing on a ghost | Burgers | `HEALING.md` | `heal.py` |
   | Cooking fish steaks for Intelligence | Icepick | `COOKING.md` | `cook.py` |
   | The Castle (new home, 2026-11-18): getting in, its chests, the move from the tower | Clem | `CASTLE.md` | `castle.py` |

   Each doc ends with how to run it, what the user's words mean, and what to tell them. `HISTORY.md` is old notes.
3. **Check what else is going on.** Several Claude sessions work on the same characters.
   - `ListAgents` shows the peer sessions; the transcripts are in `~/.claude/projects/-Users-mat-claude/*.jsonl`
     (newest first with `ls -lt`; pull the user's recent messages out with a short `python3 -I` script).
   - Running loops: `ps -axo pid,command | grep -E '[m]ine\.py|[l]umber\.py|[c]arp\.py|[h]eal\.py|[c]arto\.py|[f]ight\.py|[g]ems\.py|[t]rips\.py'`.
   - `git -C ~/claude/ClassicUO status --short`: uncommitted changes are another session's work in progress.
     Don't edit those files. Get them committed so they aren't lost: ask that session, or commit them yourself in a
     separate commit (the `uo-team` skill, "Commits").
   - **Before changing the bridge or common code, building or installing, or asking for the clients to close, use
     the `uo-team` skill:** find the other sessions and message them first (the user, 2026-11-18).
   - Never run two loops on the same character (mining, lumberjacking, carpentry, smithing and cooking all use Icepick;
     Burgers banks for mining and lumberjacking). If another session owns the character, ask the user, or message
     that session with `SendMessage`.
4. Look at the characters, read-only (nothing is sent to the server):
   `~/claude/uo-agent/uo --char NAME status`, `uo --char NAME nearby 14`, `uo --char NAME messages`.
   "No agent bridge is running" means that character isn't logged in with the bridge ticked.

## 2. The user's rules (all of them hold everywhere)

- **Don't mess up the running game.** Never build-install, smoke test or `wineserver -k` while their clients run;
  ask first, and back up with `tools/build/install.sh`. Never expose the password: don't copy `settings.json`, never
  use `-packetlog`. Leave `UOSecondAge.app` alone.
- **Full speed** everywhere: 1.1 s between requests (the bridge's floor), no breaks, no `time.sleep` between
  actions in scripts. Rules files use `"pacing": { "gap": [1100, 1100], "burst": 1000, "break": [1100, 1100],
  "aim": [0, 0] }`. Mining's and lumberjacking's town pacing is behind `pacing.py on|off`, off; only the user
  turns it on.
- **The user taking over.** Every rules file has `"handOver": true`: the user giving a character a command
  themselves makes its bridge refuse everything (423, `takenOver`). Scripts catch `uo.TakenOver` and stop at once,
  sending nothing more to that character. Never resume over it on your own. **But** any request from the user that
  needs a character *is* the handback: run `uo --char NAME handback` and do it, no asking, and mention it in a line.
- **Stop and tell on problems.** When something doesn't match the plan (an item missing, an unexpected answer), the
  script stops and Claude tells the user what it found. No workarounds, no fallbacks, no changing the user's tables
  on its own: offer, then wait. Routine recoveries (world saves, lag, the ~04:15 nightly reboot) carry on.
- **"Pause"** means within seconds. A `--park` that waits out the current step can take minutes: start it at once
  and say so in the same reply, and that they can just take over.
- **Clem outside the tower:** never unwatched, never standing among creatures, always parked back inside in the safe
  zone with the front door locked and closed (COMBAT.md). Never kill a running `fight.py`.
- **Messages:** the user reads on their phone. Put any **Question:** or **Offer:** first, marked, and keep the rest
  short. No push notifications; no feedback drafts. Items taken from the vault chests are normal: don't report them.
- Commit to the repo as features settle and push to `fork` when the user has said yes (they have for tool and doc
  changes). Commit identity is already set in the repo. Never push to `origin`.

## 3. Automating something new

1. **Pin down the task** with the user only where the docs and the game can't answer: which character, where, what
   counts as done, what to do with the output, what should stop the loop. Their earlier decisions in the project
   docs win over a guess.
2. **See how it's done by hand.** Ask the user to do it once while `uo --char NAME record FILE` follows the bridge's
   event log (menus, gumps, target cursors, messages, and what they clicked), or read `blackbox.py --show N`. Learn
   the exact server wording from that, not from RunUO memories: this server differs.
3. **Check the bridge can do it.** The bridge (`src/ClassicUO.Client/Game/Managers/AgentBridge.cs`, plus
   `AgentBridgeDialogs.cs`, `AgentBridgeShop.cs`; version and what each version added in the `VERSION` comment)
   refuses anything its rules file doesn't allow. `uo --help` lists every endpoint. Most new jobs only need a new
   **rules file**: `rules/rules-<Name>-<job>.json` copied over `Agent/rules-<Name>.json` in the client folder
   (`uo.AGENT_DIR`) by the tool's `rules` step, and the character's usual rules put back afterwards (see `heal.py`,
   `carp.py`). Keys: `area`/`areas`, `z`, `offLimits`, `neverTouch`, `useFromBackpack`, `useOnGround`, `patients`,
   `partners`, `say`, `spells`, `skills`, `mounts`, `doors`, `fight`, `handOver`, `guard`, `pacing`, vendors.
   Rules files take effect at once, no build. If the bridge itself needs a new ability, that's a client change:
   build with `tools/build/build.sh cuo-agentN`, bump `VERSION`, and ask the user before installing (they close
   their clients). The installed build is in the root AGENTS.md.
4. **Write the tool** in `tools/uo-agent/` on the pattern of the existing ones (`heal.py` is the smallest complete
   loop; `carp.py` a crafting loop; `mine.py` the biggest): Python 3, standard library only, run as
   `python3 -I tool.py run|stop|report|rules`; `import uo` for everything (`uo.find_bridge`, `uo.call`,
   `uo.TakenOver`, `uo.taken_over`, `uo.login_routine`, `uo.wait_out_world_save`, `uo.move`, `uo.walk_near`);
   a module docstring that says what it does and how this server answers; state and log in
   `~/claude/uo-agent-work/<job>/`; a stop file so `stop` ends it cleanly after the current step. The strategy lives
   in the script, not in Claude's turns: Claude's turns are slow and cost tokens.
5. **Write the doc**: `tools/uo-agent/<JOB>.md` with the user's rules for the job (quoted, dated), what was tested,
   how to run and watch it, what to tell the user. Add a paragraph to `tools/uo-agent/AGENTS.md` and a row to the
   table in section 1 of this skill.
6. **Try it small, then run it** in the background (`run_in_background`), and watch it with `Monitor` on its log
   for the events the user cares about. Relay those as short messages. When it's done (or the user says stop),
   stop: no loops or checks left running.
7. Commit (doc and tool together, a message saying what and why).

**Estimating skill or stat training** (the user, 2026-11-17): read `SKILLGAIN.md` first: the curve measured on this
server across every training run (attempts per 0.1 by band, multipliers for projecting, "too easy means no gains",
what's known about stats). Never project the early rate straight on. Record the work per 10-point band of the
skill (`cook.py`'s `bands` is the pattern), say the estimate is a floor that will rise, and write each finished
band's numbers into the job's doc so the next estimate starts from real data.

## 4. Running or changing an existing loop

Follow its doc's "running it" section exactly: how it starts, the park/stop commands (e.g. `mine.py --park`, never
`pkill`), the nightly reboot steps, and what the user's short phrases mean. When a short phrase seems to override a
documented rule, ask first. New decisions from the user go into that doc (dated, in their words) and get committed.
