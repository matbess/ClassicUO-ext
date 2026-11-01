#!/usr/bin/env python3
"""Sort potions into their crates: one crate per kind (by bottle colour), one pile per strength.

  potions.py CONTAINER [CONTAINER...]

Single-clicks every potion in the containers for its strength, then moves each onto its pile: lesser, regular,
greater and deadly (total refresh counts as greater) from left to right in the crate. Night Sight potions go in
the trash. Waits while anyone else is in the room and stops at the first problem.
"""
import importlib.util
import os
import sys
import time

spec = importlib.util.spec_from_file_location('uo', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'uo.py'))
uo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uo)

KINDS = {'yellow': 'heal', 'orange': 'cure', 'red': 'refresh', 'blue': 'agility', 'white': 'strength',
         'green': 'poison', 'purple': 'explosion', 'black': None}
STRENGTHS = ['lesser', 'regular', 'greater', 'deadly']


def say(text):
    print(time.strftime('%H:%M:%S'), text, flush=True)


def wait_until_clear(info):
    while True:
        others = uo.others_in_area(info)
        if not others:
            return
        say(f"paused: {', '.join(others)} in the room; checking again in a minute")
        time.sleep(60)


def strength(name):
    name = name.lower()
    for word, s in (('lesser', 'lesser'), ('greater', 'greater'), ('total', 'greater'), ('deadly', 'deadly')):
        if word in name:
            return s
    return 'regular'


def main():
    info = uo.find_bridge(None)
    potions = []
    for container in sys.argv[1:]:
        for item in uo.call(info, 'GET', '/contents', serial=uo.resolve(container))['items']:
            colour = item['type'].lower().split(' potion')[0]
            if item['type'].lower().endswith('potion') and colour in KINDS:
                potions.append(item)
    say(f'{len(potions)} potions')

    names = uo.load_names()
    unknown = [p['serial'] for p in potions if p['serial'] not in names]
    for i in range(0, len(unknown), 15):
        wait_until_clear(info)
        uo.call(info, 'POST', '/name', serial=','.join(unknown[i:i + 15]))
    names = uo.load_names()

    crates, piles = {}, {}
    for kind in set(KINDS.values()) - {None}:
        crates[kind] = uo.resolve(f'potions: {kind}')

    moved = 0
    for p in potions:
        kind = KINDS[p['type'].lower().split(' potion')[0]]
        name = names.get(p['serial'], p['type'])
        if kind is None:
            target, x, y = uo.resolve('trash barrel'), None, None
        else:
            target = crates[kind]
            if target not in piles:
                wait_until_clear(info)
                uo.walk_near(info, target)
                area = uo.call(info, 'POST', '/open', serial=target)['contents'].get('area', [44, 65, 186, 159])
                uo.call(info, 'POST', '/close', serial=target)
                piles[target] = area
            x1, y1, x2, y2 = piles[target]
            art = p.get('art', {'w': 44, 'h': 30})
            slot = STRENGTHS.index(strength(name))
            x = min(x1 + 8 + slot * 28, x2 - art['w'])
            y = min(y1 + 10, y2 - art['h'])
        while True:
            wait_until_clear(info)
            try:
                result = uo.move(info, p['serial'], target, x, y)
            except uo.BridgeError as e:
                if e.code == 409 and 'paused' in e.message:
                    continue
                if uo.wait_out_world_save(info, e):
                    say('world save finished; carrying on')
                    continue
                say(f'STOPPED at {name}: {e}')
                sys.exit(1)
            break
        if not result['moved']:
            say(f'STOPPED: {name} did not move (' + ('; '.join(m['text'] for m in result['messages']) or 'no message') + ')')
            sys.exit(1)
        moved += 1
        say(f'{moved}/{len(potions)}  {name} -> ' + (kind or 'trash') + (f' ({strength(name)} pile)' if kind else ''))

    say(f'done: {moved} potions')


if __name__ == '__main__':
    main()
