# How skills and stats gain on this server (measured, 2026-11-17)

The user (2026-11-17): "all skill gains follow a similar pattern/curve ... It usually slows down a lot at 90 and 95
and 99". This is that curve, measured from the logs of every training loop so far, for estimating any new one.
Update it when a new run adds data.

**Sources:** `~/claude/uo-agent-work/`:
- `smith/smith.log`: Blacksmithing 59→100, Icepick, 11,932 crafts
- `carp/carp.log`: Carpentry 40→100, Icepick, 10,785 crafts
- `carto/draws.jsonl`: Cartography to 100, Clem, 7,766 attempts
- `lumber/lumber.log`: Lumberjacking 28→97, Icepick
- `heal/`: Healing 98.4→100, Burgers, 1,490 bandages
- `cook/`: Cooking 0→59.5 and Int 23→100, Icepick, 2,656 steaks
- the blackbox: Resisting Spells 97.3→100, Burgers

Smithing, carpentry and lumberjacking logged the *shown* value. That carries a bonus over the base (Carpentry showed
40.2 on a base of 23.1). The bonus fades to nothing by about 90, so their bands below 80 sit on lower base levels.

## Attempts per +0.1, by band

| Band | Smith | Carp | Carto | Lumber | Heal / Resist |
|---|---|---|---|---|---|
| 30-40 | | | | 4.9 | |
| 40-50 | | 7-11 | | 6.3 | |
| 50-60 | 9 | 8.5 | | 7.8 | |
| 60-70 | 12-16 | 12 | | 10.6 | |
| 70-80 | 19 | 11-18 | | 16 | |
| 80-85 | 22 | 22 | 21 | 22 | |
| 85-90 | 29 | 24 | 35 | 29 | |
| 90-93 | 30 | 25 | 36 | 47 | |
| 93-95 | 50 | 33 | 49 | 51 | |
| 95-97 | 70 | 48 | 82 | 104 | |
| 97-98 | 62 | 64 | 85 | | Resist 41 |
| 98-99 | 100 | 63 | 78 | | Heal 72 |
| 99-100 | 63 | 73 | 75 | | Heal 97, Resist 58 |

- Every loop managed about 8-11 s an attempt, so 99→100 takes about 1.6-2.6 hours.
- 90→100 took about 4,300-6,300 attempts: smithing 5,900, carpentry 4,300, cartography 6,300.
- Below base 10 nearly every attempt gains 0.1-0.4: Cooking 0→10 took 44 steaks.

## The shape, and estimating with it

- **Below 90:** each 10 points costs about 1.3-1.6 times the 10 before.
- **85-93:** about flat.
- **93-95:** the first real knee, about 1.5 times.
- **95-100:** 2-3 times the 90-93 cost, levelling off at about 60-100 attempts per 0.1. Nothing measured went above
  about 115.
- **99:** no extra knee, as long as the action can still fail.

**Project with multipliers.** Measure the attempts per point in the current band. Divide by that band's multiplier.
Then add up multiplier × points for every band still to cross.

| Band | under 60 | 60-70 | 70-80 | 80-85 | 85-90 | 90-93 | 93-95 | 95-97 | 97-100 |
|---|---|---|---|---|---|---|---|---|---|
| Multiplier | 0.25 | 0.4 | 0.6 | 0.75 | 0.9 | 1 | 1.5 | 2.2 | 2.5 |

`cook.py`'s `estimate` does exactly this. Say the result is an estimate, and redo it as each band finishes.

## Too easy means no gains

Within one item, the failure rate falls as the skill rises, and the gains slow with it.
- At 99, spears (0% fail) gave nothing in 353 crafts, while plate gloves (13% fail) gave +0.6 in an hour.
- Smithing's slowdown at 98-99 was the item being too easy, not the level.
- At 65, kryss (62% fail) gained faster than cutlass.

This looks like a RunUO-style formula: about a 1% least chance of a gain per attempt, and none when success is
certain (an inference). So a training loop watches its failure rate, and the user's item tables step up to harder
items as the skill rises.

## Stats

- Only the cooking run has stat data so far (COOKING.md): Int 23 → 100 in 2,656 steaks while Cooking went 0.2 → 59.5.
  Int came only on steaks that also gave a Cooking gain (the user: "You can't gain int without gaining cooking skill").
- **Int followed the skill, not its own level:** about 1.3 Int per Cooking point in every band (9, 18, 14, 13, 10, 13
  Int across the six bands), with no slowdown as Int neared 100 (Int 96 → 100 took 126 steaks). So the cost of a stat
  point is the cost of about 0.75 skill points in whatever band the skill is in; estimate the skill level where the
  stat lands, then cost the skill with the multipliers above. Only one run, with the stat well under its cap; the user
  thinks stats curve differently, so check this on the next stat run.
- Cooking itself (a shown value, from 0): 4.6 steaks a point under 10, then 43, 50, 46, 54, 72 for the bands 10-60,
  flatter than the crafting skills because the burn rate fell from 77% to 35% as it rose.
- A down-locked stat drops on most gains of an up one (Dex fell on 7 of the first 9 Int gains), even with the stat
  total far under the cap.
- A down-locked skill drops as others rise once the skill total is at its cap: Burgers' Meditation went 4.2→0.
- The client prints "Your intelligence has changed by 1.  It is now 23". Max mana is Int and max stamina is Dex here.
