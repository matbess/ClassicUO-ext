"""What each chest holds: its bags, what kind of thing each bag is for, the marker under each bag, and what lies
loose in the chest.

Saved in layout.json next to this file. A chest's entry is rewritten whenever its contents are read
(survey.py, sortbatch.py), so it survives client restarts. The game is still the truth: open a chest before moving
things into it, since the user may have taken things out.

A bag's kind comes from its label in labels.json ("bag: plate tunics (plate + helms chest)" gives "plate tunics"),
otherwise from the type of its marker. A container with any other label (the spares pouch) has no marker.
"""
import json
import os
import time

HERE = os.path.dirname(os.path.realpath(__file__))
LAYOUT = os.path.join(HERE, 'layout.json')


def _read(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def load():
    return _read(LAYOUT)


def _box(item):
    vx, vy, vw, vh = item['art']['visible']
    return item['x'] + vx, item['y'] + vy, vw, vh


def pair(items, unmarked=()):
    """Match each bag with its marker: the nearest item under the bag that overlaps it sideways, or failing that
    (a full chest) the nearest one just to its right. Bags in unmarked get none.
    Returns ([(bag, marker or None)], loose items)."""
    bags = [i for i in items if i.get('container')]
    others = [i for i in items if not i.get('container') and 'art' in i]
    pairs = []
    for b in bags:
        if b['serial'] in unmarked:
            continue
        bx, by, bw, bh = _box(b)
        for m in others:
            mx, my, mw, mh = _box(m)
            if by + bh / 2 <= my <= by + bh + 20 and mx < bx + bw + 4 and mx + mw > bx - 4:
                pairs.append((abs(my - (by + bh)) + abs((mx + mw / 2) - (bx + bw / 2)) / 2, b['serial'], m['serial']))
            elif bx + bw - 4 <= mx <= bx + bw + 25 and my < by + bh and my + mh > by:
                pairs.append((100 + mx - (bx + bw), b['serial'], m['serial']))
    marker_of, used = {}, set()
    for _, b, m in sorted(pairs):
        if b not in marker_of and m not in used:
            marker_of[b] = m
            used.add(m)
    by_serial = {i['serial']: i for i in items}
    return ([(b, by_serial.get(marker_of.get(b['serial']))) for b in bags],
            [i for i in items if not i.get('container') and i['serial'] not in used])


def record(chest, items):
    """Rewrite the chest's entry from its contents (the items list of a /contents or /open answer)."""
    labels, names = _read(os.path.join(HERE, 'labels.json')), _read(os.path.join(HERE, 'names.json'))

    def name(i):
        return i.get('name') or names.get(i['serial']) or i.get('type', '')

    def kind(bag, marker):
        label = labels.get(bag['serial'], '')
        if label:
            return label[5:].split(' (')[0] if label.startswith('bag: ') else label
        return ' '.join(marker['type'].split()) if marker else '?'

    bags, loose = pair(items, unmarked={s for s, text in labels.items() if not text.startswith('bag: ')})
    entry = {
        'label': labels.get(chest, ''),
        'recorded': time.strftime('%Y-%m-%d %H:%M'),
        'items': len(items),
        'bags': [{'serial': b['serial'], 'kind': kind(b, m), 'x': b['x'], 'y': b['y'], 'known': b.get('knownItems', 0),
                  'marker': m and {'serial': m['serial'], 'name': name(m), 'x': m['x'], 'y': m['y']}}
                 for b, m in bags],
        'loose': [{'serial': i['serial'], 'name': name(i), 'amount': i.get('amount', 1), 'x': i['x'], 'y': i['y']}
                  for i in loose],
    }
    layout = load()
    layout[chest] = entry
    tmp = LAYOUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(layout, fh, indent=1, sort_keys=True)
    os.replace(tmp, LAYOUT)
    return entry


if __name__ == '__main__':
    # print the map: python3 layout.py
    for chest, e in sorted(load().items(), key=lambda kv: kv[1]['label']):
        print(f"{e['label'] or chest}  ({e['items']} items, recorded {e['recorded']})")
        for b in e['bags']:
            m = b['marker']
            print(f"  bag {b['serial']}  {b['kind']}" + (f"  - marker: {m['name']}" if m else '  - no marker yet'))
        for i in e['loose']:
            print(f"  {i['serial']}  {i['name']}" + (f" x{i['amount']}" if i['amount'] > 1 else ''))
