#!/usr/bin/env python3
"""The move from the tower vault to the castle (CASTLE.md, "The move"): Clem carries everything over, trip by trip,
and puts it in its castle chest (castle_plan.py) as it lay in the tower: each bag whole with its marker under it, at
the same spot in the chest, loose things too. The user, 2026-11-19: "you will take him there and do all this stuff
and move everything over too".

  python3 -I castle_move.py show        read only: what's left in the tower and where each thing goes
  python3 -I castle_move.py trip        one trip: to the tower vault, load what he can carry, to the castle, put it
                                        all away; he ends inside the castle
  python3 -I castle_move.py run         trips until the tower vault is empty (stops at the first problem)
  python3 -I castle_move.py unload      only the putting away (he's in the castle with a load: a trip that stopped)

A trip:
1. From the castle: castle.py out (reagents checked; Recall to the tower, fight.py at the tower front, in and
   parked); his reagents topped up on the ground floor (restock.py); into the vault (gems.py: the vault door locked
   and closed behind him).
2. Load: the tower's containers in ORDER, each opened; bags (with their markers) and loose things into his pack
   until it holds what he can carry (WEIGHT_LEFT stones short of his most). Every piece is written down with where
   it lay (castle/move-load.json in the work folder), so a trip that stops can be put away later (`unload`).
3. Recall to the castle from the vault (castle.py in: the castle-front fight, the front door, the rune box, the
   central door).
4. Unload: each piece to its castle chest (TARGET, castle_site.targets: east storage, the forge, the user's vault;
   the user's table opened on the way and locked down again at the end), at the spot it had in the tower, the
   chest's room checked first (125 items; a secure 395 stones). Each chest's map (layout.json) is recorded.

Kept as they are: the bags' labels ("bag: plate legs (plate chest)"), their markers, everything inside them. The
best weapons and armour aren't split out of their bags on the way (castle_plan.py's "best weapons" and "best
armour" chests stay empty until the user says).
Logs to ~/claude/uo-agent-work/castle/move.log. If the user takes him over, it stops at once.
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import uo  # noqa: E402
import castle  # noqa: E402
import castle_site  # noqa: E402
import layout  # noqa: E402
import restock  # noqa: E402

WORK = os.path.expanduser('~/claude/uo-agent-work/castle')
LOG = os.path.join(WORK, 'move.log')
LOAD = os.path.join(WORK, 'move-load.json')
WEIGHT_LEFT = 25   # stones kept free: he still has to move, fight and cast
SIDE = 'east'

# the tower's containers, in the order they're carried (supplies first: the ID wands' spares pouch is needed to sort
# in the castle), by their labels' start
ORDER = ['chest: supplies', 'chest: needs your decision', 'chest: GM armour sets', 'chest: jewellery',
         'chest: magic clothing', 'chest: magic wands', 'chest: gems', 'chest: reagents', 'chest: scrolls',
         'chest: miscellaneous', 'chest: swords', 'chest: axes', 'chest: maces & staves', 'chest: polearms',
         'chest: fencing', 'chest: archery', 'chest: plate', 'chest: chain & ring', 'chest: leather', 'chest: studded',
         'chest: spare', 'chest: helms', 'chest: bone armour', 'chest: plain gear',
         'potions: heal', 'potions: cure', 'potions: refresh', 'potions: agility', 'potions: strength',
         'potions: poison', 'potions: explosion', 'new backpacks',
         'smelting 1', 'smelting 2', 'smelting 3', 'smelting 4', 'smelting 5', 'smelting 6']
# tower chest name -> castle kind (castle_site.targets); bags whose kind has a home of its own override it (BAG_TARGET)
CHEST_TARGET = {'chain & ring + coifs': 'chain & ring + coifs', 'spare + invulnerability shields': 'shields',
                'bone armour': 'best armour', 'supplies & ID wands': 'supplies & ID wands', 'new backpacks':
                'spare backpacks', 'magic wands': 'attack wands', 'scrolls': 'scrolls, circles 1-4'}
BAG_TARGET = {'attack wands': 'attack wands', 'healing wands': 'healing wands', 'treasure maps': 'treasure maps',
              'gems': 'gems'}
for n in range(1, 9):
    BAG_TARGET[f'circle {n} scrolls'] = 'scrolls, circles 1-4' if n <= 4 else 'scrolls, circles 5-8'

info = None


class Stop(Exception):
    pass


def say(text):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + text
    print(line, flush=True)
    os.makedirs(WORK, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def call(method, endpoint, **params):
    try:
        return uo.call(info, method, endpoint, **params)
    except uo.BridgeError as e:
        if e.code == 423:
            raise Stop(f'the user took over or the bridge stopped: {e.message}')
        raise


def status():
    return call('GET', '/status')


def label_kind(text):
    """'chest: plate (col 3, top)' -> 'plate'; 'potions: heal' -> 'heal potions'; 'smelting 3 (crate ...)' ->
    'smelting'; 'bag: plate legs (plate chest)' -> 'plate legs'."""
    if text.startswith('potions: '):
        return f'{text[9:].split(" (")[0]} potions'
    if text.startswith('smelting '):
        return 'smelting'
    for p in ('chest: ', 'bag: '):
        if text.startswith(p):
            return text[len(p):].split(' (')[0]
    return text.split(' (')[0]


def towers():
    """The tower's containers in ORDER: [(serial, label)]."""
    labels = uo.load_labels()
    out = []
    for start in ORDER:
        out += sorted((s, t) for s, t in labels.items() if t.startswith(start) and s not in {x for x, _ in out})
    return out


