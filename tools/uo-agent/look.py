#!/usr/bin/env python3
"""Step 1 of a sorting batch: find the loot on the room floor, open every container in it (nested ones too) and
write down what's there.

  look.py BATCHDIR

Writes BATCHDIR/inv.json (every item, with the container it's in as "bag"), BATCHDIR/loot.json (the containers to
empty, innermost first) and BATCHDIR/targets.txt (the gear for idall.py: everything that isn't a stackable, potion,
resource or container), then prints a summary. Floor loot is anything inside the rules area and height except the
wall chests, crates, the trash barrel and the cut cloth decoration. Only opening sends anything to the server.
"""
import collections
import importlib.util
import json
import os
import sys
import time

here = os.path.dirname(os.path.realpath(__file__))
spec = importlib.util.spec_from_file_location('uo', os.path.join(here, 'uo.py'))
uo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uo)

NOT_LOOT = ('wooden chest', 'crate', 'cut cloth', 'barrel')
# graphics sortbatch.py sorts by itself; kept in step with it
STACKABLES = {
    'reagent': {'0x0F7A', '0x0F7B', '0x0F84', '0x0F85', '0x0F86', '0x0F88', '0x0F8D', '0x0F8C'},
    'gem': {'0x0F25', '0x0F16', '0x0F15', '0x0F26', '0x0F10', '0x0F13', '0x0F19', '0x0F21', '0x0F2D'},
    'gold': {'0x0EED', '0x0EEE', '0x0EEF'},
    'iron ore': {'0x19B7', '0x19B8', '0x19B9', '0x19BA'},
    'hides': {'0x1078', '0x1079'},
    'supplies': {'0x0F0E', '0x1067', '0x1068', '0x1081', '0x1082', '0x1766', '0x1767', '0x0EF3', '0x14FC',
                 '0x0F3F', '0x1BFB', '0x0E21', '0x0EE9', '0x1BD1'},
}


def say(text):
    print(time.strftime('%H:%M:%S'), text, flush=True)


def kind(item):
    g, t = item['graphic'], item['type'].lower()
    if 0x1F2D <= int(g, 16) <= 0x1F6C:
        return 'scroll'
    for k, graphics in STACKABLES.items():
        if g in graphics:
            return k
    if t.endswith('potion'):
        return 'potion'
    if item.get('container'):
        return 'container'
    return 'gear'


def open_once(info, serial):
    while True:
        while uo.others_in_area(info):
            say('paused: someone is in the room; checking again in a minute')
            time.sleep(60)
        try:
            uo.walk_near(info, serial)
            result = uo.call(info, 'POST', '/open', serial=serial)
            uo.call(info, 'POST', '/close', serial=serial)
            return result['contents']['items']
        except uo.BridgeError as e:
            if e.code == 409 and 'paused' in e.message:
                continue
            if uo.wait_out_world_save(info, e):
                continue
            raise


def on_floor(info):
    """What lies on the room floor (inside the rules area and height) apart from the chests, crates, barrel and cloth.
    Read only."""
    rules = uo.call(info, 'GET', '/rules')
    x1, y1, x2, y2 = rules['areas'][0]['box']
    z1, z2 = rules['areas'][0]['z']
    nearby = uo.call(info, 'GET', '/nearby', range=14)
    nearby = nearby.get('items', nearby) if isinstance(nearby, dict) else nearby
    return [i for i in nearby if x1 <= i['x'] <= x2 and y1 <= i['y'] <= y2 and z1 <= i['z'] <= z2
            and not any(k in i.get('type', '') for k in NOT_LOOT)]


def loot_on_floor(info):
    """Loot bags and loose loot on the floor: unlabelled things, and labelled bags (reused as loot bags)."""
    labels = uo.load_labels()
    return [i for i in on_floor(info) if not labels.get(i['serial'])
            or (i.get('container') and labels[i['serial']].startswith('bag: '))]


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    info = uo.find_bridge(None)
    labels = uo.load_labels()
    here = on_floor(info)
    # Only loot bags go on this floor, so a labelled bag lying here has been reused as one: the user takes the whole
    # gem bag to sell the gems and brings it back with loot (2026-11-07). Its label goes; sortbatch starts a new
    # gem bag when one is needed, and plan.py a new bag of any other kind.
    reused = [i for i in here if i.get('container') and labels.get(i['serial'], '').startswith('bag: ')]
    for i in reused:
        say(f"{labels[i['serial']]} is on the floor: reused as a loot bag, so it's loot now and its label is dropped")
    uo.forget_labels([i['serial'] for i in reused])
    labels = uo.load_labels()
    floor = [i for i in here if not labels.get(i['serial'])]
    loose = [i for i in floor if not i.get('container')]
    if loose:
        say('loose on the floor (not in a bag; sort these by hand): '
            + ', '.join(f"{i['serial']} {i['type']}" for i in loose))
    inv, loot, queue = {}, [], [i['serial'] for i in floor if i.get('container')]
    while queue:
        bag = queue.pop(0)
        items = open_once(info, bag)
        loot.insert(0, bag)  # innermost containers end up first, so they're emptied before what holds them
        say(f'{bag}: {len(items)} items')
        for i in items:
            i['bag'] = bag
            inv[i['serial']] = i
            if i.get('container'):
                queue.append(i['serial'])
    kinds = collections.defaultdict(list)
    for i in inv.values():
        kinds[kind(i)].append(i)
    json.dump(inv, open(os.path.join(out, 'inv.json'), 'w'), indent=1)
    json.dump(loot, open(os.path.join(out, 'loot.json'), 'w'), indent=1)
    open(os.path.join(out, 'targets.txt'), 'w').write(' '.join(i['serial'] for i in kinds['gear']))
    for k in sorted(kinds):
        say(f"{k:10} {len(kinds[k]):4} items, {sum(i.get('amount', 1) for i in kinds[k])} in all")
    say(f"gear by type: {collections.Counter(i['type'] for i in kinds['gear']).most_common()}")
    say(f'LOOK DONE: {len(loot)} containers, {len(inv)} items; next: idall.py on {out}/targets.txt')


if __name__ == '__main__':
    try:
        main()
    except uo.BridgeError as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
