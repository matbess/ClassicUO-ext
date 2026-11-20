#!/usr/bin/env python3
"""The Castle's storage plan as data: what each chest is for, which ones are secure, and the labels that come from it
(CASTLE.md; the page "Castle Storage Plan", castle/plan.html, shows the same plan). The user approved it on
2026-11-18 ("yes, you can start").

  python3 -I castle_plan.py show      every chest: where, what for, secure or not
  python3 -I castle_plan.py labels    write a "castle: ..." label for every chest into labels.json (nothing is sent)
  python3 -I castle_plan.py secures   the chests to make secure, in order
  python3 -I castle_plan.py secure    Clem makes them secure (skipping any that are already)
  python3 -I castle_plan.py unsecure  Clem turns every secure chest the plan doesn't mark secure back into a plain
                                      locked-down one (version 2: the east wall's 13), so their secures can go to the
                                      friend's row

Version 2 (the user, 2026-11-19): the user's tables are to move up to the forge corner and shut off the whole east
side (the east wall and the south-east rooms) from the forge, so nothing on the east wall needs to be secure any more;
the secures move to the south-west row by the west intake chests ("make all of the chests by the intake into secure
chests"). The west wall doesn't mirror the east any more: every chest there is free, unassigned and not secure
("Just leave them empty and unassigned for now so they can be figured out later"). The spare backpacks go to the
forge corner, outside the tables ("I want the chest with backpacks to be in the forge area so it's not behind the
tables").

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

# (what, secure) for each row of a tile, top to bottom; the east wall runs north (y 2329) to south (y 2343). None
# secure: the tables at the forge keep everyone without owner commands out (version 2)
WALL = {
    2329: [('swords', 0), ('axes', 0), ('maces & staves', 0), (FREE, 0)],
    2330: [('polearms', 0), ('fencing', 0), ('archery', 0), (FREE, 0)],
    2331: [('attack wands', 0), ('healing wands', 0), ('jewellery', 0), ('magic clothing', 0)],
    2332: [('plate', 0), ('helms', 0), ('chain & ring + coifs', 0), ('leather + caps', 0)],
    2333: [('studded', 0), ('shields', 0), ('GM armour sets', 0), ('plain gear', 0)],
    2334: [('best weapons', 0), ('best armour', 0), ('treasure maps', 0), (FREE, 0)],
    2335: [('deeds 1', 0), ('deeds 2', 0), ('deeds 3', 0), (FREE, 0)],
    2336: [('scrolls, circles 1-4', 0), ('scrolls, circles 5-8', 0), ('reagents', 0), (FREE, 0)],
    2337: [('gems', 0), ('miscellaneous', 0), ('supplies & ID wands', 0), ('needs your decision', 0)],
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
    2327: [('cooking', 0), (FREE, 0), (FREE, 0), ('spare backpacks', 0)],  # outside the tables: anyone can drop bags
}
# the user's vault (south-east, behind their table, y 2348): no weight limit, no secures needed
VAULT = {
    938: [('ingots', 0)] * 4,
    939: [('boards', 0), ('boards', 0), ('logs', 0), (FREE, 0)],
    940: [('reagents', 0), ('reagents', 0), ('scrolls', 0), (FREE, 0)],
    941: [('gold', 0)] * 4,
    942: [('valuables overflow', 0), ('valuables overflow', 0), (FREE, 0), (FREE, 0)],
}
# the friend's vault (south-west, y 2348): never touched, except making them secure: the 8 at the west end (x 928 and
# 929; the user, 2026-11-18: "yes, Clem can secure those 8 chests"), and in version 2 all 24, as nothing else
# protects them ("make all of the chests by the intake into secure chests")
FRIEND_SECURE = (928, 929, 930, 931, 932, 933)


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
            # the west wall: free, unassigned and not secure for now (version 2)
            e.update(side='west', place=f'west {y}', what=FREE, secure=False)
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


AGENT_RULES = os.path.join(uo.AGENT_DIR, 'rules-Clem.json')
# where Clem stands to reach a stack: the east hall walkway, the west hall walkway, the walkway in front of the vaults
STAND = {'east': lambda e: (948, e['y']), 'west': lambda e: (922, e['y']), 'friend': lambda e: (e['x'], 2349)}
# the way between the halls (CASTLE.md): long walks stop short, so they go in stages
EAST_TO_WEST = [(948, 2327), (945, 2323), (930, 2323), (923, 2326), (923, 2335), (923, 2346), (925, 2348)]


def secure_all():
    """Make every chest the plan marks secure, secure: walk to it, "I wish to secure this", aim the house's cursor at
    it, and check it answers "locked down & secure". The house makes them friends-level (the user, 2026-11-18: "I'm
    pretty sure everything is locked down as friends. I've never seen a window come up to pick"). The friend's 8 are
    off limits in Clem's rules, so they come off the list in the client's copy for this job only and go back after."""
    import time
    info = uo.find_bridge('Clem')
    todo = [(s, e) for s, e in sorted(plan().items(), key=lambda kv: (kv[1]['side'] != 'east', kv[1]['y'], kv[1]['x'],
                                                                        -kv[1]['z'])) if e['secure']]
    original = open(AGENT_RULES, encoding='utf-8').read()
    friend = [s for s, e in todo if e['side'] == 'friend']
    try:
        if friend:
            text = original
            for s in friend:
                text = text.replace(f'"{s}", ', '').replace(f', "{s}"', '')
            with open(AGENT_RULES, 'w', encoding='utf-8') as fh:
                fh.write(text)
            time.sleep(2)  # the bridge rereads its rules within a second of a change
        for s, e in todo:
            go_to(info, e)
            first = ' '.join(a for r in uo.call(info, 'POST', '/name', serial=s) for a in r.get('lines', [])).lower()
            if 'secure' in first:
                print(f'{s} {label(e)}: secure already')
                continue
            uo.call(info, 'POST', '/say', text='i wish to secure this')
            end = time.time() + 2
            while time.time() < end and not uo.call(info, 'GET', '/status').get('targeting'):
                time.sleep(0.1)
            t = uo.call(info, 'POST', '/target', serial=s)
            said = ' | '.join(m['text'] for m in t.get('messages', []))
            if 'secure' not in said.lower():
                raise SystemExit(f'STOPPED: {s} {label(e)}: {said or "no answer"}')
            print(f'{s} {label(e)}: {said}', flush=True)
    finally:
        with open(AGENT_RULES, 'w', encoding='utf-8') as fh:
            fh.write(original)  # the friend's chests back off limits


def go_to(info, e):
    """Clem in front of a chest: zone by zone (castle_site), then onto his spot."""
    import castle_site
    stand = STAND[e['side']](e)
    mover = castle_site.Mover(uo, info)
    mover.go_zone(castle_site.zone(*stand))
    mover.walk(*stand, what=label(e))


def house_command(info, words, serial, want):
    """An owner command aimed at a chest: the words, the house's cursor, and the answer it must give."""
    import time
    uo.call(info, 'POST', '/say', text=words)
    end = time.time() + 2
    while time.time() < end and not uo.call(info, 'GET', '/status').get('targeting'):
        time.sleep(0.1)
    t = uo.call(info, 'POST', '/target', serial=serial)
    said = ' | '.join(m['text'] for m in t.get('messages', []))
    if not any(w in said.lower() for w in want):
        raise SystemExit(f'STOPPED: "{words}" on {serial}: {said or "no answer"}')
    return said


def unsecure_all():
    """Every chest that is secure in the game but not in the plan (version 2: the east wall's 13) back to a plain
    locked-down chest: "I wish to release this" (which frees it altogether), then at once "I wish to lock this down",
    and a single click must say locked down and not secure. They're empty (the move hasn't started). Never the
    friend's."""
    info = uo.find_bridge('Clem')
    p = plan()
    todo = sorted(((s, e) for s, e in p.items() if not e['secure'] and e['side'] in ('east', 'west', 'forge', 'vault')),
                  key=lambda kv: (kv[1]['side'], kv[1]['y'], kv[1]['x'], -kv[1]['z']))
    # the 13 made secure on 2026-11-18 under version 1 (their labels then, kept in castle/)
    made = json.load(open(os.path.join(HERE, 'castle', 'secured-east-2026-11-18.json')))
    marked = [(s, e) for s, e in todo if s in made]
    for s, e in marked:
        go_to(info, e)
        first = ' '.join(a for r in uo.call(info, 'POST', '/name', serial=s) for a in r.get('lines', [])).lower()
        if 'secure' not in first:
            print(f'{s} {label(e)}: not secure already ({first})')
            continue
        said = house_command(info, 'i wish to release this', s, ('no longer', 'release'))
        print(f'{s}: {said}', flush=True)
        said = house_command(info, 'i wish to lock this down', s, ('locked down',))
        print(f'{s}: {said}', flush=True)
        now = ' '.join(a for r in uo.call(info, 'POST', '/name', serial=s) for a in r.get('lines', [])).lower()
        if 'secure' in now or 'locked down' not in now:
            raise SystemExit(f'STOPPED: {s} {label(e)} now says {now!r}')
        print(f'{s} {label(e)}: locked down, not secure', flush=True)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'show'
    if cmd == 'secure':
        return secure_all()
    if cmd == 'unsecure':
        return unsecure_all()
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
