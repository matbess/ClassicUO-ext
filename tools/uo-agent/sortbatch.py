#!/usr/bin/env python3
"""Sort a batch of loot into the chest room.

  sortbatch.py SPEC.json

SPEC says where the gear goes (decided per batch from the keep rules in the uo-sort skill):
  loot:           containers on the floor holding the batch
  new_slots:      [[chest label part, marker serial, kind], ...]  new bag (from the backpacks crate) with its marker
  into:           [[serial, bag], ...]                             keepers and plain gear into bags, by serial or label
  place_in:       [[serial, chest label part], ...]                smelting, needs your decision, ...
  spares, cut:    [serial, ...]                                    ID tools, cut with the scissors
  trash, smelt:   [serial, ...]                                    carried in loads to the trash barrel, or to the
                                                                   smelting crates (each takes up to 125 items before
                                                                   the next one is used)
  sets:           [serial, ...]                                    GM armour set pieces: each goes into the first set
                                                                   bag in the GM chest missing that piece, or a new one
  scroll_markers: {"circle": serial, ...}                          markers for circles that have none yet
  learn_first:    [chest label part, ...]                          chests to open first, so the bags inside are known

Stackables are sorted without being listed: reagents and gems (inside the gem bag) merge onto their piles; scrolls go into their
circle's bag at the spell's place; potions go into their crate; empty bottles and cut leather or cloth go to supplies;
gold goes to needs your decision and iron ore to smelting (both left in loot bags by accident); hides are cut into
leather.
Existing piles are found by looking in the containers. Containers are opened first so the client knows them.
New bags get a label ("bag: KIND (CHEST chest)"), and every chest opened is recorded in layout.json at the end.
Waits while someone is in the room and out world saves; stops at the first problem and says where.
"""
import importlib.util
import json
import os
import re
import sys
import time

here = os.path.dirname(os.path.realpath(__file__))
for module in ('uo', 'layout'):
    spec = importlib.util.spec_from_file_location(module, os.path.join(here, module + '.py'))
    globals()[module] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(globals()[module])

BACKPACK = '0x4079CC26'
SCISSORS_GRAPHICS = ('0x0F9E', '0x0F9F')  # any pair in Johnny's backpack: the user plays him and may take them
SPARES = '0x4049D6B8'
SCROLL_BAGS = {1: '0x40832F6B', 2: '0x4086BE0E', 3: '0x4092B7CC', 4: '0x4092B7D2', 5: '0x4092B7BF', 6: '0x4092B7BB',
               7: '0x407B195C', 8: '0x4087FCC6'}
SCROLL_MARKER_SPOTS = {1: (18, 128), 2: (31, 128), 3: (45, 128), 4: (59, 128), 5: (73, 128), 6: (87, 128), 7: (104, 128), 8: (118, 128)}
REAGENTS = ['0x0F7A', '0x0F7B', '0x0F84', '0x0F85', '0x0F86', '0x0F88', '0x0F8D', '0x0F8C']   # two rows of four, in order
GEMS = ['0x0F25', '0x0F16', '0x0F15', '0x0F26', '0x0F10', '0x0F13', '0x0F19', '0x0F21', '0x0F2D']  # amber .. tourmaline
GOLD = {'0x0EED', '0x0EEE', '0x0EEF'}
ORE = {'0x19B7', '0x19B8', '0x19B9', '0x19BA'}  # iron ore piles, left in the loot by accident: to smelting
HIDES = {'0x1078', '0x1079'}  # piles of hides: cut into leather like the leather armour
LOGS = {'0x1BDD', '0x1BDE', '0x1BDF', '0x1BE0', '0x1BE1', '0x1BE2'}  # made into boards with Johnny's saw
BOARDS = {'0x1BD7', '0x1BD8', '0x1BD9', '0x1BDA'}  # a pile in the supplies chest (the user, 2026-11-09)
SAWS = ('0x1034', '0x1035', '0x1028', '0x1029')  # saw and dovetail saw; the user keeps one in his backpack
SUPPLIES = {'0x0F0E', '0x1067', '0x1068', '0x1081', '0x1082', '0x1766', '0x1767', '0x0EF3', '0x14FC',
            '0x0F3F', '0x1BFB', '0x0E21', '0x0EE9', '0x1BD1'}  # bottles, leather, cloth, blank scrolls, lockpicks, arrows,
                                                                 # bolts, bandages, feathers
