#!/usr/bin/env python3
"""Open every chest once and record what's in it (bags, their kinds and markers, loose items) in layout.json.

  survey.py [S ...]     the chests to survey (default: every container labelled "chest: ...")
  survey.py --known     record only from what the client already knows; sends nothing to the server. Chests it
                        knows nothing in (after a restart) keep what was recorded before.

Walks along the wall column by column. Waits while someone is in the room and out world saves; stops at the first
problem and says where. First it checks every chest label's "(col N, ROW)" against where the chest really is
(columns left to right by x, rows from the top by height) and warns about any that disagree.
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


def open_once(info, serial):
    while True:
        while uo.others_in_area(info):
            say('paused: someone is in the room; checking again in a minute')
            time.sleep(60)
        try:
            uo.walk_near(info, serial, reach=2)
            result = uo.call(info, 'POST', '/open', serial=serial)
            uo.call(info, 'POST', '/close', serial=serial)
            return result
        except uo.BridgeError as e:
            if e.code == 409 and 'paused' in e.message:
                continue
            if uo.wait_out_world_save(info, e):
                say('world save finished; carrying on')
                continue
            raise


def place(spots):
    """serial -> (column, row) worked out from where each chest stands: columns left to right, rows from the top."""
    columns = sorted({(s['x'], s['y']) for s in spots.values()})
    out = {}
    for serial, s in spots.items():
        stack = sorted((o['z'] for o in spots.values() if (o['x'], o['y']) == (s['x'], s['y'])), reverse=True)
        out[serial] = (columns.index((s['x'], s['y'])) + 1, stack.index(s['z']), len(stack))
    return out


def check_positions(spots, labels):
    for serial, (column, row, rows) in place(spots).items():
        want = 'top' if row == 0 else 'bottom' if row == rows - 1 else ('2nd', '3rd', '4th', '5th')[row - 1] + ' from top'
        text = labels.get(serial, '')
        if f'(col {column}, {want})' not in text:
            yield serial, f'is really col {column}, {want}'


def main():
    info = uo.find_bridge(None)
    known = '--known' in sys.argv
    labels = uo.load_labels()
    chests = [uo.resolve(s) for s in sys.argv[1:] if s != '--known'] or \
        [s for s, text in labels.items() if text.startswith('chest: ')]
    spots = {s: uo.on_floor(info, s) for s in chests}
    missing = [s for s, spot in spots.items() if not spot]
    if missing:
        sys.exit('not in sight: ' + ', '.join(f'{s} {labels.get(s, "")}' for s in missing))
    # along the wall, top to bottom in each column
    chests.sort(key=lambda s: (spots[s]['x'], spots[s]['y'], -spots[s]['z']))
    for serial, problem in check_positions(spots, labels):
        say(f'LABEL CHECK: {labels.get(serial)} {problem}')

    for serial in chests:
        if known:
            items = uo.call(info, 'GET', '/contents', serial=serial)['items']
            if not items:
                continue
        else:
            result = open_once(info, serial)
            if not result['opened']:
                raise uo.BridgeError(0, f'{serial} {labels.get(serial, "")} did not open')
            items = result['contents']['items']
        entry = layout.record(serial, items)
        unmarked = sum(1 for b in entry['bags'] if not b['marker'])
        say(f"{entry['label']}: {len(items)} items, {len(entry['bags'])} bags"
            + (f' ({unmarked} without a marker)' if unmarked else '') + f", {len(entry['loose'])} loose")
    say('SURVEY DONE')


if __name__ == '__main__':
    try:
        main()
    except uo.BridgeError as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
