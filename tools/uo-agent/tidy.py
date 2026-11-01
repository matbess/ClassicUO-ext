#!/usr/bin/env python3
"""Lay a chest's bags out in one row, left to right, each with its marker underneath, spaced evenly.

  tidy.py CHEST BAG:MARKER [BAG:MARKER ...] [--dry]

Pairs are given in the order wanted. Items not named are left where they are. When the slots are wider than the
chest, neighbouring slots overlap a little. --dry prints the positions without moving anything.
"""
import importlib.util
import os
import sys
import time

here = os.path.dirname(os.path.realpath(__file__))
for module in ('uo', 'layout'):
    spec = importlib.util.spec_from_file_location(module, os.path.join(here, module + '.py'))
    globals()[module] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(globals()[module])


def say(text):
    print(time.strftime('%H:%M:%S'), text, flush=True)


def positions(area, pairs, art):
    """{serial: (x, y)} for each bag and marker."""
    x1, y1, x2, y2 = area
    widths = [max(art[b]['visible'][2], art[m]['visible'][2] if m else 0) for b, m in pairs]
    # the row runs as far as the end slots' widest items can go; a narrower bag is clamped back inside on its own
    left = min(x1 + art[s]['visible'][0] for s in pairs[0] if s)
    right = max(x2 - art[s]['w'] + art[s]['visible'][0] + art[s]['visible'][2] for s in pairs[-1] if s)
    gap = (right - left - sum(widths)) / max(len(pairs) - 1, 1)
    spots, at = {}, left
    for (bag, marker), width in zip(pairs, widths):
        middle = at + width / 2
        bx, by, bw, bh = art[bag]['visible']
        x = min(max(round(middle - bw / 2 - bx), x1), x2 - art[bag]['w'])
        y = y1 + 1 - by
        spots[bag] = (x, y)
        if marker:
            mx, my, mw, mh = art[marker]['visible']
            spots[marker] = (min(max(round(middle - mw / 2 - mx), x1), x2 - art[marker]['w']),
                             min(y + by + bh + 3 - my, y2 - art[marker]['h']))
        at += width + gap
    return spots


def main():
    args = [a for a in sys.argv[1:] if a != '--dry']
    chest = uo.resolve(args[0])
    pairs = [tuple(p.split(':')) if ':' in p else (p, None) for p in args[1:]]
    info = uo.find_bridge(None)
    contents = uo.call(info, 'GET', '/contents', serial=chest)
    art = {i['serial']: i['art'] for i in contents['items']}
    missing = [s for p in pairs for s in p if s and s not in art]
    if missing:
        sys.exit(f'not in {chest}: ' + ', '.join(missing))
    spots = positions(contents.get('area') or [18, 105, 162, 178], pairs, art)
    where = {i['serial']: (i['x'], i['y']) for i in contents['items']}
    for serial, (x, y) in spots.items():
        if where[serial] == (x, y):
            continue
        if '--dry' in sys.argv:
            say(f'{serial} {where[serial]} -> {x},{y}')
            continue
        while True:
            try:
                result = uo.move(info, serial, chest, x, y)
                break
            except uo.BridgeError as e:
                if e.code == 409 and 'paused' in e.message:
                    time.sleep(60)
                    continue
                if uo.wait_out_world_save(info, e):
                    continue
                raise
        if not result['moved']:
            sys.exit(f'{serial} did not move: ' + '; '.join(m['text'] for m in result['messages']))
        say(f'{serial} -> {x},{y}')
    if '--dry' not in sys.argv:
        layout.record(chest, uo.call(info, 'GET', '/contents', serial=chest)['items'])
    say('TIDY DONE')


if __name__ == '__main__':
    try:
        main()
    except uo.BridgeError as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
