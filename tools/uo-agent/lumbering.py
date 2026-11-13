#!/usr/bin/env python3
"""Shared pieces for lumberjacking (see LUMBERJACKING.md): the trees in Icepick's area, the 8x8 wood blocks, and
the tour through them.

  python3 lumbering.py plan            work out the blocks and the tour, and save the tour (routes/lumber-tour.json)
  python3 lumbering.py show            the saved tour: blocks in order, trees and spots in each, the longest hops
  python3 lumbering.py draw OUT.png    the area, the tour and the meeting spot on the map (north up)

Wood is shared by the 8x8 blocks of the map grid, as the ore is (tested 2026-11-12): one tree per block is chopped
until "not enough wood", then on to the next block. The tour visits every block with a choppable tree once, in an
order that keeps the rides short (nearest neighbour, then 2-opt), as a loop: the lap ends next to where it began.
It's saved, so the loop's place in it ("next") keeps its meaning; plan again only on purpose.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import mining  # noqa: E402

HERE = os.path.dirname(os.path.realpath(__file__))
TOUR = os.path.join(HERE, 'routes', 'lumber-tour.json')
RULES = 'Icepick-lumber'
MEET_BURGERS = (1200, 1716)   # where Burgers waits, hidden (the user, 2026-11-12: "by this building", off the road)
MEET_ICEPICK = (1200, 1714)   # where Icepick comes up for the trade
RUNE_MEET = '0x406EAA75'      # Burgers' "Lumber meet" rune, marked on his spot
REACH = 2                     # an axe reaches a tree 2 tiles off (as a shovel does a rock)
NOT_CHOPPABLE = ("o'hii",)    # "You can't use an axe on that." (0x0C9E, 2026-11-12)


def areas():
    return mining.load_rules(RULES)['areas']


def is_tree(m, tile):
    name = m.static_name(tile).lower()
    return 'tree' in name and 'stump' not in name and not any(n in name for n in NOT_CHOPPABLE)


def trees(area_list=None):
    """Every choppable tree inside the areas: (x, y, z, graphic), one per tile (the tallest part's z doesn't
    matter: the server takes the trunk or the leaves)."""
    m = mining.game_map()
    area_list = area_list or areas()
    x1 = min(a['box'][0] for a in area_list)
    y1 = min(a['box'][1] for a in area_list)
    x2 = max(a['box'][2] for a in area_list)
    y2 = max(a['box'][3] for a in area_list)
    found = []
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            if not mining.in_areas(area_list, x, y):
                continue
            for t, z, _ in m.statics(x, y):
                if is_tree(m, t):
                    found.append((x, y, z, t))
                    break
    return found


def blocks(area_list=None):
    """The wood blocks: {(bx, by): {'trees': [...], 'pairs': [(tree, stand), ...]}} for every block with a tree that
    has somewhere to stand within reach (a walkable tile inside the areas, clear of learned buildings)."""
    area_list = area_list or areas()
    stand_ok = {}

    def can_stand(x, y):
        if (x, y) not in stand_ok:
            stand_ok[(x, y)] = mining.in_areas(area_list, x, y) and mining.walkable(x, y)
        return stand_ok[(x, y)]

    out = {}
    for tree in trees(area_list):
        x, y = tree[0], tree[1]
        stands = [(x + dx, y + dy) for dx in range(-REACH, REACH + 1) for dy in range(-REACH, REACH + 1)
                  if (dx or dy) and can_stand(x + dx, y + dy)]
        if not stands:
            continue
        b = out.setdefault((x // 8, y // 8), {'trees': [], 'pairs': []})
        b['trees'].append(tree)
        b['pairs'] += [(tree, s) for s in stands]
    return out


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def centre(block):
    ts = block['trees']
    return (round(sum(t[0] for t in ts) / len(ts)), round(sum(t[1] for t in ts) / len(ts)))


RIDE_LIMIT = 45  # tiles: hops are measured along the ground up to this far; further ones count double the straight line


def ride_distances(points, area_list):
    """How far apart the points are riding (8 ways over walkable tiles inside the areas), not as the crow flies: a
    straight line from the north lobe to the south one crosses the mountain in the west. Each point is first moved to
    the nearest walkable tile. Pairs further than RIDE_LIMIT apart get twice their straight distance."""
    from collections import deque
    ok = {}

    def walk(x, y):
        if (x, y) not in ok:
            ok[(x, y)] = mining.in_areas(area_list, x, y) and mining.walkable(x, y, learned=False)
        return ok[(x, y)]

    starts = []
    for p in points:
        near = [(p[0] + dx, p[1] + dy) for r in range(0, 6) for dx in range(-r, r + 1) for dy in range(-r, r + 1)
                if max(abs(dx), abs(dy)) == r and walk(p[0] + dx, p[1] + dy)]
        starts.append(near[0] if near else tuple(p))
    index = {}
    for i, s in enumerate(starts):
        index.setdefault(s, []).append(i)
    n = len(points)
    dist = [[2 * cheb(points[i], points[j]) for j in range(n)] for i in range(n)]
    for i, s in enumerate(starts):
        seen = {s: 0}
        q = deque([s])
        while q:
            x, y = q.popleft()
            d = seen[(x, y)]
            for j in index.get((x, y), ()):
                dist[i][j] = min(dist[i][j], d)
            if d >= RIDE_LIMIT:
                continue
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nb = (x + dx, y + dy)
                    if nb not in seen and abs(nb[0] - s[0]) <= RIDE_LIMIT and abs(nb[1] - s[1]) <= RIDE_LIMIT and walk(*nb):
                        seen[nb] = d + 1
                        q.append(nb)
    for i in range(n):
        for j in range(i):
            dist[i][j] = dist[j][i] = min(dist[i][j], dist[j][i])
    return dist


def tour_order(points, start, dist):
    """A short closed tour through the points (indices): nearest neighbour from the one nearest start, then 2-opt
    until no swap shortens it; distances from ride_distances."""
    n = len(points)
    first = min(range(n), key=lambda i: cheb(points[i], start))
    order, left = [first], set(range(n)) - {first}
    while left:
        here = order[-1]
        nxt = min(left, key=lambda i: dist[here][i])
        order.append(nxt)
        left.remove(nxt)
    d = lambda i, j: dist[order[i % n]][order[j % n]]  # noqa: E731
    better = True
    while better:
        better = False
        for i in range(n - 1):
            for j in range(i + 2, n if i else n - 1):
                if d(i, i + 1) + d(j, j + 1) > d(i, j) + d(i + 1, j + 1):
                    order[i + 1:j + 1] = reversed(order[i + 1:j + 1])
                    better = True
    # start at the block nearest the start spot, in the loop's own direction
    k = order.index(first)
    return order[k:] + order[:k]


def plan(start=MEET_ICEPICK):
    area_list = areas()
    found = blocks(area_list)
    keys = sorted(found)
    points = [centre(found[k]) for k in keys]
    dist = ride_distances(points, area_list)
    order = tour_order(points, start, dist)
    # only the order is saved (the trees and spots come from the map each time: a few seconds)
    saved = [{'block': list(keys[i]), 'ride': dist[i][order[(k + 1) % len(order)]]} for k, i in enumerate(order)]
    with open(TOUR, 'w', encoding='utf-8') as fh:
        fh.write('[\n' + ',\n'.join(json.dumps(s) for s in saved) + '\n]\n')
    return load_tour(found)


def load_tour(found=None):
    """The saved tour, each block with its trees, (tree, stand) pairs and centre from the map. A block that no longer
    has a tree with somewhere to stand (a building learned since) is left out."""
    with open(TOUR, encoding='utf-8') as fh:
        saved = json.load(fh)
    found = found or blocks()
    tour = []
    for s in saved:
        b = found.get(tuple(s['block']))
        if b:
            tour.append({'block': tuple(s['block']), 'ride': s['ride'], 'centre': centre(b), 'trees': b['trees'],
                         'pairs': b['pairs']})
    return tour


def choose(target, rng=random):
    """A random tree of the block and a random place to stand within reach of it (as mining.choose: not the same
    spot every time). Returns (tree, stand, the block's other trees in random order to try next)."""
    tree = rng.choice(target['trees'])
    stand = rng.choice([s for t, s in target['pairs'] if t == tree] or [target['pairs'][0][1]])
    others = [t for t in target['trees'] if t != tree]
    rng.shuffle(others)
    return tree, stand, others


def draw(out, tour, scale=3):
    import drawmap
    m = mining.game_map()
    area_list = areas()
    x1 = min(a['box'][0] for a in area_list) - 4
    y1 = min(a['box'][1] for a in area_list) - 4
    x2 = max(a['box'][2] for a in area_list) + 4
    y2 = max(a['box'][3] for a in area_list) + 4
    s = scale
    w, h = (x2 - x1 + 1) * s, (y2 - y1 + 1) * s
    px = [(0, 0, 0)] * (w * h)

    def fill(tx, ty, colour, inset=0):
        if x1 <= tx <= x2 and y1 <= ty <= y2:
            for dy in range(inset, s - inset):
                row = ((ty - y1) * s + dy) * w
                for dx in range(inset, s - inset):
                    px[row + (tx - x1) * s + dx] = colour

    for ty in range(y1, y2 + 1):
        for tx in range(x1, x2 + 1):
            tile, z = m.land(tx, ty)
            colour = m.radar_land(tile)
            st = m.statics(tx, ty)
            if st:
                top = max(st, key=lambda q: q[1] + m.static_heights[q[0]])
                colour = m.radar_static(top[0])
            if not mining.in_areas(area_list, tx, ty):
                colour = tuple(c // 3 for c in colour)
            fill(tx, ty, colour)
    # the trees, small; then the tour over them: a bold line from block to block, white at the start fading through
    # yellow to red at the end, so the direction shows
    for t in tour:
        for tr in t['trees']:
            fill(tr[0], tr[1], (40, 160, 40), inset=1)
    pts = [t['centre'] for t in tour] + [tour[0]['centre']]
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        f = i / max(1, len(pts) - 2)
        colour = (255, int(255 - 225 * f), int(255 * max(0.0, 1 - 3 * f)))
        steps = max(abs(b[0] - a[0]), abs(b[1] - a[1]), 1)
        for k in range(steps + 1):
            fill(round(a[0] + (b[0] - a[0]) * k / steps), round(a[1] + (b[1] - a[1]) * k / steps), colour)
    for d in range(-3, 4):
        for spot, colour in ((MEET_BURGERS, (0, 230, 230)), (tour[0]['centre'], (255, 0, 255))):
            fill(spot[0] + d, spot[1], colour)
            fill(spot[0], spot[1] + d, colour)
    drawmap.write_png(out, w, h, px)
    return w, h


def show(tour):
    total = sum(t.get('ride', 0) for t in tour)
    print(f"{len(tour)} blocks, {sum(len(t['trees']) for t in tour)} trees; a lap is about {total} tiles of riding "
          f"between blocks")
    hops = sorted(((t.get('ride', 0), n) for n, t in enumerate(tour)), reverse=True)
    print('longest hops:', ', '.join(f"{d} tiles after block {n} {tour[n]['centre']}" for d, n in hops[:8]))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'show'
    if cmd == 'plan':
        tour = plan()
        show(tour)
    elif cmd == 'show':
        show(load_tour())
    elif cmd == 'draw':
        w, h = draw(sys.argv[2], load_tour())
        print(f'{sys.argv[2]}: {w}x{h}')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
