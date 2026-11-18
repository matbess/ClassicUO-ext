# Cooking for Intelligence (Icepick, from 2026-11-17)

Icepick cooks raw fish steaks on the forge on the tower's ground floor to raise his **Intelligence** (Cooking gains
bring Int gains). The loop is `cook.py`, the rules `rules/rules-Icepick-cook.json`. It uses Icepick, so never with
mining, lumberjacking, carpentry or smithing.

## The user's rules (2026-11-17)

- "Cook them on the forge and watch his int go up. If his int gets to 100 then stop (his dex should be at 25 then)."
- The 5000 raw fish steaks are in the **bottom wooden chest** by the forge (0x4074A4C1, 1757,1407,6). There's a much
  bigger raw pile on the floor (0x408A39B9, 55,000 at 1758,1408): "I do NOT want you to accidentally cook that whole
  pile, that's why it's separated". The rules' area stops at x 1757 and raw/cooked steaks are in `neverTouch`, so the
  bridge can't reach or lift it.
- **One steak at a time** ("wtf! don't cook the whole stack! ... You have to take 1 fish steak at a time and cook
  it."): a double-click on a stack cooks the whole stack for one skill check. In the first test (20:37) 9 steaks went
  for a single check. cook.py moves exactly 1 steak from the chest, and stops rather than double-click a raw stack
  bigger than 1.
- Skill locks (set by the user): Cooking **up**; Herding (47.6) **down** to make room, then Swordsmanship, Tactics and
  Wrestling; Hiding stays locked until all of those are 0. "You can't gain int without gaining cooking skill." When
  they're all 0 and Int isn't 100 yet, tell the user. The bridge can't set skill locks, so the user sets Hiding down.
- Give an estimate of how many steaks it will take while cooking: the user will add more if 5000 isn't enough.

- **Dex** (2026-11-17 21:45): with Dex set down, every Int gain took a point of Dex, so Dex hit 25 at Int 46, not at
  Int 100 as the user expected. The loop was stopped to ask; the user locked Dex at 24 ("Ok I locked it at 24,
  Continue please"). A down stat that falls faster than planned is a stop-and-tell.

## How the server does it (tested 2026-11-17)

- From 1756,1409 (a tile from the forge 0x408A3611 at 1755,1410; two from the chest). From two tiles: "That is too
  far away." Mounted is fine.
- Double-click the raw steak in the pack (a target cursor), aim at the forge. Nothing is said at once. About 5 s later:
  - "Looks delicious." (said by him) + "You put the cooked food into your backpack." (cooked steak, graphic 0x097B,
    joins the pack's stack), or
  - "You burn the food to a crisp! It's ruined."
- A stat gain shows as the client's line "Your intelligence has changed by 1.  It is now 23" (and the same for
  strength and dexterity). On this server his max mana is his Int and his max stamina his Dex.
- `/use` with a target waits only 2 s for an answer and stopped the bridge, so cook.py double-clicks (`/use`, no
  target: the cursor comes up) and then answers the cursor with `/target` on the forge, which waits up to 10 s.
- A steak moved out of a stack keeps the stack's serial; what stays in the chest gets a new one, so cook.py reads the
  chest each time.
- Start (2026-11-17 20:43): Int 23 (22 before the test's gain), Dex 45, Str 100; Cooking 0.2; skill total 634.9 of
  700, so Cooking can rise about 65 before Herding starts to drop.

## Estimating the steaks (the user, 2026-11-17)

"The curve is somewhat exponential when gaining skill. It usually slows down a lot at 90 and 95 and 99 etc." So the
steaks per Int point so far (4 at the start) badly underestimates the rest. Int comes with Cooking gains (the user:
"You can't gain int without gaining cooking skill"), so cook.py estimates in two steps:
1. Int points per Cooking point so far gives the Cooking level where Int reaches 100;
2. steaks per Cooking point in the current band of 10 points is the least the rest can cost (higher bands cost
   more), so the estimate is a floor that rises as he goes. `cook.py report` prints the table by band.

| Cooking band | Steaks | Cooking points | Int points | Steaks per Cooking point | Steaks per Int |
|---|---|---|---|---|---|
| 0-10 | 45 | 9.8 | 9 | 4.6 | 5.0 |
| 10-20 | 430 | 10.0 | 18 | 43.0 | 23.9 (77% burnt) |
| 20-30 | 500 | 10.0 | 14 | 50.0 | 35.7 (68% burnt) |
| 30-40 | 460 | 10.0 | 13 | 46.0 | 35.4 (52% burnt) |

(Fill in from `cook.py report` as each band finishes. Int 81 at Cooking 43.8 after 1638 steaks, 2026-11-18 01:04;
about 1.3 Int per Cooking point all the way, so Int 100 at about Cooking 58.) Dex dropped one for most Int gains from the start (Dex is set
down), though his stat total (about 168) was under the cap: the server lowers a down stat on a gain by chance even
below the cap.

## Running it

```
python3 -I cook.py run       # in the background; log ~/claude/uo-agent-work/cook/cook.log
python3 -I cook.py report    # steaks so far, Int, steaks per Int point, the estimate
python3 -I cook.py stop      # after the steak it's on
```

It logs every stat change, and a line every 25 steaks or on each Cooking gain, with the steaks-per-Int estimate. It
stops when Int reaches 100, Cooking reaches its cap, the down skills are all 0 at the skill cap, the chest runs out,
something unexpected happens, he's too heavy, or the user takes him over.

Cooked steaks (about 0.1 stone each) go onto the cooked pile on the forge (0x407D3384, 1755,1410,9; the user,
2026-11-17: "put the cooked steaks on the pile on the forge if your weight gets too much. Or just put them over there
once in a while"): at the start, every 100 steaks, and whenever he's within 40 stones of his max. Cooked steaks aren't
in the rules' `neverTouch`, since that also blocks dropping onto a pile. A pile holds at most 60000 and this one had
58290, so it has room for about 1700. After that (the user, 2026-11-17: "make a cooked pile on the floor next to the
uncooked pile") he steps to 1757,1408, puts the steaks down at his feet (the rules' `dropOnGround` allows cooked
steaks only) and steps back; later loads go onto that pile (`floorPile` in the state).

How fast it goes, by band, and how the estimate works: SKILLGAIN.md (the curve measured on every training run).
Cooking 10-20 burns 98% of steaks and costs about 39 steaks a Cooking point (2026-11-17, first 100 steaks); a band
where nearly nothing burns any more would give no gains, so the loop stops after 300 steaks with no Cooking gain.