def target_of(container_label, bag_label=None):
    if bag_label:
        k = label_kind(bag_label)
        if k in BAG_TARGET:
            return BAG_TARGET[k]
    k = label_kind(container_label)
    return CHEST_TARGET.get(k, k)


def open_items(serial):
    uo.walk_near(info, serial)
    r = call('POST', '/open', serial=serial)
    call('POST', '/close', serial=serial)
    if not r.get('opened'):
        raise Stop(f'{serial} did not open')
    return r['contents']['items']


def weight_of(serial):
    """A container's weight from its single click "(N items, M stones)": (items, stones), or None."""
    lines = ' '.join(a for r in call('POST', '/name', serial=serial) for a in r.get('lines', []))
    m = re.search(r'\((\d+) items?, (\d+) stones?\)', lines)
    return (int(m.group(1)), int(m.group(2))) if m else None


def guess_stones(item):
    return castle_site.stones(item)


# ---- loading in the tower vault ----

def load():
    """Fill his pack from the tower's containers, in ORDER. Returns the pieces taken (also written to LOAD)."""
    labels = uo.load_labels()
    pack = status()['backpack']['serial']
    taken = read_load()
    for serial, text in towers():
        items = open_items(serial)
        if not items:
            continue
        pairs, loose = layout.pair(items, unmarked={s for s, t in labels.items() if not t.startswith('bag: ')})
        groups = []  # (pieces, stones): a bag and its marker go together
        for bag, marker in pairs:
            w = weight_of(bag['serial'])
            pieces = [dict(bag, role='bag', count=(w[0] if w else 0) + 1)] + \
                ([dict(marker, role='marker', count=1)] if marker else [])
            groups.append((pieces, (w[1] if w else 10) + (guess_stones(marker) if marker else 0)))
        for i in loose:
            groups.append(([dict(i, role='loose', count=1)], guess_stones(i)))
        for pieces, stones in groups:
            st = status()
            room = st['weightMax'] - st['weight'] - WEIGHT_LEFT
            known = pieces[0]['role'] == 'bag'  # a bag says what it weighs; a loose thing is weighed by lifting it
            if known and stones > room:
                say(f'his pack is full ({st["weight"]}/{st["weightMax"]} stones): this load is done')
                return taken
            bag_label = labels.get(pieces[0]['serial']) if pieces[0]['role'] == 'bag' else None
            what = target_of(text, bag_label)
            before = st['weight']
            for p in pieces:
                r = uo.move(info, p['serial'], pack)
                said = ' '.join(m['text'] for m in r.get('messages', [])).lower()
                if not r.get('moved') and 'cannot hold more weight' in said:
                    # too heavy for his pack all at once (1954 lockpicks, 2026-11-19): the part that fits, the rest
                    # on a later trip. A pile split keeps its serial on the part moved; the rest gets a new one.
                    amount = p.get('amount', 1)
                    part = amount // 2
                    while part >= 1 and not r.get('moved'):
                        r = uo.move(info, p['serial'], pack, amount=part)
                        part //= 2
                    if not r.get('moved'):
                        say(f"his pack takes no more ({status()['weight']} stones): this load is done")
                        return taken
                    p['amount'] = part * 2
                    say(f"{p['type']}: {p['amount']} of {amount} this trip, the rest next time")
                if not r.get('moved'):
                    raise Stop(f"{p['serial']} {p['type']} did not come out of {text}: {r}")
            after = status()
            if after['weight'] > after['weightMax'] - WEIGHT_LEFT:  # too much after all: back where it lay
                for p in pieces:
                    uo.move(info, p['serial'], serial, p['x'], p['y'])
                say(f'his pack is full ({before}/{after["weightMax"]} stones; {pieces[0]["type"]} would make it '
                    f'{after["weight"]}): this load is done')
                return taken
            stones = after['weight'] - before
            for p in pieces:
                taken.append({'serial': p['serial'], 'type': p['type'], 'role': p['role'], 'from': text,
                              'x': p['x'], 'y': p['y'], 'what': what, 'count': p['count'],
                              'stones': stones if p is pieces[0] else 0, 'amount': p.get('amount', 1),
                              'graphic': p['graphic'], 'crate': not text.startswith('chest: ')})
                write_load(taken)
            say(f"{labels.get(pieces[0]['serial'], pieces[0]['type'])}"
                f"{' + its marker' if len(pieces) > 1 else ''} from {text} -> for {what}")
    say('the tower vault is empty')
    return taken