SET_PIECES = {'ringmail gloves': 'gloves', 'ringmail sleeves': 'sleeves', 'chainmail leggings': 'leggings',
              'chainmail tunic': 'tunic', 'platemail gorget': 'gorget',
              'plate helm': 'helm', 'close helmet': 'helm', 'close helm': 'helm', 'helmet': 'helm',
              'nose helm': 'helm'}  # item types as the client's tiledata names them; "nose helm" is the norse helm
POTIONS = {'yellow': 'heal', 'orange': 'cure', 'red': 'refresh', 'blue': 'agility', 'white': 'strength',
           'green': 'poison', 'purple': 'explosion', 'black': None}


def say(text):
    print(time.strftime('%H:%M:%S'), text, flush=True)


info = uo.find_bridge(None)
names = uo.load_names()
labels = uo.load_labels


def call(method, path, **params):
    while True:
        while uo.others_in_area(info):
            say('paused: someone is in the room; checking again in a minute')
            time.sleep(60)
        try:
            return uo.call(info, method, path, **params)
        except uo.BridgeError as e:
            if e.code == 409 and 'paused' in e.message:
                continue
            if uo.wait_out_world_save(info, e):
                say('world save finished; carrying on')
                continue
            raise


def move(serial, to, x=None, y=None):
    while True:
        while uo.others_in_area(info):
            say('paused: someone is in the room; checking again in a minute')
            time.sleep(60)
        try:
            result = uo.move(info, serial, to, x, y)
        except uo.BridgeError as e:
            if e.code == 409 and 'paused' in e.message:
                continue
            if uo.wait_out_world_save(info, e):
                say('world save finished; carrying on')
                continue
            if uo.resume_after_barrel_emptied(info, e):
                say('the trash barrel was full and emptied itself; carrying on')
                return {'moved': True, 'messages': []}
            raise
        if not result['moved'] and not landed_in(serial, to):
            raise uo.BridgeError(0, f'{serial} did not go into {to}: ' + '; '.join(m['text'] for m in result['messages']))
        return result


def landed_in(serial, to):
    """Whether the item is in `to` after all. A server-wide message (a tournament announcement) arriving just as a
    drop is answered can make the bridge report a move that did happen as not done (2026-11-04)."""
    time.sleep(1)
    try:
        found = uo.call(info, 'GET', '/item', serial=serial)
    except uo.BridgeError:
        return False
    inside = [i['serial'] for i in found.get('insideOf', [])]
    if inside and inside[0] == to:
        say(f'{serial} did go into {to} (the bridge missed it)')
        return True
    return False


def chest(part):
    return uo.resolve('chest: ' + part)


CONTENTS, AREA, OCCUPIED = {}, {}, {}
TAKEN = set()  # bags already taken from the backpacks crate in this run
LIMIT = 125    # items a container holds, counting everything inside
FULL = set()   # containers the server said can't hold more


def rect(item, x=None, y=None):
    vx, vy, vw, vh = item['art']['visible']
    return (item['x'] if x is None else x) + vx, (item['y'] if y is None else y) + vy, vw, vh


def overlaps(a, b, margin=2):
    return not (a[0] + a[2] + margin <= b[0] or b[0] + b[2] + margin <= a[0] or
                a[1] + a[3] + margin <= b[1] or b[1] + b[3] + margin <= a[1])


def learn(serial):
    """Open a container so the client knows it; remember what's in it and where."""
    if serial in CONTENTS:
        return CONTENTS[serial]
    uo.walk_near(info, serial)
    result = call('POST', '/open', serial=serial)
    call('POST', '/close', serial=serial)
    if not result['opened']:
        raise uo.BridgeError(0, f'{serial} did not open')
    c = result['contents']
    CONTENTS[serial] = c['items']
    AREA[serial] = c.get('area') or [18, 105, 162, 178]
    OCCUPIED[serial] = [rect(i) for i in c['items'] if 'art' in i]
    return c['items']


