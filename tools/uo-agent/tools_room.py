"""The Castle's tools room (the user, 2026-11-21): the south-east room, where tools are kept in bulk, in backpacks
stacked along its north and west walls, one kind of tool to a bag. The tools chests by the forge keep just one bag of
each kind.

  python3 tools_room.py put       every tool of the room's kinds in Clem's pack (loose, or in any bag in it) into
                                  that kind's bags (`shovels` or `axes` for one kind only)
  python3 tools_room.py show      the stacks and what each bag holds (opens them; nothing is moved)
  python3 tools_room.py count [--known]   open every bag in the room and put the totals on The Vault page (then
                                  publish it); --known sends nothing, from what the client knows

The kinds (the user, 2026-11-21):
- shovels on the north wall, 4 stacks (x 944-947 at y 2345, the user's first bags): "I want each bag to hold 50
  shovels (because they're kind of heavy). You'll place the bags along the ground and then stack bags on top of bags".
- axes for lumberjacking on the west wall, 3 stacks (x 944 at y 2346-2348): "along the west wall we can fix 3 stacks
  of bags and we'll put hatches/axes for lumberjacking. That will probably be all we put in this room". Every plain
  (non-magic) one: "the tools room will store all non-magical axes and hatchets.. AND it will also store any
  axe/hatchet you find that would normally go to smelting" (plan.py sends those here from a sort), and "only bring the
  ones that work for lumberjacking" ("i mostly bring double axe"): hatchet, axe, battle axe, double axe,
  executioner's axe, large battle axe, two handed axe. Not the war axe (RunUO's has no harvest system) or the pickaxe
  (mining). In a bag together, any mix of them.
- saws stay in the tools chests by the forge ("we'll leave the saws where they are for now").

A bag holds up to 50 tools and 250 stones (50 shovels; the double, two handed and executioner's axes weigh 8, so 31 of
those). Bags fill bottom layer first, along the wall from the north-west corner. When they're full, more come from the
spare backpacks chest (938 3rd), only plain backpacks and only empty ones, each put on top of the lowest stack (west
first), stacks up to 20 bags high (the user, 2026-11-21: "when we run out of room in these backpacks you'll get more
backpacks from the chest ... you should only use backpacks for the tools room, not other containers"; "Let's set it at
20").

Clem's own things in his pack (KEEP) are never put away. Pouches in his pack are never opened (trapped).

The Vault page shows the room combined, one total per tool, never bag by bag (the user, 2026-11-21: "combine
everything, don't list each bag just list the total number of shovels (and any other tools we add there)"). What
each bag holds is kept in castle/tools-room.json, but every put-away opens and counts every bag in the room again
(the user takes tools out often: "You shouldn't rely on the previous count being correct") and updates the page from
that (vault/inventory.json "tools_room", embedded in vault/index.html; publish it after).
"""
import collections
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import uo  # noqa: E402
import castle_move  # noqa: E402
import look  # noqa: E402
import tower_down as td  # noqa: E402

# tiledata weights (stones), which match the server's (21 shovels: 105 stones)
WEIGHT = {'0x0F39': 5, '0x0F3A': 5, '0x0F43': 4, '0x0F44': 4, '0x0F49': 4, '0x0F4A': 4, '0x0F47': 4, '0x0F48': 4,
          '0x0F4B': 8, '0x0F4C': 8, '0x0F45': 8, '0x0F46': 8, '0x13FA': 6, '0x13FB': 6, '0x1442': 8, '0x1443': 8}
TYPE = {'0x0F39': 'shovel', '0x0F3A': 'shovel', '0x0F43': 'hatchet', '0x0F44': 'hatchet', '0x0F49': 'axe',
        '0x0F4A': 'axe', '0x0F47': 'battle axe', '0x0F48': 'battle axe', '0x0F4B': 'double axe', '0x0F4C': 'double axe',
        '0x0F45': "executioner's axe", '0x0F46': "executioner's axe", '0x13FA': 'large battle axe',
        '0x13FB': 'large battle axe', '0x1442': 'two handed axe', '0x1443': 'two handed axe'}
