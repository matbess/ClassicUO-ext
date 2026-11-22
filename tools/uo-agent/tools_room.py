"""The Castle's tools room (the user, 2026-11-21): the south-east room, where tools are kept in bulk, in backpacks
stacked along its north and west walls, one kind of tool to a bag. Shovels first: "I want each bag to hold 50 shovels
(because they're kind of heavy). You'll place the bags along the ground and then stack bags on top of bags". The
tools chests by the forge keep just one bag of each kind.

  python3 tools_room.py put       every tool of the room's kinds in Clem's pack (loose, or in any bag in it) into
                                  that kind's bags (`shovels` or `hatchets` for one kind only)
  python3 tools_room.py show      the stacks and what each bag holds (opens them; nothing is moved)
  python3 tools_room.py count [--known]   open every bag in the room and put the totals on The Vault page (then
                                  publish it); --known sends nothing, from what the client knows

The Vault page shows the room combined, one total per tool, never bag by bag (the user, 2026-11-21: "combine
everything, don't list each bag just list the total number of shovels (and any other tools we add there)"). A
put-away updates those totals itself (vault/inventory.json "tools_room", embedded in vault/index.html).

The kinds (the user, 2026-11-21): shovels on the north wall, 4 stacks (x 944-947 at y 2345, the user's first bags);
hatchets for lumberjacking on the west wall, 3 stacks (x 944 at y 2346-2348: "along the west wall we can fix 3 stacks
of bags and we'll put hatches/axes for lumberjacking. That will probably be all we put in this room"). Saws stay in
the tools chests by the forge ("we'll leave the saws where they are for now").

Bags fill bottom layer first, along the wall from the north-west corner, each up to 50. When they're full, more come from the spare backpacks chest (938 floor), only plain backpacks and only empty
ones, stacks up to 20 bags high (the user, 2026-11-21: "when we run out of room in these backpacks you'll get more backpacks from the chest ...
you should only use backpacks for the tools room, not other containers"), each put on top of the lowest stack (west
first).
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import uo  # noqa: E402
import castle_move  # noqa: E402
import look  # noqa: E402
import tower_down as td  # noqa: E402

# each kind: its graphics, its stacks (bottom layer filled first, in this order), how many to a bag
KINDS = {
    'shovels': {'graphics': {'0x0F39', '0x0F3A'}, 'stacks': [(944, 2345), (945, 2345), (946, 2345), (947, 2345)],
                'per_bag': 50},  # "because they're kind of heavy" (5 stones: 250 a bag)
    'hatchets': {'graphics': {'0x0F43', '0x0F44'}, 'stacks': [(944, 2346), (944, 2347), (944, 2348)],
                 'per_bag': 50},  # as the shovels (4 stones: 200 a bag)
}
BACKPACK = '0x0E75'
# never a pouch: the user keeps trapped pouches in Clem's pack (2026-11-21: "you're opening my trapped bags, dont'
# open those ones"); the 3 there are offLimits in his rules too
CONTAINERS = {'0x0E75', '0x0E76', '0x09B0', '0x0E7D', '0x09AA', '0x09A8', '0x0E3D', '0x0E3E', '0x0E3F'}
ROOM = (943, 2344, 947, 2348)
STACKS = {k: v['stacks'] for k, v in KINDS.items()}
PER_BAG = {k: v['per_bag'] for k, v in KINDS.items()}
STAND = (945, 2346)  # within 2 of every stack, both walls
STACK_MAX = 20  # bags to a stack, up to the ceiling (the user, 2026-11-21: "I think 20 is the limit allowed. Let's set it at 20")
SPARE_BACKPACKS = '0x406E85EC'  # 938 floor, the spare backpacks chest (castle_plan)
SPARE_STAND = (939, 2349)       # in front of it, on the south walkway (the tables are up at the forge since 2026-11-20)
info = None
OFF_LIMITS = set()


def say(text):
    td.say(text)


def walk_to(p, what):
    for _ in range(3):
        st = uo.call(info, 'GET', '/status')
        if (st['x'], st['y']) == tuple(p):
            return
        uo.call(info, 'POST', '/walk', x=p[0], y=p[1])
        time.sleep(0.5)
    raise td.Stop(f"couldn't get {what} ({p[0]},{p[1]}): he's at {st['x']},{st['y']}")


def stand():
    """Into the tools room. A plain walk from behind the tables (the tools room, the south-east rooms, the east
    hall); from anywhere else the castle's own route, which deals with the tables (castle_site.Mover)."""
    import castle_site
    st = uo.call(info, 'GET', '/status')
    here = (st['x'], st['y'])
    if not (ROOM[0] <= here[0] <= ROOM[2] and ROOM[1] <= here[1] <= ROOM[3]) and not castle_site.behind(here):
        global MOVER
        MOVER = castle_site.Mover(uo, info, say)
        MOVER.go((944, 2348), 'to the tools room')
    walk_to(STAND, 'to the tools room')


