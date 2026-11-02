#!/usr/bin/env python3
"""Shared pieces for the mining work (see MINING.md): the route, walking along it, and the characters' things.

  python3 mining.py where             where Icepick is on the route
  python3 mining.py walk INDEX|forge  walk Icepick along the route to a waypoint (or the forge)
  python3 mining.py dig X Y Z [MAX]   dig one rock until it's empty (Icepick must be on foot, within 2 tiles)
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import uo  # noqa: E402
import mining_area  # noqa: E402

HERE = os.path.dirname(os.path.realpath(__file__))
ROUTE = os.path.join(HERE, 'routes', 'route1.jsonl')  # the user's walk, 2026-11-01
FORGE = '0x400BF6E0'          # the forge at 1148,1859 (an item)
FORGE_SPOT = (1147, 1857)      # where Icepick stands to smelt and trade (Burgers waits at 1147,1856)
BURGERS_SPOT = (1147, 1856)
RUNES = {'bank': '0x406EDA8E', 'start': '0x406EBB72', 'forge': '0x406EDA9E', 'gate': '0x406EC754'}
HORSE = '0x00042FCB'           # Icepick's horse
SHOVELS = ('0x0F39', '0x0F3A')
ORE = ('0x19B7', '0x19B8', '0x19B9', '0x19BA')


def pause():
    """A random 1.5-2 s pause around walks (the user, 2026-11-01: never act faster than a person might). The bridge
    paces walks itself from build cuo-agent10 on; this covers the build before it."""
    time.sleep(random.uniform(1.5, 2.0))


def say(text):
    print(time.strftime('%H:%M:%S'), text, flush=True)


def route():
    """The recorded route inside Icepick's corridor, in walking order, one waypoint per spot."""
    points, last = [], None
    with open(ROUTE, encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            if 'message' in r or not mining_area.kept(r):
                continue
            spot = (r['x'], r['y'])
            if spot != last:
                points.append(spot)
                last = spot
    return points


def nearest(points, x, y):
    return min(range(len(points)), key=lambda i: max(abs(points[i][0] - x), abs(points[i][1] - y)))


def walk_route(info, points, target, stop=None, reach=15):
    """Travel to waypoint `target` along the route, taking short cuts: each request walks straight to the furthest
    waypoint (towards the target) within `reach` tiles of where the character stands, so loops in the recorded
    walk (the trip into the canyon and back out) are skipped. Falls back to shorter hops when a path fails.
    `stop()` can cut it short."""
    s = uo.call(info, 'GET', '/status')
    x, y = s['x'], s['y']
    i = nearest(points, x, y)
    step = 1 if target >= i else -1
    while True:
        if stop and stop():
            return False
        if max(abs(points[target][0] - x), abs(points[target][1] - y)) <= 1:
            return True
        # every waypoint from here to the target that lies within reach, furthest first
        ahead = [j for j in range(i + step, target + step, step)
                 if max(abs(points[j][0] - x), abs(points[j][1] - y)) <= reach]
        ahead.reverse()
        moved = False
        for j in ahead[:6]:
            pause()
            r = uo.call(info, 'POST', '/walk', x=points[j][0], y=points[j][1], distance=1)
            x, y = r['x'], r['y']
            if r['arrived']:
                i, moved = j, True
                break
            if r.get('leftArea'):
                # stepped just outside the corridor: try a nearer waypoint from here
                continue
        if not moved:
            raise uo.BridgeError(0, f"couldn't walk on from {x},{y} towards waypoint {target} {points[target]}")


def shovels(info):
    """Icepick's shovels, as serials."""
    pack = uo.call(info, 'GET', '/status')['backpack']['serial']
    items = uo.call(info, 'GET', '/contents', serial=pack)['items']
    return [i['serial'] for i in items if i.get('graphic') in SHOVELS]


def dig(info, x, y, z, max_digs=40, weight_margin=30, log=say):
    """Dig one rock until the server says there's no metal left (or the pack is nearly full, or max_digs).
    Returns (why it stopped, ore digs, misses). Swaps to the next shovel when one wears out."""
    ore = misses = 0
    tools = shovels(info)
    for _ in range(max_digs):
        if not tools:
            return 'no shovels', ore, misses
        r = uo.call(info, 'POST', '/use', serial=tools[0], x=x, y=y, z=z, graphic=0)
        texts = [m['text'] for m in r['messages'] if m['type'] != 'Label']
        answer = next((t for t in texts if 'wish to dig' not in t.lower()), '(no answer)')
        low = answer.lower()
        if 'you dig some' in low:
            ore += 1
        elif 'loosen some rocks' in low:
            misses += 1
        log(f'dig {x},{y}: {answer}  (weight {r["weight"]}/{r["weightMax"]})')
        if any('worn out' in t.lower() for t in texts):
            tools = shovels(info)
            log(f'a shovel wore out; {len(tools)} left')
        if 'no metal here' in low:
            return 'empty', ore, misses
        if not ('you dig some' in low or 'loosen some rocks' in low or 'worn out' in low):
            return answer, ore, misses
        if r['weight'] >= r['weightMax'] - weight_margin:
            return 'heavy', ore, misses
    return 'max digs', ore, misses


def main():
    info = uo.find_bridge('Icepick')
    points = route()
    s = uo.call(info, 'GET', '/status')
    if sys.argv[1] == 'where':
        i = nearest(points, s['x'], s['y'])
        print(f"Icepick at {s['x']},{s['y']}: waypoint {i} of {len(points)} {points[i]}")
    elif sys.argv[1] == 'dig':
        x, y, z = (int(v) for v in sys.argv[2:5])
        why, ore, misses = dig(info, x, y, z, max_digs=int(sys.argv[5]) if len(sys.argv) > 5 else 40)
        say(f'stopped: {why}; {ore} digs found ore, {misses} missed')
    elif sys.argv[1] == 'walk':
        if sys.argv[2] == 'forge':
            target = nearest(points, *FORGE_SPOT)
        else:
            target = int(sys.argv[2])
        walk_route(info, points, target)
        if sys.argv[2] == 'forge':
            uo.call(info, 'POST', '/walk', x=FORGE_SPOT[0], y=FORGE_SPOT[1], distance=0)
        s = uo.call(info, 'GET', '/status')
        say(f"Icepick at {s['x']},{s['y']}")


if __name__ == '__main__':
    try:
        main()
    except uo.BridgeError as e:
        sys.exit(str(e))