# each kind: its graphics, its stacks (bottom layer filled first, in this order), and whether only plain (non-magic)
# ones in Clem's pack go (a sort's leftovers are passed in by serial, magic or not)
KINDS = {
    'shovels': {'graphics': {'0x0F39', '0x0F3A'}, 'stacks': [(944, 2345), (945, 2345), (946, 2345), (947, 2345)],
                'plain_only': False},
    'axes': {'graphics': {g for g, t in TYPE.items() if t != 'shovel'},
             'stacks': [(944, 2346), (944, 2347), (944, 2348)], 'plain_only': True},
}
ALIASES = {'hatchets': 'axes'}
PER_BAG, MAX_STONES = 50, 250
STACK_MAX = 20
# Clem's own things, never put away into the room's bags (still his to use: not offLimits in his rules)
KEEP = {
    '0x4084BB01': "Clem's own hatchet (the user, 2026-11-21: \"that hatchet is his own and should never go into another bag\")",
}
BACKPACK = '0x0E75'
# never a pouch: the user keeps trapped pouches in Clem's pack (2026-11-21: "you're opening my trapped bags, dont'
# open those ones"); the 3 there are offLimits in his rules too
CONTAINERS = {'0x0E75', '0x0E76', '0x09B0', '0x0E7D', '0x09AA', '0x09A8', '0x0E3D', '0x0E3E', '0x0E3F'}
ROOM = (943, 2344, 947, 2348)
STAND = (945, 2346)  # within 2 of every stack, both walls
OUT = (944, 2348)    # the room's side on the castle's routes (zone east): where a sort carries on from
SPARE_BACKPACKS = '0x406ED0AA'  # 938 3rd, the spare backpacks chest (castle_plan; 938 floor until 2026-11-23)
SPARE_STAND = (939, 2349)       # in front of it, on the south walkway (the tables are up at the forge since 2026-11-20)
CACHE = os.path.join(HERE, 'castle', 'tools-room.json')  # bag serial -> {x, y, z, items: {graphic: n}}
info = None
OFF_LIMITS = set()
# during a shovel run (shovels.py; the user, 2026-11-24: "you don't have to keep re-inventorying it, that would be slow,
# just assume no one is taking them out while you're doing a run. You only inventory it at the start of a run"): True
# skips the full bags and the recount of the rest; only the bags with room are opened. Off for every other job.
TRUST_CACHE = False
MOVER = None  # set when he came in past the tables: he leaves the same way at the end, the table locked behind him


def say(text):
    td.say(text)


def setup(i):
    """For a caller (sortbatch.py) with its own bridge info: this module's uo goes past Razor's AutoSearch."""
    global info
    info = i
    td.info = castle_move.info = info
    castle_move.say = say
    uo.call = td.call_past_razor
    look.uo = uo


def load():
    try:
        return json.load(open(CACHE))
    except (OSError, ValueError):
        return {}


def save(cache):
    json.dump(cache, open(CACHE, 'w'), indent=1, sort_keys=True)


def record(cache, bag, items):
    cache[bag['serial']] = {'x': bag['x'], 'y': bag['y'], 'z': bag.get('z'),
                            'items': dict(collections.Counter(i['graphic'] for i in items))}


def stones(entry):
    return sum(WEIGHT.get(g, 8) * n for g, n in entry['items'].items())


def count_in(entry):
    return sum(entry['items'].values())


def fits(entry, graphic):
    return count_in(entry) < PER_BAG and stones(entry) + WEIGHT.get(graphic, 8) <= MAX_STONES


