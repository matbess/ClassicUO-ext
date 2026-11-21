"""The tower's ground-floor chests (the user, 2026-11-20): what's left to move to the castle after the vault.

  python3 tower_down.py out      castle -> tower (reagents checked, Recall, the front fight, in, parked)
  python3 tower_down.py list     the chests on the ground floor the client knows, nothing sent
  python3 tower_down.py record [SERIAL...]  every item's place in its chest (bags all the way down)
  python3 tower_down.py count    open every ground-floor chest in his areas and write what's in it
  python3 tower_down.py in       tower -> castle (the Castle rune, the castle-front fight, in)
  python3 tower_down.py carry SRC...   (in the tower) every piece of these chests into his pack, in their order,
                                       then to the castle and each piece into its castle chest at its tower spot
  python3 tower_down.py place          (in the castle) put away what carry left in his pack
  python3 tower_down.py gems           (in the castle) the gem bag and its marker from 942 floor to 939 floor

Writes ~/claude/uo-agent-work/castle/tower-down.json: one entry per chest, its place and its bags and loose items
in the Vault page's form.
"""
import json
import re
import os
import sys
import time

import uo
import castle
import castle_site
import castle_move
import inventory
import layout
import look
import restock

WORK = os.path.expanduser('~/claude/uo-agent-work/castle')
OUT = os.path.join(WORK, 'tower-down.json')
LAYOUT = os.path.join(WORK, 'tower-layout.json')  # the exact layout, for putting it back the same in the castle
TOWER = (1750, 1402, 1763, 1413)
GROUND_Z = 25
info = None


class Stop(Exception):
    pass


CARRY = os.path.join(WORK, 'tower-carry.json')  # what's in his pack, where it came from and where it goes
# the user's own chests by the stairs -> the castle's 942 stack, same heights (castle_plan.VAULT[942])
DEST = {'0x4058ABA9': '0x406EE45B', '0x40746D31': '0x406DF442', '0x4074D82B': '0x406F29C0'}
GEMS_FROM, GEMS_TO = '0x406F29C0', '0x406E7AA0'


