"""The forge chests, grey-dyed, swapped for plain undyed ones (the user, 2026-11-21: "swap out the grey chests by the
forge with regular non-dyed chests and then I'll move those dyed-grey chests to the great hall. There is a chest with
11 other chests inside of it next to the forge, those are to be used to replace the grey chests. You'll have to move
all the contents to swap them ... (and unlock/relock the chests)").

  python3 forge_swap.py          do the swaps (picks up where a stopped run left off, from forge-swap.json)
What happened (2026-11-21): 5 went in this way, but every new chest faced the other way (0x0E43, the grey ones
0x0E42), which Clem can't change; the user stopped it, turned them and placed the rest themselves, and Clem then moved
smelting 1's 62 pieces into its new chest (944,2322 top, 0x40590715, the box). forge-swap.json's "done" holds the
user's final mapping by place.

  python3 forge_swap.py remap    only rename the old serials to the new ones in the data files

For each of the 12 places (3 stacks of 4 at 944,2322 / 2326 / 2327), from the side of the forge corner (behind the
user's tables; nothing here crosses them):
  - a grey chest with things in it first has its pieces moved, in their drawing order and at their spots, into a
    holding chest: the new chest already in 2327 floor (free, empty but for its key);
  - the grey chest is released ("I wish to release this") and put down on the floor, on one of the piles for the user
    (947,2323, 947,2324, 946,2324; up to 5 a tile);
  - the new chest goes down on its tile: the house puts it in the lowest gap that fits, the grey chest's height
    (checked: same x, y, z, or it stops);
  - "I wish to lock this down" on it (checked: "locked down");
  - the pieces from the holding chest into it, at the same spots and in the same order (checked).
The 11 chests come out of the box (0x40590715); the 12th is the box itself, once it's empty (it's a plain undyed
chest too; its own key stays in it). Each new chest keeps the key that came in it.
Then the old serials become the new ones in labels.json, layout.json, names.json, castle/chests.json and the Vault
page's data (no recount, no publish: only when the user asks).
"""
import json
import os
import re
import sys
import time

import uo
import castle_plan
import castle_site
import look
import razor

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.expanduser('~/claude/uo-agent-work/castle')
STATE = os.path.join(WORK, 'forge-swap.json')
LOG = os.path.join(WORK, 'forge-swap.log')
BOX = '0x40590715'
NEW = ['0x4058E8DE', '0x4058EDBE', '0x4058E2D7', '0x4058D51C', '0x40589C3C', '0x4058A89F', '0x4059020A',
       '0x4058CCBA', '0x4058B001', '0x4058C67C', '0x4058DAD8']
# (old grey chest, x, y, z), in the order they're done: 2327 floor first (it holds the pieces of the full ones on
# their way), the empty ones, then the full ones; the last empty one gets the box
SLOTS = [
    ('0x404804BD', 944, 2327, 6),   # free (2327 floor)
    ('0x40789150', 944, 2322, 6),   # smelting 4
    ('0x406195D4', 944, 2322, 10),  # smelting 3
    ('0x40C9CAF9', 944, 2322, 14),  # smelting 2
    ('0x404485F8', 944, 2326, 6),   # boards & logs 2
    ('0x4045267F', 944, 2326, 14),  # ingots 2
    ('0x40A519B7', 944, 2322, 18),  # smelting 1
    ('0x40790A06', 944, 2326, 10),  # boards & logs
    ('0x405F351C', 944, 2326, 18),  # ingots
    ('0x405685FA', 944, 2327, 14),  # cloth & leather
    ('0x40444EE4', 944, 2327, 18),  # cooking
    ('0x403A90F5', 944, 2327, 10),  # tools (the box goes here)
]
PILES = [(947, 2323), (947, 2324), (946, 2324)]
PER_PILE = 5
FILES = ['labels.json', 'layout.json', 'names.json', 'castle/chests.json', 'vault/inventory.json',
         'vault/index.html']
info = None
mover = None


class Stop(Exception):
    pass


def say(text):
    line = f"{time.strftime('%H:%M:%S')} {text}"
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def load():
    try:
        return json.load(open(STATE))
    except FileNotFoundError:
        return {'done': {}, 'piled': [], 'holding': {}}


def save(state):
    with open(STATE, 'w') as fh:
        json.dump(state, fh, indent=1)


def lines(serial):
    return ' '.join(a for r in uo.call(info, 'POST', '/name', serial=serial) for a in r.get('lines', [])).lower()


def where(serial):
    r = uo.call(info, 'GET', '/item', serial=serial)
    if r.get('insideOf'):
        return None
    i = r['item']
    return (i['x'], i['y'], i['z'])


def stand_for(x, y):
    st = uo.call(info, 'GET', '/status')
    spot = castle_site.stand_spot(x, y)
    if (st['x'], st['y']) != spot:
        mover.go(spot, f'to {x},{y}')


def house(words, serial, want):
    said = castle_plan.house_command(info, words, serial)
    now = lines(serial)
    say(f'{serial} "{words}": {said or "no answer"} -> {now}')
    if not want(now):
        raise Stop(f'{serial} after "{words}": {now!r} ({said})')