def in_room(p):
    return ROOM[0] <= p[0] <= ROOM[2] and ROOM[1] <= p[1] <= ROOM[3]


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
    global MOVER
    import castle
    st = uo.call(info, 'GET', '/status')
    here = (st['x'], st['y'])
    if not in_room(here) and not castle.inside(here):  # the entrance room, the courtyard or the front: in first
        import restock                                    # (window top-up, courtyard rune, doors locked behind him)
        castle.info = restock.info = info
        try:
            castle.go_in()
        except castle.Stop as e:
            raise td.Stop(f'getting in: {e}')
        st = uo.call(info, 'GET', '/status')
        here = (st['x'], st['y'])
    if not in_room(here) and not castle_site.behind(here):
        MOVER = castle_site.Mover(uo, info, say)
        MOVER.go(OUT, 'to the tools room')
    walk_to(STAND, 'to the tools room')


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
    spots = KINDS[kind]['stacks']
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


def nearby_bags():
    """Every backpack on the tools room floor, whatever stack it's in."""
    found = uo.call(info, 'GET', '/nearby', range=8, containers=1)
    items = found.get('items', found) if isinstance(found, dict) else found
    return [i for i in items if not i.get('parent') and i.get('graphic') == BACKPACK and i.get('x') is not None
            and in_room((i['x'], i['y']))]


def bags(kind):
    """The backpacks on the floor of that kind's stacks, bottom layer first, along the wall."""
    spots = KINDS[kind]['stacks']
    by_spot = {}
    for i in sorted((i for i in nearby_bags() if (i['x'], i['y']) in spots), key=lambda i: i.get('z', 0)):
        by_spot.setdefault((i['x'], i['y']), []).append(i)
    order = []
    for level in range(max((len(v) for v in by_spot.values()), default=0)):
        for s in spots:
            if level < len(by_spot.get(s, [])):
                order.append(by_spot[s][level])
    return order, by_spot


def plural(name):
    name = name.lower()
    return name if name.endswith('s') else name[:-1] + 'ies' if name.endswith('y') else name + 's'


