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
LINES = {
    # the great hall, up the stairs (z 26) and down into the west hall
    'stairs': [(935, 2338), (933, 2336), (933, 2335), (933, 2332), (932, 2332), (928, 2333), (928, 2336), (925, 2336),
               (923, 2335), (921, 2331), (923, 2329), (923, 2327), (924, 2327), (924, 2323), (921, 2323), (921, 2327),
               (922, 2327), (923, 2328)],
    # the west hall walkway, north to south
    'west hall': [(923, 2328), (923, 2329), (923, 2330), (923, 2333), (923, 2334), (923, 2336), (923, 2338),
                  (923, 2342), (923, 2343), (923, 2348)],
    # along the friend's row to the west intake chests
    'south-west': [(923, 2348), (925, 2348), (926, 2349), (929, 2349), (931, 2349), (932, 2349)],
    # the north corridor to the forge corner and the top of the east hall
    'north': [(923, 2328), (924, 2326), (925, 2325), (927, 2323), (929, 2323), (932, 2324), (936, 2323), (941, 2323),
              (945, 2323), (945, 2324), (947, 2326), (948, 2327)],
    # the east hall walkway, north to south, to the user's table
    'east hall': [(948, 2327), (949, 2328), (949, 2330), (949, 2334), (949, 2337), (949, 2340), (949, 2343),
                  (949, 2346), (947, 2349), (946, 2349), (944, 2349)],
    # past the user's table (943,2349: released and moved first) to their vault and the east intake chests
    'south-east': [(944, 2349), (943, 2349), (941, 2349), (940, 2349), (939, 2349)],
}
TABLE_SPOT = (943, 2349)


def _graph():
    links = {}
    for pts in LINES.values():
        for a, b in zip(pts, pts[1:]):
            links.setdefault(a, set()).add(b)
            links.setdefault(b, set()).add(a)
    return links


GRAPH = _graph()


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def nearest_point(p, z=None):
    """The lines' point nearest p; up on the stairs (z 20 and over) only the stairs' own points (the floor below is
    near on the map but not to him: 2026-11-19 20:18, at 927,2324,26 the nearest was 925,2325 down in the corridor)."""
    pool = STAIRS if z is not None and z >= 20 else GRAPH
    return min(pool, key=lambda q: (cheb(p, q), abs(p[0] - q[0]) + abs(p[1] - q[1])))


def route(start, goal, z=None):
    """The points along the lines from the one nearest start (at height z) to the one nearest goal (breadth first:
    fewest points; the lines are short)."""
    a, b = nearest_point(start, z), nearest_point(goal)
    seen, queue = {a: None}, [a]
    while queue:
        q = queue.pop(0)
        if q == b:
            break
        for n in sorted(GRAPH[q]):
            if n not in seen:
                seen[n] = q
                queue.append(n)
    if b not in seen:
        raise KeyError(f'no way along the lines from {start} to {goal}')
    out, q = [], b
    while q is not None:
        out.insert(0, q)
        q = seen[q]
    return out


STAIRS = set(LINES['stairs'][1:-1])  # the points up on the stairs (not the two ends, on the floors)


def stretches(pts):
    """pts cut where he goes onto or off the stairs."""
    out, cur = [], []
    for p in pts:
        if cur and (p in STAIRS) != (cur[-1] in STAIRS):
            out.append(cur + [p])  # the joining point ends this stretch and starts the next
            cur = [p]
            continue
        cur.append(p)
    if cur and (not out or len(cur) > 1):
        out.append(cur)
    return out