def put_down(serial, x, y):
    r = uo.call(info, 'POST', '/move', serial=serial, ground=1, x=x, y=y)
    at = where(serial)
    if not at or at[:2] != (x, y):
        raise Stop(f'{serial} did not go down at {x},{y}: it is at {at} '
                   f"({' | '.join(m.get('text', '') for m in r.get('messages', []))})")
    return at


def move_pieces(pieces, dest, what):
    there = {i['serial']: i for i in look.open_once(info, dest)}
    for p in pieces:
        if p['serial'] in there and (there[p['serial']]['x'], there[p['serial']]['y']) == (p['x'], p['y']):
            continue
        uo.call(info, 'POST', '/move', serial=p['serial'], to=dest, x=p['x'], y=p['y'])
    items = look.open_once(info, dest)
    at = {i['serial']: i for i in items}
    off = [p['serial'] for p in pieces if p['serial'] not in at or (at[p['serial']]['x'], at[p['serial']]['y'])
           != (p['x'], p['y'])]
    order = [i['serial'] for i in items if i['serial'] in {p['serial'] for p in pieces}]
    if off or order != [p['serial'] for p in pieces]:
        raise Stop(f'{what}: off their spots {off}, order {"same" if not off and order else order}')
    say(f'{what}: {len(pieces)} pieces at their spots, same order')


def pile_spot(state):
    n = len(state['piled'])
    if n >= PER_PILE * len(PILES):
        raise Stop('no room left on the piles')
    return PILES[n // PER_PILE]


def swap(state, old, x, y, z, new, holding):
    stand_for(x, y)
    if where(old) != (x, y, z):
        raise Stop(f'{old} is not at {x},{y},{z} but at {where(old)}')
    pieces = state['holding'].get(old)
    if pieces is None:
        items = look.open_once(info, old)
        pieces = [dict(serial=i['serial'], x=i['x'], y=i['y'], name=i.get('type', '')) for i in items]
        state['holding'][old] = pieces
        save(state)
        say(f'{old} ({x},{y},{z}): {len(pieces)} pieces')
    if pieces:
        if not holding:
            raise Stop(f'{old} has things in it and no holding chest is ready')
        move_pieces(pieces, holding, f'{old} -> holding chest {holding}')
        if look.open_once(info, old):
            raise Stop(f'{old} is not empty after its pieces went to {holding}')
    # the grey chest: released, onto a pile
    if 'locked down' in lines(old):
        house('i wish to release this', old, lambda t: 'locked down' not in t)
    spot = pile_spot(state)
    at = put_down(old, *spot)
    state['piled'].append(old)
    save(state)
    say(f'{old} (grey) on the pile at {at}')
    # the new chest into the gap
    stand_for(x, y)
    at = put_down(new, x, y)
    if at != (x, y, z):
        raise Stop(f'the new chest {new} went down at {at}, not {x},{y},{z}')
    house('i wish to lock this down', new, lambda t: 'locked down' in t)
    if pieces:
        move_pieces(pieces, new, f'holding chest {holding} -> {new}')
    state['done'][old] = new
    state['holding'].pop(old, None)
    save(state)
    say(f'DONE {old} -> {new} at {x},{y},{z}')


def remap():
    done = load()['done']
    if not done:
        print('nothing swapped yet')
        return
    for f in FILES:
        path = os.path.join(HERE, f)
        text = open(path, encoding='utf-8').read()
        new = text
        for old, n in done.items():
            new = new.replace(old, n)
        if new != text:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(new)
            print(f'{f}: renamed')
    seen = os.path.join(WORK, 'seen.json')
    if os.path.exists(seen):
        text = open(seen).read()
        for old, n in done.items():
            text = text.replace(old, n)
        open(seen, 'w').write(text)


def main():
    global info, mover
    if sys.argv[1:] == ['remap']:
        return remap()
    info = uo.find_bridge('Clem')
    mover = castle_site.install(uo, info, say)
    razor.install(uo, info, say)
    if not mover:
        raise Stop('Clem is not in the castle')
    look.uo.walk_near = mover.walk_near
    st = uo.call(info, 'GET', '/status')
    if not castle_site.behind((st['x'], st['y'])):
        raise Stop(f"Clem is at {st['x']},{st['y']}, not behind the tables")
    state = load()
    used = set(state['done'].values())
    holding = state['done'].get(SLOTS[0][0])
    for old, x, y, z in SLOTS:
        if old in state['done']:
            continue
        spare = [n for n in NEW if n not in used]
        new = spare[0] if spare else BOX
        if new == BOX:
            box_items = look.open_once(info, BOX)
            if any(i['serial'] in NEW for i in box_items):
                raise Stop('the box still holds new chests')
        state.setdefault('picked', {})[old] = new
        save(state)
        swap(state, old, x, y, z, new, holding)
        used.add(new)
        if old == SLOTS[0][0]:
            holding = new
    say(f'ALL SWAPPED: {len(state["done"])} chests')
    remap()


if __name__ == '__main__':
    try:
        main()
    except (Stop, uo.BridgeError) as e:
        import traceback
        traceback.print_exc()
        say(f'STOPPED: {e}')
        sys.exit(1)