def empty_bags(n):
    """n empty bags from the backpacks crate. A bag holding anything goes to needs your decision."""
    bags = []
    for item in learn(uo.resolve('new backpacks')):
        if len(bags) == n:
            break
        if item['type'] not in ('backpack', 'bag', 'pouch') or item['serial'] in TAKEN:
            continue
        if learn(item['serial']):
            say(f"{item['serial']} in the backpacks crate isn't empty; moving it to needs your decision")
            move(item['serial'], chest('needs your decision'))
            TAKEN.add(item['serial'])
            continue
        bags.append(item)
        TAKEN.add(item['serial'])
    if len(bags) < n:
        sys.exit('not enough empty bags in the backpacks crate')
    return bags


def room_in(name):
    """Where trash or smelting goes: trash into the trash barrel, smelting into the first of the numbered smelting
    crates by the door with room (the user's rules, 2026-11-01: no smelting chest, all smelting in one place)."""
    if name == 'trash':
        barrel = uo.resolve('trash barrel')
        learn(barrel)
        return barrel
    crates = sorted((text, serial) for serial, text in labels().items() if re.match(rf'{name} \d', text))
    for c in [serial for _, serial in crates]:
        if c not in FULL and len(learn(c)) < LIMIT:
            return c
    sys.exit(f'every {name} container is full')


def deliver(serials, name, inv):
    """Carry items to the smelting or trash containers in loads, as much as Johnny can carry at a time."""
    pending = list(serials)
    while pending:
        load = []
        carried = {i['serial']: i for i in call('GET', '/contents', serial=BACKPACK)['items']}
        inv = dict(carried, **inv)
        while pending and len(load) < 30:
            status = call('GET', '/status')
            if status['weight'] + 20 > status['weightMax']:
                break
            serial = pending.pop(0)
            if serial not in carried:  # already in the backpack when a run picks up where another stopped
                move(serial, BACKPACK)
            load.append(serial)
        if not load:
            sys.exit('Johnny is carrying too much to pick anything up')
        for serial in load:
            while True:
                c = room_in(name)
                try:
                    put(inv[serial], c)
                    break
                except uo.BridgeError as e:
                    if 'cannot hold' not in e.message.lower():
                        raise
                    say(f'{labels().get(c, c)} is full')
                    FULL.add(c)
            say(f"{names.get(serial, inv[serial]['type'])} -> {labels().get(c, c)}")


def cut_up(serials, inv):
    """Cut leather and cloth with the scissors in Johnny's backpack, 15 at a time so the cuttings never weigh him
    down, and pile the cut leather and cloth in the supplies chest."""
    pending = list(serials)
    if not pending:
        return
    CONTENTS.pop(BACKPACK, None)
    scissors = next((i['serial'] for i in learn(BACKPACK) if i['graphic'] in SCISSORS_GRAPHICS), None)
    if scissors is None:  # 2026-11-08: the user had taken them; the cutting is left in the loot bags for later
        say(f'NO SCISSORS in Johnny\'s backpack: {len(pending)} items to cut are left in their loot bags: '
            + ', '.join(names.get(s, inv[s]['type']) for s in pending))
        return
    while pending:
        before = {i['serial'] for i in call('GET', '/contents', serial=BACKPACK)['items']}
        for serial in pending[:15]:
            move(serial, BACKPACK)
            call('POST', '/use', serial=scissors, target=serial)
            say(f"cut {names.get(serial, inv[serial]['type'])}")
        pending = pending[15:]
        c = chest('supplies')
        learn(c)
        for item in call('GET', '/contents', serial=BACKPACK)['items']:
            if item['serial'] not in before and item['serial'] != scissors:
                say(f"{item['type']} x{item.get('amount', 1)} -> supplies ({stack(item, c)})")


def menu_answer(answer, title):
    """The menu called title from an answer to /use or /menu, waiting up to 30 s for a late one (as smith.py)."""
    for second in range(31):
        menus = [d for d in answer.get('dialogs', []) if d['kind'] != 'gump'
                 and title in (d.get('title') or '').lower()]
        if menus:
            return menus[-1]
        if second < 30:
            time.sleep(1)
            answer = call('GET', '/gumps')
    raise uo.BridgeError(0, f'no "{title}" menu came')