def read_load():
    try:
        with open(LOAD, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


def write_load(taken):
    os.makedirs(WORK, exist_ok=True)
    tmp = LOAD + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(taken, fh, indent=1)
    os.replace(tmp, LOAD)


# ---- unloading in the castle ----

def unload():
    """Every piece written down in LOAD to its castle chest, at its tower spot; a marker into the chest its bag went
    to. The user's table opened when the way goes behind it, closed at the end."""
    taken = read_load()
    if not taken:
        say('nothing to put away')
        return
    mover = castle_site.Mover(uo, info, say)
    original = uo.walk_near
    uo.walk_near = mover.walk_near
    room = castle_site.Room(uo, info)
    touched = []
    try:
        chest_of_bag = None
        for p in list(taken):
            here = call('GET', '/item', serial=p['serial'])
            inside = [i['serial'] for i in here.get('insideOf', [])]
            pack = status()['backpack']['serial']
            if pack not in inside:
                say(f"{p['serial']} {p['type']} isn't in his pack any more: skipped")
                taken.remove(p)
                write_load(taken)
                continue
            if p['role'] == 'marker' and chest_of_bag:
                c = chest_of_bag
            else:
                c = room.pick(p['what'], SIDE, p['count'], p['stones'] if castle_site.is_secure_kind(p['what']) else 0)
                if c is None:
                    raise Stop(f"no castle chest has room for {p['type']} ({p['what']}): TELL THE USER")
            x, y = (None, None) if p['crate'] else (p['x'], p['y'])
            r = uo.move(info, p['serial'], c, x, y)
            if not r.get('moved'):
                raise Stop(f"{p['serial']} {p['type']} did not go into {c}: {r}")
            if castle_site.is_secure(c):
                room.read(c)
            else:
                room.added(c, p['count'], p['stones'])
            if p['role'] == 'bag':
                chest_of_bag = c
            elif p['role'] == 'loose':
                chest_of_bag = None
            if c not in touched:
                touched.append(c)
            say(f"{uo.load_labels().get(p['serial'], p['type'])} -> {castle_site.chest_title(c, uo.load_labels())}")
            taken.remove(p)
            write_load(taken)
        for c in touched:  # the chest map, from what the client now knows (nothing sent)
            layout.record(c, call('GET', '/contents', serial=c)['items'])
    finally:
        try:
            mover.close_up()
        finally:
            uo.walk_near = original
    say('all put away')


# ---- the trip ----

def to_vault():
    """From inside the castle (or the tower) into the tower vault, the door locked and closed behind him."""
    import gems
    import fight
    import trips
    import carto
    import door
    st = status()
    gems.info = trips.info = carto.info = door.info = restock.info = info
    if castle.inside((st['x'], st['y'])):
        castle.go_out()  # reagents checked, Recall, the tower-front fight, in and parked
    fight.setup(info)
    st = status()
    if 1714 <= st['x'] <= 1830 and 1414 <= st['y'] <= 1485 and st['y'] > 1413:
        # outside the tower (a trip restarted mid-fight): the tower-front fight, then in
        fight.use_place(fight.TOWER_FRONT)
        try:
            fight.Fight(10, front=True).run()
        except fight.Stop as e:
            raise Stop(f'at the tower front: {e}')
        st = status()
    if not (1745 <= st['x'] <= 1765 and 1400 <= st['y'] <= 1414):
        raise Stop(f"he isn't in the tower ({st['x']},{st['y']})")
    if carto.floor_of(st['z']) == 1:
        try:
            restock.ensure()  # topped up here, where the chest is: he leaves for the castle from the vault
        except restock.Stop as e:
            raise Stop(f'reagents: {e}')
    if not gems.in_vault(status()):
        gems.into_vault()


def trip():
    if read_load():
        st = status()
        import gems
        gems.info = info
        if castle.inside((st['x'], st['y'])):
            say('a load from an earlier trip is still in his pack: putting it away first')
            unload()
        elif not gems.in_vault(st):
            raise Stop('a load is written down but he is neither in the castle nor in the vault')
        else:
            say('a load was started here: filling his pack the rest of the way')
    to_vault()
    taken = load()
    if not taken:
        say('nothing left to carry')
        return False
    say(f'loaded {len(taken)} pieces; to the castle')
    castle.go_in()
    unload()
    return True


def show():
    labels = uo.load_labels()
    for serial, text in towers():
        try:
            items = call('GET', '/contents', serial=serial)['items']
        except uo.BridgeError:
            items = []
        print(f'{text:55} -> {target_of(text)}  ({len(items)} known items)')
        for i in items:
            if layout.is_bag(i) and labels.get(i['serial'], '').startswith('bag: '):
                t = target_of(text, labels[i['serial']])
                if t != target_of(text):
                    print(f'    {labels[i["serial"]]:51} -> {t}')


def main():
    global info
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'show'
    info = uo.find_bridge('Clem')
    castle.info = restock.info = info
    if cmd == 'show':
        return show()
    st = status()
    if st.get('takenOver') or st.get('halted'):
        sys.exit(f"the user has him ({st.get('takenOver') or st.get('halted')}); only they hand him back")
    try:
        if cmd == 'unload':
            unload()
        elif cmd == 'trip':
            trip()
        elif cmd == 'run':
            n = 0
            while trip():
                n += 1
                say(f'trip {n} done')
            say(f'THE MOVE IS DONE: {n} trips')
        else:
            sys.exit(__doc__)
    except (Stop, castle.Stop) as e:
        say(f'STOPPED: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
