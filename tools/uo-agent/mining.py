#!/usr/bin/env python3
"""Shared pieces for the mining work (see MINING.md): the route, walking along it, and the characters' things.

  python3 mining.py where             where Icepick is on the route
  python3 mining.py walk INDEX|forge  walk Icepick along the route to a waypoint (or the forge)
  python3 mining.py plan              the ore blocks along the route and where Icepick digs each
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


def load_rules(name='Icepick'):
    """A rules file from rules/ (JSON with // comment lines)."""
    with open(os.path.join(HERE, 'rules', f'rules-{name}.json'), encoding='utf-8') as fh:
        return json.loads(''.join(line for line in fh if not line.lstrip().startswith('//')))


def in_areas(areas, x, y):
    return any(a['box'][0] <= x <= a['box'][2] and a['box'][1] <= y <= a['box'][3] for a in areas)


_MAP = None


def game_map():
    global _MAP
    if _MAP is None:
        import uomap
        _MAP = uomap.Map()
    return _MAP


def walkable(x, y):
    """Whether the map shows a tile one can stand on (no rock, water, tree or wall); houses and other items
    the map doesn't hold are the path finder's business."""
    m = game_map()
    tile, z = m.land(x, y)
    if m.impassable_land(tile) or m.land_name(tile) == 'rock':
        return False
    return not any(m.impassable_static(t) and sz + m.static_heights[t] > z for t, sz, _ in m.statics(x, y))


RIDES = os.path.join(HERE, 'routes')  # the user's recorded rides to the forge: ride-*.jsonl


def rides():
    """The user's recorded rides (2026-11-01: from the top of the route, the canyon and the bottom end, each to the
    forge), each a list of spots, one per step."""
    import glob
    found = []
    for path in sorted(glob.glob(os.path.join(RIDES, 'ride-*.jsonl'))):
        points, last = [], None
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                r = json.loads(line)
                if 'message' in r:
                    continue
                spot = (r['x'], r['y'])
                if spot != last:
                    points.append(spot)
                    last = spot
        if points:
            found.append(points)
    return found


def ride_path(start, goal, areas, join=25, step=10):
    """A path for a long trip that follows one of the user's recorded rides: plan to the ride's point nearest the
    start, along the ride (every `step`-th point, whichever way) to its point nearest the goal, then plan to the
    goal. Picks the ride that needs the least planning off it. None if no ride helps (none recorded, too far from
    them, or the stretch along one is short)."""

    def dist(a, b):
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

    best = None
    for points in rides():
        i = min(range(len(points)), key=lambda k: dist(points[k], start))
        j = min(range(len(points)), key=lambda k: dist(points[k], goal))
        off = dist(points[i], start) + dist(points[j], goal)
        lo, hi = min(i, j), max(i, j)
        along_tiles = sum(dist(points[k], points[k + 1]) for k in range(lo, hi))
        if dist(points[i], start) <= join and dist(points[j], goal) <= join and along_tiles >= 25:
            if best is None or off < best[0]:
                best = (off, points, i, j)
    if best is None:
        return None
    _, points, i, j = best
    first = plan_path(start, points[i], areas) if dist(points[i], start) > 1 else []
    last = plan_path(points[j], goal, areas) if dist(points[j], goal) > 1 else []
    if first is None or last is None:
        return None
    stretch = points[i:j + 1] if j > i else points[j:i + 1][::-1]
    # a waypoint about every `step` tiles along the ride (the recorder caught him every few tiles)
    along = [stretch[0]]
    for spot in stretch[1:]:
        if dist(spot, along[-1]) >= step:
            along.append(spot)
    if along[-1] != stretch[-1]:
        along.append(stretch[-1])
    path = []
    for spot in first + along + last:
        if not path or spot != path[-1]:
            path.append(spot)
    return path


def plan_path(start, goal, areas, longest=14):
    """A path across the map from start to goal, planned in advance (the user, 2026-11-01: see where you're going
    beforehand): A* over the tiles the map shows walkable inside the areas, eight ways, no cutting corners. Returns
    waypoints a few tiles to a dozen apart, wherever the path turns (each stretch straight and clear on the map, so
    the client's path finder can ride it), ending at the goal; or None if the map shows no way."""
    import heapq
    passable = {}

    def ok(x, y):
        if (x, y) in (start, goal):
            return True
        if (x, y) not in passable:
            passable[(x, y)] = in_areas(areas, x, y) and walkable(x, y)
        return passable[(x, y)]

    def h(p):
        return max(abs(p[0] - goal[0]), abs(p[1] - goal[1]))

    open_heap = [(h(start), 0, start)]
    came, cost = {start: None}, {start: 0}
    while open_heap:
        _, g, cur = heapq.heappop(open_heap)
        if cur == goal:
            break
        if g > cost[cur]:
            continue
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == dy == 0:
                    continue
                nxt = (cur[0] + dx, cur[1] + dy)
                if not ok(*nxt) or dx and dy and not (ok(cur[0] + dx, cur[1]) and ok(cur[0], cur[1] + dy)):
                    continue
                ng = g + (1.0 if dx == 0 or dy == 0 else 1.001)  # straight a hair cheaper: fewer zigzags
                if ng < cost.get(nxt, 1e9):
                    cost[nxt], came[nxt] = ng, cur
                    heapq.heappush(open_heap, (ng + h(nxt), ng, nxt))
    if goal not in came:
        return None
    path = [goal]
    while came[path[-1]] is not None:
        path.append(came[path[-1]])
    path.reverse()

    def clear(a, b):
        # every tile on the straight line from a to b is walkable
        n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
        return all(ok(round(a[0] + (b[0] - a[0]) * k / n), round(a[1] + (b[1] - a[1]) * k / n)) for k in range(n + 1))

    points, i = [], 0
    while i < len(path) - 1:
        j = min(len(path) - 1, i + longest)
        while j > i + 1 and not clear(path[i], path[j]):
            j -= 1
        points.append(path[j])
        i = j
    return points


def plan(points=None, reach=2):
    """The ore blocks along the route, in the order Icepick reaches them. Ore is shared by an 8x8 block, so any rock
    in a block will do. For each block: the waypoint where it first comes within reach (for the order), and every
    (rock, place to stand) pair that works: rocks inside Icepick's corridor, standing on a waypoint or on a walkable
    tile one step off one, within reach of the rock. choose() picks one of them at random for each pass."""
    import uomap
    m = uomap.Map()
    points = points or route()
    # dig only from the mining corridor, not the open town Icepick may run into to get away
    areas = [a for a in load_rules()['areas'] if a['name'] != 'getting away']
    on_route = set(points)

    def walkable(x, y):
        if (x, y) in on_route:
            return True
        tile, z = m.land(x, y)
        if m.impassable_land(tile) or not in_areas(areas, x, y):
            return False
        return not any(m.impassable_static(t) and sz + m.static_heights[t] > z for t, sz, _ in m.statics(x, y))

    stands = set()
    for x, y in points:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if walkable(x + dx, y + dy):
                    stands.add((x + dx, y + dy))

    rocks_by_block = {}
    for x, y in points:
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                rx, ry = x + dx, y + dy
                tile, z = m.land(rx, ry)
                if m.land_name(tile) == 'rock' and in_areas(areas, rx, ry):
                    rocks_by_block.setdefault((rx // 8, ry // 8), set()).add((rx, ry, z))

    targets, seen = [], set()
    for i, (x, y) in enumerate(points):
        reached = [b for b, rocks in rocks_by_block.items()
                   if b not in seen and any(max(abs(rx - x), abs(ry - y)) <= reach for rx, ry, _ in rocks)]
        for block in sorted(reached):
            seen.add(block)
            pairs = []
            for rx, ry, z in sorted(rocks_by_block[block]):
                for sx, sy in stands:
                    if max(abs(rx - sx), abs(ry - sy)) <= reach and (sx, sy) != (rx, ry):
                        pairs.append(((rx, ry, z), (sx, sy)))
            targets.append({'block': block, 'index': i, 'stand': (x, y), 'pairs': pairs,
                            'rocks': sorted(rocks_by_block[block], key=lambda r: (max(abs(r[0] - x), abs(r[1] - y)), abs(r[2])))})
    return targets


def choose(target, rng=random):
    """A random rock of the block and a random place to stand within reach of it (the user, 2026-11-01: don't dig
    from exactly the same spot every time). Rocks nearer the ground are a little more likely (the server must be
    able to see them). Returns (rock, stand, the block's other rocks in random order to try next)."""
    rocks = sorted({r for r, _ in target['pairs']})
    weights = [1.0 / (1 + abs(r[2]) / 10) for r in rocks]
    rock = rng.choices(rocks, weights)[0]
    stand = rng.choice([st for r, st in target['pairs'] if r == rock])
    others = [r for r in rocks if r != rock]
    rng.shuffle(others)
    return rock, stand, others


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
    elif sys.argv[1] == 'plan':
        targets = plan(points)
        for n, t in enumerate(targets):
            rock, stand, _ = choose(t)
            print(f"{n:3} block {t['block']} (waypoint {t['index']}): {len(t['pairs'])} rock/stand pairs;"
                  f" this time rock {rock} from {stand}")
        print(f'{len(targets)} ore blocks')
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
