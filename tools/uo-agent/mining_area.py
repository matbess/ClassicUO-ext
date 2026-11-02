#!/usr/bin/env python3
"""Turn a recorded route into the boxes of Icepick's allowed area (the "areas" of his rules file).

  python3 mining_area.py ROUTE.jsonl [--margin 4]   prints the areas as JSON

Route points beyond the guards' edges are dropped and every box is clipped well inside them (the user's walk
on 2026-11-01 found the edges near x 1092-1096 on the northern bulge and y 1903-1906 in the south; see MINING.md).
Consecutive points are grouped into boxes no bigger than about 12 tiles, then widened by the margin, so the
corridor follows the mountain face and the boxes overlap where they meet.
"""
import argparse
import json
import sys

# keep at least 4 tiles inside the guarded zone
MIN_X = 1100
MAX_Y = 1898
# the canyon leads out of town: only its first half (the mouth is by the forge, about 1150,1862)
CANYON = lambda x, y: x < 1128 and y > 1878  # noqa: E731


def kept(p):
    return p['x'] >= MIN_X and p['y'] <= MAX_Y and not CANYON(p['x'], p['y'])


def boxes(points, margin, size=12):
    out, group = [], []
    for p in points:
        trial = group + [p]
        xs, ys = [q['x'] for q in trial], [q['y'] for q in trial]
        if group and (max(xs) - min(xs) > size or max(ys) - min(ys) > size):
            out.append(group)
            trial = [group[-1], p]  # overlap with the previous box
        group = trial
    if group:
        out.append(group)
    result = []
    for g in out:
        xs, ys = [q['x'] for q in g], [q['y'] for q in g]
        x1, y1 = max(MIN_X, min(xs) - margin), min(ys) - margin
        x2, y2 = max(xs) + margin, min(MAX_Y, max(ys) + margin)
        # a box reaching past the canyon's halfway point (x < 1128 and y > 1878) is split around it
        if x1 < 1128 and y2 > 1878:
            parts = [[x1, y1, x2, min(y2, 1878)], [1128, max(y1, 1879), x2, y2]]
        else:
            parts = [[x1, y1, x2, y2]]
        result += [b for b in parts if b[0] <= b[2] and b[1] <= b[3]]
    return result


def uncovered(points, areas):
    return [q for q in points if not any(b[0] <= q['x'] <= b[2] and b[1] <= q['y'] <= b[3] for b in areas)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('route')
    p.add_argument('--margin', type=int, default=4)
    a = p.parse_args()
    points = [r for r in map(json.loads, open(a.route, encoding='utf-8')) if 'message' not in r]
    points = [q for q in points if kept(q)]
    found = boxes(points, a.margin)
    missing = uncovered(points, found)
    if missing:
        sys.exit(f'{len(missing)} route points fall outside the boxes, e.g. {missing[0]}')
    areas = [{'name': f'route {i + 1}', 'box': b, 'z': [-10, 40]} for i, b in enumerate(found)]
    print(json.dumps(areas))


if __name__ == '__main__':
    main()