def menu_choose(menu, name):
    index = next((i['index'] for i in menu['items'] if i['name'].split(':')[0].strip().lower() == name), None)
    if index is None:
        raise uo.BridgeError(0, f'no "{name}" in the menu: ' + ', '.join(i['name'] for i in menu['items']))
    return call('POST', '/menu', serial=menu['serial'], id=menu['id'], index=index)


def make_boards(serials, inv):
    """Logs into boards with the saw in Johnny's backpack (the user, 2026-11-09): saw, "Other", "board" turns a whole
    pile into boards at once ("You create the item."). Carpentry needs no skill for boards. The boards go on their pile
    in the supplies chest. With no saw, the logs stay in their loot bags."""
    if not serials:
        return
    CONTENTS.pop(BACKPACK, None)
    saw = next((i['serial'] for i in learn(BACKPACK) if i['graphic'] in SAWS), None)
    if saw is None:
        say(f"NO SAW in Johnny's backpack: {len(serials)} piles of logs are left in their loot bags")
        return
    for serial in serials:
        amount = inv[serial].get('amount', 1)
        move(serial, BACKPACK)
        for attempt in range(5):  # a failed craft may leave some logs
            answer = call('POST', '/use', serial=saw)
            answer = menu_choose(menu_answer(answer, 'what type of item'), 'other')
            menu_choose(menu_answer(answer, 'what do you want to make'), 'board')
            for _ in range(15):
                time.sleep(1)
                if not any(i['serial'] == serial for i in call('GET', '/contents', serial=BACKPACK)['items']):
                    break
            else:
                continue
            break
        else:
            raise uo.BridgeError(0, f'logs {serial} are still in the backpack after 5 tries')
        say(f'{amount} logs -> boards')
    c = chest('supplies')
    learn(c)
    for item in call('GET', '/contents', serial=BACKPACK)['items']:
        if item['graphic'] in BOARDS:
            say(f"boards x{item.get('amount', 1)} -> supplies ({stack(item, c)})")


GEM_BAG = {}


def gem_bag():
    """The gem bag in the gems chest. The user takes the whole bag to sell the gems, then uses it as a loot bag
    (2026-11-07), so when no labelled gem bag is in the chest, start a new one at the top left from the backpacks
    crate. It gets a marker at the end of the batch (gem_marker) unless a loose gem is already lying in the chest."""
    if GEM_BAG.get('serial'):
        return GEM_BAG['serial']
    c = chest('gems')
    items = learn(c)
    here = {i['serial'] for i in items}
    labelled = [s for s, t in labels().items() if t.startswith('bag: gems (')]
    bag = next((s for s in labelled if s in here), None)
    if bag is None:
        uo.forget_labels(labelled)
        new = empty_bags(1)[0]
        put(new, c, AREA[c][0], AREA[c][1])
        bag = new['serial']
        CONTENTS[bag], AREA[bag], OCCUPIED[bag] = [], [44, 65, 186, 159], []
        uo.save_label(bag, 'bag: gems (gems chest)')
        say('no gem bag in the gems chest (taken to sell the gems); started a new one')
    # a new bag, or the old one brought back empty with its marker sold too (2026-11-10): a gem goes under it
    GEM_BAG['needs marker'] = not any(i['graphic'] in GEMS for i in items)
    learn(bag)
    GEM_BAG['serial'] = bag
    return bag


def gem_marker():
    """Split one gem out of the new gem bag and lay it under the bag as its marker."""
    bag, c = GEM_BAG['serial'], chest('gems')
    piles = [i for i in call('GET', '/contents', serial=bag)['items'] if i['graphic'] in GEMS]
    if not piles:
        return
    pile = min(piles, key=lambda i: i['art']['visible'][0])  # the one whose picture can sit right under the bag
    x1, y1 = AREA[c][:2]
    vx, vy = pile['art']['visible'][:2]
    result = uo.move(info, pile['serial'], c, max(x1, x1 + 18 - vx), y1 + 23 - vy, amount=1)
    say(f"{pile['type']}: one under the gem bag as its marker" if result['moved'] else 'the gem marker did not move')