MOVER = None  # set when he came in past the tables: he leaves the same way at the end, the table locked behind him


def fetch_backpacks(n, pack):
    """n empty backpacks from the spare backpacks chest into his pack, and back to the tools room. Only backpacks,
    and only empty ones."""
    walk_to(SPARE_STAND, 'to the spare backpacks chest')
    items = look.open_once(info, SPARE_BACKPACKS)
    got = []
    for b in [i for i in items if i.get('graphic') == BACKPACK]:
        if len(got) == n:
            break
        if contents(b['serial'])[0]:
            say(f"{b['serial']} in the spare backpacks chest isn't empty: left there")
            continue
        uo.call(info, 'POST', '/move', serial=b['serial'], to=pack, x=60 + 8 * len(got), y=70)
        got.append(b['serial'])
    walk_to(STAND, 'back to the tools room')
    if len(got) < n:
        say(f'the spare backpacks chest had only {len(got)} empty backpacks of the {n} needed')
    return got


def place_bag(serial, kind):
    """A backpack from his pack onto the lowest of that kind's stacks (west first)."""
    _, by_spot = bags(kind)
    spots = STACKS[kind]
    room = [s for s in spots if len(by_spot.get(s, [])) < STACK_MAX]
    if not room:
        raise td.Stop(f'the {kind} stacks are all {STACK_MAX} high: where do the next bags go? '
                      f'(the backpack {serial} is in his pack)')
    x, y = min(room, key=lambda s: (len(by_spot.get(s, [])), spots.index(s)))
    r = uo.call(info, 'POST', '/move', serial=serial, ground=1, x=x, y=y)
    got = uo.call(info, 'GET', '/item', serial=serial)
    it = got['item']
    if got.get('insideOf') or (it.get('x'), it.get('y')) != (x, y):
        raise td.Stop(f"the backpack {serial} didn't go down on the stack at {x},{y} "
                      f"({' | '.join(m.get('text', '') for m in r.get('messages', []))})")
    return dict(it, serial=serial)


def bags(kind):
    """The backpacks on the floor of that kind's stacks, bottom layer first, west to east."""
    spots = STACKS[kind]
    found = uo.call(info, 'GET', '/nearby', range=8, containers=1)
    items = found.get('items', found) if isinstance(found, dict) else found
    out = [i for i in items if not i.get('parent') and i.get('graphic') == BACKPACK and (i.get('x'), i.get('y')) in spots]
    by_spot = {}
    for i in sorted(out, key=lambda i: i.get('z', 0)):
        by_spot.setdefault((i['x'], i['y']), []).append(i)
    order = []
    for level in range(max((len(v) for v in by_spot.values()), default=0)):
        for s in spots:
            if level < len(by_spot.get(s, [])):
                order.append(by_spot[s][level])
    return order, by_spot


