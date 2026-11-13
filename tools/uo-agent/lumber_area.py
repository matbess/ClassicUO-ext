#!/usr/bin/env python3
"""Turn the user's ride round the tree area into the boxes of Icepick's lumberjacking area (LUMBERJACKING.md).

  python3 lumber_area.py RIDE.jsonl [--band 3]   prints the areas as JSON

The ride is a closed loop (the user rode the edge, 2026-11-12); every tile inside it counts, less what lies past the
guards' edges: the user rode a little past them on purpose in four places to find them. Those edges are mining's
(mining_area.py: x 1100 and y 1898, and the canyon past halfway), and in the north y 1543 (out at 1536 by the start,
in again at 1543; out at 1529 by the castle). The inside is cut into bands of a few rows; each band's runs of tiles
that are inside on every row of the band become one box, so no box holds a tile outside the loop.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import mining_area  # noqa: E402

MIN_Y = 1543


def polygon(path):
    rows = [json.loads(line) for line in open(path, encoding='utf-8')]
    return [(r['x'], r['y']) for r in rows if 'message' not in r]


def inside_fn(poly):
    edges = list(zip(poly, poly[1:] + poly[:1]))

    def inside(x, y):
        if x < mining_area.MIN_X or y > mining_area.MAX_Y or y < MIN_Y or mining_area.CANYON(x, y):
            return False
        c = False
        for (x1, y1), (x2, y2) in edges:
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                c = not c
        return c
    return inside


def boxes(poly, band=3):
    inside = inside_fn(poly)
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    out = []
    for top in range(min(ys), max(ys) + 1, band):
        rows = range(top, min(top + band, max(ys) + 1))
        run = None
        for x in range(min(xs), max(xs) + 2):
            ok = x <= max(xs) and all(inside(x, y) for y in rows)
            if ok and run is None:
                run = x
            elif not ok and run is not None:
                out.append([run, rows[0], x - 1, rows[-1]])
                run = None
    return out, inside


def main():
    p = argparse.ArgumentParser()
    p.add_argument('ride')
    p.add_argument('--band', type=int, default=3)
    a = p.parse_args()
    found, _ = boxes(polygon(a.ride), a.band)
    areas = [{'name': f'trees {i + 1}', 'box': b, 'z': [-10, 40]} for i, b in enumerate(found)]
    # the user rode along the foot of the mountain, so the trees between the ride and the rock (chopped by hand at
    # 1124,1557 and 1124,1560) lie just outside the loop: mining's corridor, already inside the guards, adds them
    import mining
    areas += [dict(a, name='mining ' + a['name']) for a in mining.load_rules()['areas']]
    print(json.dumps(areas))


if __name__ == '__main__':
    main()
