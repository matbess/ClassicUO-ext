#!/usr/bin/env python3
"""The vault's inventory for the shared page (the user, 2026-11-10): every chest on the wall with its bags (and the
marker under each), what lies loose in it and what's in the bags, plus the potion crates and the backpacks crate.
Not the smelting crates or the trash barrel (the user). Opens every container, as the client's copy can be stale or
empty after a restart; --known reads only what the client already knows and sends nothing.

  inventory.py [--known] [--out PATH]

Writes PATH (default vault/inventory.json here), which the page "The Vault" (vault/index.html) shows: publish both
(skill uo-sort, "The Vault page"). Also refreshes layout.json for every chest it opens.
"""
import importlib.util
import json
import os
import re
import sys
import time

here = os.path.dirname(os.path.realpath(__file__))
for module in ('uo', 'look', 'layout', 'survey'):
    spec = importlib.util.spec_from_file_location(module, os.path.join(here, module + '.py'))
    globals()[module] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(globals()[module])

OUT = os.path.join(here, 'vault', 'inventory.json')  # published beside vault/index.html, the page
ROWS = ('top', '2nd from top', '3rd from top', 'bottom')
# spell scrolls 0x1F2D-0x1F6C, 8 to a circle (the tiledata names are cut short: "Greater Heal Scrol")
SPELLS = ['Reactive Armor', 'Clumsy', 'Create Food', 'Feeblemind', 'Heal', 'Magic Arrow', 'Night Sight', 'Weaken',
          'Agility', 'Cunning', 'Cure', 'Harm', 'Magic Trap', 'Magic Untrap', 'Protection', 'Strength',
          'Bless', 'Fireball', 'Magic Lock', 'Poison', 'Telekinesis', 'Teleport', 'Unlock', 'Wall of Stone',
          'Arch Cure', 'Arch Protection', 'Curse', 'Fire Field', 'Greater Heal', 'Lightning', 'Mana Drain', 'Recall',
          'Blade Spirits', 'Dispel Field', 'Incognito', 'Magic Reflection', 'Mind Blast', 'Paralyze', 'Poison Field',
          'Summon Creature',
          'Dispel', 'Energy Bolt', 'Explosion', 'Invisibility', 'Mark', 'Mass Curse', 'Paralyze Field', 'Reveal',
          'Chain Lightning', 'Energy Field', 'Flamestrike', 'Gate Travel', 'Mana Vampire', 'Mass Dispel',
          'Meteor Swarm', 'Polymorph',
          'Earthquake', 'Energy Vortex', 'Resurrection', 'Summon Air Elemental', 'Summon Daemon',
          'Summon Earth Elemental', 'Summon Fire Elemental', 'Summon Water Elemental']


def say(text):
    print(time.strftime('%H:%M:%S'), text, flush=True)


def display(item, names):
    """What the page calls an item: the spell for a scroll, the server's name for identified gear, else its type."""
    g = int(item['graphic'], 16)
    if 0x1F2D <= g <= 0x1F6C:
        return f'{SPELLS[g - 0x1F2D]} scroll'
    if item.get('amount', 1) > 1 or item.get('container'):
        return ' '.join(item.get('type', '?').split())
    name = (names.get(item['serial']) or '').split(' / ')[0].strip()
    name = re.sub(r'^(an?|the) ', '', name, flags=re.I)
    return name or ' '.join(item.get('type', '?').split())


def entries(items, names):
    """Items merged by what they're called: [{name, amount, graphic}], biggest piles first, then by name."""
    merged = {}
    for i in items:
        n = display(i, names)
        e = merged.setdefault(n, {'name': n, 'amount': 0, 'graphic': i['graphic']})
        e['amount'] += i.get('amount', 1)
    return sorted(merged.values(), key=lambda e: (-e['amount'] if e['amount'] > 1 else 0, e['name'].lower()))


def main():
    known = '--known' in sys.argv
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else OUT
    info = uo.find_bridge(None)
    labels, names = uo.load_labels(), uo.load_names()

    def contents(serial):
        if known:
            return uo.call(info, 'GET', '/contents', serial=serial)['items']
        return look.open_once(info, serial)

    def inside(bag, depth=0):
        """A bag's items, with any container in it opened too (a pouch in a bag)."""
        items = contents(bag)
        out = []
        for i in items:
            if i.get('container') and depth < 2:
                out.append({'name': labels.get(i['serial'], display(i, names)), 'amount': 1, 'graphic': i['graphic'],
                            'items': entries(inside(i['serial'], depth + 1), names)})
        return out + entries([i for i in items if not i.get('container')], names)

    chests = [s for s, t in labels.items() if t.startswith('chest: ')]
    spots = {s: uo.on_floor(info, s) for s in chests}
    missing = [labels[s] for s, spot in spots.items() if not spot]
    if missing:
        sys.exit('not in sight: ' + ', '.join(missing))
    place = survey.place(spots)
    wall = []
    for serial in sorted(chests, key=lambda s: (place[s][0], place[s][1])):
        items = contents(serial)
        layout.record(serial, items)
        pairs, loose = layout.pair(items, unmarked={s for s, t in labels.items() if not t.startswith('bag: ')})
        bags = []
        for bag, marker in pairs:
            text = labels.get(bag['serial'], '')
            bags.append({
                'name': text[5:].split(' (')[0] if text.startswith('bag: ') else (text or display(bag, names)),
                'marker': entries([marker], names)[0] if marker else None,
                'items': inside(bag['serial']),
            })
        bags.sort(key=lambda b: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', b['name'].lower())])
        column, row, _ = place[serial]
        wall.append({'name': labels[serial][7:].split(' (')[0], 'col': column, 'row': ROWS[row],
                     'bags': bags, 'loose': entries(loose, names)})
        say(f"{labels[serial]}: {len(bags)} bags, {len(loose)} loose")

    crates = []
    for serial, text in sorted(labels.items(), key=lambda p: p[1]):
        if text.startswith('potions: ') or text == 'new backpacks':
            items = contents(serial)
            crates.append({'name': text, 'items': entries(items, names)})
            say(f'{text}: {len(items)}')

    data = {'updated': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'wall': wall, 'crates': crates}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = f'{out}.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=1)
    os.replace(tmp, out)
    say(f'INVENTORY DONE: {out}')


if __name__ == '__main__':
    try:
        main()
    except uo.BridgeError as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
