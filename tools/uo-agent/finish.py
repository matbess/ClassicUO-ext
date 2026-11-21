#!/usr/bin/env python3
"""Leave the sorter (Johnny, or Clem when Johnny is offline) ready for the user to play once sorting is done.

  finish.py [--side east|west]

In the castle (he's inside it): the castle's 4 smelting chests by the forge are counted, he waits on the east hall
walkway (now the middle of the forge room, 945,2324) and it says what's still in the intake chests (that side's, or both); the user's table, if a walk opened
it, is closed and locked down.

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
sys.path.insert(0, here)
import castle_site  # noqa: E402
PARK = (933, 2336)  # in the castle: the middle of the great hall, the square the user put him on (the user, 2026-11-20: "I want you to take him into the
#                    center of the great hall at the end of sorting"), in front of the tables

SPARES = '0x4049D6B8'  # pouch of spare ID wands and staves, in the supplies chest


def say(text):
    print(time.strftime('%H:%M:%S'), text, flush=True)


def main():
    info = uo.find_bridge(None)
    mover = castle_site.install(uo, info, say)
    import razor
    razor.install(uo, info, say)
    if mover:  # look.py loads its own uo: its walks go the castle's way too
        look.uo.walk_near = mover.walk_near
    try:
        finish(info, mover)
    finally:
        if mover:
            mover.close_up()


def finish(info, mover):
    for item in uo.call(info, 'GET', '/status')['hands']:
        name = uo.call(info, 'POST', '/name', serial=item['serial'])[0]['lines']
        # any wand or staff: the sorter only ever holds the ID tool idall.py took from the pouch. Its name won't do:
        # identifying is per character here, so Johnny's ID wands are "magic wand" to Clem (2026-11-14)
        if any('identification' in line for line in name) or any(w in item.get('type', '') for w in ('wand', 'staff')):
            result = uo.move(info, item['serial'], SPARES)
            if not result['moved']:
                sys.exit(f"{item['serial']} did not go into the spares pouch")
            say(f"{' '.join(name)} -> spares pouch")
    # what's waiting to be smelted: the user wants the number every run (2026-11-08; Icepick smelts, and he's on the
    # same account as Johnny, so never during sorting). Every crate is opened, as the client's copy can be stale.
    counts = []
    crates = sorted((t, s) for s, t in uo.load_labels().items() if re.match(r'smelting \d', t))
    if mover:
        crates = [(castle_site.PLAN[c]['what'], c) for c in castle_site.targets('smelting', 'east')]
    for text, crate in crates:
        pieces = [i for i in look.open_once(info, crate) if 'key' not in i['type'].lower()]
        counts.append((text.split(' (')[0], len(pieces)))
    say(f"SMELTING: {sum(n for _, n in counts)} pieces waiting to be smelted ("
        + ', '.join(f'{name}: {n}' for name, n in counts) + ')')
    if mover:
        sides = [sys.argv[sys.argv.index('--side') + 1]] if '--side' in sys.argv else list(castle_site.SIDES)
        left = []
        for side in ([] if '--floor' in sys.argv else sides):  # loot on the forge floor: the intake chests aren't used
            for c in castle_site.intake(side):
                left += [f"{i['serial']} {i['type']} ({side})" for i in look.open_once(info, c)]
        if '--floor' not in sys.argv:
            say(('STILL IN THE INTAKE CHESTS (sort as another batch): ' + ', '.join(left)) if left
                else f"the {' and '.join(sides)} intake chests are empty")
        mover.walk(*PARK)  # there first, past the tables, then the table shut from that side
        mover.close_up()
        mover.walk(*PARK)
        say(f'{uo.call(info, "GET", "/status")["character"].split()[-1]} is in the middle of the great hall at {PARK[0]},{PARK[1]}')
        return
    x1, y1, x2, y2 = look.VAULT['box']
    walked = uo.call(info, 'POST', '/walk', x=(x1 + x2) // 2, y=(y1 + y2) // 2, distance=0)
    who = uo.call(info, 'GET', '/status')['character'].split()[-1]
    say(f"{who} is at {walked['x']},{walked['y']}" + ('' if walked['arrived'] else ' (the middle was blocked)'))
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
