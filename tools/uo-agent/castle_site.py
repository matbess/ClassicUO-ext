#!/usr/bin/env python3
"""Sorting in the Castle: what the sorting tools (look.py, idall.py, plan.py, sortbatch.py, finish.py) need to know
when the sorter (Clem) is in the user's castle rather than the tower vault (CASTLE.md, "Sorting").

- **Which chest**: the plan's chests (castle_plan.py) for each of the sorter's chest names, with the overflow order:
  the side's own chest(s), then the other wall's (the user, 2026-11-18: "If we run out of space on the east side then
  we can add it to the west side (and vice versa)"), then the forge's and the user's vault's of the same kind. Since
  version 2 of the plan (2026-11-19) the west wall is all free and unassigned, and only the east side is sorted
  ("For now we'll do just the east and southeast and forge"; SIDES). A kind with secure chests (the east wall's 13,
  kept as made on 2026-11-18) goes only to those, then to "valuables overflow" behind the user's table. Gold always goes behind the table. A chest takes 125 items (counting everything inside) and a secure 395
  stones; past that the next one is used, and when none is left the run stops and says so.
- **Getting around**: long walks stop short and some places are only reached by stairs, so every walk goes zone by
  zone along the user's own routes (route.jsonl, 2026-11-18). Opening the user's table on the way to the south-east
  rooms (the east intake chests and the user's vault are behind it), and closing it at the end (close_up), always.
- **The intake chests**: the loot is whatever lies in the side's two intake chests.

Nothing here runs by itself; the tools call it. `python3 -I castle_site.py test` checks the tables offline.
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import castle  # noqa: E402
import castle_plan  # noqa: E402

LIMIT = 125            # items a chest holds, counting everything inside (the tower's rule, the same server)
SECURE_STONES = 395    # what a secure chest holds (the user, 2026-11-18: "either 395 or 400")
BARREL = '0x407EECC7'  # the trash barrel in the forge corner, 949,2322 (the user, 2026-11-18: "yes that's the trash barrel")
SITE_FILE = 'site.json'  # in a batch directory: {"site": "castle", "side": "east"}
# the sides sorted for now: the west intake chests, the west wall and the south-west wait (the user, 2026-11-19: "We'll
# figure out the west and southwest & secures later. For now we'll do just the east and southeast and forge")
SIDES = ('east',)

# the sorter's chest names (plan.py and sortbatch.py, from the tower's labels) -> the castle plan's
NAMES = {
    'chain & ring': 'chain & ring + coifs',
    'spare + invulnerability shields': 'shields',
    'supplies': 'supplies & ID wands',
    'bone armour': 'best armour',  # only really good bone is kept (daemon bone, hardening and up)
    'new backpacks': 'spare backpacks',
}
SECURE_KINDS = None  # filled from the plan: the kinds with a secure chest on the east wall


def base(what):
    """'heal potions 2' -> 'heal potions'; 'deeds 1' -> 'deeds'; 'smelting 3' -> 'smelting'."""
    return re.sub(r' \d+$', '', what)


def number(what):
    m = re.search(r' (\d+)$', what)
    return int(m.group(1)) if m else 0


PLAN = castle_plan.plan()
SECURE_KINDS = {base(e['what']) for e in PLAN.values() if e['secure'] and e['side'] == 'east'}


def chests(what, side=None):
    """The plan's chests for a kind ('swords', 'heal potions'), on one side or all, in order: number, then top
    down."""
    found = [(s, e) for s, e in PLAN.items() if base(e['what']) == what and (side is None or e['side'] == side)]
    return [s for s, e in sorted(found, key=lambda kv: (number(kv[1]['what']), kv[1]['y'], -kv[1]['z']))]


def targets(name, side):
    """Every chest that can take `name` (a sorter chest name) for a sort of `side` ('east' or 'west'), in the order
    they're filled."""
    what = NAMES.get(name, name)
    other = 'west' if side == 'east' else 'east'
    if what in SECURE_KINDS:
        secure = [s for s in chests(what, 'east') if PLAN[s]['secure']]
        mine = chests(what, 'vault') or chests('valuables overflow', 'vault')
        return secure + mine
    if what == 'gold':
        return chests('gold', 'vault')
    found = chests(what, side) + chests(what, other) + chests(what, 'forge') + chests(what, 'vault')
    if not found:
        raise KeyError(f'no castle chest for "{name}"')
    return found


