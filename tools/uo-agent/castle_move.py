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


# loose things that have a castle home of their own, whatever tower chest they lay in (the castle plan: crafting by
# the forge): cut leather and cloth, hides; saws, planes, scissors, tongs, shovels and other tools; boards and logs;
# ingots
LOOSE_HOME = {}
for g in ('0x1067', '0x1068', '0x1081', '0x1082', '0x1766', '0x1767', '0x1078', '0x1079'):
    LOOSE_HOME[g] = 'cloth & leather'
for g in ('0x1034', '0x1035', '0x1028', '0x1029', '0x102C', '0x102D', '0x1030', '0x1031', '0x0F9E', '0x0F9F',
          '0x0FBB', '0x0FBC', '0x0F39', '0x0F3A', '0x13E3', '0x13E4', '0x0FB4', '0x0FB5', '0x1022', '0x1023'):
    LOOSE_HOME[g] = 'tools'
for g in ('0x1BD7', '0x1BD8', '0x1BD9', '0x1BDA', '0x1BDD', '0x1BDE', '0x1BDF', '0x1BE0', '0x1BE1', '0x1BE2'):
    LOOSE_HOME[g] = 'boards & logs'
for g in ('0x1BEF', '0x1BF0', '0x1BF1', '0x1BF2', '0x1BF3', '0x1BF4'):
    LOOSE_HOME[g] = 'ingots'


def target_of(container_label, bag_label=None, graphic=None):
    if graphic in LOOSE_HOME:
        return LOOSE_HOME[graphic]
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

LEFT = [False]  # set when a load ends with things still in the tower


def load():
    """Fill his pack from the tower's containers, in ORDER. Returns the pieces taken (also written to LOAD); LEFT[0]
    says whether anything was left behind."""
    LEFT[0] = False
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
                LEFT[0] = True
                return taken
            bag_label = labels.get(pieces[0]['serial']) if pieces[0]['role'] == 'bag' else None
            what = target_of(text, bag_label, pieces[0]['graphic'] if pieces[0]['role'] == 'loose' else None)
            before = st['weight']
            for p in pieces:
                try:
                    r = uo.move(info, p['serial'], pack)
                except uo.TakenOver:
                    # Razor's AutoSearch opens a bag the moment it lands in his pack (2026-11-19 20:47:03, the rings
                    # bag): that double-click isn't the user (fight.razor_click checks, and resumes)
                    import fight
                    fight.info = info
                    if not fight.razor_click(bag=p['serial']):
                        time.sleep(0.6)  # the click may not be in the bridge's log yet (20:47:43)
                        if not fight.razor_click(bag=p['serial']):
                            raise
                    r = {'moved': True, 'messages': []}
                said = ' '.join(m['text'] for m in r.get('messages', [])).lower()
                if not r.get('moved') and 'cannot hold more weight' in said:
                    # too heavy for his pack all at once (1954 lockpicks, 2026-11-19): the part that fits, the rest
                    # on a later trip. A pile split keeps its serial on the part moved; the rest gets a new one.
                    amount = p.get('amount', 1)
                    # as many as his room holds, at a stone a piece (lockpicks, ingots and the like are about that;
                    # lighter piles just leave room); halved again while even that's refused
                    room_now = status()['weightMax'] - status()['weight'] - WEIGHT_LEFT
                    if room_now < 30:  # nearly full already: this pile waits for the next trip
                        say(f"his pack is full ({status()['weight']} stones): this load is done")
                        LEFT[0] = True
                        return taken
                    part = max(1, min(amount - 1, room_now))
                    while part >= 1 and not r.get('moved'):
                        time.sleep(1)
                        # the refused drop bounced back as a new item (2026-11-19: 0x4088B57F came back as
                        # 0x4087D2B3): find the pile again by what it is
                        again = [i for i in open_items(serial) if i['graphic'] == p['graphic']
                                 and i.get('hue') == p.get('hue') and i.get('amount', 1) == amount]
                        if again:
                            p['serial'] = again[0]['serial']
                        w0 = status()['weight']
                        try:
                            r = uo.move(info, p['serial'], pack, amount=part)
                        except uo.BridgeError as e:
                            if e.code == 423 and landed(w0):
                                r = {'moved': True}
                            elif e.code != 404:
                                raise
                            else:
                                r = {}
                        part //= 2
                    if not r.get('moved'):
                        say(f"his pack takes no more ({status()['weight']} stones): this load is done")
                        LEFT[0] = True
                        return taken
                    p['amount'] = part * 2
                    trim(p, serial, pack)
                    say(f"{p['type']}: {p['amount']} of {amount} this trip, the rest next time")
                if not r.get('moved'):
                    raise Stop(f"{p['serial']} {p['type']} did not come out of {text}: {r}")
            after = status()
            if after['weight'] > after['weightMax'] - WEIGHT_LEFT:  # too much after all: back where it lay
                LEFT[0] = True
                p0 = pieces[0]
                if len(pieces) == 1 and p0.get('amount', 1) > 1:
                    # a pile: only the part that fits comes along (the user, 2026-11-19: "you have to break up large
                    # piles into smaller piles"); the moved part keeps the serial, the rest stays as a new pile
                    each = (after['weight'] - before) / p0['amount']
                    fits = int((after['weightMax'] - WEIGHT_LEFT - before) / each) if each > 0 else 0
                    uo.move(info, p0['serial'], serial, p0['x'], p0['y'])
                    if fits >= 1:
                        time.sleep(1)
                        again = [i for i in open_items(serial) if i['graphic'] == p0['graphic']
                                 and i.get('hue') == p0.get('hue') and i.get('amount', 1) == p0['amount']]
                        if again:
                            p0['serial'] = again[0]['serial']
                        r = uo.move(info, p0['serial'], pack, amount=fits)
                        if r.get('moved'):
                            p0['amount'] = fits
                            trim(p0, serial, pack)
                            fits = p0['amount']
                            say(f"{p0['type']}: {fits} of {p0['amount']} this trip (about {each:.1f} stones each), the "
                                'rest next time')
                            p0['amount'] = fits
                            taken.append({'serial': p0['serial'], 'type': p0['type'], 'role': p0['role'],
                                          'from': text, 'x': p0['x'], 'y': p0['y'], 'what': what, 'count': 1,
                                          'stones': int(fits * each), 'amount': fits, 'graphic': p0['graphic'],
                                          'crate': not text.startswith('chest: ')})
                            write_load(taken)
                    return taken
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


