#!/usr/bin/env python3
"""Carry out a list of moves, one at a time, at the bridge's pace.

  moves.py PLAN.json

PLAN.json is a list of moves: ["SERIAL", "TO"], ["SERIAL", "TO", X, Y] or ["SERIAL", "TO", X, Y, AMOUNT], where TO is
a serial or a label, X and Y may be null, and AMOUNT takes only that many from a stack.
Johnny walks within reach first, and carries an item in the backpack when he can't reach both ends. Waits while
anyone else is in the room (checking once a minute). Stops at the first move that fails, or when the bridge
stops, and says which move it stopped at, so the rest of the plan can be run again from there.
"""
import importlib.util
import json
import os
import sys
import time

spec = importlib.util.spec_from_file_location('uo', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'uo.py'))
uo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uo)


def say(text):
    print(time.strftime('%H:%M:%S'), text, flush=True)


def wait_until_clear(info):
    while True:
        others = uo.others_in_area(info)
        if not others:
            return
        say(f"paused: {', '.join(others)} in the room; checking again in a minute")
        time.sleep(60)


def main():
    plan = json.load(open(sys.argv[1]))
    info = uo.find_bridge(None)
    names = uo.load_names()

    for number, step in enumerate(plan, start=1):
        serial, to = step[0], uo.resolve(step[1])
        x, y = (step[2], step[3]) if len(step) >= 4 else (None, None)
        amount = step[4] if len(step) >= 5 else None
        what = names.get(serial, serial)
        where = uo.load_labels().get(to, to)

        while True:
            wait_until_clear(info)
            try:
                result = uo.move(info, serial, to, x, y, amount)
            except uo.BridgeError as e:
                if e.code == 409 and 'paused' in e.message:
                    continue
                if uo.wait_out_world_save(info, e):
                    say('world save finished; carrying on')
                    # the move may have gone through during the save
                    found = uo.call(info, 'GET', '/item', serial=serial)
                    inside = found['insideOf'][0]['serial'] if found['insideOf'] else None
                    if inside == to or found['item']['serial'] == to:
                        result = {'moved': True, 'messages': []}
                        break
                    continue
                say(f'STOPPED at move {number} of {len(plan)} ({what} -> {where}): {e}')
                sys.exit(1)
            break

        if not result['moved']:
            texts = '; '.join(m['text'] for m in result['messages']) or 'no message'
            say(f'STOPPED at move {number} of {len(plan)}: {what} did not go into {where} ({texts})')
            sys.exit(1)

        say(f'{number}/{len(plan)}  {what}' + (f' (x{amount})' if amount else '') + f' -> {where}' + (f' at {x},{y}' if x is not None else ''))

    say(f'done: {len(plan)} moves')


if __name__ == '__main__':
    main()
