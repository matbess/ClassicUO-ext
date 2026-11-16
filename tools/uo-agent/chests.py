#!/usr/bin/env python3
"""Icepick makes wooden chests for the user's furniture and packs them in crates (the user, 2026-11-15).

  python3 -I chests.py run [--count 50]   make that many wooden chests (on top of what's already made), into the
                                          crate at 1760,1409; stops early when too many fail
  python3 -I carp.py stop                 stops it too (same stop file)

The user, 2026-11-15: 150 wooden chests in all, into the crate they put down; a crate mustn't go over 300 stones,
start a new crate then (stacked on the other). Start with 50 and see: 1 in 5 failing is fine, 1 in 2 means wait
until his Carpentry is higher. So the loop stops after MIN_CRAFTS crafts once the failures reach FAIL_STOP.

The bridge can only put a thing down on his own tile, so a new crate (a medium crate he makes) goes down at his feet
(1759,1410) and the user stacks it. Uses carp.py's saws, boards and menus; logs to ~/claude/uo-agent-work/carp/chests.log.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import carp  # noqa: E402
import uo  # noqa: E402
from carp import Stop, Interrupted, say  # noqa: E402

carp.LOG = os.path.join(carp.WORK, 'chests.log')
STATE = os.path.join(carp.WORK, 'chests.json')
FIRST_CRATE = '0x405EE726'      # the user's crate at 1760,1409 (2026-11-15)
CRATE_GRAPHICS = ('0x0E3E', '0x0E3F')
MAX_STONES = 300                # the user: a crate mustn't go over 300 stones
MAX_ITEMS = 125                 # a container's item limit
MIN_CRAFTS = 10
FAIL_STOP = 0.4                 # the user: 1 in 5 failing is fine, 1 in 2 isn't
CHEST = 'wooden chest'


def load():
    try:
        with open(STATE) as fh:
            s = json.load(fh)
    except FileNotFoundError:
        s = {}
    s.setdefault('crates', [FIRST_CRATE])
    s.setdefault('made', 0)
    s.setdefault('crafts', 0)
    s.setdefault('failed', 0)
    return s


def save(s):
    uo.write_json(STATE, s, 1)


def crate_load(serial):
    """(items, stones) from the crate's single-click label "(N items, M stones)"."""
    for r in carp.call('POST', '/name', serial=serial):
        for line in r.get('lines', []):
            m = re.search(r'\((\d+) items?, (\d+) stones?\)', line)
            if m:
                return int(m.group(1)), int(m.group(2))
    raise Stop(f'no weight on crate {serial}\'s label')


def craft(state, item):
    """One craft of item; the new thing in his pack, or None on a failure."""
    while True:
        try:
            s = carp.saw(state)
            carp.top_up(carp.BOARD_GRAPHICS, carp.PACK_BOARDS, carp.BOARDS_LOW, carp.BOARD_WEIGHT, 'boards')
            before = {i['serial'] for i in carp.pack()}
            sub, index = carp.find_item(state, s, item)
            if sub is None:
                raise Stop(f'{item} is on none of the saw\'s menus at Carpentry {carp.skill()}')
            text = carp.craft_result(carp.choose(sub, index))
        except Interrupted as e:
            say(f'craft interrupted ({e}); again')
            continue
        low = text.lower()
        if 'must wait' in low:
            time.sleep(1)
            continue
        if 'do not have' in low or "don't have" in low or 'not enough' in low or 'lack' in low:
            raise Stop(f'not enough materials for {item}: {text}')
        state['saws'][s] = state.setdefault('saws', {}).get(s, 0) + 1
        after = carp.pack()
        if not any(i['serial'] == s for i in after):
            say(f'saw {s} wore out')
        if 'you create' not in low:
            return None
        new = [i for i in after if i['serial'] not in before and i.get('graphic') not in carp.supplies_kinds()]
        if not new:
            raise Stop(f'made a {item} but nothing new is in his pack')
        return new[0]


def on_ground(serial):
    """Lying on the ground: only ground items have a distance and nothing they're inside of (an item in his pack has
    x and y too, its place in the pack: the first check took the crate in his pack for one set down, 2026-11-15)."""
    found = carp.call('GET', '/item', serial=serial)
    return 'distance' in found['item'] and not found.get('insideOf')


