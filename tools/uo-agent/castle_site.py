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
# getting around: zones joined by the user's routes (route.jsonl, 2026-11-18). All on the ground floor (z 6), except
# the stairs between the great hall and the west hall.
EDGES = {
    ('east', 'forge'): [(948, 2327), (947, 2326), (945, 2324)],
    ('forge', 'north'): [(945, 2323), (936, 2323)],
    ('north', 'west'): [(927, 2323), (924, 2326), (923, 2328)],
    ('west', 'south-west'): [(923, 2346), (923, 2348), (925, 2348), (926, 2349)],
    ('east', 'south-east'): [(949, 2346), (947, 2349), (944, 2349), (941, 2349)],  # through the user's table
    ('hall', 'west'): [(933, 2335), (932, 2332), (928, 2333), (925, 2336), (921, 2331), (924, 2323), (921, 2323),
                       (921, 2327), (923, 2328)],  # up the stairs and down again
}
TABLE_EDGE = ('east', 'south-east')


def zone(x, y):
    """Which part of the castle a ground-floor spot is in (None: the courtyard, the entrance room, outside)."""
    if y >= 2348 and 943 <= x <= 949 or x >= 946 and 2325 <= y <= 2348:
        return 'east'      # the east hall walkway, and the walkway's east end up to the user's table
    if y >= 2348 and 937 <= x <= 942:
        return 'south-east'  # behind the user's table: the east intake chests and the user's vault
    if y >= 2348 and 924 <= x <= 934:
        return 'south-west'  # the walkway past the friend's chests to the west intake chests
    if y <= 2327 and x >= 940:
        return 'forge'
    if y <= 2326 and 924 <= x < 940:
        return 'north'
    if x <= 924 and 2327 <= y <= 2348:
        return 'west'
    if 924 < x < 946 and 2324 <= y <= 2340:
        return 'hall'
    return None


def stand_zone(x, y):
    """The zone the sorter stands in to reach a chest or container at x,y (the walls' chests are on the wall)."""
    if x == 947 and 2329 <= y <= 2343:
        return 'east'
    if x == 921 and 2329 <= y <= 2343:
        return 'west'
    if x == 944 and y <= 2327 or (x, y) == (949, 2322):
        return 'forge'
    return zone(x, y)


def path(a, b):
    """The zones from a to b, as a list of (from, to) steps (breadth first over EDGES)."""
    if a == b:
        return []
    links = {}
    for (p, q) in EDGES:
        links.setdefault(p, []).append(q)
        links.setdefault(q, []).append(p)
    seen, queue = {a: None}, [a]
    while queue:
        z = queue.pop(0)
        for n in links.get(z, []):
            if n not in seen:
                seen[n] = z
                queue.append(n)
    if b not in seen:
        raise KeyError(f'no way from {a} to {b}')
    steps, z = [], b
    while seen[z] is not None:
        steps.insert(0, (seen[z], z))
        z = seen[z]
    return steps


def waypoints(step):
    if step in EDGES:
        return list(EDGES[step])
    return list(reversed(EDGES[(step[1], step[0])]))


