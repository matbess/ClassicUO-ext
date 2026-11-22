"""The friend's chest in the tower bedroom (the top left of its 9: 1755,1402,14) to his personal chest by the forge in
the castle (944,2327 top), everything at its spot and in its order (the user, 2026-11-21: "it's my friends chest and I
need you to help me move it into his personal chest by the forge. I want everything to be moved so that it stays
looking the same, as usual. This chest is more tricky because it's heavy! I want you to first inventory the entire
chest and then make a plan on how to break it up into smaller loads that will fit into clems inventory. He only has
about 300 stones of weight he can carry at a time").

  python3 friend_chest.py survey     in the tower: open the chest, record every piece (spot, order), weigh each, and
                                     split them, in their drawing order, into loads he can carry; writes the plan
  python3 friend_chest.py show       the plan as written
  python3 friend_chest.py trip       one load: castle -> tower, the next load's pieces into his pack, home, each into
                                     the friend's chest at its tower spot (the chest is off limits in his rules: lifted
                                     for the drops only, and put back)

Loads go in the drawing order (load 1 is the bottom of the pile), so each trip's pieces lie over the last trip's, as
in the tower. A piece's weight: a bag's from its single click "(N items, M stones)", anything else from the game's
tile data (each one's weight times the amount). His pack also holds at most 125 items, a bag counting with
everything in it.
"""
import json
import os
import re
import struct
import sys
import time

import uo
import castle
import castle_move
import look
import restock
import tower_down as td

SRC = '0x40437B4A'   # the friend's chest, tower bedroom, top left (1755,1402,14)
DEST = '0x4058DAD8'  # his personal chest by the forge (944,2327 top), off limits in Clem's rules
WORK = os.path.expanduser('~/claude/uo-agent-work/castle')
PLAN = os.path.join(WORK, 'friend-chest-plan.json')
TILEDATA = os.path.expanduser('~/Games/UOSA-data/tiledata.mul')
CAP = 300        # stones a load may weigh (the user: "about 300 stones")
ITEM_ROOM = 125  # what a backpack holds
info = None


def say(text):
    td.say(text)


def tile_weight(graphic):
    """The item's weight in the game's tile data (the old format: 512 land blocks of 32 x 26 bytes, then item blocks
    of a 4-byte header and 32 x 37 bytes; the weight is the byte after the 4 flag bytes). 255 means not movable."""
    g = int(graphic, 16) if isinstance(graphic, str) else graphic
    land = 512 * (4 + 32 * 26)
    block, n = divmod(g, 32)
    off = land + block * (4 + 32 * 37) + 4 + n * 37 + 4
    with open(TILEDATA, 'rb') as fh:
        fh.seek(off)
        return struct.unpack('B', fh.read(1))[0]


# what a pile weighs a piece on this server where the tile data says 0 (checked 2026-11-21 in the castle: 516 ingots
# with one more were 53 stones, 7996 boards 3998, 116833 fish steaks 11684); gold coins a fiftieth
PER_PIECE = {0x0EED: 0.02, 0x0EEE: 0.02, 0x0EEF: 0.02, 0x1BD7: 0.5, 0x1BD8: 0.5, 0x1BD9: 0.5, 0x1BDA: 0.5}