def room_bags():
    """Every backpack on the tools room floor, whatever stack it's in."""
    found = uo.call(info, 'GET', '/nearby', range=8, containers=1)
    items = found.get('items', found) if isinstance(found, dict) else found
    return [i for i in items if not i.get('parent') and i.get('graphic') == BACKPACK and i.get('x') is not None
            and ROOM[0] <= i['x'] <= ROOM[2] and ROOM[1] <= i['y'] <= ROOM[3]]


def plural(name):
    name = name.lower()
    return name if name.endswith('s') else name[:-1] + 'ies' if name.endswith('y') else name + 's'


def to_page(held):
    """The room's totals onto The Vault page: held is {bag serial: [item type, ...]} for every bag in the room."""
    import collections
    import json
    import importlib.util
    spec = importlib.util.spec_from_file_location('inventory', os.path.join(HERE, 'inventory.py'))
    inv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inv)
    totals = collections.Counter(plural(t) for items in held.values() for t in items)
    data = json.load(open(inv.OUT, encoding='utf-8'))
    data['tools_room'] = {'updated': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'bags': len(held),
                          'in_use': sum(1 for items in held.values() if items),
                          'tools': [{'name': k, 'amount': v} for k, v in sorted(totals.items())]}
    inv.save(inv.OUT, data)
    say('the page: tools room ' + (', '.join(f'{v} {k}' for k, v in sorted(totals.items())) or 'empty')
        + f' in {len(held)} bags (publish vault/index.html)')


def count():
    """--known: from what the client already knows (sends nothing; fine while the user has Clem)."""
    known = '--known' in sys.argv
    if not known:
        stand()
    held = {}
    for b in room_bags():
        items = uo.call(info, 'GET', '/contents', serial=b['serial'])['items'] if known else contents(b['serial'])[0]
        held[b['serial']] = [i.get('type') or i['graphic'] for i in items]
    to_page(held)


def contents(serial):
    r = uo.call(info, 'POST', '/open', serial=serial)
    uo.call(info, 'POST', '/close', serial=serial)
    return r['contents']['items'], r['contents'].get('area')


def find_in_pack(pack):
    """Every tool of the room's kinds in the pack, opening each bag in it (and bags in those); returns
    ({kind: [items]}, bags opened)."""
    global OFF_LIMITS
    OFF_LIMITS = set(uo.call(info, 'GET', '/rules').get('offLimits', []))
    found, opened = {k: [] for k in KINDS}, []
    queue = [pack]
    while queue:
        c = queue.pop(0)
        try:
            items = contents(c)[0] if c != pack else uo.call(info, 'POST', '/open', serial=pack)['contents']['items']
        except uo.BridgeError as e:  # a pouch that never answers a double-click (like the tower's runebooks)
            if not (e.code == 423 and 'no answer' in e.message) or c == pack:
                raise
            uo.call(info, 'POST', '/resume')
            say(f'{c} gave no answer when opened: skipped (look in it yourself)')
            continue
        if c != pack:
            opened.append(c)
        for i in items:
            kind = kind_of(i)
            if kind:
                found[kind].append(dict(i, inside=c))
            elif i.get('graphic') in CONTAINERS and i['serial'] not in OFF_LIMITS:
                queue.append(i['serial'])
    return found, opened


def kind_of(item):
    return next((k for k, v in KINDS.items() if item.get('graphic') in v['graphics']), None)