class Mover:
    """Walks one character around the castle, opening the user's table when the way goes behind it and closing it in
    close_up(). `uo` is the caller's own uo module (each tool loads its own copy)."""

    def __init__(self, uo, info, say=print):
        self.uo, self.info, self.say = uo, info, say
        self.table_opened = False

    def status(self):
        return self.uo.call(self.info, 'GET', '/status')

    def walk(self, x, y, what=''):
        """Walk to x,y, again while he gets closer (long walks stop short)."""
        best = None
        for _ in range(6):
            st = self.status()
            d = max(abs(st['x'] - x), abs(st['y'] - y))
            if d == 0:
                return
            if best is not None and d >= best:
                break
            best = d
            r = self.uo.call(self.info, 'POST', '/walk', x=x, y=y, distance=0)
            if r.get('arrived'):
                return
        st = self.status()
        raise self.uo.BridgeError(0, f"could not walk to {x},{y}{' (' + what + ')' if what else ''}: he's at "
                                     f"{st['x']},{st['y']}")

    def go_zone(self, target):
        st = self.status()
        here = zone(st['x'], st['y'])
        if here is None:
            raise self.uo.BridgeError(0, f"he's at {st['x']},{st['y']}, not in the castle's halls")
        for step in path(here, target):
            for i, p in enumerate(waypoints(step)):
                if step == TABLE_EDGE and p == (941, 2349):
                    self.open_table()
                if step == (TABLE_EDGE[1], TABLE_EDGE[0]) and i == 0:
                    self.open_table()  # it should be open already, as he's behind it
                self.walk(*p, what=f'{step[0]} to {step[1]}')

    def walk_near(self, info, serial, reach=1):
        """uo.walk_near for the castle: zone by zone, then up to the thing."""
        spot = self.uo.on_floor(info, serial)
        if not spot or spot['distance'] <= reach:
            return
        target = stand_zone(spot['x'], spot['y'])
        if target is None:
            raise self.uo.BridgeError(0, f"{serial} at {spot['x']},{spot['y']} isn't anywhere the castle routes go")
        self.go_zone(target)
        for _ in range(5):
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
        self.walk(*castle.TABLE_STAND, what="to the user's table")
        castle.table('open')
        self.table_opened = True

    def close_up(self):
        """The user's table back in its place, locked down, if this run opened it. Always called at the end."""
        if not self.table_opened:
            return
        castle.info = self.info
        st = self.status()
        if zone(st['x'], st['y']) == 'south-east':
            self.walk(941, 2349)
        else:
            self.go_zone('east')
        self.walk(*castle.TABLE_STAND, what="back out past the user's table")
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
    for name in ('jewellery', 'magic clothing', 'attack wands', 'healing wands', 'GM armour sets', 'best weapons',
                 'best armour', 'treasure maps', 'deeds', 'gems', 'reagents'):
        t = targets(name, 'east')
        assert PLAN[t[0]]['secure'] and PLAN[t[0]]['side'] == 'east', name
        assert PLAN[t[-1]]['side'] == 'vault', name
    assert PLAN[targets('reagents', 'east')[-1]]['side'] == 'vault'
    assert [PLAN[s]['what'] for s in targets('heal potions', 'east')][:2] == ['heal potions 1', 'heal potions 2']
    assert len(targets('poison potions', 'east')) == 3
    assert [PLAN[s]['what'] for s in targets('smelting', 'east')] == [f'smelting {i}' for i in range(1, 5)]
    assert all(PLAN[s]['what'] == 'gold' for s in targets('gold', 'west'))
    assert PLAN[targets('ingots', 'east')[0]]['side'] == 'forge'
    assert [PLAN[s]['side'] for s in targets('new backpacks', 'west')] == ['forge']
    assert PLAN[targets('supplies', 'east')[0]]['what'] == 'supplies & ID wands'
    assert len(intake('east')) == 2 and len(intake('west')) == 2
    for name in ('swords', 'axes', 'maces & staves', 'polearms', 'fencing', 'archery', 'plate', 'helms', 'chain & ring',
                 'leather + caps', 'studded', 'spare + invulnerability shields', 'bone armour', 'plain gear',
                 'miscellaneous', 'needs your decision', 'cooking', 'cloth & leather', 'tools', 'boards & logs',
                 'scrolls, circles 1-4', 'scrolls, circles 5-8'):
        assert targets(name, 'east'), name
    # zones and routes
    assert zone(948, 2338) == 'east' and zone(940, 2349) == 'south-east' and zone(944, 2349) == 'east'
    assert zone(922, 2335) == 'west' and zone(932, 2349) == 'south-west' and zone(935, 2338) == 'hall'
    assert zone(945, 2323) == 'forge' and zone(930, 2323) == 'north'
    assert stand_zone(947, 2335) == 'east' and stand_zone(921, 2335) == 'west' and stand_zone(944, 2326) == 'forge'
    assert stand_zone(938, 2349) == 'south-east' and stand_zone(933, 2350) == 'south-west'
    assert stand_zone(940, 2348) == 'south-east' and stand_zone(949, 2322) == 'forge'
    assert [s[1] for s in path('east', 'south-west')] == ['forge', 'north', 'west', 'south-west']
    assert path('hall', 'east') == [('hall', 'west'), ('west', 'north'), ('north', 'forge'), ('forge', 'east')]
    assert waypoints(('forge', 'east'))[-1] == (948, 2327)
    # every waypoint is in one of the two zones it joins
    for (a, b), pts in EDGES.items():
        for p in pts:
            assert zone(*p) in (a, b) or (a, b) == ('hall', 'west'), (a, b, p)
    print('castle_site: all checks pass')


if __name__ == '__main__':
    if sys.argv[1:] == ['test']:
        test()
    else:
        sys.exit(__doc__)
