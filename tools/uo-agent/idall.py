#!/usr/bin/env python3
"""Identify items with ID wands, swapping in a spare when the one in hand runs out.

  idall.py TARGET [TARGET...]

Each target is named first (one single-click, unless its name is already known), and only the ones the server calls
"magic X" get a charge. Identified, plain and GM-crafted ("exceptional ... crafted by") items are skipped.
Wands and staves are identified first: any ID ones among them join the spares, so their charges go on the rest.
Uses the ID wand or staff in Johnny's hand first. When it's out of charges it goes into the trash barrel,
and the spare with the fewest charges (from the spares pouch or found in this batch) comes out. Waits while anyone
else is in the room (checking once a minute), and stops on anything it doesn't understand, or when the bridge halts.
"""
import importlib.util
import os
import re
import sys
import time

spec = importlib.util.spec_from_file_location('uo', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'uo.py'))
uo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uo)

TRASH = '0x4068E2BB'   # the trash barrel by the door; empty ID wands and staves go here
SPARES = '0x4049D6B8'  # pouch of spare ID wands and staves, in the supplies chest
WANDS = {'0x0DF2', '0x0DF3', '0x0DF4', '0x0DF5',             # wands
         '0x0DF0', '0x0DF1', '0x13F8', '0x13F9', '0x0E89', '0x0E8A'}  # black, gnarled and quarter staves
FOUND = {}  # ID wands and staves found in this batch: serial -> charges
UNIDENTIFIED = re.compile(r'^(an? )?magic ', re.I)  # how the server names magic items nobody has identified yet


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


def name_of(item):
    # after a client restart the bridge has forgotten names; names.json remembers them
    return item.get('name') or uo.load_names().get(item['serial'], '')


def wand_in_hand(info):
    for item in uo.call(info, 'GET', '/status')['hands']:
        if 'identification' in name_of(item):
            return item['serial'], charges(name_of(item))
    return None, 0


def spares(info):
    """ID tools in the spares pouch with charges left, fewest charges first. Opens the pouch if its contents aren't known."""
    try:
        contents = uo.call(info, 'GET', '/contents', serial=SPARES)
    except uo.BridgeError as e:
        if e.code != 404:
            raise
        # the client doesn't know the pouch yet: open the chest it's in
        chest = uo.resolve('supplies')
        uo.walk_near(info, chest)
        uo.call(info, 'POST', '/open', serial=chest)
        uo.call(info, 'POST', '/close', serial=chest)
        contents = uo.call(info, 'GET', '/contents', serial=SPARES)
    if contents['container'].get('knownItems', 0) == 0:
        uo.walk_near(info, SPARES)
        contents = uo.call(info, 'POST', '/open', serial=SPARES)['contents']
        uo.call(info, 'POST', '/close', serial=SPARES)
    tools = [(charges(name_of(i)), i['serial']) for i in contents['items'] if 'identification' in name_of(i)]
    return sorted(t for t in tools if t[0])


def swap(info, wand):
    if wand:
        wait_until_clear(info)
        try:
            result = uo.move(info, wand, TRASH)
        except uo.BridgeError as e:
            if not uo.resume_after_barrel_emptied(info, e):
                raise
            result = {'moved': True}
        if not result['moved']:
            raise uo.BridgeError(0, f'could not put the empty wand {wand} in the trash barrel')
        say(f'{wand} is empty; put it in the trash barrel')
    while True:
        tools = sorted(spares(info) + [(left, serial) for serial, left in FOUND.items()])
        if tools:
            break
        say('no spare ID wands left; checking the spares pouch again in a minute')
        time.sleep(60)
    left, serial = tools[0]
    FOUND.pop(serial, None)
    wait_until_clear(info)
    uo.walk_near(info, serial)
    result = uo.call(info, 'POST', '/equip', serial=serial)
    if not result['equipped']:
        raise uo.BridgeError(0, f'could not equip {serial}: ' + '; '.join(m['text'] for m in result['messages']))
    say(f'now using {serial} ({left} charges)')
    return serial, left


def needing_id(info, targets):
    """The targets still to identify. Names not known yet are asked for in one paced request per ten."""
    unknown = [t for t in targets if t not in uo.load_names()]
    for i in range(0, len(unknown), 10):
        while True:
            wait_until_clear(info)
            try:
                uo.call(info, 'POST', '/name', serial=','.join(unknown[i:i + 10]))  # names go into names.json
                break
            except uo.BridgeError as e:
                if e.code == 409 and 'paused' in e.message:
                    continue
                if uo.wait_out_world_save(info, e):
                    say('world save finished; carrying on')
                    continue
                raise
    names = uo.load_names()
    left = []
    for t in targets:
        name = names.get(t, '').split(' / ')[0]
        if UNIDENTIFIED.match(name):
            left.append(t)
        else:
            say(f'{t}  {name or "(no name)"}: no charge needed')
    return left


def main():
    info = uo.find_bridge(None)
    targets = needing_id(info, [uo.resolve(t) for t in sys.argv[1:]])
    targets.sort(key=lambda t: uo.call(info, 'GET', '/item', serial=t)['item']['graphic'] not in WANDS)
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
                if uo.wait_out_world_save(info, e):
                    say('world save finished; carrying on')
                    continue
                raise
            texts = [m['text'] for m in result['messages']]
            if result['targeted']:
                left -= 1
                done += 1
                name = result.get('target', {}).get('name') or ' / '.join(texts) or '(no name shown)'
                say(f'{target}  {name}')
                if 'identification' in name and charges(name):
                    FOUND[target] = charges(name)
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
