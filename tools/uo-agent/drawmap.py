#!/usr/bin/env python3
"""Draw a piece of the map as a PNG (north up: x to the right, y down), with recorded routes and marks on it.

  python3 drawmap.py OUT.png X1 Y1 X2 Y2 [--scale 4] [--route route.jsonl ...] [--mark X,Y,COLOUR ...]
                     [--mineable] [--grid 10]

The ground and statics use the game's radar colours (like the client's mini map). --mineable outlines the
tiles a pickaxe or shovel can dig (mountain and cave ground). Colours: red, yellow, cyan, blue, white, magenta.
"""
import argparse
import json
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import uomap  # noqa: E402

COLOURS = {'red': (230, 30, 30), 'yellow': (255, 230, 0), 'cyan': (0, 230, 230), 'blue': (40, 90, 255),
           'white': (255, 255, 255), 'magenta': (255, 0, 255), 'orange': (255, 140, 0), 'black': (0, 0, 0)}


def mineable_land(m, tile):
    name = m.land_name(tile).lower()
    return 'mountain' in name or 'rock' in name or 'cave' in name


def write_png(path, w, h, pixels):
    raw = b''.join(b'\0' + bytes(c for px in pixels[y * w:(y + 1) * w] for c in px) for y in range(h))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)

    with open(path, 'wb') as fh:
        fh.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
                 chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('out')
    p.add_argument('box', nargs=4, type=int)
    p.add_argument('--scale', type=int, default=4)
    p.add_argument('--route', action='append', default=[])
    p.add_argument('--mark', action='append', default=[])
    p.add_argument('--mineable', action='store_true')
    p.add_argument('--grid', type=int, default=0)
    p.add_argument('--areas', help='a JSON list of areas ({"box": [x1, y1, x2, y2]}) to outline in white')
    a = p.parse_args()

    m = uomap.Map()
    x1, y1, x2, y2 = a.box
    s = a.scale
    w, h = (x2 - x1 + 1) * s, (y2 - y1 + 1) * s
    px = [(0, 0, 0)] * (w * h)

    def fill(tx, ty, colour, inset=0):
        if not (x1 <= tx <= x2 and y1 <= ty <= y2):
            return
        for dy in range(inset, s - inset):
            row = ((ty - y1) * s + dy) * w
            for dx in range(inset, s - inset):
                px[row + (tx - x1) * s + dx] = colour

    for ty in range(y1, y2 + 1):
        for tx in range(x1, x2 + 1):
            tile, z = m.land(tx, ty)
            colour = m.radar_land(tile)
            statics = m.statics(tx, ty)
            if statics:
                top = max(statics, key=lambda st: st[1] + m.static_heights[st[0]])
                colour = m.radar_static(top[0])
            if a.mineable and mineable_land(m, tile) and not statics:
                colour = tuple(min(255, c + 40) for c in colour)
            fill(tx, ty, colour)
            if a.grid and (tx % a.grid == 0 or ty % a.grid == 0):
                for d in range(s):
                    if tx % a.grid == 0:
                        px[((ty - y1) * s + d) * w + (tx - x1) * s] = (90, 90, 90)
                    if ty % a.grid == 0:
                        px[((ty - y1) * s) * w + (tx - x1) * s + d] = (90, 90, 90)

    for path in a.route:
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                r = json.loads(line)
                if 'message' in r:
                    text = r['message'].lower()
                    colour = 'yellow' if 'left the protection' in text else 'cyan' if 'now under the protection' in text else None
                    if colour:
                        for d in range(-1, 2):
                            fill(r['x'] + d, r['y'], COLOURS[colour])
                            fill(r['x'], r['y'] + d, COLOURS[colour])
                else:
                    fill(r['x'], r['y'], COLOURS['red'], inset=max(0, s // 4))

    if a.areas:
        with open(a.areas, encoding='utf-8') as fh:
            for area in json.load(fh):
                bx1, by1, bx2, by2 = area['box']
                for tx in range(bx1, bx2 + 1):
                    for ty in (by1, by2):
                        fill(tx, ty, COLOURS['white'], inset=max(0, s // 3))
                for ty in range(by1, by2 + 1):
                    for tx in (bx1, bx2):
                        fill(tx, ty, COLOURS['white'], inset=max(0, s // 3))

    for mark in a.mark:
        x, y, colour = mark.split(',')
        for d in range(-1, 2):
            fill(int(x) + d, int(y), COLOURS[colour])
            fill(int(x), int(y) + d, COLOURS[colour])

    write_png(a.out, w, h, px)
    print(f'{a.out}: {w}x{h}')


if __name__ == '__main__':
    main()
