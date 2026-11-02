#!/usr/bin/env python3
"""Leave Johnny ready for the user to play once sorting is done.

  finish.py

Puts an ID wand or staff from his hands back in the spares pouch (after a single-click, so names.json has its real
charges), then walks him to the middle of the room in rules.json.
"""
import importlib.util
import os
import sys
import time

spec = importlib.util.spec_from_file_location('uo', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'uo.py'))
uo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uo)

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
    x1, y1, x2, y2 = uo.call(info, 'GET', '/rules')['areas'][0]['box']
    walked = uo.call(info, 'POST', '/walk', x=(x1 + x2) // 2, y=(y1 + y2) // 2, distance=0)
    say(f"Johnny is at {walked['x']},{walked['y']}" + ('' if walked['arrived'] else ' (the middle was blocked)'))


if __name__ == '__main__':
    try:
        main()
    except uo.BridgeError as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