def chest_title(serial, labels):
    """What a chest is called in a bag's label: "swords" for the tower's "chest: swords (col 1, top)", and "swords,
    east 2329" for the castle's "castle: swords (east 2329, top)" (both walls have one)."""
    if serial in PLAN:
        e = PLAN[serial]
        return f"{e['what']}, {e['place']}"
    return re.sub(r'^(chest|castle): ', '', labels.get(serial, serial)).split(' (')[0]


def new_bag_label(kind, chest, labels):
    return f'bag: {kind} ({chest_title(chest, labels)} chest)'


def bag_in(items, kind, labels):
    """The bag of this kind among a chest's items (by its label), or None."""
    return next((i['serial'] for i in items if labels.get(i['serial'], '').startswith(f'bag: {kind} (')), None)


def is_secure_kind(name):
    """Whether a kind's chests are secures (their weight is checked)."""
    return NAMES.get(name, name) in SECURE_KINDS


def is_secure(serial):
    return bool(PLAN.get(serial, {}).get('secure'))


def intake(side):
    return [s for s, e in PLAN.items() if e['what'] == f'intake ({side})']


def site_of(batch):
    try:
        with open(os.path.join(batch, SITE_FILE), encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {'site': 'tower'}


def write_site(batch, side):
    with open(os.path.join(batch, SITE_FILE), 'w', encoding='utf-8') as fh:
        json.dump({'site': 'castle', 'side': side}, fh)


# ---------------------------------------------------------------------------------------------------------------
# getting around: the user's own walk through the castle (route.jsonl, 2026-11-18 00:43-00:44), coded as lines of
# points. A trip is the shortest way along the lines, sent to the bridge as one path (/travel: one smooth ride, the
# next stretch started before the last ends), the way mining rides its recorded routes (the user, 2026-11-19: "You need
# to map out these walking paths so the coordinates are coded. You shouldn't need to walk so jerky and slow").
# the user's own walk from the great hall to the south-east (recorded 2026-11-19 20:32-20:33, rec2/walk.jsonl), kept as
# its turn points only: where the direction changes or a ramp starts or ends (the user: "you just record which points
# the vector (walk direction) changes"). (x, y, z): the stairs put two of them on the same x,y at two heights.
ROUTE = [(934, 2338, 6), (933, 2338, 6), (933, 2333, 6), (932, 2332, 8), (928, 2332, 26), (928, 2336, 26),
         (923, 2336, 26), (923, 2327, 26), (925, 2327, 26), (925, 2322, 26), (921, 2322, 26), (921, 2327, 6),
         (925, 2327, 6), (926, 2326, 6), (926, 2323, 6), (947, 2323, 6), (947, 2326, 6), (948, 2326, 6),
         (948, 2350, 6), (939, 2350, 6)]
UP = 20  # z this high and over: upstairs
TABLE_SPOT = (943, 2349)


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _tiles(a, b):
    """The tiles of a straight (or diagonal) stretch from a to b, a included."""
    n = cheb(a, b)
    return [(round(a[0] + (b[0] - a[0]) * k / n), round(a[1] + (b[1] - a[1]) * k / n)) for k in range(n + 1)] if n \
        else [(a[0], a[1])]


def locate(p, z=6):
    """Where p meets the route: (stretch index i, between ROUTE[i] and ROUTE[i+1], the tile on it nearest p). Only
    stretches at his height (upstairs or not) count, so the two floors at one x,y aren't mixed up."""
    up = z >= UP
    best = None
    for i, (a, b) in enumerate(zip(ROUTE, ROUTE[1:])):
        if up and not (a[2] >= UP or b[2] >= UP) or not up and not (a[2] < UP or b[2] < UP):
            continue
        for t in _tiles(a, b):
            d = (cheb(p, t), abs(p[0] - t[0]) + abs(p[1] - t[1]))
            if best is None or d < best[0]:
                best = (d, i, t)
    return best[1], best[2]


def route(start, goal, z=6):
    """The turn points from start to goal along the route, the tile where he leaves it, then the goal."""
    i, s_tile = locate(start, z)
    j, g_tile = locate(goal)
    if j > i or j == i and ROUTE.index(ROUTE[i]) == i and cheb(ROUTE[i], s_tile) <= cheb(ROUTE[i], g_tile):
        mid = [r[:2] for r in ROUTE[i + 1:j + 1]]
    else:
        mid = [r[:2] for r in reversed(ROUTE[j + 1:i + 1])]
    pts = [s_tile] + mid + [g_tile, tuple(goal)]
    return [p for k, p in enumerate(pts) if k == 0 or p != pts[k - 1]]


def nearest_point(p, z=None):
    return locate(p, z if z is not None else 6)[1]


def stand_spot(x, y):
    """Where he stands to reach a chest or container at x,y: the walkway in front of a wall's chests, the row in front
    of the user's vault, else the route's tile nearest it (and the last steps by the bridge's own walk)."""
    if x == 947 and 2329 <= y <= 2343:
        return (948, y)
    if x == 921 and 2329 <= y <= 2343:
        return (922, y)
    if y == 2348 and 937 <= x <= 942:
        return (x, 2349)
    if x == 944 and y <= 2327:  # the forge chests: in front of them, where the user stood (945,2323 and 946,2325;
        return (945, 2323) if y <= 2323 else (945, 2325)  # 2026-11-19 20:50: from 943,2324 one wouldn't open)
    return nearest_point((x, y))


def zone(x, y):
    """Which part of the castle a ground-floor spot is in (None: the courtyard, the entrance room, outside)."""
    if y >= 2348 and 943 <= x <= 949 or x >= 946 and 2325 <= y <= 2348:
        return 'east'
    if y >= 2348 and 937 <= x <= 942:
        return 'south-east'
    if y >= 2348 and 924 <= x <= 934:
        return 'south-west'
    if y <= 2327 and x >= 940:
        return 'forge'
    if y <= 2326 and 924 <= x < 940:
        return 'north'
    if x <= 924 and 2327 <= y <= 2348:
        return 'west'
    if 924 < x < 946 and 2324 <= y <= 2340:
        return 'hall'
    return None


class Mover:
    """Walks one character around the castle along the user's ROUTE, opening the user's table when the way goes behind it and
    closing it in close_up(). `uo` is the caller's own uo module (each tool loads its own copy)."""

    def __init__(self, uo, info, say=print):
        self.uo, self.info, self.say = uo, info, say
        self.table_opened = False

    def status(self):
        return self.uo.call(self.info, 'GET', '/status')

    def travel(self, pts, what):
        """One smooth ride along pts (/travel; his rules allow every height in the castle's halls, so the ramps ride
        with the rest). Done when he stands on the last point; else again from the route's tile nearest him."""
        end = tuple(pts[-1])
        for attempt in range(4):
            st = self.status()
            if (st['x'], st['y']) == end:
                return
            if attempt:
                pts = route((st['x'], st['y']), end, st['z'])
            r = self.uo.call(self.info, 'POST', '/travel', path=';'.join(f'{x},{y}' for x, y in pts[:200]))
            if r.get('stopped'):
                self.say(f"the way {what} stopped at {r.get('x')},{r.get('y')} ({r.get('stopped')}); on from there")
            st = self.status()
            if 0 < cheb((st['x'], st['y']), end) <= 2:  # the last tile or two: a plain step
                self.uo.call(self.info, 'POST', '/walk', x=end[0], y=end[1], distance=0)
        st = self.status()
        if cheb((st['x'], st['y']), end) <= 1:
            return  # a tile off: close enough for anything within reach (2 tiles)
        raise self.uo.BridgeError(0, f"could not go {what}: he's at {st['x']},{st['y']},{st['z']}")

    def go(self, goal, what=''):
        """Along the user's route to goal (the last tile included), in one ride."""
        st = self.status()
        here = (st['x'], st['y'])
        if here == tuple(goal):
            return
        pts = route(here, goal, st['z'])
        behind = lambda p: zone(*p) == 'south-east'  # noqa: E731 (behind the user's table)
        if not behind(here) and behind(tuple(goal)) and TABLE_SPOT not in pts and not any(p[1] == 2350 for p in pts):
            self.open_table()
        self.travel(pts, what or f'to {goal[0]},{goal[1]}')

    def walk(self, x, y, what=''):
        self.go((x, y), what)

    def go_zone(self, target):
        """Kept for callers that name a zone: onto the route where that zone's walks start."""
        start = {'east': (948, 2338), 'south-east': (940, 2350), 'forge': (945, 2323), 'north': (936, 2323),
                 'hall': (934, 2338)}[target]
        self.go(start, f'to the {target}')

    def walk_near(self, info, serial, reach=1):
        """uo.walk_near for the castle: along the route to where he stands for it, then the last steps. A castle chest
        out of his client's sight goes by its spot in the plan. Within 2 tiles is within reach (the bridge's REACH)."""
        reach = max(reach, 2)
        try:
            spot = self.uo.on_floor(info, serial)
        except self.uo.BridgeError as e:
            if e.code != 404 or serial not in PLAN:
                raise
            self.go(stand_spot(PLAN[serial]['x'], PLAN[serial]['y']), f'to {serial}')
            spot = self.uo.on_floor(info, serial)
        if not spot or spot['distance'] <= reach:
            return
        self.go(stand_spot(spot['x'], spot['y']), f'to {serial}')
        for _ in range(3):
            spot = self.uo.on_floor(info, serial)
            if spot['distance'] <= reach:
                return
            r = self.uo.call(info, 'POST', '/walk', to=spot['serial'], distance=reach)
            if r.get('arrived'):
                return
        raise self.uo.BridgeError(0, f"could not get within {reach} of {serial} at {spot['x']},{spot['y']}")

    def open_table(self):
        if self.table_opened:
            return
        castle.info = self.info
        st = self.status()
        if (st['x'], st['y']) != castle.TABLE_STAND:
            self.go(castle.TABLE_STAND, "to the user's table")
        castle.table('open')
        self.table_opened = True

    def close_up(self):
        """The user's table back in its place, locked down, if this run opened it. Always called at the end."""
        if not self.table_opened:
            return
        castle.info = self.info
        st = self.status()
        if (st['x'], st['y']) != castle.TABLE_STAND:
            self.go(castle.TABLE_STAND, "back out past the user's table")
        castle.table('close')
        self.table_opened = False


def install(uo, info, say=print):
    """When the character is inside the castle: send every walk of this uo module through the castle's routes, and
    return the Mover (call its close_up() at the end). Outside the castle: None, nothing changes."""
    st = uo.call(info, 'GET', '/status')
    castle.info = info
    if not castle.inside((st['x'], st['y'])):
        return None
    mover = Mover(uo, info, say)
    uo.walk_near = mover.walk_near
    return mover


# ---------------------------------------------------------------------------------------------------------------
# room left in a chest: "(N items, M stones)" from a single click, kept up to date as things go in
class Room:
    def __init__(self, uo, info):
        self.uo, self.info, self.known = uo, info, {}

    def read(self, serial):
        m = None
        for attempt in range(2):
            try:
                lines = ' '.join(a for r in self.uo.call(self.info, 'POST', '/name', serial=serial)
                                 for a in r.get('lines', []))
            except self.uo.BridgeError as e:
                if e.code not in (404, 409):
                    raise
                lines = str(e)
            m = re.search(r'\((\d+) items?, (\d+) stones?\)', lines)
            if m or attempt:
                break
            self.uo.walk_near(self.info, serial, 2)  # out of sight (the other wall): go and look
        if not m:
            raise self.uo.BridgeError(0, f'{serial} gave no item count: {lines!r}')
        self.known[serial] = [int(m.group(1)), int(m.group(2))]
        return self.known[serial]

    def fits(self, serial, items=1, stones=0):
        n, w = self.known.get(serial) or self.read(serial)
        if n + items > LIMIT:
            return False
        return not is_secure(serial) or w + stones <= SECURE_STONES

    def added(self, serial, items=1, stones=0):
        if serial in self.known:
            self.known[serial][0] += items
            self.known[serial][1] += stones

    def pick(self, name, side, items=1, stones=0):
        """The first chest for `name` with room for this many items and stones; None when all are full."""
        for c in targets(name, side):
            if self.fits(c, items, stones):
                return c
        return None


def stones(item):
    """A guess at what an item weighs, for the secure chests' limit: reagents, gems and scrolls a tenth of a stone
    each, other piles a stone each, gear 10 (a plate tunic; the heaviest weapons are about 15). After every move into
    a secure, the chest is read again."""
    g = int(item['graphic'], 16)
    amount = item.get('amount', 1)
    if 0x0F0F <= g <= 0x0F30 or 0x0F78 <= g <= 0x0F91 or 0x1F2D <= g <= 0x1F72:
        return max(1, amount // 10)
    if amount > 1:
        return amount
    return 10


def test():
    """Offline checks of the tables above (version 2 of the plan: the west wall free, the secures as made on 18 Nov)."""
    assert targets('swords', 'east')[0] == next(s for s, e in PLAN.items() if e['what'] == 'swords' and e['side'] == 'east')
    assert SIDES == ('east',)
    assert sum(e['secure'] for e in PLAN.values() if e['side'] == 'east') == 13
    assert sum(e['secure'] for e in PLAN.values() if e['side'] == 'friend') == 0
    assert all(e['what'] == 'free' for e in PLAN.values() if e['side'] == 'west' and e['x'] == 921)
    assert [PLAN[s]['place'] for s in targets('gems', 'east')] == ['my vault 942']
    assert [PLAN[s]['place'] for s in targets('house deeds', 'east')] == ['my vault 942']
    for name in ('jewellery', 'magic clothing', 'attack wands', 'healing wands', 'GM armour sets', 'best weapons',
                 'best armour', 'treasure maps', 'deeds', 'reagents'):
        t = targets(name, 'east')
        assert PLAN[t[0]]['secure'] and PLAN[t[0]]['side'] == 'east', name
        assert PLAN[t[-1]]['side'] == 'vault', name
    assert PLAN[targets('reagents', 'east')[-1]]['side'] == 'vault'
    assert [PLAN[s]['what'] for s in targets('heal potions', 'east')][:2] == ['heal potions 1', 'heal potions 2']
    assert len(targets('poison potions', 'east')) == 3
    assert [PLAN[s]['what'] for s in targets('smelting', 'east')] == [f'smelting {i}' for i in range(1, 5)]
    assert all(PLAN[s]['what'] == 'gold' for s in targets('gold', 'west'))
    assert [PLAN[s]['what'] for s in targets('ingots', 'east')] == ['ingots', 'ingots 2']
    assert [PLAN[s]['what'] for s in targets('boards & logs', 'east')] == ['boards & logs', 'boards & logs 2']
    assert [PLAN[s]['side'] for s in targets('new backpacks', 'west')] == ['forge']
    assert PLAN[targets('supplies', 'east')[0]]['what'] == 'supplies & ID wands'
    assert len(intake('east')) == 2 and len(intake('west')) == 2
    for name in ('swords', 'axes', 'maces & staves', 'polearms', 'fencing', 'archery', 'plate', 'helms', 'chain & ring',
                 'leather + caps', 'studded', 'spare + invulnerability shields', 'bone armour', 'plain gear',
                 'miscellaneous', 'needs your decision', 'cooking', 'cloth & leather', 'tools', 'boards & logs',
                 'scrolls, circles 1-4', 'scrolls, circles 5-8'):
        assert targets(name, 'east'), name
    # the user's route
    r = route((935, 2338), (948, 2335))
    assert r[0] == (934, 2338) and (928, 2332) in r and (921, 2327) in r and r[-1] == (948, 2335), r
    r = route((948, 2335), (934, 2338))
    assert r[-1] == (934, 2338) and r.index((921, 2327)) < r.index((921, 2322)), r
    assert route((923, 2330), (948, 2340), 26)[0] == (923, 2330)
    assert locate((925, 2327), 26)[1] == (925, 2327) and ROUTE[locate((925, 2327), 26)[0]][2] >= UP
    assert stand_spot(947, 2335) == (948, 2335) and stand_spot(940, 2348) == (940, 2349)
    assert zone(948, 2338) == 'east' and zone(940, 2349) == 'south-east'
    print('castle_site: all checks pass')


if __name__ == '__main__':
    if sys.argv[1:] == ['test']:
        test()
    else:
        sys.exit(__doc__)