def stand_spot(x, y):
    """Where he stands to reach a chest or container at x,y: the walkway in front of a wall's chests, else the
    nearest point of the lines (and the last steps by the bridge's own walk)."""
    if x == 947 and 2329 <= y <= 2343:
        return (948, y)
    if x == 921 and 2329 <= y <= 2343:
        return (922, y)
    if y == 2348 and 937 <= x <= 942:
        return (x, 2349)
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
    """Walks one character around the castle along LINES, opening the user's table when the way goes behind it and
    closing it in close_up(). `uo` is the caller's own uo module (each tool loads its own copy)."""

    def __init__(self, uo, info, say=print):
        self.uo, self.info, self.say = uo, info, say
        self.table_opened = False

    def status(self):
        return self.uo.call(self.info, 'GET', '/status')

    def travel(self, pts, what):
        """One smooth ride along pts; again from where he got to if it stops short (twice)."""
        for attempt in range(3):
            st = self.status()
            here = (st['x'], st['y'])
            rest = pts[min(range(len(pts)), key=lambda k: cheb(here, pts[k])):] if attempt else pts
            if cheb(here, pts[-1]) == 0:
                return
            r = self.uo.call(self.info, 'POST', '/travel', path=';'.join(f'{x},{y}' for x, y in rest[:200]))
            if r.get('arrived'):
                return
            self.say(f"the way {what} stopped at {r.get('x')},{r.get('y')} ({r.get('stopped')}); on from there")
        st = self.status()
        raise self.uo.BridgeError(0, f"could not go {what}: he's at {st['x']},{st['y']}")

    def go(self, goal, what=''):
        """Along the lines to goal (the last tile included)."""
        st = self.status()
        here = (st['x'], st['y'])
        if here == tuple(goal):
            return
        pts = route(here, goal, st['z'])
        if tuple(goal) != pts[-1]:
            pts.append(tuple(goal))
        behind = lambda p: zone(*p) == 'south-east'  # noqa: E731 (behind the user's table)
        if not behind(here) and any(behind(p) for p in pts):  # going in: the table first
            cut = next(i for i, p in enumerate(pts) if p == TABLE_SPOT or behind(p))
            if cut:
                self.travel(pts[:cut], f'to the user\'s table ({what})')
            self.open_table()
            pts = pts[cut:]
        # in stretches, one per line: the bridge checks every point of a ride against his areas at the height he's
        # at when it starts, so the stairs (z 26) and the floors (z 6) can't share a ride (2026-11-19 20:18:
        # "waypoint 936,2323 is outside the agent's area", sent from the top of the stairs)
        for part in stretches(pts):
            self.travel(part, what or f'to {goal[0]},{goal[1]}')

    def walk(self, x, y, what=''):
        self.go((x, y), what)

    def go_zone(self, target):
        """Kept for callers that name a zone: onto the lines' point that zone's walks start from."""
        start = {'east': (948, 2338), 'south-east': (940, 2349), 'south-west': (929, 2349), 'forge': (945, 2324),
                 'north': (936, 2323), 'west': (923, 2338), 'hall': (935, 2338)}[target]
        self.go(start, f'to the {target}')

    def walk_near(self, info, serial, reach=1):
        """uo.walk_near for the castle: along the lines to where he stands for it, then the last steps. A castle chest
        out of his client's sight goes by its spot in the plan."""
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
            self.travel(route((st['x'], st['y']), castle.TABLE_STAND), "to the user's table")
        castle.table('open')
        self.table_opened = True

    def close_up(self):
        """The user's table back in its place, locked down, if this run opened it. Always called at the end."""
        if not self.table_opened:
            return
        castle.info = self.info
        st = self.status()
        if (st['x'], st['y']) != castle.TABLE_STAND:
            self.travel(route((st['x'], st['y']), castle.TABLE_STAND), "back out past the user's table")
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
    # the coded walk
    assert route((935, 2338), (922, 2335))[:3] == [(935, 2338), (933, 2336), (933, 2335)]
    r = route((948, 2338), (932, 2349))
    assert (923, 2328) in r and (945, 2323) in r and r[-1] == (932, 2349), r
    r = route((929, 2349), (940, 2349))
    assert TABLE_SPOT in r and r[-1] == (940, 2349)
    assert stand_spot(947, 2335) == (948, 2335) and stand_spot(921, 2335) == (922, 2335)
    assert stand_spot(940, 2348) == (940, 2349) and stand_spot(938, 2350) == (939, 2349)
    assert zone(948, 2338) == 'east' and zone(940, 2349) == 'south-east' and zone(944, 2349) == 'east'
    assert all(len(pts) <= 200 for pts in LINES.values())
    parts = stretches(route((935, 2338), (948, 2335)))
    assert len(parts) == 3 and parts[1][1] in STAIRS and parts[2][0] not in STAIRS or parts[2][0] == (923, 2328), parts
    print('castle_site: all checks pass')


if __name__ == '__main__':
    if sys.argv[1:] == ['test']:
        test()
    else:
        sys.exit(__doc__)