def spot(area, n):
    """The nth drop spot in a bag: a 10 x 5 grid over its area, so no two tools sit on the same pixel."""
    x0, y0, x1, y1 = area or (44, 65, 186, 159)  # a backpack's
    col, row = n % 10, (n // 10) % 5
    return int(x0 + col * (x1 - x0 - 50) / 9), int(y0 + row * (y1 - y0 - 50) / 4)


def put(kinds=None):
    kinds = kinds or list(KINDS)
    pack = uo.call(info, 'GET', '/status')['backpack']['serial']
    found, opened = find_in_pack(pack)
    for kind in kinds:
        f = found[kind]
        say(f'{len(f)} {kind} in his pack ({sum(1 for i in f if i["inside"] == pack)} loose, '
            f'the rest in {len({i["inside"] for i in f} - {pack})} bags)')
    if not any(found[k] for k in kinds):
        return
    stand()
    for kind in kinds:
        if found[kind]:
            fill(kind, found[kind], pack)
    page = {}
    for b in room_bags():  # the page's totals: every bag in the room
        page[b['serial']] = [i.get('type') or i['graphic'] for i in contents(b['serial'])[0]]
    to_page(page)
    empty = [c for c in opened if not contents(c)[0]]
    if empty:
        say(f"emptied and still in his pack: {', '.join(empty)}")
    if MOVER:  # he came in past the tables: out the same way, the table locked down behind him
        MOVER.leave_to((933, 2336))


def fill(kind, found, pack):
    graphics = KINDS[kind]['graphics']
    order, _ = bags(kind)
    held = {}
    areas = {}
    for b in order:
        items, area = contents(b['serial'])
        others = [i for i in items if i.get('graphic') not in graphics]
        if others:
            raise td.Stop(f"the bag {b['serial']} at {b['x']},{b['y']},{b['z']} holds other things: "
                          f"{', '.join(i.get('type') or i['graphic'] for i in others)}")
        held[b['serial']], areas[b['serial']] = len(items), area
    say('the bags: ' + ', '.join(f"{b['x']},{b['y']} z{b['z']} {held[b['serial']]}" for b in order))
    short = len(found) - sum(PER_BAG[kind] - n for n in held.values())
    if short > 0:  # more bags: from the spare backpacks chest, onto the stacks
        _, by_spot = bags(kind)
        free = sum(STACK_MAX - len(by_spot.get(s, [])) for s in STACKS[kind])
        need = -(-short // PER_BAG[kind])
        if need > free:
            say(f'{need} more bags needed but only room for {free} on the {kind} stacks ({STACK_MAX} high)')
        for serial in fetch_backpacks(min(need, free), pack):
            b = place_bag(serial, kind)
            items, area = contents(serial)
            order.append(b)
            held[serial], areas[serial] = len(items), area
            say(f"a new bag {serial} on the stack at {b['x']},{b['y']} (z {b.get('z')})")
    moved = 0
    for b in order:
        while found and held[b['serial']] < PER_BAG[kind]:
            s = found.pop(0)
            x, y = spot(areas[b['serial']], held[b['serial']])
            uo.call(info, 'POST', '/move', serial=s['serial'], to=b['serial'], x=x, y=y)
            held[b['serial']] += 1
            moved += 1
        if not found:
            break
    say(f'{moved} {kind} put away. The bags: '
        + ', '.join(f"{b['x']},{b['y']} z{b['z']} {held[b['serial']]}" for b in order))
    if found:
        raise td.Stop(f'{len(found)} {kind} left with no room in the bags (the stacks are full or the spare '
                      'backpacks chest ran out of empty backpacks)')


def show():
    for kind in STACKS:
        order, _ = bags(kind)
        for b in order:
            items, _ = contents(b['serial'])
            n = sum(1 for i in items if i.get('graphic') in KINDS[kind]['graphics'])
            print(f"{kind}: {b['serial']} {b['x']},{b['y']} z{b['z']}: {n} {kind}"
                  + (f", {len(items) - n} other" if len(items) != n else ''))


def main():
    global info
    info = uo.find_bridge('Clem')
    td.info = castle_move.info = info
    castle_move.say = say
    uo.call = td.call_past_razor
    look.uo = uo
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'show'
    if cmd in KINDS:
        put([cmd])
    else:
        {'put': put, 'show': show, 'count': count}[cmd]()


if __name__ == '__main__':
    main()
