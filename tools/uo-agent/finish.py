#!/usr/bin/env python3
"""Leave Johnny ready for the user to play once sorting is done.

  finish.py

Puts an ID wand or staff from his hands back in the spares pouch (after a single-click, so names.json has its real
charges), counts the pieces waiting in the smelting crates (opening each), then walks him to the middle of the room in
rules.json. Last, says whether any loot is still on the floor (bags the user brought while the batch ran): if so,
sort it as another batch.
"""
import importlib.util
import os
import re
import sys
import time

here = os.path.dirname(os.path.realpath(__file__))
for module in ('uo', 'look'):
    spec = importlib.util.spec_from_file_location(module, os.path.join(here, module + '.py'))
    globals()[module] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(globals()[module])

SPARES = '0x4049D6B8'  # pouch of spare ID wands and staves, in the supplies chest


def say(text):
    print(time.strftime('%H:%M:%S'), text, flush=True)


def main():
    info = uo.find_bridge(None)
    for item in uo.call(info, 'GET', '/status')['hands']:
        name = uo.call(info, 'POST', '/name', serial=item['serial'])[0]['lines']
        if any('identification' in line for line in name):
            result = uo.move(info, item['serial'], SPARES)
            if not result['moved']:
                sys.exit(f"{item['serial']} did not go into the spares pouch")
            say(f"{' '.join(name)} -> spares pouch")
    # what's waiting to be smelted: the user wants the number every run (2026-11-08; Icepick smelts, and he's on the
    # same account as Johnny, so never during sorting). Every crate is opened, as the client's copy can be stale.
    counts = []
    for text, crate in sorted((t, s) for s, t in uo.load_labels().items() if re.match(r'smelting \d', t)):
        pieces = [i for i in look.open_once(info, crate) if 'key' not in i['type'].lower()]
        counts.append((text.split(' (')[0], len(pieces)))
    say(f"SMELTING: {sum(n for _, n in counts)} pieces waiting to be smelted ("
        + ', '.join(f'{name}: {n}' for name, n in counts) + ')')
    x1, y1, x2, y2 = uo.call(info, 'GET', '/rules')['areas'][0]['box']
    walked = uo.call(info, 'POST', '/walk', x=(x1 + x2) // 2, y=(y1 + y2) // 2, distance=0)
    say(f"Johnny is at {walked['x']},{walked['y']}" + ('' if walked['arrived'] else ' (the middle was blocked)'))
    # loot the user brought while the batch ran (2026-11-08: Clem dropped a bag 11 s after look.py had looked)
    left = look.loot_on_floor(info)
    if left:
        say('MORE LOOT ON THE FLOOR (sort it as another batch): '
            + ', '.join(f"{i['serial']} {i['type']} at {i['x']},{i['y']}" for i in left))
    else:
        say('the floor is clear')


if __name__ == '__main__':
    try:
        main()
    except uo.BridgeError as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
