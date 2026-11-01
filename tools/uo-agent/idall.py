#!/usr/bin/env python3
"""Identify items with ID wands, swapping in a spare when the one in hand runs out.

  idall.py TARGET [TARGET...]

Uses the ID wand or staff in Johnny's hand first. When it's out of charges it goes into the wand trash crate,
and the spare with the fewest charges comes out of the spares pouch. Waits while anyone else is in the room
(checking once a minute), and stops on anything it doesn't understand, or when the bridge halts.
"""
import importlib.util
import os
import re
import sys
import time

spec = importlib.util.spec_from_file_location('uo', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'uo.py'))
uo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uo)

TRASH = '0x408AD7D5'   # the trash crate by the door; empty ID wands and staves go here
SPARES = '0x4049D6B8'  # pouch of spare ID wands and staves, in the supplies chest


def say(text):
    print(time.strftime('%H:%M:%S'), text, flush=True)


def charges(name):
    m = re.search(r'\((\d+) charges?\)', name or '')
    return int(m.group(1)) if m else None


def wait_until_clear(info):
    while True:
        others = uo.others_in_area(info)
        if not others:
            return
        say(f"paused: {', '.join(others)} in the room; checking again in a minute")
        time.sleep(60)


def wand_in_hand(info):
    for item in uo.call(info, 'GET', '/status')['hands']:
        if 'identification' in (item.get('name') or ''):
            return item['serial'], charges(item['name'])
    return None, 0


def spares(info):
    """ID tools in the spares pouch with charges left, fewest charges first. Opens the pouch if its contents aren't known."""
    contents = uo.call(info, 'GET', '/contents', serial=SPARES)
    if contents['container'].get('knownItems', 0) == 0:
        uo.walk_near(info, SPARES)
        contents = uo.call(info, 'POST', '/open', serial=SPARES)['contents']
        uo.call(info, 'POST', '/close', serial=SPARES)
    tools = [(charges(i.get('name')), i['serial']) for i in contents['items'] if 'identification' in (i.get('name') or '')]
    return sorted(t for t in tools if t[0])


def swap(info, wand):
    if wand:
        wait_until_clear(info)
        result = uo.move(info, wand, TRASH)
        if not result['moved']:
            raise uo.BridgeError(0, f'could not put the empty wand {wand} in the trash crate')
        say(f'{wand} is empty; put it in the trash crate')
    while True:
        tools = spares(info)
        if tools:
            break
        say('no spare ID wands left; checking the spares pouch again in a minute')
        time.sleep(60)
    left, serial = tools[0]
    wait_until_clear(info)
    uo.walk_near(info, serial)
    result = uo.call(info, 'POST', '/equip', serial=serial)
    if not result['equipped']:
        raise uo.BridgeError(0, f'could not equip {serial}: ' + '; '.join(m['text'] for m in result['messages']))
    say(f'now using {serial} ({left} charges)')
    return serial, left


def main():
    info = uo.find_bridge(None)
    targets = [uo.resolve(t) for t in sys.argv[1:]]
    wand, left = wand_in_hand(info)
    if left is None:
        left = 1  # charges unknown; use it until it says it's empty
    done = 0

    for target in targets:
        while True:
            wait_until_clear(info)
            if not wand or left <= 0:
                wand, left = swap(info, wand)
            try:
                result = uo.call(info, 'POST', '/use', serial=wand, target=target)
            except uo.BridgeError as e:
                if e.code == 409 and 'paused' in e.message:
                    continue
                if e.code == 409 and 'too far' in e.message:
                    uo.walk_near(info, target)
                    continue
                raise
            texts = [m['text'] for m in result['messages']]
            if result['targeted']:
                left -= 1
                done += 1
                name = result.get('target', {}).get('name') or ' / '.join(texts) or '(no name shown)'
                say(f'{target}  {name}')
                break
            if any('charges' in t.lower() for t in texts):
                left = 0  # out of charges: swap and try again
                continue
            raise uo.BridgeError(0, f'using the wand on {target} did nothing: ' + ('; '.join(texts) or 'no message'))

    say(f'identified {done} items; {wand} has {left} charges left')


if __name__ == '__main__':
    try:
        main()
    except uo.BridgeError as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
