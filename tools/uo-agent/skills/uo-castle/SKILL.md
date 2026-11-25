---
name: uo-castle
description: Run the user's Ultima Online castle with Clem through the ClassicUO agent bridge - sorting the incoming loot (the dump chests and the bags on the forge room floor) and putting it away, the tools room (shovels and lumberjacking axes in stacked backpacks), the spare backpacks chest, topping up the user's entrance reagent chest, taking reagents out for another character, the user's loot bag in Clem's pack, and the vault page. Use when the user mentions the castle, shovels, axes or hatchets to put away, the tools room, backpacks, the reagent chest, reagents for Burgers or another character, the dump chests, intake loot, sorting, or Clem's bag.
---

# Running the castle with Clem

The user lives in the **castle** now (2026-11-21: "we live in the castle now"); the tower isn't managed any more.
Clem runs it: he sorts what the user brings home, keeps the tools room, and keeps the user's reagents topped up.
Everything is in `~/claude/ClassicUO/tools/uo-agent` (`~/claude/uo-agent` links to it). **`CASTLE.md` has the
details and the user's exact words for every rule here; read the section for the job before doing it.** This skill is
the short version: what each job is, the command, and what to tell the user.

## Before any job

1. **A request that needs Clem is the handback** (memory `start-means-handback`): if he's taken over (`takenOver`,
   or a 423 "the user took over"), run `uo --char Clem handback` and go on; say so in one line afterwards. Never hand
   him back without a request, and never mid-run.
2. **Another session may be driving Clem**: from 2026-11-24 an hourly shovel-buying loop (`shovels.py`, its own
   session) takes him to the tinkers and back. `ps` for it and `ListAgents` (the `uo-team` skill); if it runs,
   message its session to park him between rounds before you touch him, and never drive him while it does.
3. `uo --char Clem status`: where he is. The tools come in by themselves from the entrance room, the courtyard or
   the front (`castle.go_in`: window restock, the courtyard rune, the central door locked behind him).
4. Changing shared code (uo.py, rules, labels, layout, the bridge): the `uo-team` skill first. Commit and push your
   own changes to `fork` as they settle.
5. Long jobs run in the background with their output in `~/claude/uo-agent-work/castle/*.out`; read it when it ends.

## Rules that are always on

- **Doors always end locked and closed. The user's table** (943,2323) stands across the corridor and shuts off the
  forge corner, the east wall, the user's vault and the dump chests: a job that pushes it aside ends with it back
  and locked down ("LOCK THE TABLE DOWN RIGHT WHEN YOU LEAVE"). `finish.py --side east --floor` does that and parks
  Clem in the middle of the great hall (933,2336). If a job stops early: `python3 -I castle.py table close`.
- **Never leave Clem outside**; park him inside. Gray creatures aren't hostile. His fight logic is weak (fix later).
- **Never open a pouch in Clem's pack**: the user's 3 trapped pouches (offLimits in his rules; `uo.call` refuses).
- **The user's loot bag stays in Clem's pack** (0x409167C6 on 2026-11-24): never move it out, empty it away or offer
  to. When the user says it's full, sort what's in it and leave the bag where it is.
- **Clem's own hatchet `0x4084BB01`** stays in his pack (`tools_room.KEEP`).
- **Never touch**: the friend's chests (south-west row, x 928-933, and 2327 top by the forge); the red and green
  repair bags by the forge (players only); the user's personal chests (938 top 3, 2327 2nd) except for the reagent
  top-up below.
- **GM-made things are always kept** in their east-wall homes, never the tools room or smelting.
- Messages lead with the blocker or question. Taking things from chests is normal: don't report what's missing.

## Sorting the incoming loot

Loot comes in two places: the **dump chests** (east: 938,2349, 938,2350 and, since 2026-11-23, the floor chest of
the 938 column; west: 933,2349 and 933,2350) and **bags on the forge room floor** (never the red and green repair
bags). "Sort the intake loot" means both. The procedure is the `uo-sort` skill's ("Sorting in the castle"):

```
python3 -I look.py BATCHDIR --side east [--floor]   # out of the dump chests (or off the forge floor) into his pack
python3 -I idall.py $(cat BATCHDIR/targets.txt)       # ID the magic ones
python3 -I plan.py BATCHDIR                           # the keep rules -> spec.json; read its report
python3 -I sortbatch.py BATCHDIR/spec.json            # put it all away
python3 -I finish.py --side east --floor              # table locked, parked in the great hall
```