def landed(weight_before):
    """The bridge stopped on a drop into his pack ("no answer after dropping"), but the pack got heavier: it landed
    (2026-11-19 20:41 and 20:42, splitting piles in the vault). Resumed; only when he's not taken over, and he's
    indoors when this runs."""
    st = uo.call(info, 'GET', '/status')
    if st.get('takenOver') or 'after dropping' not in (st.get('halted') or '') or st['weight'] <= weight_before:
        return False
    uo.call(info, 'POST', '/resume')
    say(f"the bridge stopped on a drop that landed ({st['halted']}): resumed")
    return True


def trim(p, container, pack):
    """Never over his most (2026-11-19 20:41: 329 cut leather took him to 408/390, and overloaded he can't move):
    while he's over, the excess of the pile p goes back to where it came from, at the stones a piece it weighs."""
    for _ in range(4):
        st = status()
        over = st['weight'] - (st['weightMax'] - WEIGHT_LEFT)
        if over <= 0:
            return
        mine = [i for i in call('GET', '/contents', serial=pack)['items'] if i['graphic'] == p['graphic']]
        if not mine:
            return
        pile = mine[0]
        back = min(pile.get('amount', 1) - 1, over + 5)
        if back < 1:
            return
        call('POST', '/move', serial=pile['serial'], to=container, amount=back)  # the part moved keeps the serial
        time.sleep(1)
        rest = [i for i in call('GET', '/contents', serial=pack)['items'] if i['graphic'] == p['graphic']]
        if rest:
            p['serial'], p['amount'] = rest[0]['serial'], rest[0].get('amount', 1)
        say(f"{p['type']}: {back} back, he was {over} stones over")


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
        if LEFT[0]:
            raise Stop('things are left in the tower but none of them would go into his pack: TELL THE USER')
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
