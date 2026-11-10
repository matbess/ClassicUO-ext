"""Ingots by colour, worked out from the mining log (the user asks for the totals of every ore type now and then).

    python3 -I colours.py [mine.log]

The handoff lines give each trip's ingots and how many were iron; the coloured rest is split between the colours by
the ore smelted since the previous handoff, so the colour figures are estimates (a colour's ingots per ore varies).
The early handoff lines (2026-11-01) don't give iron, so those are split by all the ore smelted.

After a nightly reboot the server rolls the world back to its last save, and what happened after it never happened:
add each one's window to ROLLED_BACK (from just after the last handoff that survived to when the clients were back;
MINING.md has the reboots)."""
import collections
import os
import re
import sys

LOG = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/claude/uo-agent-work/mining/mine.log')
NAMES = {0: 'iron', 2419: 'dull copper', 2406: 'shadow iron', 2413: 'copper', 2418: 'bronze',
         2213: 'golden', 2425: 'agapite', 2207: 'verite', 2219: 'valorite'}
ROLLED_BACK = [('2026-11-02 04:00:20', '2026-11-02 04:19:00'),
               ('2026-11-04 04:00:14', '2026-11-04 04:19:00'),
               ('2026-11-05 03:58:06', '2026-11-05 04:19:00'),
               ('2026-11-09 03:57:07', '2026-11-09 04:19:00'),
               ('2026-11-10 03:59:03', '2026-11-10 04:19:00')]
smelt = re.compile(r'^(\S+ \S+) smelt \S+ \(hue (\d+), (\d+)\): You smelt the ore')
hand = re.compile(r'^(\S+ \S+) handed Burgers (\d+) ingots(?: \((\d+) iron\))?')

window = collections.Counter()  # ore smelted since the last handoff, by hue
ingots = collections.Counter()
ore = collections.Counter()
unassigned = total = iron_total = 0
for line in open(LOG, encoding='utf-8'):
    t = line[:19]
    if any(a <= t < b for a, b in ROLLED_BACK):
        continue
    m = smelt.match(line)
    if m:
        h, a = int(m.group(2)), int(m.group(3))
        ore[h] += a
        window[h] += a
        continue
    m = hand.match(line)
    if m:
        n = int(m.group(2))
        total += n
        if m.group(3) is None:
            w, coloured = dict(window), n
        else:
            i = int(m.group(3))
            iron_total += i
            ingots[0] += i
            w, coloured = {h: a for h, a in window.items() if h}, n - i
        s = sum(w.values())
        if coloured and s:
            for h, a in w.items():
                ingots[h] += coloured * a / s
        elif coloured:
            unassigned += coloured
        window.clear()

print(f'handed over in the log: {total} ingots, {iron_total} iron (coloured not matched to a colour: {unassigned})')
print(f'ore smelted: {sum(ore.values())}, {total / max(sum(ore.values()), 1):.2f} ingots per ore')
for h, v in sorted(ingots.items(), key=lambda kv: -kv[1]):
    print(f'{NAMES.get(h, h):12} {round(v):7}   (ore {ore[h]}, {v / max(ore[h], 1):.2f} per ore)')