def to_page(cache):
    """The room's totals onto The Vault page, from the bags' record."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('inventory', os.path.join(HERE, 'inventory.py'))
    inv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inv)
    totals = collections.Counter()
    for e in cache.values():
        for g, n in e['items'].items():
            totals[plural(TYPE.get(g, g))] += n
    data = json.load(open(inv.OUT, encoding='utf-8'))
    data['tools_room'] = {'updated': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'bags': len(cache),
                          'in_use': sum(1 for e in cache.values() if e['items']),
                          'tools': [{'name': k, 'amount': v} for k, v in sorted(totals.items())]}
    inv.save(inv.OUT, data)
    say('the page: tools room ' + (', '.join(f'{v} {k}' for k, v in sorted(totals.items())) or 'empty')
        + f' in {len(cache)} bags (publish vault/index.html)')


def refresh(cache, known=False):
    """Every bag in the room into the record: opened (or, known, as the client knows it), dropping bags gone."""
    here = nearby_bags()
    for gone in set(cache) - {b['serial'] for b in here}:
        del cache[gone]
    for b in here:
        items = uo.call(info, 'GET', '/contents', serial=b['serial'])['items'] if known else contents(b['serial'])[0]
        record(cache, b, items)
    save(cache)


def count():
    """--known: from what the client already knows (sends nothing; fine while the user has Clem)."""
    known = '--known' in sys.argv
    if not known:
        stand()
    cache = load()
    refresh(cache, known)
    to_page(cache)


def contents(serial):
    r = uo.call(info, 'POST', '/open', serial=serial)
    uo.call(info, 'POST', '/close', serial=serial)
    return r['contents']['items'], r['contents'].get('area')


def kind_of(item):
    return next((k for k, v in KINDS.items() if item.get('graphic') in v['graphics']), None)


def plain(item):
    """Not magic: its single-click name is just its kind ("a double axe")."""
    n = uo.load_names().get(item['serial'], '').split(' / ')[0].lower()
    return re.fullmatch(r"(an? )?" + re.escape(TYPE.get(item['graphic'], '?')), n) is not None


def find_in_pack(pack, extra=()):
    """Every tool of the room's kinds in the pack, opening each bag in it (and bags in those); returns
    ({kind: [items]}, bags opened). Plain-only kinds take plain ones (named by a single click when not known), and
    any serial in extra."""
    global OFF_LIMITS
    OFF_LIMITS = set(uo.call(info, 'GET', '/rules').get('offLimits', []))
    found, opened = {k: [] for k in KINDS}, []
    queue = [pack]
    while queue:
        c = queue.pop(0)
        try:
            items = contents(c)[0] if c != pack else uo.call(info, 'POST', '/open', serial=pack)['contents']['items']
        except uo.BridgeError as e:  # a container that never answers a double-click (like the tower's runebooks)
            if not (e.code == 423 and 'no answer' in e.message) or c == pack:
                raise
            uo.call(info, 'POST', '/resume')
            say(f'{c} gave no answer when opened: skipped (look in it yourself)')
            continue
        if c != pack:
            opened.append(c)
        for i in items:
            kind = kind_of(i)
            if kind and i['serial'] not in KEEP:
                found[kind].append(dict(i, inside=c))
            elif i.get('graphic') in CONTAINERS and i['serial'] not in OFF_LIMITS:
                queue.append(i['serial'])
    names = uo.load_names()
    unnamed = [i['serial'] for k, v in KINDS.items() if v['plain_only'] for i in found[k]
               if i['serial'] not in extra and not names.get(i['serial'])]
    if unnamed:
        uo.call(info, 'POST', '/name', serial=','.join(unnamed))
    for k, v in KINDS.items():
        if v['plain_only']:
            magic = [i for i in found[k] if i['serial'] not in extra and not plain(i)]
            if magic:
                names = uo.load_names()
                say(f"not plain, left in his pack: {', '.join(names.get(i['serial'], i['serial']) for i in magic)}")
            found[k] = [i for i in found[k] if i['serial'] in extra or plain(i)]
    return found, opened


def spot(area, n):
    """The nth drop spot in a bag: a 10 x 5 grid over its area, so no two tools sit on the same pixel."""
    x0, y0, x1, y1 = area or (44, 65, 186, 159)  # a backpack's
    col, row = n % 10, (n // 10) % 5
    return int(x0 + col * (x1 - x0 - 50) / 9), int(y0 + row * (y1 - y0 - 50) / 4)


def put(kinds=None, extra=(), leave=True):
    """Everything of these kinds in his pack into the room's bags. extra: serials to take even if magic (a sort's
    axes that would have gone to smelting)."""
    kinds = kinds or list(KINDS)
    pack = uo.call(info, 'GET', '/status')['backpack']['serial']
    found, opened = find_in_pack(pack, set(extra))
    for kind in kinds:
        f = found[kind]
        if f:
            say(f'{len(f)} {kind} in his pack ({sum(1 for i in f if i["inside"] == pack)} loose, '
                f'the rest in {len({i["inside"] for i in f} - {pack})} bags)')
    if not any(found[k] for k in kinds):
        say('nothing for the tools room in his pack')
        return
    stand()
    cache = load()
    filled = set()
    for kind in kinds:
        if found[kind]:
            filled |= fill(kind, found[kind], pack, cache)
    # the rest of the room counted again too (the user takes tools out): the page's totals are today's
    here = nearby_bags()
    for gone in set(cache) - {b['serial'] for b in here}:
        del cache[gone]
    for b in here:
        if b['serial'] not in filled and not (TRUST_CACHE and b['serial'] in cache):
            record(cache, b, contents(b['serial'])[0])
    save(cache)
    to_page(cache)
    # a bag emptied of its tools stays in his pack, nothing more: the user keeps their loot bag there (2026-11-24,
    # 0x409167C6: "that's my loot bag, leave it alone, I always have a loot bag. once I fill it up with loot ill have
    # you sort the loot"); never offer to move it to the spare backpacks
    empty = [c for c in opened if not contents(c)[0]]
    if empty:
        say(f"emptied, left in his pack (the user's loot bag stays there): {', '.join(empty)}")
    if MOVER and leave:  # he came in past the tables: out the same way, the table locked down behind him
        MOVER.leave_to((933, 2336))


def assign(entries, items):
    """Greedy, on copies of the bags' records: each item into the first bag it fits; returns what's left."""
    left = []
    for it in items:
        e = next((e for e in entries if fits(e, it['graphic'])), None)
        if e is None:
            left.append(it)
        else:
            e['items'][it['graphic']] = e['items'].get(it['graphic'], 0) + 1
    return left


def fill(kind, found, pack, cache):
    graphics = KINDS[kind]['graphics']
    order, _ = bags(kind)
    areas = {}
    for b in order:
        if TRUST_CACHE and b['serial'] in cache and not fits(cache[b['serial']], graphics[0]):
            continue  # full, as counted at the start of the run
        # every bag opened, full or not: the user takes tools out often (2026-11-21: "you should check the count ...
        # You shouldn't rely on the previous count being correct")
        items, areas[b['serial']] = contents(b['serial'])
        others = [i for i in items if i.get('graphic') not in graphics]
        if others:
            raise td.Stop(f"the bag {b['serial']} at {b['x']},{b['y']},{b['z']} holds other things: "
                          f"{', '.join(i.get('type') or i['graphic'] for i in others)}")
        record(cache, b, items)
    save(cache)
    open_bags = [b for b in order if b['serial'] in areas]
    left = assign([json.loads(json.dumps(cache[b['serial']])) for b in open_bags], found)
    if left:  # more bags: from the spare backpacks chest, onto the stacks
        need = 0
        while left:
            need += 1
            left = assign([{'items': {}}], left)
        _, by_spot = bags(kind)
        free = sum(STACK_MAX - len(by_spot.get(s, [])) for s in KINDS[kind]['stacks'])
        if need > free:
            say(f'{need} more bags needed but only room for {free} on the {kind} stacks ({STACK_MAX} high)')
        for serial in fetch_backpacks(min(need, free), pack):
            b = place_bag(serial, kind)
            items, areas[serial] = contents(serial)
            record(cache, b, items)
            open_bags.append(b)
            say(f"a new bag {serial} on the stack at {b['x']},{b['y']} (z {b.get('z')})")
        save(cache)
    moved, pending = 0, list(found)
    for b in open_bags:
        e = cache[b['serial']]
        for it in list(pending):
            if not fits(e, it['graphic']):
                continue
            x, y = spot(areas[b['serial']], count_in(e))
            uo.call(info, 'POST', '/move', serial=it['serial'], to=b['serial'], x=x, y=y)
            e['items'][it['graphic']] = e['items'].get(it['graphic'], 0) + 1
            pending.remove(it)
            moved += 1
        save(cache)
        if not pending:
            break
    say(f'{moved} {kind} put away. The bags: ' + ', '.join(
        f"{b['x']},{b['y']} z{b.get('z')} {count_in(cache[b['serial']])} ({stones(cache[b['serial']])} st)"
        for b in open_bags))
    if pending:
        raise td.Stop(f'{len(pending)} {kind} left with no room in the bags (the stacks are full or the spare '
                      'backpacks chest ran out of empty backpacks)')
    return set(areas)


def show():
    cache = load()
    refresh(cache)
    for kind in KINDS:
        order, _ = bags(kind)
        for b in order:
            e = cache[b['serial']]
            print(f"{kind}: {b['serial']} {b['x']},{b['y']} z{b['z']}: {count_in(e)} ({stones(e)} stones) "
                  + ', '.join(f'{n} {TYPE.get(g, g)}' for g, n in e['items'].items()))


def main():
    setup(uo.find_bridge('Clem'))
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'show'
    cmd = ALIASES.get(cmd, cmd)
    if cmd in KINDS:
        put([cmd])
    else:
        {'put': put, 'show': show, 'count': count}[cmd]()


if __name__ == '__main__':
    main()