BATCHDIR is a new `~/claude/uo-agent-work/batchN`. One batch per place (the dump chests, then the floor); he
carries what he can and the rest waits for the next batch (look.py says so). Where things go: plan.py and
`castle_site.py`; shovels, plain hatchets and the chopping axes that would be smelted go to the tools room, emptied
loot bags to the spare backpacks chest. Anything new or unsure goes to "needs your decision" (east 2337 floor):
tell the user.

## The tools room (south-east room)

Backpacks in stacks on the floor, one kind per bag, up to 250 stones a bag, **20 bags a stack** at most. Shovels, 50
a bag: the first row x 944-947 at y 2345, then (once all four are 20 high) the second row x 944-947 at y 2346 (the
user, 2026-11-25, via the shovel session: the axes are on hold). Plain lumberjacking axes and hatchets: x 944 at
y 2347-2348. `tools_room.KINDS` has the spots. Saws stay in the forge's tools chests. The shovel-buying loop
(`uo-shovels` skill) fills the room hourly: 3,396 shovels in 68 bags on 2026-11-25 01:50.

- **"Put the shovels away"** (or axes): `python3 -I tools_room.py put` (or `shovels` / `axes`). It finds them in
  Clem's pack, loose or in a bag (never a pouch), **recounts every bag in the room** (the user takes shovels out),
  fills bags in order, takes new empty backpacks from the spare backpacks chest when the bags are full, updates the
  vault page data. Then `finish.py --side east --floor`, unless the user wants him left there: then lock the table
  from behind it (`castle_site.Mover.close_up` from 944,2348) and walk back in (see
  `~/claude/uo-agent-work/castle/shovels-stay.py`).
- Report: how many were put away and the room's total (e.g. "177 shovels in 4 bags").
- `tools_room.py show` lists the bags; `count [--known]` recounts.

## The spare backpacks chest

938 3rd (`0x406ED0AA`, secure) since 2026-11-23, so the user can reach it through the window by the entrance
("I can't take stuff out of the bottom chest through the window"). Empty loot bags go here after a sort (the trash
once it holds 125); the tools room takes plain empty backpacks from it. 64 backpacks on 2026-11-23.

## The user's entrance reagent chest

Kept at **250 of each reagent**: 938 2nd (`0x406F2466`, secure, by the window). From the user's backup chest by the
forge (2327 2nd) first, then the main reagents chest (east 2336 3rd); nowhere else.

- `python3 -I reagents_topup.py` (`--then-shovels` puts shovels away first in the same trip).
- **Report two full tables, all 8 reagents each** (memory `reagent-topup-report`): the entrance chest (before, from
  the backup chest, from the main chest, now, still short), and **what's left in the backup chest**. Both are in
  `~/claude/uo-agent-work/castle/reagents-topup.json`. Lead with anything still short or running low.
- **Reagents for another character: only when the user asks, that one time.** Never part of a normal top-up (the
  user, 2026-11-24: "I don't want you to do leave 200 reagents every time you top up the reagent chest either. This
  is something I'm asking for this time only"). When asked (that day: "put 200 of black pearl, blood moss and
  mandrake into clems bag, i need to give it to burgers"): `--pack 'black pearl=200,blood moss=200,mandrake=200'`
  (`--pack-only` without a top-up) takes them from the main chest, then the user's backup chest for the rest, into
  Clem's pack as their own piles, apart from his casting reagents. **Bring the whole amount they asked for**: the main
  chest had 6 of each and I stopped to ask; they wanted their 200 ("where's my 200 reagents i asked for").
- Clem's own casting reagents are separate: `restock.py` before he leaves (below 25), from the entrance chest.

## The vault page

https://claude.ai/artifact/5nsmouJoGEEEMFdaffrXLP, from `vault/index.html`. No full recount unless the user asks
(`inventory.py --asked`). After a layout change, recount just the chests touched (`inventory.py --asked --only
SERIAL,SERIAL`) and publish; tool put-aways update the tools room's totals themselves (one total per tool, never bag
by bag). Publish with the Artifact tool on the same file path, then commit `vault/`.

## When the user changes something

Write it into `CASTLE.md` (their words, dated), the code (`castle_plan.py`, `castle_site.py`, `tools_room.py`,
`reagents_topup.py`, `labels.json` via `uo label`), this skill, and the `uo-sort` skill if sorting changes. Commit and
push.
