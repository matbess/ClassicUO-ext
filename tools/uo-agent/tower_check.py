"""The tower emptied? Every container on its ground and second floors opened and listed (the user, 2026-11-21: "go to
the tower and inventory the entire first and second floors and make sure everything is empty"). Nothing is moved.

  python3 tower_check.py ground     from the castle or the tower: the ground floor's chests (by the stairs, the
                                    bedroom through its door, by the forge), then parked in the safe zone
  python3 tower_check.py second     the second floor: the bag room, then the vault (gems.py's way in and out, its
                                    door ending locked and closed), then down and parked
  python3 tower_check.py report     what was found, from the file

Writes ~/claude/uo-agent-work/castle/tower-check.json: per container its place, its "(N items, M stones)" and what's
inside (top level).
"""
import json
import os
import subprocess
import sys
import time

import uo
import castle
import castle_move
import look
import restock
import tower_down as td
import friend_chest as fc

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.expanduser('~/claude/uo-agent-work/castle/tower-check.json')
TOWER = (1745, 1400, 1765, 1414)
CONTAINER_GRAPHICS = None
info = None


def say(text):
    td.say(text)


def load():
    try:
        return json.load(open(OUT))
    except (OSError, ValueError):
        return {}


def save(data):
    json.dump(data, open(OUT, 'w'), indent=1)


def containers(z1, z2):
    found = uo.call(info, 'GET', '/nearby', range=18, containers=1)
    items = found.get('items', found) if isinstance(found, dict) else found
    return sorted([i for i in items if i.get('container') and not i.get('parent') and i.get('x') is not None
                   and TOWER[0] <= i['x'] <= TOWER[2] and TOWER[1] <= i['y'] <= TOWER[3] and z1 <= i.get('z', 0) <= z2],
                  key=lambda i: (i['x'], i['y'], -i.get('z', 0)))


def place(i):
    x, y, z = i['x'], i['y'], i.get('z', 0)
    if z <= 25:
        return td.place(i)
    if x <= 1756:
        return 'bag room (2nd floor)'
    return 'vault (2nd floor)'


def check(i, data):
    s = i['serial']
    if s in data and data[s].get('checked'):
        return
    lines = ' '.join(a for r in uo.call(info, 'POST', '/name', serial=s) for a in r.get('lines', []))
    try:
        items = look.open_once(info, s)
        inside = [f"{x.get('type') or x['graphic']}{' x' + str(x['amount']) if x.get('amount', 1) > 1 else ''}"
                  for x in items]
        err = None
    except KeyError:  # opened, but no container window came (the vault's key ring on the bag room wall)
        inside, err = None, 'opened, but no container window (not a container to look in)'
    except uo.BridgeError as e:
        inside, err = None, str(e)
        if e.code == 423 and 'no answer' in e.message:
            uo.call(info, 'POST', '/resume')
    data[s] = {'serial': s, 'graphic': i['graphic'], 'x': i['x'], 'y': i['y'], 'z': i.get('z', 0), 'place': place(i),
               'label': lines, 'inside': inside, 'error': err, 'checked': time.strftime('%H:%M:%S')}
    save(data)
    say(f"{s} {place(i)} {i['x']},{i['y']},{i.get('z', 0)}: "
        + (f"ERROR {err}" if err else ('empty' if not inside else f"{len(inside)}: {', '.join(inside)}")))


def ground():
    data = load()
    st = uo.call(info, 'GET', '/status')
    if not (TOWER[0] <= st['x'] <= TOWER[2] and TOWER[1] <= st['y'] <= TOWER[3]):
        castle.go_out()
    if st.get('z', 6) > 25:
        import trips
        trips.info = info
        trips.go_floor(1)
    cs = containers(0, 25)
    say(f'the ground floor: {len(cs)} containers')
    outside = [i for i in cs if td.place(i) != 'bedroom']
    bedroom = [i for i in cs if td.place(i) == 'bedroom']
    fc.out_of_bedroom()
    for i in outside:
        check(i, data)
    if bedroom:
        fc.into_bedroom()
        for i in bedroom:
            check(i, data)
        fc.out_of_bedroom()
    import trips
    trips.info = info
    trips.park()
    report('ground')


def second():
    data = load()
    gems = os.path.join(HERE, 'gems.py')
    env = dict(os.environ, UO_CHAR='Clem')
    import carto
    import trips
    carto.info = trips.info = info
    trips.go_floor(2)
    room = [i for i in containers(26, 45) if i['x'] <= 1756]
    say(f'the bag room: {len(room)} containers')
    for i in room:
        carto.walk(i['x'], i['y'], 1)
        check(i, data)
    r = subprocess.run([sys.executable, '-I', gems, 'vault-in'], env=env)
    if r.returncode:
        raise td.Stop('into the vault failed (gems.py vault-in)')
    try:
        vault = [i for i in containers(26, 45) if i['x'] >= 1757]
        say(f'the vault: {len(vault)} containers')
        for i in vault:
            check(i, data)
    finally:
        r = subprocess.run([sys.executable, '-I', gems, 'vault-home'], env=env)
        if r.returncode:
            raise td.Stop('out of the vault failed (gems.py vault-home): check the vault door')
    report('second')


def report(which=None):
    data = load()
    for floor, test in (('ground', lambda e: e['z'] <= 25), ('second', lambda e: e['z'] > 25)):
        if which and which != floor:
            continue
        es = sorted((e for e in data.values() if test(e)), key=lambda e: (e['place'], e['x'], e['y'], -e['z']))
        full = [e for e in es if e['inside'] or e['error']]
        print(f'{floor} floor: {len(es)} containers checked, {len(es) - len(full)} empty, {len(full)} not')
        for e in full:
            print(f"   {e['serial']} {e['place']} {e['x']},{e['y']},{e['z']} {e['label']}: "
                  + (e['error'] or ', '.join(e['inside'])))


def main():
    global info
    info = uo.find_bridge('Clem')
    td.info = fc.info = castle.info = restock.info = castle_move.info = info
    castle_move.say = say
    uo.call = td.call_past_razor
    look.uo = uo
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'report'
    {'ground': ground, 'second': second, 'report': report}[cmd]()


if __name__ == '__main__':
    main()
