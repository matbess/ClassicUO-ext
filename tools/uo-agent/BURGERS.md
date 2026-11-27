# Shovels and reagents for Burgers (Clem, from the castle tools room)

The tool is `burgers.py`, its checks `burgers_test.py`, the skill `skills/uo-burgers/SKILL.md`. Clem and Burgers are
both driven by the one script; the log is `~/claude/uo-agent-work/burgers/burgers.log`.

## The user's rules (2026-11-26, in their words)

- "you'll be in charge of giving shovels & reagents to Burgers. This will involve taking control of burgers, this
  requires you to coordinate with the mining agent to make sure it's done using Burgers and will hand him over to you,
  most likely that agent will message you and tell you burgers needs shovels."
- "You'll take burgers to the ocllo bank (he has a rune to it) and hide him. The agent should tell you how many
  reagents are needed, you can also look in burgers bank and his bag to verify. He should have about 30-50 of 4
  reagents in his bag and about 250 of each of those 4 in his bank. They are sulfrous ash, bloodmoss, mandrake and
  black pearl." Settled: **his pack to 50 of each, his bank to 250 of each**, unless the mining agent gives numbers.
- "You'll first take clem to the tools room and then fetch the recall rune for the castle courtyard from my chest"
  (the "skara" rune 0x406EAA74 in the user's chest 938 top, SHOVELS.md).
- "get 1 bag of shovels from teh tools room and get the reagents Burgers needs (unless you don't have room, then take
  the reagents on a separate trip) and go to Ocllo bank and hand them to Burgers, then put them in burgers bank (there
  is a reagents bag in his bank), just put the whole bag of shovels in his bank." At first the reagents rode along on
  the shovel trips, but on 2026-11-26 the entrance chest ran short on trip 2 and its top-up (reagents_topup.py) loaded
  52 stones of reagents onto Clem on top of the bag: 399/390, stuck. The user: "I thought you were going to do the
  reagents as a separate trip?" So: **the bags first, then the reagents on trips of their own**, and Clem never leaves
  carrying more than his max less 10 stones.
- "give Clem the empty bags from burgers bank and inventory (they were used to hold shovels) so he can bring them back
  to the castle. Go back to the castle, (make sure clem has enough reagents before you start btw) put the empty
  backpacks away, then get another bag of shovels and take it to burgers again. Then do that once more. You'll give
  burgers 3 bags of shovels (150 shovels) and then take clem back to the tools room and leave burgers hidden at the
  bank."
- "**only 2 bags of shovels go into burgers bank, the 3rd bag stays in his inventory so he can hand them to
  icepick**." (The bank box holds 125 things counting what's inside its bags, so 3 full bags wouldn't fit anyway.)
- "make sure that burgers can hold the shovels and has enough weight available. If for some reason he can't hold them,
  he should always be able to hold 50 shovels though. If he can't then I guess You'll have to pause it." Before every
  trip with a bag he must have 253 stones free (50 shovels and the backpack), or it stops and the user is told.
- "When you are done then you'll tell the mining agent that shovels and reagents were topped up if that agent was the
  one who requested for you to do this. If I requested it then you just tell me and not that agent."
- A shovel loop that's running is paused for it (`shovels.py pause`), and resumed after (`shovels.py resume`).
- 2026-11-26: "we're not buying shovels anymore for a while. I'm playing clem as well. When the mining agent needs
  more shovels then I'll hand over clem to you when you ask me". So a request from the mining agent means: ask the
  user for Clem first, and run only after they say yes.

## What's where

| What | Where |
|---|---|
| Burgers' "Ocllo" rune | 0x406EDA8E in his pack; lands him at 3686,2506 |
| Clem's "Ocllo Bank" rune | in his reagent bag; lands him at 3686,2505 (so Burgers never waits there) |
| Burgers' bank bags | the reagent bag (0x407D0B95 on 2026-11-26), the ingot bag (0x4045C032), shovel bags (found by what's in them) |
| The bag mine.py keeps his spare shovels in | `shovel_bag` in `~/claude/uo-agent-work/mining/state.json`: never taken back |
| Full bags of shovels | the tools room stacks: the top bag of the highest stack holding 50 shovels (`castle/tools-room.json` updated) |
| Reagents for him | the user's entrance chest (938 2nd), as piles of their own in Clem's pack; topped up from the backup chest when short |
| Empty backpacks brought back | the spare backpacks chest (938 3rd) |

Burgers' rules: while the job runs, his rules file in the client's Agent folder gets the Ocllo bank as an area (he
steps out of hiding next to Clem for each trade: a step reveals him) at full speed; it's put back as it was at the end.
His guard is off at the bank (MINING.md: the bank is relaxed). Clem's rules name Burgers as his partner (the bridge
only lets him hand things to a partner).

## Running it

```
python3 -I burgers_test.py                     # offline checks, after any change
python3 -I burgers.py run                      # the whole job: 3 bags (2 to his bank, 1 in his pack), the reagents
python3 -I burgers.py run --reagents 'black pearl=200,blood moss=200,mandrake=200,sulfurous ash=100'
                                               # the mining agent's numbers in place of 50 in his pack / 250 in his bank
python3 -I burgers.py survey                   # Burgers to the bank, hidden; what his pack and bank hold
python3 -I burgers.py stop                     # no more trips after this one
```

It refuses to start while mine.py, lumber.py or heal.py (Burgers) or the shovel loop (Clem) runs. Run it in the
background and watch `burgers.log` for `trip `, `FINAL:`, `STOPPED`, `Traceback` and `TOPUP:`.

## What to tell

- Each trip: what went to Burgers (a bag: bank or pack, the reagents) and what's still to bring.
- At the end, the FINAL line: shovels in his bank and pack, the four reagents in his pack and bank, and that Clem is
  in the tools room with the table locked and Burgers hidden at the bank (guard off).
- To whoever asked (the mining agent, or only the user if the user asked). The mining agent restarts its loop; if the
  bank had been found empty in the last 30 minutes it clears `bank_out_of_shovels` first (MINING.md).
