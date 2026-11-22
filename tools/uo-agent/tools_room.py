"""The Castle's tools room (the user, 2026-11-21): the south-east room, where tools are kept in bulk, in backpacks
stacked along its north and west walls, one kind of tool to a bag. Shovels first: "I want each bag to hold 50 shovels
(because they're kind of heavy). You'll place the bags along the ground and then stack bags on top of bags". The
tools chests by the forge keep just one bag of each kind.

  python3 tools_room.py shovels   every shovel in Clem's pack (loose, or in any bag in it) into the shovel bags
  python3 tools_room.py show      the stacks and what each bag holds (opens them; nothing is moved)
  python3 tools_room.py count [--known]   open every bag in the room and put the totals on The Vault page (then
                                  publish it); --known sends nothing, from what the client knows

The Vault page shows the room combined, one total per tool, never bag by bag (the user, 2026-11-21: "combine
everything, don't list each bag just list the total number of shovels (and any other tools we add there)"). A
put-away updates those totals itself (vault/inventory.json "tools_room", embedded in vault/index.html).

Bags fill bottom layer first, west to east (the user's first 4 stacks on the north wall, x 944-947 at y 2345), each
up to 50. When they're full, an empty backpack from Clem's pack goes on top of the lowest stack (west first).
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

SHOVELS = {'0x0F39', '0x0F3A'}
BACKPACK = '0x0E75'
# never a pouch: the user keeps trapped pouches in Clem's pack (2026-11-21: "you're opening my trapped bags, dont'
# open those ones"); the 3 there are offLimits in his rules too
CONTAINERS = {'0x0E75', '0x0E76', '0x09B0', '0x0E7D', '0x09AA', '0x09A8', '0x0E3D', '0x0E3E', '0x0E3F'}
ROOM = (943, 2344, 947, 2348)
STACKS = {'shovels': [(944, 2345), (945, 2345), (946, 2345), (947, 2345)]}
STAND = (945, 2346)  # within 2 of all four north-wall stacks
PER_BAG = {'shovels': 50}
info = None
OFF_LIMITS = set()


def say(text):
    td.say(text)


def stand():
    st = uo.call(info, 'GET', '/status')
    if (st['x'], st['y']) != STAND:
        uo.call(info, 'POST', '/walk', x=STAND[0], y=STAND[1])
        time.sleep(0.5)


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
    """Every shovel in the pack, opening each bag in it (and bags in those); returns (shovels, bags opened)."""
    global OFF_LIMITS
    OFF_LIMITS = set(uo.call(info, 'GET', '/rules').get('offLimits', []))
    found, opened = [], []
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
            if i.get('graphic') in SHOVELS:
                found.append(dict(i, inside=c))
            elif i.get('graphic') in CONTAINERS and i['serial'] not in OFF_LIMITS:
                queue.append(i['serial'])
    return found, opened


def spot(area, n):
    """The nth drop spot in a bag: a 10 x 5 grid over its area, so no two shovels sit on the same pixel."""
    x0, y0, x1, y1 = area or (44, 65, 186, 159)  # a backpack's
    col, row = n % 10, (n // 10) % 5
    return int(x0 + col * (x1 - x0 - 50) / 9), int(y0 + row * (y1 - y0 - 50) / 4)


def shovels():
    kind = 'shovels'
    pack = uo.call(info, 'GET', '/status')['backpack']['serial']
    found, opened = find_in_pack(pack)
    say(f'{len(found)} shovels in his pack ({sum(1 for f in found if f["inside"] == pack)} loose, '
        f'the rest in {len({f["inside"] for f in found} - {pack})} bags)')
    if not found:
        return
    stand()
    order, _ = bags(kind)
    held = {}
    areas = {}
    for b in order:
        items, area = contents(b['serial'])
        others = [i for i in items if i.get('graphic') not in SHOVELS]
        if others:
            raise td.Stop(f"the bag {b['serial']} at {b['x']},{b['y']},{b['z']} holds other things: "
                          f"{', '.join(i.get('type') or i['graphic'] for i in others)}")
        held[b['serial']], areas[b['serial']] = len(items), area
    say('the bags: ' + ', '.join(f"{b['x']},{b['y']} z{b['z']} {held[b['serial']]}" for b in order))
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
    if found:
        raise td.Stop(f'{moved} shovels put away; {len(found)} left with no room in the bags (needs another bag on a stack)')
    say(f'{moved} shovels put away. The bags: '
        + ', '.join(f"{b['x']},{b['y']} z{b['z']} {held[b['serial']]}" for b in order))
    others = {b['serial'] for b in room_bags()} - set(held)  # other tools' bags: opened for the page's totals
    page = {serial: ['shovel'] * n for serial, n in held.items()}
    for serial in others:
        page[serial] = [i.get('type') or i['graphic'] for i in contents(serial)[0]]
    to_page(page)
    empty = [c for c in opened if not contents(c)[0]]
    if empty:
        say(f"emptied and still in his pack: {', '.join(empty)}")


def show():
    for kind in STACKS:
        order, _ = bags(kind)
        for b in order:
            items, _ = contents(b['serial'])
            n = sum(1 for i in items if i.get('graphic') in SHOVELS)
            print(f"{kind}: {b['serial']} {b['x']},{b['y']} z{b['z']}: {n} shovels"
                  + (f", {len(items) - n} other" if len(items) != n else ''))


def main():
    global info
    info = uo.find_bridge('Clem')
    td.info = castle_move.info = info
    castle_move.say = say
    uo.call = td.call_past_razor
    look.uo = uo
    {'shovels': shovels, 'show': show, 'count': count}[sys.argv[1] if len(sys.argv) > 1 else 'show']()


if __name__ == '__main__':
    main()
