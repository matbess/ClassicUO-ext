#!/usr/bin/env python3
"""The human-like pacing out in town, for mining (mine.py) and lumberjacking (lumber.py): on or off.

  python3 -I pacing.py            show the flag
  python3 -I pacing.py on|off     set it; a running mining or lumberjacking loop gets the new rules at once

Off (the user, 2026-11-13: "remove that pacing for lumberjacking and for mining. There should be a flag around it so
we can enable/disable it. Disable it for now."): Icepick's and Burgers' rules get full speed, the bridge's 1.1 s
floor with no breaks and no pause before aiming; repeat strokes at the same rock or tree stay as quick as before.
On: the rules files' own pacing (2.5-4 s between actions, a 6-10 s break after every 5, 0.7-1.5 s before aiming;
MINING.md, "Pacing"). Burgers is quick at the bank either way. The flag is pacing.json next to this file.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
FLAG = os.path.join(HERE, 'pacing.json')
LUMBER_PID = os.path.expanduser('~/claude/uo-agent-work/lumber/lumber.pid')


def running(pid_file, name):
    try:
        with open(pid_file, encoding='utf-8') as fh:
            pid = int(fh.read().strip())
    except (OSError, ValueError):
        return None
    ps = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True)
    return pid if name in ps.stdout and '--park' not in ps.stdout and '--stop' not in ps.stdout else None


def main():
    import mine  # (before lumber: importing lumber points mine's settings at the lumberjacking work folder)
    if len(sys.argv) < 2:
        print(f"town pacing is {'ON (slow, human-like)' if mine.town_pacing() else 'OFF (full speed)'}")
        return
    if sys.argv[1] not in ('on', 'off'):
        sys.exit(__doc__)
    with open(FLAG, 'w', encoding='utf-8') as fh:
        json.dump({'town_pacing': sys.argv[1] == 'on'}, fh)
        fh.write('\n')
    print(f"town pacing is now {'ON (slow, human-like)' if sys.argv[1] == 'on' else 'OFF (full speed)'}")
    mining_pid = mine.running_loop()
    if running(LUMBER_PID, 'lumber.py'):
        import lumber
        module, what = lumber, 'lumberjacking'
    elif mining_pid:
        module, what = mine, 'mining'
    else:
        print('no mining or lumberjacking loop is running: the next one to start writes its rules with it')
        return
    import uo
    b = uo.call(uo.find_bridge('Burgers'), 'GET', '/status')
    at_bank = max(abs(b['x'] - mine.OCLLO_BANK[0]), abs(b['y'] - mine.OCLLO_BANK[1])) <= 10
    module.icepick_rules()
    module.burgers_rules(bank=at_bank)
    print(f"the running {what} loop's rules for Icepick and Burgers are rewritten (the bridges reload them at once)")


if __name__ == '__main__':
    main()