def pile_weight(graphic, amount):
    g = int(graphic, 16) if isinstance(graphic, str) else graphic
    if g in PER_PIECE:
        return max(1, round(amount * PER_PIECE[g]))
    w = tile_weight(g)
    if w == 255:
        return 0
    if w == 0:
        return max(1, -(-int(amount * PER_PIECE.get(g, 0.1) * 100) // 100))
    return w * amount


def label_counts(serial):
    lines = ' '.join(a for r in uo.call(info, 'POST', '/name', serial=serial) for a in r.get('lines', []))
    m = re.search(r'\((\d+) items?, (\d+) stones?\)', lines)
    return (int(m.group(1)), int(m.group(2))) if m else None, lines


def survey():
    st = uo.call(info, 'GET', '/status')
    if not (castle.TOWER[0] <= st['x'] <= castle.TOWER[2] and castle.TOWER[1] <= st['y'] <= castle.TOWER[3]):
        castle.go_out()
    uo.walk_near(info, SRC)
    total, lines = label_counts(SRC)
    say(f'{SRC}: {lines}')
    items = look.open_once(info, SRC)
    pieces = []
    for n, i in enumerate(items):
        p = dict(serial=i['serial'], graphic=i['graphic'], hue=i.get('hue', 0), amount=i.get('amount', 1),
                 x=i['x'], y=i['y'], order=n, name=i.get('type') or i.get('name') or i['graphic'])
        if i.get('container'):
            counts, text = label_counts(i['serial'])
            if counts:
                p['items'], p['stones'] = counts[0] + 1, counts[1] + max(tile_weight(i['graphic']), 1)
            p['label'] = text
        if 'stones' not in p:
            p['items'], p['stones'] = 1, pile_weight(i['graphic'], p['amount'])
        pieces.append(p)
    st = uo.call(info, 'GET', '/status')
    pack = st['backpack']['serial']
    pack_counts, _ = label_counts(pack)
    room_items = ITEM_ROOM - (pack_counts[0] if pack_counts else 30) - 2
    cap = min(CAP, st['weightMax'] - st['weight'] - 10)
    loads, cur, w, k = [], [], 0, 0
    for p in pieces:
        if cur and (w + p['stones'] > cap or k + p['items'] > room_items):
            loads.append(cur)
            cur, w, k = [], 0, 0
        cur.append(p['serial'])
        w += p['stones']
        k += p['items']
    if cur:
        loads.append(cur)
    too_big = [p for p in pieces if p['stones'] > cap or p['items'] > room_items]
    plan = {'src': SRC, 'dest': DEST, 'surveyed': time.strftime('%Y-%m-%d %H:%M'), 'chest_label': lines,
            'chest': total, 'cap': cap, 'room_items': room_items, 'carrying': st['weight'],
            'pieces': pieces, 'loads': loads, 'done': [], 'too_big': [p['serial'] for p in too_big]}
    json.dump(plan, open(PLAN, 'w'), indent=1)
    # the exact layout, for tower_down's own checks too
    layout = json.load(open(td.LAYOUT))
    layout[SRC] = {'serial': SRC, 'x': 1755, 'y': 1402, 'z': 14, 'place': 'bedroom',
                   'recorded': time.strftime('%Y-%m-%d %H:%M'),
                   'items': [{k: p[k] for k in ('serial', 'graphic', 'hue', 'amount', 'x', 'y', 'order', 'name')}
                             for p in pieces]}
    json.dump(layout, open(td.LAYOUT, 'w'), indent=1)
    show()


def show():
    plan = json.load(open(PLAN))
    by = {p['serial']: p for p in plan['pieces']}
    print(f"{plan['src']} ({plan['chest_label']}); {len(plan['pieces'])} pieces; a load up to {plan['cap']} stones "
          f"and {plan['room_items']} items (he carries {plan['carrying']} stones of his own)")
    for n, load in enumerate(plan['loads'], 1):
        ps = [by[s] for s in load]
        print(f"load {n}{' (done)' if n in plan['done'] else ''}: {len(ps)} pieces, "
              f"{sum(p['stones'] for p in ps)} stones, {sum(p['items'] for p in ps)} items")
        for p in ps:
            print(f"   {p['order']:>3} {p['name']}{' x' + str(p['amount']) if p['amount'] > 1 else ''}"
                  f"  {p['stones']} st, {p['items']} it  @{p['x']},{p['y']}")
    if plan['too_big']:
        print('TOO BIG FOR ONE LOAD:', plan['too_big'])


# ---- the trips (the user said go, 2026-11-21) ----
# the reagent backpack (piece 0, 798 stones) goes over in four parts: the backpack with what's at the bottom of it
# first, the rest into it on later trips in its own order; the gold (piece 9, 22415 coins) in two halves, the second
# dropped onto the first so it's one pile again
TRIPS = {1: ['bp'], 2: ['in5', 'out1', 'out2', 'out3', 'out4', 'out5', 'out6', 'out7'], 3: ['in6'],
         4: ['in7', 'in8', 'out8'], 5: ['gold1'], 6: ['gold2']}
GOLD_FIRST = 11208
DOOR, DOOR_SHUT = '0x408AEA57', (1759, 1406)  # the bedroom's door (no need to lock it: the user, 2026-11-21)
IN_FRONT, INSIDE_DOOR, OUTSIDE_DOOR = (1756, 1403), (1759, 1405), (1759, 1407)
PARK = (933, 2336)
RULES_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rules', 'rules-Clem.json')


def units(plan):
    """Every unit of the move by id, with what it is and where it goes."""
    ps = plan['pieces']
    bp = ps[0]
    inner = plan['inner']
    out = {'bp': dict(kind='outer', serial=bp['serial'], x=bp['x'], y=bp['y'], name='the reagent backpack')}
    for n, i in enumerate(inner):
        out[f'in{n}'] = dict(kind='inner', serial=i['serial'], x=i['x'], y=i['y'], name=i['name'])
    for p in ps[1:9]:
        out[f"out{p['order']}"] = dict(kind='outer', serial=p['serial'], x=p['x'], y=p['y'], name=p['name'])
    gold = ps[9]
    out['gold1'] = dict(kind='gold1', serial=gold['serial'], x=gold['x'], y=gold['y'], amount=GOLD_FIRST,
                        name=f'{GOLD_FIRST} gold')
    out['gold2'] = dict(kind='gold2', serial=None, x=gold['x'], y=gold['y'], name='the rest of the gold')
    return out


def status():
    return uo.call(info, 'GET', '/status')


def where():
    st = status()
    return (st['x'], st['y'])


def in_tower():
    x, y = where()
    return castle.TOWER[0] <= x <= castle.TOWER[2] and castle.TOWER[1] <= y <= castle.TOWER[3]


def into_bedroom():
    if where()[1] <= INSIDE_DOOR[1]:
        castle.step(IN_FRONT, 'to the chest')
        return
    castle.step(OUTSIDE_DOOR, 'to the bedroom door')
    castle.set_door(DOOR, DOOR_SHUT, False)
    castle.step(INSIDE_DOOR, 'in through the bedroom door')
    castle.set_door(DOOR, DOOR_SHUT, True)
    castle.step(IN_FRONT, 'to the chest')


def out_of_bedroom():
    if where()[1] > INSIDE_DOOR[1] + 1:
        return
    castle.step(INSIDE_DOOR, 'to the bedroom door')
    castle.set_door(DOOR, DOOR_SHUT, False)
    castle.step(OUTSIDE_DOOR, 'out through the bedroom door')
    castle.set_door(DOOR, DOOR_SHUT, True)


def save_plan(plan):
    json.dump(plan, open(PLAN, 'w'), indent=1)


def take(plan, n):
    """In the tower, in front of the chest: trip n's units into his pack (the reagent backpack's later parts out of it
    first, on trip 1). His real weight is read after each: a unit that takes him over stays (put back) for later."""
    u = units(plan)
    pack = status()['backpack']['serial']
    state = plan.setdefault('state', {})
    look.open_once(info, SRC)
    if n == 1 and not plan.get('parked_inner'):
        bp = plan['pieces'][0]['serial']
        inside = {i['serial'] for i in uo.call(info, 'POST', '/open', serial=bp)['contents']['items']}
        for k in range(5, len(plan['inner'])):
            x = u[f'in{k}']
            if x['serial'] in inside:  # at a spot of its own: dropped anywhere it went onto a pile of its kind (the
                # 1213 sulfurous ash onto the chest's 1 loose ash, 2026-11-21 17:12)
                uo.call(info, 'POST', '/move', serial=x['serial'], to=SRC, x=x['x'], y=x['y'])
        plan['parked_inner'] = True
        save_plan(plan)
        say('trip 1: black pearl, nightshade, sulfurous ash and spider\'s silk out of the reagent backpack, loose in '
            'the chest for their own trips')
    for uid in TRIPS[n]:
        if state.get(uid) in ('carried', 'placed'):
            continue
        x = u[uid]
        st = status()
        before = st['weight']
        if uid in plan.get('merged', {}):
            pile = plan['merged'][uid]
            amount = pile.get('amount')
            sub = [i for i in look.open_once(info, SRC) if i['graphic'] == pile['graphic']]
            if len(sub) != 1:
                raise td.Stop(f"{x['name']}: {len(sub)} piles of {pile['graphic']} in the chest, not the one")
            pre = {i['serial'] for i in uo.call(info, 'GET', '/contents', serial=pack)['items']}
            uo.call(info, 'POST', '/move', serial=sub[0]['serial'], to=pack, x=60, y=70, **({'amount': amount} if amount else {}))
            got = [i for i in uo.call(info, 'GET', '/contents', serial=pack)['items']
                   if i['graphic'] == pile['graphic'] and (i['serial'] not in pre or i['serial'] == sub[0]['serial'])]
            if len(got) != 1:
                raise td.Stop(f"{x['name']}: {len(got)} new piles of it in his pack")
            plan.setdefault('actual', {})[uid] = got[0]['serial']
        elif x['kind'] == 'gold1':
            r = uo.call(info, 'POST', '/move', serial=x['serial'], to=pack, x=60, y=70, amount=GOLD_FIRST)
            # the lifted part may come with a serial of its own: the pile of GOLD_FIRST in his pack
            mine = [i for i in uo.call(info, 'GET', '/contents', serial=pack)['items']
                    if i['graphic'] in ('0x0EED', '0x0EEE', '0x0EEF') and i.get('amount') == GOLD_FIRST]
            if len(mine) != 1:
                raise td.Stop(f'after taking {GOLD_FIRST} gold: {len(mine)} such piles in his pack')
            plan['gold1'] = mine[0]['serial']
        elif x['kind'] == 'gold2':
            items = look.open_once(info, SRC)
            gold = [i for i in items if i['graphic'] in ('0x0EED', '0x0EEE', '0x0EEF')]
            if len(gold) != 1:
                raise td.Stop(f'the chest holds {len(gold)} gold piles, not the one left')
            plan['gold2'] = gold[0]['serial']
            r = uo.call(info, 'POST', '/move', serial=gold[0]['serial'], to=pack, x=60, y=70)
        else:
            r = uo.call(info, 'POST', '/move', serial=x['serial'], to=pack, x=60, y=70)  # a spot: never onto a pile
        st = status()
        say(f"{x['name']}: into his pack, {st['weight'] - before} stones ({st['weight']}/{st['weightMax']})")
        if st['weight'] > st['weightMax'] - 3:
            raise td.Stop(f"{x['name']} takes him to {st['weight']}/{st['weightMax']}: too heavy, stopping")
        state[uid] = 'carried'
        save_plan(plan)


def off_limits(lift):
    """The friend's chest off limits in Clem's rules (lift=False), or not (lift=True: the drops)."""
    path = os.path.join(uo.AGENT_DIR, 'rules-Clem.json')
    text = open(RULES_SRC).read()
    if lift:
        text = text.replace(f'"offLimits": ["{DEST}", ', '"offLimits": [')
    open(path, 'w').write(text)
    time.sleep(2)  # the bridge rereads its rules within a second


def place(plan, n):
    """In the castle: trip n's carried units into the friend's chest (or the reagent backpack in it), each at its
    tower spot, in order; checked."""
    import castle_site
    u = units(plan)
    state = plan['state']
    mover = castle_site.install(uo, info, say)
    look.uo.walk_near = mover.walk_near
    bp = plan['pieces'][0]['serial']
    off_limits(True)
    try:
        mover.walk_near(info, DEST)
        uo.call(info, 'POST', '/open', serial=DEST)
        for uid in TRIPS[n]:
            if state.get(uid) != 'carried':
                continue
            x = dict(u[uid], serial=plan.get('actual', {}).get(uid, u[uid]['serial']))
            if x['kind'] == 'inner':
                uo.call(info, 'POST', '/open', serial=bp)
                uo.call(info, 'POST', '/move', serial=x['serial'], to=bp, x=x['x'], y=x['y'])
            elif x['kind'] == 'gold2':
                uo.call(info, 'POST', '/move', serial=plan['gold2'], to=plan['gold1'])
            elif x['kind'] == 'gold1':
                uo.call(info, 'POST', '/move', serial=plan['gold1'], to=DEST, x=x['x'], y=x['y'])
            elif x['kind'] == 'inner':
                pass
            else:
                uo.call(info, 'POST', '/move', serial=x['serial'], to=DEST, x=x['x'], y=x['y'])
            state[uid] = 'placed'
            save_plan(plan)
        check(plan)
    finally:
        try:
            uo.call(info, 'POST', '/close', serial=DEST)
        except uo.BridgeError:
            pass
        off_limits(False)
        mover.leave_to(PARK)
    plan['done'].append(n)
    save_plan(plan)
    say(f'TRIP {n} DONE')


def check(plan):
    u = units(plan)
    top = {i['serial']: i for i in uo.call(info, 'POST', '/open', serial=DEST)['contents']['items']}
    inner = {i['serial']: i for i in uo.call(info, 'POST', '/open', serial=plan['pieces'][0]['serial'])['contents']['items']}
    off, n_top, n_in = [], 0, 0
    for uid, x in u.items():
        if plan['state'].get(uid) != 'placed' or x['kind'] == 'gold2':
            continue
        where_ = inner if x['kind'] == 'inner' else top
        s = plan.get('gold1') if x['kind'] == 'gold1' else plan.get('actual', {}).get(uid, x['serial'])
        i = where_.get(s)
        if not i or (i['x'], i['y']) != (x['x'], x['y']):
            off.append(x['name'])
        n_in += x['kind'] == 'inner'
        n_top += x['kind'] != 'inner'
    act = plan.get('actual', {})
    tops = [act.get(f"out{p['order']}", plan.get('gold1') if p['order'] == 9 else p['serial']) for p in plan['pieces']]
    tops[0] = plan['pieces'][0]['serial']
    ins = [act.get(f'in{n}', i['serial']) for n, i in enumerate(plan['inner'])]
    order_top = [s for s in top if s in tops]
    want_top = [s for s in tops if s in top]
    order_in = [s for s in inner if s in ins]
    want_in = [s for s in ins if s in inner]
    say(f"the friend's chest: {n_top} pieces and {n_in} in the reagent backpack at their tower spots"
        f"{'' if not off else ' (OFF: ' + ', '.join(off) + ')'}; order {'the same' if order_top == want_top and order_in == want_in else 'DIFFERENT'}")


def trip():
    """The next trip, from wherever he is (in the tower, the castle, or half way through one)."""
    plan = json.load(open(PLAN))
    if 'inner' not in plan:
        raise td.Stop('the reagent backpack is not recorded: run inner first')
    n = next((k for k in sorted(TRIPS) if k not in plan['done']), None)
    if n is None:
        say('ALL TRIPS DONE')
        return
    state = plan.setdefault('state', {})
    carrying = [uid for uid in TRIPS[n] if state.get(uid) == 'carried']
    pending = [uid for uid in TRIPS[n] if state.get(uid) not in ('carried', 'placed')]
    if pending:
        if not in_tower():
            import castle_site
            if castle_site.behind(where()):  # out past the tables first, the table locked as he passes it
                castle_site.Mover(uo, info, say).leave_to(PARK)
            castle.go_out()
        into_bedroom()
        take(plan, n)
    if in_tower():
        out_of_bedroom()
    castle.go_in()
    place(plan, n)


def record_inner():
    """The reagent backpack's own layout (its pieces, spots and order), opened where it lies in the chest."""
    plan = json.load(open(PLAN))
    bp = plan['pieces'][0]['serial']
    items = uo.call(info, 'POST', '/open', serial=bp)['contents']['items']
    plan['inner'] = [dict(serial=i['serial'], graphic=i['graphic'], amount=i.get('amount', 1), x=i['x'], y=i['y'],
                          order=n, name=i.get('type') or i['graphic']) for n, i in enumerate(items)]
    save_plan(plan)
    say(f"the reagent backpack: {len(plan['inner'])} pieces recorded")


def main():
    global info
    info = uo.find_bridge('Clem')
    td.info = castle.info = restock.info = castle_move.info = info
    castle_move.say = say
    uo.call = td.call_past_razor
    look.uo = uo
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'show'
    if cmd == 'survey':
        survey()
    elif cmd == 'show':
        show()
    elif cmd == 'inner':
        record_inner()
    elif cmd == 'trip':
        trip()
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
