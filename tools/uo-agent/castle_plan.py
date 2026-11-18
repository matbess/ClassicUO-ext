#!/usr/bin/env python3
"""The Castle's storage plan as data: what each chest is for, which ones are secure, and the labels that come from it
(CASTLE.md; the page "Castle Storage Plan", castle/plan.html, shows the same plan). The user approved it on
2026-11-18 ("yes, you can start").

  python3 -I castle_plan.py show      every chest: where, what for, secure or not
  python3 -I castle_plan.py labels    write a "castle: ..." label for every chest into labels.json (nothing is sent)
  python3 -I castle_plan.py secures   the chests to make secure, in order

The chests' serials and spots are in castle/chests.json (recorded 2026-11-18). Each tile holds a stack of 4 chests,
z 18 (top), 14, 10 and 6 (the floor). East storage is the east wall (x 947), west storage the west wall (x 921), the
same plan tile for tile. Labels read "castle: <what> (<place>, <row>)", and "[secure]" on the secure ones. A chest
with no job yet is "free".
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import uo  # noqa: E402

CHESTS = os.path.join(HERE, 'castle', 'chests.json')
ROWS = {18: 'top', 14: '2nd', 10: '3rd', 6: 'floor'}
Z = [18, 14, 10, 6]
FREE = 'free'

# (what, secure) for each row of a tile, top to bottom; the walls run north (y 2329) to south (y 2343)
WALL = {
    2329: [('swords', 0), ('axes', 0), ('maces & staves', 0), ('spare backpacks', 0)],
    2330: [('polearms', 0), ('fencing', 0), ('archery', 0), (FREE, 0)],
    2331: [('attack wands', 1), ('healing wands', 1), ('jewellery', 1), ('magic clothing', 1)],
    2332: [('plate', 0), ('helms', 0), ('chain & ring + coifs', 0), ('leather + caps', 0)],
    2333: [('studded', 0), ('shields', 0), ('GM armour sets', 1), ('plain gear', 0)],
    2334: [('best weapons', 1), ('best armour', 1), ('treasure maps', 1), (FREE, 0)],
    2335: [('deeds 1', 1), ('deeds 2', 1), ('deeds 3', 1), (FREE, 0)],
    2336: [('scrolls, circles 1-4', 0), ('scrolls, circles 5-8', 0), ('reagents', 1), (FREE, 0)],
    2337: [('gems', 1), ('miscellaneous', 0), ('supplies & ID wands', 0), ('needs your decision', 0)],
    2338: [(FREE, 0)] * 4,
    2339: [('heal potions 1', 0), ('heal potions 2', 0), ('cure potions 1', 0), ('cure potions 2', 0)],
    2340: [('refresh potions 1', 0), ('refresh potions 2', 0), ('agility potions 1', 0), ('agility potions 2', 0)],
    2341: [('strength potions 1', 0), ('strength potions 2', 0), ('poison potions 1', 0), ('poison potions 2', 0)],
    2342: [('poison potions 3', 0), ('explosion potions 1', 0), ('explosion potions 2', 0), (FREE, 0)],
    2343: [(FREE, 0)] * 4,
}
# the forge corner (x 944): crafting and leveling
FORGE = {
    2322: [('smelting 1', 0), ('smelting 2', 0), ('smelting 3', 0), ('smelting 4', 0)],
    2326: [('ingots', 0), ('boards & logs', 0), ('cloth & leather', 0), ('tools', 0)],
    2327: [('cooking', 0), (FREE, 0), (FREE, 0), (FREE, 0)],
}
# the user's vault (south-east, behind their table, y 2348): no weight limit, no secures needed
VAULT = {
    938: [('ingots', 0)] * 4,
    939: [('boards', 0), ('boards', 0), ('logs', 0), (FREE, 0)],
    940: [('reagents', 0), ('reagents', 0), ('scrolls', 0), (FREE, 0)],
    941: [('gold', 0)] * 4,
    942: [('valuables overflow', 0), ('valuables overflow', 0), (FREE, 0), (FREE, 0)],
}
# the friend's vault (south-west, y 2348): never touched, except securing the 8 at the west end (x 928 and 929; the
# user, 2026-11-18: "yes, Clem can secure those 8 chests")
FRIEND_SECURE = (928, 929)


def plan():
    """{serial: {x, y, z, place, row, what, secure, side}} for all 180 chests."""
    chests = json.load(open(CHESTS))
    out = {}
    for serial, c in chests.items():
        x, y, z = c['x'], c['y'], c['z']
        row = ROWS.get(z)
        i = Z.index(z) if z in Z else None
        e = dict(c, row=row)
        if x == 947 and y in WALL:
            e.update(side='east', place=f'east {y}', what=WALL[y][i][0], secure=bool(WALL[y][i][1]))
        elif x == 921 and y in WALL:
            # the west wall: the same plan; its secures wait until the west wall takes overflow of those kinds
            e.update(side='west', place=f'west {y}', what=WALL[y][i][0], secure=False)
        elif x == 944 and y in FORGE:
            e.update(side='forge', place=f'forge {y}', what=FORGE[y][i][0], secure=False)
        elif y == 2348 and x in VAULT:
            e.update(side='vault', place=f'my vault {x}', what=VAULT[x][i][0], secure=False)
        elif y == 2348 and 928 <= x <= 933:
            e.update(side='friend', place=f'his vault {x}', what="friend's", secure=x in FRIEND_SECURE)
        elif (x, y) in ((938, 2349), (938, 2350)):
            e.update(side='east', place=f'intake {x},{y}', what='intake (east)', secure=False, row='floor')
        elif (x, y) in ((933, 2349), (933, 2350)):
            e.update(side='west', place=f'intake {x},{y}', what='intake (west)', secure=False, row='floor')
        else:
            e.update(side='?', place=f'{x},{y}', what='?', secure=False)
        out[serial] = e
    return out


def label(e):
    return f"castle: {e['what']} ({e['place']}, {e['row']})" + (' [secure]' if e['secure'] else '')


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'show'
    p = plan()
    order = sorted(p.items(), key=lambda kv: (kv[1]['side'], kv[1]['x'], kv[1]['y'], -kv[1]['z']))
    if cmd == 'show':
        for s, e in order:
            print(s, label(e))
    elif cmd == 'secures':
        for s, e in order:
            if e['secure']:
                print(s, label(e))
        print(sum(e['secure'] for e in p.values()), 'secure chests')
    elif cmd == 'labels':
        labels = uo.load_labels()
        unknown = [s for s, e in p.items() if e['what'] == '?']
        if unknown:
            sys.exit(f'chests not in the plan: {unknown}')
        labels.update({s: label(e) for s, e in p.items()})
        uo.write_json(uo.LABELS, labels, 2)
        print(f'{len(p)} castle labels written')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
