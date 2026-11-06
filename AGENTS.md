# Notes for agents working on this fork

This is the user's fork of ClassicUO (github.com/matbess/ClassicUO-ext). All of the user's changes are on the branch
**`extensions`**, on top of upstream commit `ee79d7e` (ClassicUO 1.1.0.347). Remotes: `fork` is the user's repository
(push here), `origin` is upstream ClassicUO (never push there).

## The user's setup

- They play Ultima Online on an Intel Mac through the Sikarugir Wine wrapper `~/Applications/Sikarugir/ClassicUO-Wine10.app`.
  The client lives in its Wine prefix at `drive_c/ClassicUO`, with Razor CE (`~/Games/Razor`); `Play.bat` starts several
  clients sharing one `settings.json`.
- The server is a private one based on the UOSA (Second Age, T2A-era) server code, hosted elsewhere by someone who no
  longer plays. Besides the user's brother (who cooperates) there are now a couple of other players (2026-11-01).
  There's no moderation now, but the user wants to be safe if old rules come back: mining is paced slower than a
  person would bother to be (see MINING.md, "Pacing"); nothing else is (see "Pacing is for mining only" below).
  Staff get the normal guard like anyone
  else (the user, 2026-11-04: the old stand-still-and-tell-the-user rule for staff is gone).
- `UOSecondAge.app` is the original UOSA launcher: leave it untouched. Game data files: `~/Games/UOSA-data`.
- "Crashes" have turned out to be server-side disconnects before; check the macOS log (tcp_connection_summary) before
  assuming the client crashed. Razor.exe is IL-patched for a runebook gump crash; WINEDEBUG is `fixme-all`.

## Rules from the user

- **Don't mess up the running game.** Never install, smoke test or run `wineserver -k` while their clients run; ask
  them to close the clients, and ask before installing. Back up `cuo.dll`/`cuo.pdb` first (`tools/build/install.sh`).
- Never expose the account password: don't copy their `settings.json`, and don't use `-packetlog` (it logs the password).
- Check source out under `~/claude`, not a temporary folder.
- Commit and push to `fork` when the user asks (they have said yes to pushing tool and doc changes as they settle).
  Commit identity is set in the repository: matbess <1884731+matbess@users.noreply.github.com>. Push access is a
  repo-only deploy key (`~/.ssh/github_classicuo`, ssh host alias `github-classicuo`). No `gh` CLI on the Mac.
- Don't draft feedback reports about the session.
- **Pacing is for mining only** (the user, 2026-11-05: "for johnny too, for everyone"). Only Icepick's digging out in
  town has the slow, human-like pacing (MINING.md, "Pacing"). Everything else runs at **full speed**: inside the
  tower or house (Johnny's sorting, Clem's cartography, Icepick's smithing) and the bank (mine.py switches Burgers to
  quick pacing there). Full speed is the bridge's floor of 1.1 s between requests, no breaks, and no waits added in
  scripts: in the rules file `"pacing": { "gap": [1100, 1100], "burst": 1000, "break": [1100, 1100], "aim": [0, 0] }`.

## What the fork adds (one commit per feature)

| Feature | Profile key | Where |
|---|---|---|
| Forgiving item pick-up range | `forgiving_pick_up_range` | item pick-up |
| Info bar items one per line | `info_bar_vertical` | info bar gump |
| Buff tracker: works out buffs and debuffs on servers that send no buff packets (UOSA), from stat changes, flags, light, body, spell sounds and effects, words and messages | `track_buffs` (on by default) | `Game/Managers/BuffTracker.cs` |
| Option to hide the buff bar frame and rotate gem | `buff_bar_frame` (on by default) | buff gump |
| Effect recorder for studying buff signals (logs to `Logs/Effects`); can be dropped once the tracker is settled | `record_effects` | `Network/EffectRecorder.cs` |
| **Agent bridge**: a local HTTP API that lets an agent such as Claude see the game and act as one character | `agent_bridge` (Options > Experimental) | `Game/Managers/AgentBridge.cs`, hooks in `World.cs` and `Network/PacketHandlers.cs` |

The agent bridge and its tools are how Claude sorts the user's loot (as Johnny), mines (as Icepick, with
Burgers banking) and trains Cartography (as Clem). Everything about the bridge and sorting lives in
**`tools/uo-agent/AGENTS.md`**; mining is in **`tools/uo-agent/MINING.md`** (the user's rules, the route, the guard,
everything tested) and `mine.py`; cartography is in **`tools/uo-agent/CARTO.md`** and `carto.py`.

## Other tools in this repository

- `tools/uo-agent/`: the agent tools for sorting, mining and cartography (see its AGENTS.md).
- `tools/build/`: building, smoke testing and installing the client on the Mac.
- `tools/effects/`: the effect recorder's log decoder and a replay harness for the buff tracker.

## Building and installing

See **`tools/build/README.md`**: `build.sh NAME`, `smoke.sh NAME`, `install.sh NAME BACKUP_NAME`. The installed build
is the latest `cuo-agentN` in `~/claude/builds` (cuo-agent21, bridge 7, as of 2026-11-06 21:55); backups of every earlier install are in
`~/Games/backups/classicuo-1.1.0.347-*`.