def say(text):
    line = f"{time.strftime('%H:%M:%S')} {text}"
    print(line, flush=True)
    with open(os.path.join(WORK, 'tower-down.log'), 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def status():
    return uo.call(info, 'GET', '/status')


def chests():
    found = uo.call(info, 'GET', '/nearby', range=18, containers=1)
    items = found.get('items', found) if isinstance(found, dict) else found
    out = []
    for i in items:
        if not i.get('container') or i.get('parent'):
            continue
        x, y, z = i.get('x'), i.get('y'), i.get('z', 0)
        if x is None or not (TOWER[0] <= x <= TOWER[2] and TOWER[1] <= y <= TOWER[3]) or z > GROUND_Z:
            continue
        out.append(i)
    return sorted(out, key=lambda i: (i['x'], i['y'], -i.get('z', 0)))


def place(i):
    x, y = i['x'], i['y']
    if 1750 <= x <= 1753 and 1402 <= y <= 1409:
        return 'by the stairs'
    if 1755 <= x <= 1758 and 1407 <= y <= 1409:
        return 'by the forge'
    return 'bedroom' if y <= 1409 else 'hall'


def allowed(i):
    for a in uo.call(info, 'GET', '/rules').get('areas', []):
        b, z = a['box'], a.get('z', [-128, 127])
        if b[0] <= i['x'] <= b[2] and b[1] <= i['y'] <= b[3] and z[0] <= i.get('z', 0) <= z[1]:
            return True
    return False


def read_carry():
    try:
        return json.load(open(CARRY, encoding='utf-8'))
    except (OSError, ValueError):
        return []


def write_carry(taken):
    with open(CARRY, 'w', encoding='utf-8') as fh:
        json.dump(taken, fh, indent=1)


def pack_room():
    pack = status()['backpack']['serial']
    lines = ' '.join(uo.call(info, 'POST', '/name', serial=pack)[0].get('lines', []))
    m = re.search(r'\((\d+) items?, (\d+) stones?\)', lines)
    st = status()
    return 125 - int(m.group(1)), st['weightMax'] - st['weight']


def piece_size(serial):
    lines = ' '.join(uo.call(info, 'POST', '/name', serial=serial)[0].get('lines', []))
    m = re.search(r'\((\d+) items?, (\d+) stones?\)', lines)
    return (int(m.group(1)) + 1, int(m.group(2)) + 1) if m else None


def carry(sources):
    """In the tower: each source chest's pieces into his pack in the recorded order (a chest only whole), then to
    the castle and into place."""
    recorded = json.load(open(LAYOUT, encoding='utf-8'))
    pack = status()['backpack']['serial']
    taken = read_carry()  # a carry stopped part way: those pieces are in his pack already
    if taken and any(t['src'] not in sources for t in taken):
        sys.exit(f'{CARRY} lists pieces from other chests in his pack: run place first')
    have = {t['serial'] for t in taken}
    for src in sources:
        c = recorded[src]
        items, stones = pack_room()
        now = {i['serial'] for i in look.open_once(info, src)}
        want = [i for i in c['items'] if i['serial'] in now]
        gone = [i['name'] for i in c['items'] if i['serial'] not in now and i['serial'] not in have]
        if gone:
            say(f'{src}: no longer in the chest since the recording: {gone}')
        new = [i['serial'] for i in now - {i['serial'] for i in c['items']}]
        if new:
            raise Stop(f'{src} holds pieces that were not recorded ({new}): record it again first')
        lines = ' '.join(uo.call(info, 'POST', '/name', serial=src)[0].get('lines', []))
        m = re.search(r'\((\d+) items?, (\d+) stones?\)', lines)
        if m and not have and (int(m.group(1)) > items - 2 or int(m.group(2)) > stones - 5):
            say(f'{src} ({m.group(1)} items, {m.group(2)} stones) will not fit with {items} items and {stones} '
                f'stones of room: next trip')
            continue
        for i in want:
            uo.call(info, 'POST', '/move', serial=i['serial'], to=pack)
            taken.append(dict(i, src=src, dest=DEST[src]))
            write_carry(taken)
        say(f"{src}: {len(want)} pieces in his pack")
    if not taken:
        raise Stop('nothing was taken')
    castle.go_in()
    place_all()


def place_all():
    taken = read_carry()
    if not taken:
        say('nothing to put away')
        return
    mover = castle_site.install(uo, info, say)
    if not mover:
        raise Stop('place is done inside the castle')
    look.uo.walk_near = mover.walk_near
    try:
        for dest in dict.fromkeys(p['dest'] for p in taken):
            pieces = sorted((p for p in taken if p['dest'] == dest), key=lambda p: p['order'])
            # only pieces of the same tower chest may be in it already (an earlier trip's part)
            ours = {i['serial'] for c in json.load(open(LAYOUT, encoding='utf-8')).values() for i in c['items']}
            other = [i for i in look.open_once(info, dest) if i['serial'] not in ours]
            if other:
                raise Stop(f'{dest} holds {len(other)} other pieces: nothing goes in on top of them')
            mover.walk_near(info, dest)
            for p in pieces:
                uo.call(info, 'POST', '/move', serial=p['serial'], to=dest, x=p['x'], y=p['y'])
                taken = [t for t in taken if t['serial'] != p['serial']]
                write_carry(taken)
            check(dest, pieces)
    finally:
        mover.close_up()
    say('PLACED: everything from this trip is in its castle chest')


def check(dest, pieces):
    """Open the castle chest again and compare: same spots, same order."""
    uo.call(info, 'POST', '/close', serial=dest)
    items = look.open_once(info, dest)
    at = {i['serial']: i for i in items}
    off = [p['name'] for p in pieces if p['serial'] not in at or (at[p['serial']]['x'], at[p['serial']]['y'])
           != (p['x'], p['y'])]
    order = [i['serial'] for i in items if i['serial'] in {p['serial'] for p in pieces}]
    same_order = order == [p['serial'] for p in pieces]
    say(f"{dest}: {len(pieces) - len(off)} of {len(pieces)} at their tower spots"
        f"{'' if not off else ' (off: ' + ', '.join(off) + ')'}; drawing order "
        f"{'the same' if same_order else 'DIFFERENT'}")


def relay(pairs):
    """In the castle: each SRC chest's pieces into DEST, every piece at its spot and in its order (the drawing order),
    a chest at a time through his pack, then checked. The user's own chests from 942 to 938's secures (2026-11-20)."""
    mover = castle_site.install(uo, info, say)
    if not mover:
        raise Stop('relay is done inside the castle')
    look.uo.walk_near = mover.walk_near
    pack = status()['backpack']['serial']
    for src, dest in pairs:
        before = [p for p in read_carry() if p['src'] == src and p['dest'] == dest]  # a relay stopped part way
        if before:
            record = sorted(before, key=lambda p: p['order'])
            if not look.open_once(info, src) and not look.open_once(info, dest):
                pass
            elif not set(i['serial'] for i in look.open_once(info, dest)) <= {p['serial'] for p in record}:
                raise Stop(f'{dest} holds pieces that are not from {src}')
        else:
            if look.open_once(info, dest):
                raise Stop(f'{dest} is not empty: nothing goes in on top of it')
            pieces = look.open_once(info, src)
            lines = ' '.join(uo.call(info, 'POST', '/name', serial=src)[0].get('lines', []))
            m = re.search(r'\((\d+) items?, (\d+) stones?\)', lines)
            items, stones = pack_room()
            if m and (int(m.group(1)) > items - 2 or int(m.group(2)) > stones - 5):
                raise Stop(f'{src} ({m.group(1)} items, {m.group(2)} stones) will not fit in his pack '
                           f'({items} items, {stones} stones of room)')
            record = [dict(serial=i['serial'], x=i['x'], y=i['y'], order=n, name=i.get('type', ''), src=src, dest=dest)
                      for n, i in enumerate(pieces)]
            write_carry(record)
        still = {i['serial'] for i in look.open_once(info, src)}
        for p in record:
            if p['serial'] in still:
                uo.call(info, 'POST', '/move', serial=p['serial'], to=pack)
        say(f'{src}: {len(record)} pieces in his pack')
        mover.walk_near(info, dest)
        taken = read_carry()
        there = {i['serial'] for i in look.open_once(info, dest)}
        for p in record:
            if p['serial'] in there:
                continue
            uo.call(info, 'POST', '/move', serial=p['serial'], to=dest, x=p['x'], y=p['y'])
            taken = [t for t in taken if t['serial'] != p['serial']]
            write_carry(taken)
        check(dest, record)
    say('RELAY DONE (the table stays as it is: finish.py or castle.py table close puts it back)')


def gems_over():
    """The gem bag and its marker gem from 942 floor to 939 floor, each at the same spot, in the same order."""
    mover = castle_site.install(uo, info, say)
    if not mover:
        raise Stop('gems is done inside the castle')
    look.uo.walk_near = mover.walk_near
    try:
        if look.open_once(info, GEMS_TO):
            raise Stop(f'{GEMS_TO} (939 floor) is not empty')
        items = look.open_once(info, GEMS_FROM)
        if not items:
            say('942 floor is empty already')
            return
        pack = status()['backpack']['serial']
        for i in items:
            uo.call(info, 'POST', '/move', serial=i['serial'], to=pack)
        mover.walk_near(info, GEMS_TO)
        for i in items:
            uo.call(info, 'POST', '/move', serial=i['serial'], to=GEMS_TO, x=i['x'], y=i['y'])
        say(f'{len(items)} pieces from 942 floor to 939 floor')
    finally:
        mover.close_up()


_call = uo.call


def call_past_razor(i, method, endpoint, **params):
    """uo.call, except that a takeover which is Razor's AutoSearch opening a bag as it lands in his pack
    (castle_move.razor_opened checks the click came within a second of its drop) is handed back and the request
    sent again. A real takeover goes on up."""
    for _ in range(4):
        try:
            return _call(i, method, endpoint, **params)
        except uo.TakenOver:
            if not castle_move.razor_opened(params.get('serial')):
                raise
    return _call(i, method, endpoint, **params)


def main():
    global info
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'
    info = uo.find_bridge('Clem')
    castle.info = restock.info = castle_move.info = info
    castle_move.say = say
    uo.call = call_past_razor
    st = status()
    if st.get('takenOver') and castle_move.razor_opened(None):
        st = status()
    if st.get('takenOver') or st.get('halted'):
        sys.exit(f"the user has him ({st.get('takenOver') or st.get('halted')}); only they hand him back")
    if cmd == 'out':
        castle.go_out()
        st = status()
        say(f"in the tower at {st['x']},{st['y']},{st['z']}")
    elif cmd == 'in':
        castle.go_in()
        st = status()
        say(f"in the castle at {st['x']},{st['y']},{st['z']}")
    elif cmd == 'list':
        names = uo.load_names()
        for i in chests():
            print(f"{i['serial']} {i['x']},{i['y']},{i.get('z', 0):<3} {place(i):14} "
                  f"{'ok ' if allowed(i) else 'OUT'} {names.get(i['serial'], i.get('name', ''))}")
    elif cmd == 'carry':
        carry(sys.argv[2:])
    elif cmd == 'place':
        place_all()
    elif cmd == 'gems':
        gems_over()
    elif cmd == 'relay':
        relay([a.split(':') for a in sys.argv[2:]])
    elif cmd == 'record':
        # the exact layout (the user, 2026-11-20: "i want the items placed in the chests exactly the same so when i
        # open the chests it looks the same as it does here in the tower"): every item's x,y in its container, in
        # the order the server lists them (the drawing order), bags opened all the way down
        names = uo.load_names()
        try:
            data = json.load(open(LAYOUT, encoding='utf-8'))
        except (OSError, ValueError):
            data = {}
        want = sys.argv[2:]

        def tree(serial, depth=0):
            try:
                items = look.open_once(info, serial)
            except uo.BridgeError as e:
                # a pouch that never answered (2026-11-20 18:11, inside a backpack in the top chest by the stairs):
                # left unopened; it goes over inside its bag, as it is
                if e.code == 423 and 'no answer when opening' in e.message and depth > 0:
                    uo.call(info, 'POST', '/resume')
                    say(f'{serial} never opened; recorded as unopened')
                    return None
                raise
            out = []
            for n, i in enumerate(items):
                e = {'serial': i['serial'], 'graphic': i['graphic'], 'hue': i.get('hue', 0),
                     'amount': i.get('amount', 1), 'x': i['x'], 'y': i['y'], 'order': n,
                     'name': names.get(i['serial'], i.get('type', ''))}
                if layout.is_bag(i) and depth < 4:
                    e['items'] = tree(i['serial'], depth + 1)
                out.append(e)
            return out

        for i in chests():
            if want and i['serial'] not in want:
                continue
            if not allowed(i):
                say(f"{i['serial']} at {i['x']},{i['y']},{i.get('z', 0)} ({place(i)}): outside his areas, skipped")
                continue
            items = tree(i['serial'])
            data[i['serial']] = {'serial': i['serial'], 'x': i['x'], 'y': i['y'], 'z': i.get('z', 0),
                                 'hue': i.get('hue', 0), 'place': place(i),
                                 'recorded': time.strftime('%Y-%m-%d %H:%M'), 'items': items}
            with open(LAYOUT, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=1)
            say(f"{i['serial']} {place(i)} {i['x']},{i['y']},{i.get('z', 0)}: {len(items)} pieces recorded")
        say(f'RECORD DONE: {len(data)} chests in {LAYOUT}')
    elif cmd == 'count':
        labels, names = uo.load_labels(), uo.load_names()
        try:
            data = json.load(open(OUT, encoding='utf-8'))
        except (OSError, ValueError):
            data = {}
        for i in chests():
            if not allowed(i):
                say(f"{i['serial']} at {i['x']},{i['y']},{i.get('z', 0)} ({place(i)}): outside his areas, skipped")
                continue
            items = look.open_once(info, i['serial'])
            bags, loose = inventory.bag_entries(items, labels, names, lambda s: look.open_once(info, s))
            data[i['serial']] = {'serial': i['serial'], 'x': i['x'], 'y': i['y'], 'z': i.get('z', 0),
                                 'place': place(i), 'name': labels.get(i['serial'], ''),
                                 'bags': bags, 'loose': loose}
            say(f"{i['serial']} {place(i)} {i['x']},{i['y']},{i.get('z', 0)}: {len(bags)} bags, {len(loose)} loose")
            with open(OUT, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=1)
        say(f'COUNT DONE: {len(data)} chests')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    look.uo = uo
    try:
        main()
    except (castle.Stop, Stop) as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