def set_piece(item):
    return SET_PIECES.get(' '.join(item['type'].split()))


def free_spot(container, art, ys=None, xs=None):
    x1, y1, x2, y2 = AREA[container]
    vx, vy, vw, vh = art['visible']
    for y in (ys or range(y1, y2 - art['h'] + 1, 3)):
        for x in (xs or range(x1, x2 - art['w'] + 1, 3)):
            if not (x1 <= x <= x2 - art['w'] and y1 <= y <= y2 - art['h']):
                continue
            r = (x + vx, y + vy, vw, vh)
            if all(not overlaps(r, o) for o in OCCUPIED[container]):
                OCCUPIED[container].append(r)
                return x, y
    return None, None


def pile_in(container, item):
    """An existing pile in the container that this item can merge onto."""
    for i in CONTENTS[container]:
        if i['graphic'] == item['graphic'] and i['hue'] == item['hue'] and i['serial'] != item['serial']:
            return i['serial']
    return None


def put(item, container, x=None, y=None):
    move(item['serial'], container, x, y)
    CONTENTS[container].append(dict(item, x=x if x is not None else 0, y=y if y is not None else 0))


def stack(item, container, slot=None):
    """Merge onto the pile already there, or start one at the slot (or the first free spot)."""
    target = pile_in(container, item)
    if target:
        move(item['serial'], target)
        return 'merged'
    if slot:
        vx, vy = item['art']['visible'][:2]
        x1, y1, x2, y2 = AREA[container]
        x, y = max(x1, min(slot[0] - vx, x2 - item['art']['w'])), max(y1, min(slot[1] - vy, y2 - item['art']['h']))
        OCCUPIED[container].append(rect(item, x, y))
    else:
        x, y = free_spot(container, item['art'])
    put(item, container, x, y)
    return f'new pile at {x},{y}'