def new_crate(state):
    """Makes a medium crate and puts it down at his feet."""
    while True:
        c = craft(state, 'medium crate')
        if c:
            break
        say('a crate failed; again')
    # the server gave no answer when he put a crate down at his feet (2026-11-15 15:25: it stayed in his pack), so
    # the user takes it out of his pack and sets it down; he waits, sending nothing, until it's on the ground
    state['crates'].append(c['serial'])
    save(state)
    carp.wait_for(f'new crate {c["serial"]} is in his pack: the user sets it down in his corner',
                  lambda: on_ground(c['serial']))
    carp.call('POST', '/open', serial=c['serial'])
    say(f'NEW CRATE {c["serial"]} is down; filling it')
    return c['serial']


def run(count):
    if os.path.exists(carp.STOP_FILE):
        os.remove(carp.STOP_FILE)
    state = load()
    # the saws are looked for in every container in his corner: not in the furniture crates
    plain = carp.saw_containers
    carp.saw_containers = lambda: [b for b in plain() if b['serial'] not in state['crates']]
    if carp.status().get('takenOver'):
        raise Stop('the user has Icepick; waiting for them to hand him back')
    carp.cancel_open_menus()
    carp.call('POST', '/open', serial=carp.pack_serial())
    crate = state['crates'][-1]
    try:
        uo.call(carp.info, 'GET', '/item', serial=crate)
        if not on_ground(crate):
            carp.wait_for(f'crate {crate} is in his pack: the user sets it down in his corner',
                          lambda: on_ground(crate))
        carp.call('POST', '/open', serial=crate)
    except uo.BridgeError as e:
        if e.code != 404:
            raise
        # the user took the full crate away (2026-11-15: "Make a new [crate] and then put the other 100 in it")
        say(f'crate {crate} is gone (the user took it): a new crate')
        crate = new_crate(state)
    goal = state['made'] + count
    run_crafts = run_failed = 0
    say(f'start: Carpentry {carp.skill()}; {state["made"]} wooden chests made so far, making {count} more '
        f'(crate {crate}: {crate_load(crate)})')
    while state['made'] < goal:
        if os.path.exists(carp.STOP_FILE):
            os.remove(carp.STOP_FILE)
            say('STOPPED: asked to stop')
            return
        chest = craft(state, CHEST)
        state['crafts'] += 1
        run_crafts += 1
        if not chest:
            state['failed'] += 1
            run_failed += 1
            save(state)
            if run_crafts >= MIN_CRAFTS and run_failed / run_crafts >= FAIL_STOP:
                say(f'STOPPED: too many failures: {run_failed} of {run_crafts} wooden chests failed at Carpentry '
                    f'{carp.skill()}')
                return
            continue
        items, stones = crate_load(crate)
        weight = state.get('chest_stones')
        if items + 3 > MAX_ITEMS or (weight and stones + weight > MAX_STONES):
            say(f'crate {crate} has {items} items, {stones} stones: a new crate')
            crate = new_crate(state)
            items, stones = crate_load(crate)
        carp.call('POST', '/move', serial=chest['serial'], to=crate)
        n_items, n_stones = crate_load(crate)
        if not weight:
            state['chest_stones'] = n_stones - stones
            say(f'a wooden chest (with what is inside it) weighs {n_stones - stones} stones and counts '
                f'{n_items - items} items')
        state['made'] += 1
        save(state)
        say(f"wooden chest {state['made']} into crate {crate} ({n_items} items, {n_stones} stones); "
            f"{run_failed} of {run_crafts} failed this run")
    say(f"STOPPED: done, {state['made']} wooden chests made ({state['failed']} of {state['crafts']} crafts failed); "
        f'Carpentry {carp.skill()}')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('cmd', choices=['run'])
    p.add_argument('--count', type=int, default=50)
    args = p.parse_args()
    os.makedirs(carp.WORK, exist_ok=True)
    carp.info = uo.find_bridge(carp.CHAR)
    carp.install_rules()
    if os.path.exists(carp.PID):
        try:
            with open(carp.PID) as fh:
                os.kill(int(fh.read().strip()), 0)
            sys.exit('a loop is already running')
        except (OSError, ValueError):
            pass
    with open(carp.PID, 'w') as fh:
        fh.write(str(os.getpid()))
    try:
        run(args.count)
    except Stop as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
    finally:
        os.remove(carp.PID)


if __name__ == '__main__':
    main()