def main():
    plan = json.load(open(sys.argv[1]))
    loot = plan['loot']
    for part in plan.get('learn_first', []):  # chests whose bags get things put into them
        learn(chest(part))
    inv = {}
    for l in loot:
        for i in learn(l):
            inv[i['serial']] = i

    # ---- new bags and their markers ----
    if plan.get('new_slots'):
        bags = empty_bags(len(plan['new_slots']))
        for (part, marker, kind), bag in zip(plan['new_slots'], bags):
            c = chest(part)
            learn(c)
            bx, by = free_spot(c, bag['art'], ys=[105, 106])
            if bx is None:  # top row full: any free spot, or overlap at the right edge as a last resort
                bx, by = free_spot(c, bag['art'])
            if bx is None:
                say(f"{labels().get(c)} is out of room; the new bag overlaps others")
                bx, by = AREA[c][2] - bag['art']['w'], AREA[c][1]
            put(bag, c, bx, by)
            CONTENTS[bag['serial']], AREA[bag['serial']], OCCUPIED[bag['serial']] = [], [44, 65, 186, 159], []
            m = inv[marker]
            mvx, mvy = m['art']['visible'][:2]
            bvx, bvy, bvw, bvh = bag['art']['visible']
            mx, my = free_spot(c, m['art'], ys=range(by + bvy + bvh + 3 - mvy, AREA[c][3] - m['art']['h'] + 1, 3),
                               xs=range(bx + bvx - mvx - 6, bx + bvx - mvx + 16))
            if mx is None:
                mx, my = free_spot(c, m['art'], ys=range(AREA[c][1], AREA[c][1] + 4), xs=range(bx + bvx + bvw + 3 - mvx, AREA[c][2]))
            put(m, c, mx, my)
            uo.save_label(bag['serial'], f"bag: {kind} ({labels()[c][7:].split(' (')[0]} chest)")
            say(f"new bag '{kind}' in {labels().get(c)}; marker {names.get(marker, m['type'])}")

    # ---- gear into existing bags and chests ----
    for serial, bag in plan.get('into', []):
        bag = uo.resolve(bag)  # a serial, or the label of a bag made above ("bag: plate legs")
        learn(bag)
        x, y = free_spot(bag, inv[serial]['art'])
        put(inv[serial], bag, x, y)
        say(f"{names.get(serial, inv[serial]['type'])} -> {labels().get(bag, bag)}")
    for serial, part in plan.get('place_in', []):
        c = chest(part)
        learn(c)
        x, y = free_spot(c, inv[serial]['art'])
        put(inv[serial], c, x, y)
        say(f"{names.get(serial, inv[serial]['type'])} -> {labels().get(c)}")

    # ---- GM armour sets: one bag per set, no markers; each piece fills the first set missing it ----
    # Only GM ("exceptional") pieces count, so a GM piece replaces a plain stand-in (sets 2 and 3 have plain
    # gorgets); the plain piece it replaces goes to smelting.
    if plan.get('sets'):
        c = chest('GM armour sets')

        def gm(serial):
            return 'exceptional' in names.get(serial, '')

        sets = [[b, {set_piece(i) for i in learn(b['serial']) if gm(i['serial'])}]
                for b in sorted((i for i in learn(c) if layout.is_bag(i)), key=lambda i: (i['y'], i['x']))]
        missing = [s for s in plan['sets'] if not set_piece(inv[s])]
        if missing:
            sys.exit('not GM set pieces: ' + ', '.join(f"{s} {inv[s]['type']}" for s in missing))
        needed, have = 0, [set(k) for _, k in sets]  # how many new set bags this batch needs
        for serial in plan['sets']:
            kinds = next((k for k in have if set_piece(inv[serial]) not in k), None)
            if kinds is None:
                kinds = set()
                have.append(kinds)
                needed += 1
            kinds.add(set_piece(inv[serial]))
        for bag in empty_bags(needed):
            bx, by = free_spot(c, bag['art'])
            put(bag, c, bx, by)
            CONTENTS[bag['serial']], AREA[bag['serial']], OCCUPIED[bag['serial']] = [], [44, 65, 186, 159], []
            uo.save_label(bag['serial'], f'bag: GM set {len(sets) + 1} (GM armour sets chest)')
            say(f'new set bag {len(sets) + 1} in the GM chest')
            sets.append([bag, set()])
        replaced = []
        for serial in plan['sets']:
            kind = set_piece(inv[serial])
            bag, kinds = next(s for s in sets if kind not in s[1])
            for i in CONTENTS[bag['serial']]:
                if set_piece(i) == kind and not gm(i['serial']) and i['serial'] not in replaced:
                    replaced.append(i['serial'])
                    inv[i['serial']] = i
            x, y = free_spot(bag['serial'], inv[serial]['art'])
            put(inv[serial], bag['serial'], x, y)
            kinds.add(kind)
            say(f"{names.get(serial, inv[serial]['type'])} -> {labels().get(bag['serial'], bag['serial'])}")
        if replaced:
            say('plain pieces replaced by GM ones go to smelting: ' + ', '.join(names.get(r, inv[r]['type']) for r in replaced))
            deliver(replaced, 'smelting', inv)

    if plan.get('spares'):
        learn(chest('supplies'))
        for serial in plan['spares']:
            move(serial, SPARES)
            say(f'{names.get(serial)} -> ID spares pouch')
    trash = plan.get('trash', [])
    deliver(trash, 'trash', inv)
    deliver(plan.get('smelt', []), 'smelting', inv)

    # ---- scroll markers for circles that have none ----
    for circle, serial in plan.get('scroll_markers', {}).items():
        c = chest('scrolls')
        learn(c)
        item = inv[serial]
        x, y = SCROLL_MARKER_SPOTS[int(circle)]
        x = max(18, min(x + 11 - item['art']['visible'][0], 162 - item['art']['w']))
        put(item, c, x, y)
        say(f"{item['type']} -> marker for circle {circle}")
    done = {s for s, _ in plan.get('into', [])} | {s for s, _ in plan.get('place_in', [])} | set(plan.get('spares', [])) | \
        set(trash) | set(plan.get('scroll_markers', {}).values()) | {m for _, m, _ in plan.get('new_slots', [])} | set(plan.get('cut', [])) | \
        set(plan.get('sets', [])) | set(plan.get('smelt', []))

    # ---- stackables ----
    hides, logs = [], []
    for serial, item in inv.items():
        if serial in done:
            continue
        g, t = item['graphic'], item['type'].lower()
        if 0x1F2D <= int(g, 16) <= 0x1F6C:
            circle = (int(g, 16) - 0x1F2D) // 8 + 1
            bag = SCROLL_BAGS[circle]
            learn(chest('scrolls'))
            learn(bag)
            index = (int(g, 16) - 0x1F2D) % 8
            x1, y1 = AREA[bag][:2]
            how = stack(item, bag, slot=(x1 + 4 + (index % 4) * 28, y1 + 4 + (index // 4) * 24))
            say(f"{item['type']} x{item.get('amount', 1)} -> circle {circle} ({how})")
        elif g in REAGENTS:
            c = chest('reagents')
            learn(c)
            i = REAGENTS.index(g)
            how = stack(item, c, slot=(30 + (i % 4) * 30, 108 + (i // 4) * 26))
            say(f"{item['type']} x{item.get('amount', 1)} -> reagents ({how})")
        elif g in GEMS:  # one bag holding every gem pile, so the user can grab it to sell
            bag = gem_bag()
            i = GEMS.index(g)
            x1, y1 = AREA[bag][:2]
            how = stack(item, bag, slot=(x1 + 6 + (i % 5) * 26, y1 + 6 + (i // 5) * 30))
            say(f"{item['type']} x{item.get('amount', 1)} -> gem bag ({how})")
        elif g in GOLD:  # gold left in the loot by accident: the user wants to see it (2026-11-01)
            c = chest('needs your decision')
            learn(c)
            say(f"gold x{item.get('amount', 1)} -> needs your decision ({stack(item, c)})")
        elif g in HIDES:
            hides.append(serial)
        elif g in LOGS:
            logs.append(serial)
        elif g in BOARDS:
            c = chest('supplies')
            learn(c)
            say(f"boards x{item.get('amount', 1)} -> supplies ({stack(item, c)})")
        elif g in ORE:
            c = room_in('smelting')
            say(f"iron ore x{item.get('amount', 1)} -> {labels().get(c)} ({stack(item, c)})")
        elif g in SUPPLIES:
            c = chest('supplies')
            learn(c)
            say(f"{item['type']} x{item.get('amount', 1)} -> supplies ({stack(item, c)})")
        elif t.endswith('potion') and t.split(' potion')[0].split()[-1] in POTIONS:
            kind = POTIONS[t.split(' potion')[0].split()[-1]]
            target = uo.resolve(f'potions: {kind}') if kind else room_in('trash')  # Night Sight: the barrel
            if kind:
                learn(target)
                x1, y1, x2, y2 = AREA[target]
                move(serial, target, min(x1 + 36, x2 - item['art']['w']), min(y1 + 10, y2 - item['art']['h']))
            else:
                move(serial, target)
            say(f"{item['type']} -> {kind or 'trash'}")
        else:
            say(f"left in the loot (not in the plan): {names.get(serial, item['type'])} {serial}")

    # ---- logs into boards; boards to supplies ----
    make_boards(logs, inv)

    # ---- cut leather and cloth; results to supplies ----
    cut_up(plan.get('cut', []) + hides, inv)
    if GEM_BAG.get('needs marker'):
        gem_marker()

    # ---- emptied loot bags back to the crate ----
    for l in loot:
        left = uo.call(info, 'GET', '/contents', serial=l)['items']
        if left:
            say(f'{l} still holds: ' + ', '.join(i['type'] for i in left))
            continue
        move(l, uo.resolve('new backpacks'))
        say(f'{l} empty -> backpacks crate')

    # ---- what the chests hold now, for layout.json (read from the client; nothing is sent) ----
    for c in CONTENTS:
        if labels().get(c, '').startswith('chest: '):
            layout.record(c, uo.call(info, 'GET', '/contents', serial=c)['items'])
    say('BATCH DONE')


if __name__ == '__main__':
    try:
        main()
    except uo.BridgeError as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
