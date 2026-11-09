#!/usr/bin/env python3
"""Clem's cartography in the tower (see CARTO.md): the map bags and their kinds, and the reorganisation.

  python3 -I carto.py bags                    the bags in the state: spot, kind, count
  python3 -I carto.py reorg [--dry] [--check]  bring every bag down to 100 maps (CARTO.md, "the reorganisation");
                                              --dry prints the plan from what the client knows and sends nothing

Every bag holds only one kind of map, blank (the server calls it "map") or completed (any drawn kind), and a map
only goes into a bag of its own kind. The user keeps the bags pure, so maps are moved without single-clicking them
first (2026-11-05); --check single-clicks each one before it's moved. The plan is worked out again from the bags'
real contents on every run, so a run that stopped can simply be started again. Only ever acts as Clem (his bridge).
State in ~/claude/uo-agent-work/carto/state.json; logs to carto.log there.
"""
import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import uo  # noqa: E402

CHAR = 'Clem'
WORK = os.path.expanduser('~/claude/uo-agent-work/carto')
STATE = os.path.join(WORK, 'state.json')
LOG = os.path.join(WORK, 'carto.log')
PER_BAG = 100          # maps in a bag (the user, 2026-11-05)
PACK_LIMIT = 125       # items a container holds, everything inside bags included
REACH = 2
FLOOR_Z = {1: 6, 2: 26, 3: 46}
# the stairs from the second floor (bottom step, z 26) to the third (top step, z 41), and a tile on the third floor
STAIRS_2_BOTTOM = (1755, 1406)
STAIRS_2_TOP = (1755, 1403)
THIRD_LANDING = (1753, 1403)
SECOND_LANDING = (1755, 1407)
# the ground floor stairs (x 1750-1751, y 1406 at z 6 up to 1403 at z 23) and the tile they lead to on the second
GROUND_STAIRS_FOOT = (1751, 1407)
GROUND_STAIRS_TOP = (1751, 1403)
SECOND_FROM_GROUND = (1752, 1402)
# walking on a floor (see walk()): hops of at most HOP tiles; the second floor's wall along y 1409 with its gap at
# x 1753-1754; tiles on the second floor not to aim a hop at (box x1, y1, x2, y2): the ground floor stairwell (no floor
# there) and the stairs up to the third floor
HOP = 3
WALL_Y = 1409
GAP_NORTH, GAP_SOUTH = (1753, 1408), (1753, 1410)
SECOND_NO_HOP = [(1750, 1402, 1751, 1408), (1755, 1403, 1756, 1405)]

info = None
DRY = False
CHECK = False  # single-click every map before moving it


def say(text):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + text
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def load_state():
    with open(STATE, encoding='utf-8') as fh:
        return json.load(fh)


def save_state(state):
    uo.write_json(STATE, state, 1)


def kind_of(name):
    name = (name or '').strip().lower()
    if name == 'map':
        return 'blank'
    if 'map' in name or 'chart' in name:
        return 'completed'
    return None


def floor_of(z):
    if z >= 66:
        return 4  # the roof
    return 3 if z >= 46 else 2 if z >= 26 else 1


# ---- talking to the bridge, with the usual stops handled ----

LAST_SAVE = [0.0]


def act(method, endpoint, **params):
    """A bridge call that waits out what a person would wait out: a world save, someone in the room."""
    for _ in range(200):
        try:
            return uo.call(info, method, endpoint, **params)
        except uo.BridgeError as e:
            # uo.wait_out_world_save takes any stop for a save while a save's messages are among the last 15, so a
            # double-click the server answered with "I can't reach that" was resumed and sent 12 times (2026-11-05):
            # a stop within two minutes of a save is something else
            if e.code == 423 and time.time() - LAST_SAVE[0] > 120 and uo.wait_out_world_save(info, e):
                LAST_SAVE[0] = time.time()
                say('world save: waited it out')
                continue
            if e.code == 423:
                said = [m['text'] for m in uo.call(info, 'GET', '/messages')['messages'][-3:]]
                raise SystemExit(f'the bridge stopped: {e.message}; last messages: {said}')
            if e.code == 409 and 'paused' in e.message:
                say(f'paused: {e.message}; waiting for the room to clear')
                while uo.others_in_area(info):
                    time.sleep(20)
                continue
            raise
    raise uo.BridgeError(0, 'gave up after too many waits')


def status():
    return uo.call(info, 'GET', '/status')


def here():
    s = status()
    return s['x'], s['y'], s['z']


def item(serial):
    return uo.call(info, 'GET', '/item', serial=serial)


def contents(bag):
    """The maps (or whatever) the client knows in a bag; opens it first if the client knows nothing about it."""
    found = item(bag)['item']
    if found.get('container') and not found.get('knownItems') and not found.get('open') and not DRY:
        come_within_reach(bag)
        act('POST', '/open', serial=bag)
        act('POST', '/close', serial=bag)
    return uo.call(info, 'GET', '/contents', serial=bag, depth=1)['items']


def pack_items():
    """Items in Clem's backpack, counting everything inside bags (not the spell icons of a spellbook)."""
    pack = status()['backpack']['serial']

    def count(items):
        n = 0
        for i in items:
            if int(i['serial'], 16) >= 0x7F000000:
                continue
            n += 1 + count(i.get('items', []))
        return n
    return count(uo.call(info, 'GET', '/contents', serial=pack, depth=4)['items'])


def names(serials, kind=None):
    """The server's names, single-clicking only those names.json doesn't know. Without --check, maps in a bag of a
    known kind are taken to be that kind."""
    if kind and not CHECK:
        return {s: 'map' if kind == 'blank' else 'drawn map' for s in serials}
    known = uo.load_names()
    todo = [s for s in serials if s not in known]
    for i in range(0, len(todo), 10):
        act('POST', '/name', serial=','.join(todo[i:i + 10]))
    known = uo.load_names()
    return {s: known.get(s) for s in serials}


# ---- moving about the tower ----

def stride(x, y, distance=0):
    """One walk, wherever the path finder takes him: only for the stairs (go_to_floor). It runs, and doesn't wait its
    turn: the next step starts the moment he arrives (the user, 2026-11-08: "why does he walk up and down the stairs so
    weird. Can't you walk up and down them fast?"; each step used to wait for the bridge's 1.1 s gap)."""
    return quick_walk(x, y, distance)


def quick_walk(x, y, distance=0):
    """A running walk that comes back at once (wait=0, his rules allow it for fights), then watched until he is there
    or has stopped moving. Only inside the tower: its walls and the locked door keep the walk in."""
    act('POST', '/walk', x=x, y=y, distance=distance, run=1, wait=0)
    last, since = None, time.time()
    end = time.time() + 10
    while time.time() < end:
        s = status()
        here_now = (s['x'], s['y'], s['z'])
        if max(abs(s['x'] - x), abs(s['y'] - y)) <= distance:
            return {'arrived': True}
        if here_now != last:
            last, since = here_now, time.time()
        elif time.time() - since > 0.8:
            break
        time.sleep(0.08)
    return {'arrived': False}


def side(y):
    return None if y == WALL_Y else ('north' if y < WALL_Y else 'south')


def walk(x, y, distance=0):
    """Walk to within `distance` of x,y on the floor he's on. The path finder stops at the goal's x,y on whatever floor
    it reaches first, and the ground floor stairs come up into the bag room at 1751,1403: a long walk across the room
    went down them and ended under the bag he was going to (2026-11-05). So he walks in hops of at most HOP tiles
    (down the stairs and back is always longer), through the gap in the wall, and the floor is checked after each."""
    sx, sy, sz = here()
    floor = floor_of(sz)
    legs = []
    if floor == 2 and side(sy) and side(y) and side(sy) != side(y):
        legs += [GAP_NORTH, GAP_SOUTH] if side(sy) == 'north' else [GAP_SOUTH, GAP_NORTH]
    legs.append((x, y))
    for n, (lx, ly) in enumerate(legs):
        near = distance if n == len(legs) - 1 else 1
        stuck = 0
        while True:
            cx, cy, cz = here()
            if floor_of(cz) != floor:
                raise SystemExit(f'meant to stay on floor {floor}, but Clem is at {cx},{cy},{cz}')
            d = max(abs(lx - cx), abs(ly - cy))
            if d <= near:
                break
            if d <= HOP:
                hx, hy, hd = lx, ly, near
            else:
                hx, hy, hd = cx + round((lx - cx) * HOP / d), cy + round((ly - cy) * HOP / d), 1
                if floor == 2:
                    for x1, y1, x2, y2 in SECOND_NO_HOP:
                        if x1 <= hx <= x2 and y1 <= hy <= y2:
                            hx = x1 - 1 if x1 > 1752 else x2 + 1
            quick_walk(hx, hy, hd)
            if here()[:2] == (cx, cy):
                stuck += 1
                if stuck >= 2:
                    raise SystemExit(f"couldn't walk from {cx},{cy},{cz} towards {lx},{ly}")


def go_to_floor(floor):
    x, y, z = here()
    if floor_of(z) == floor:
        return
    if floor_of(z) == 1:
        # the path finder stops at a goal's x,y on whatever floor it reaches first: onto the stairs, then up
        # walks on these stairs often stop a tile short (2026-11-05), so the last step is tried again
        stride(*GROUND_STAIRS_FOOT)
        stride(*GROUND_STAIRS_TOP)
        for _ in range(3):
            stride(*SECOND_FROM_GROUND)
            x, y, z = here()
            if floor_of(z) == 2:
                break
        if floor_of(z) != 2:
            raise SystemExit(f'meant to reach floor 2, but Clem is at {x},{y},{z}')
        say(f'now on floor 2 at {x},{y},{z}')
        return go_to_floor(floor)
    if floor_of(z) == 2 and floor == 3:
        walk(*SECOND_LANDING)
        stride(*STAIRS_2_BOTTOM)
        stride(*STAIRS_2_TOP)
        stride(*THIRD_LANDING)
    elif floor_of(z) == 3 and floor == 2:
        stride(*STAIRS_2_TOP)
        stride(*STAIRS_2_BOTTOM)
        stride(*SECOND_LANDING)
    else:
        raise SystemExit(f'no way planned from floor {floor_of(z)} to floor {floor}')
    x, y, z = here()
    if floor_of(z) != floor:
        raise SystemExit(f'meant to reach floor {floor}, but Clem is at {x},{y},{z}')
    say(f'now on floor {floor} at {x},{y},{z}')


def come_within_reach(serial):
    spot = uo.on_floor(info, serial)
    if not spot:
        return
    go_to_floor(floor_of(spot['z']))
    spot = uo.on_floor(info, serial)
    if spot['distance'] > REACH:
        walk(spot['x'], spot['y'], distance=1)
        spot = uo.on_floor(info, serial)
        if spot['distance'] > REACH:
            raise SystemExit(f"can't get within reach of {serial} at {spot['x']},{spot['y']},{spot['z']}")


def move(serial, to):
    """Move one map; True when it's in `to`."""
    source, target = uo.on_floor(info, serial), uo.on_floor(info, to)
    if any(s and s['distance'] > REACH for s in (source, target)):
        if source and target:
            # both on the floor: stand where both are within reach, or carry the map over in the pack
            apart = max(abs(source['x'] - target['x']), abs(source['y'] - target['y']))
            if apart <= 2 * REACH and floor_of(source['z']) == floor_of(target['z']):
                go_to_floor(floor_of(source['z']))
                mid = ((source['x'] + target['x']) // 2, (source['y'] + target['y']) // 2)
                for distance in (0, 1):
                    try:
                        walk(*mid, distance=distance)
                        break
                    except uo.BridgeError as e:
                        if e.code != 409:
                            raise
            source, target = uo.on_floor(info, serial), uo.on_floor(info, to)
            if source['distance'] > REACH or target['distance'] > REACH:
                come_within_reach(serial)
                pack = status()['backpack']['serial']
                if not act('POST', '/move', serial=serial, to=pack).get('moved'):
                    say(f"{serial} couldn't be taken into the pack")
                    return False
                come_within_reach(to)
        elif source:
            come_within_reach(serial)
        else:
            come_within_reach(to)
    result = act('POST', '/move', serial=serial, to=to)
    if result.get('moved'):
        return True
    time.sleep(1)
    inside = [i['serial'] for i in item(serial).get('insideOf', [])]
    if inside and inside[0] == to:
        say(f'{serial} did go into {to} (the bridge missed it)')
        return True
    say(f'{serial} did not go into {to}: {json.dumps(result)[:200]}')
    return False


def pick_up(bag):
    come_within_reach(bag)
    pack = status()['backpack']['serial']
    if not act('POST', '/move', serial=bag, to=pack).get('moved'):
        raise SystemExit(f"couldn't pick up {bag}")
    # moving a bag makes the client forget what's in it; and drops are only answered in an opened container
    act('POST', '/open', serial=bag)
    act('POST', '/close', serial=bag)


def put_down(bag, spot):
    x, y, z = spot
    go_to_floor(floor_of(z))
    walk(x, y)
    if (here()[0], here()[1]) != (x, y):
        raise SystemExit(f"couldn't stand on {x},{y} to put {bag} down")
    result = act('POST', '/move', serial=bag, ground=1)
    if not result.get('moved'):
        raise SystemExit(f"couldn't put {bag} down at {x},{y}")
    found = item(bag)['item']
    say(f"put {bag} down at {found.get('x')},{found.get('y')},{found.get('z')}")
    return [found.get('x'), found.get('y'), found.get('z')]


# ---- the reorganisation ----

def label(state, bag):
    b = state['bags'][bag]
    where = "Clem's pack" if b.get('spot') is None else ('overflow, 3rd floor' if floor_of(b['spot'][2]) == 3
                                                         else "Clem's bag room")
    labels = uo.load_labels()
    labels['0x' + bag[2:].upper().zfill(8)] = f"maps: {b['kind']} ({where})"
    uo.write_json(uo.LABELS, labels, 2)


def note(state, bag, kind, count, spot='keep'):
    b = state['bags'].setdefault(bag, {})
    b['kind'] = kind
    b['maps'] = count
    if spot != 'keep':
        b['spot'] = spot
    b['seen'] = time.strftime('%Y-%m-%d %H:%M')
    save_state(state)
    label(state, bag)


def misfit(state, serial, kind, holder):
    """A map found in a bag of the other kind: into the nearest bag of its own kind with room."""
    room = [(b, v) for b, v in state['bags'].items() if v['kind'] == kind and v['maps'] < PER_BAG and b != holder]
    if not room:
        say(f'{serial} is {kind} but sits in {holder}, and no {kind} bag has room: left there')
        return False
    me = here()
    room.sort(key=lambda bv: max(abs(bv[1]['spot'][0] - me[0]), abs(bv[1]['spot'][1] - me[1]))
              if bv[1].get('spot') else -1)
    to = room[0][0]
    if move(serial, to):
        state['bags'][to]['maps'] += 1
        state['bags'][holder]['maps'] -= 1
        save_state(state)
        say(f'{serial} was {kind} in a {state["bags"][holder]["kind"]} bag: moved to {to}')
        return True
    return False


def refresh(state):
    """Real counts of every bag in the state, from the client."""
    def where(bag):  # in his pack first, then floor by floor, the north half before the south, column by column
        spot = state['bags'][bag].get('spot')
        return (0, 0, 0, 0) if not spot else (floor_of(spot[2]), spot[1] > WALL_Y, spot[0], spot[1])
    for bag in sorted(state['bags'], key=where):
        b = state['bags'][bag]
        b['maps'] = len(contents(bag))
    if not DRY:  # a dry run opens nothing, so a bag the client has forgotten would count as empty
        save_state(state)


def reorg(dry):
    state = load_state()
    plan = state.setdefault('reorg', {})
    refresh(state)
    bags = state['bags']
    completed = {b: v for b, v in bags.items() if v['kind'] == 'completed' and floor_of(v['spot'][2]) == 2}
    blank = {b: v for b, v in bags.items() if v['kind'] == 'blank' and v.get('spot') and floor_of(v['spot'][2]) == 2}

    if 'freed' not in plan:
        total = sum(v['maps'] for v in completed.values())
        keep = math.ceil(total / PER_BAG)
        by_size = sorted(completed, key=lambda b: completed[b]['maps'])
        plan['freed'] = by_size[:len(completed) - keep]
    if 'empties' not in plan:
        near = uo.call(info, 'GET', '/nearby', range=14)['items']
        upstairs = [i for i in near if i.get('container') and i['type'] in ('backpack', 'bag', 'pouch')
                    and 1750 <= i['x'] <= 1756 and 1402 <= i['y'] <= 1413 and 46 <= i['z'] <= 65
                    and i['serial'] not in bags]
        empties = []
        for i in upstairs:
            if dry:
                empties.append(i['serial'])
                continue
            inside = contents(i['serial'])
            say(f"3rd floor {i['serial']} at {i['x']},{i['y']},{i['z']}: {len(inside)} items")
            if not inside:
                empties.append(i['serial'])
            else:
                kinds = {kind_of(n) for n in names([x['serial'] for x in inside[:2]]).values()}
                say(f"  holds {len(inside)}: {kinds}; not used")
        plan['empties'] = [[s, [i['x'], i['y'], i['z']]] for s in empties for i in upstairs if i['serial'] == s]
        if not dry:
            save_state(state)
    freed = plan['freed']
    extras_blank = sum(max(0, v['maps'] - PER_BAG) for v in blank.values())
    to_empty = ', '.join('%s (%d)' % (b, completed[b]['maps']) for b in freed if b in completed)
    say(f"completed bags: {len(completed)} with {sum(v['maps'] for v in completed.values())}; to empty: "
        f"{to_empty}; over 100: {sum(max(0, v['maps'] - PER_BAG) for v in completed.values())}")
    say(f"blank bags: {len(blank)} with {sum(v['maps'] for v in blank.values())}; over 100: {extras_blank}")
    say(f"empty bags upstairs: {[s for s, _ in plan['empties']]}")
    if dry:
        return

    if len(plan['empties']) < 1 + math.ceil(max(0, extras_blank - PER_BAG * (len(freed) + 1)) / PER_BAG):
        raise SystemExit('not enough empty bags upstairs for the extra blank maps')

    # the working bag rides in Clem's pack from the start: blanks found among the completed maps go into it
    if 'working' not in plan:
        plan['working'] = plan['empties'][0][0]
        save_state(state)
    working = plan['working']
    pack = status()['backpack']['serial']
    if uo.on_floor(info, working):
        pick_up(working)
    note(state, working, 'blank', len(contents(working)), spot=None)
    say(f'working bag {working} in the pack ({pack_items()} items in the pack)')

    # 1. the completed maps: empty the smallest bags into the others, trim those over 100. From 1752,1411 every
    # completed bag (x 1750-1754, y 1410-1413) is within reach.
    go_to_floor(2)
    walk(1752, 1411)
    for src in [b for b in completed if b in freed] + [b for b in completed if b not in freed]:
        quota = 0 if src in freed else PER_BAG
        maps = [i['serial'] for i in contents(src)]
        extra = maps[quota:] if len(maps) > quota else []
        if not extra:
            continue
        say(f"{src}: moving {len(extra)} of its {len(maps)}")
        for serial, name in names(extra, bags[src]['kind']).items():
            k = kind_of(name)
            if k == 'blank':
                if move(serial, working):
                    bags[src]['maps'] -= 1
                    bags[working]['maps'] += 1
                    save_state(state)
                    say(f'{serial} was blank in a completed bag: into the working bag')
                continue
            if k != 'completed':
                say(f'{serial} is "{name}", not a map: left in {src}')
                continue
            targets = [b for b in completed if b not in freed and b != src and bags[b]['maps'] < PER_BAG]
            if not targets:
                say('no completed bag has room left')
                break
            me = here()
            targets.sort(key=lambda b: (max(abs(bags[b]['spot'][0] - me[0]), abs(bags[b]['spot'][1] - me[1])) > REACH,
                                        -bags[b]['maps']))
            if move(serial, targets[0]):
                bags[src]['maps'] -= 1
                bags[targets[0]]['maps'] += 1
                save_state(state)
    for b in freed:
        if not contents(b):
            note(state, b, 'blank', 0)
            say(f'{b} is empty: it becomes a blank bag on its spot')

    # 2. the blank maps over 100: into the freed bags, overflow bags upstairs, and last the working bag
    def extras():
        return sum(max(0, bags[b]['maps'] - PER_BAG) for b in blank)

    # where each bag being filled goes back to (kept in the plan: a bag being filled is in the pack, spot None)
    home = plan.setdefault('home', {})
    for f in freed:
        if f not in home and bags[f].get('spot'):
            home[f] = bags[f]['spot']
    for e, spot in plan['empties'][1:]:
        home.setdefault(e, spot)
    save_state(state)
    fills = [(f, home[f]) for f in freed if bags[f]['kind'] == 'blank'] + \
            [(e, home[e]) for e, _ in plan['empties'][1:]]
    for bag, spot in fills:
        # what's left once the working bag (filled last, up to 100) has taken its share
        left = extras() - (PER_BAG - bags[working]['maps'])
        if left <= 0:
            break
        if floor_of(spot[2]) == 2:
            quota = min(PER_BAG, left)
        else:
            # the overflow: as few bags as will do, filled evenly
            quota = math.ceil(left / math.ceil(left / PER_BAG))
        if uo.on_floor(info, bag):
            pick_up(bag)
        note(state, bag, 'blank', len(contents(bag)), spot=None)
        room = PACK_LIMIT - pack_items()
        quota = min(quota, bags[bag]['maps'] + room)
        say(f'filling {bag} to {quota} (it has {bags[bag]["maps"]}; {room} places left in the pack)')
        fill(state, bag, quota, blank)
        spot = put_down(bag, spot)
        note(state, bag, 'blank', len(contents(bag)), spot=spot)

    if extras() > 0:
        room = PACK_LIMIT - pack_items()
        quota = min(PER_BAG, bags[working]['maps'] + room)
        say(f'filling the working bag {working} to {quota}')
        fill(state, working, quota, blank)
        note(state, working, 'blank', len(contents(working)), spot=None)

    refresh(state)
    over = {b: v['maps'] for b, v in bags.items() if v['maps'] > PER_BAG}
    say(f'reorganisation done; bags over {PER_BAG}: {over or "none"}; pack {pack_items()} items')
    finish()


def fill(state, bag, quota, blank):
    bags = state['bags']
    while bags[bag]['maps'] < quota:
        sources = [b for b in blank if bags[b]['maps'] > PER_BAG]
        if not sources:
            return
        me = here()
        sources.sort(key=lambda b: (floor_of(bags[b]['spot'][2]) != floor_of(me[2]),
                                    max(abs(bags[b]['spot'][0] - me[0]), abs(bags[b]['spot'][1] - me[1]))))
        src = sources[0]
        maps = [i['serial'] for i in contents(src)]
        take = maps[PER_BAG:][:quota - bags[bag]['maps']]
        come_within_reach(src)
        for serial, name in names(take, bags[src]['kind']).items():
            k = kind_of(name)
            if k == 'completed':
                misfit(state, serial, 'completed', src)
                continue
            if k != 'blank':
                say(f'{serial} is "{name}", not a map: left in {src}')
                bags[src]['maps'] -= 1  # don't count it as a map
                continue
            if move(serial, bag):
                bags[src]['maps'] -= 1
                bags[bag]['maps'] += 1
                save_state(state)
        say(f"{src} down to {bags[src]['maps']}; {bag} has {bags[bag]['maps']}")


def finish():
    """Leave Clem standing in the bag room, out of everyone's way."""
    go_to_floor(2)
    walk(1753, 1409)
    say('Clem is in the bag room, in the gap in the wall')


def show_bags():
    state = load_state()
    for bag, b in sorted(state['bags'].items(), key=lambda bv: (bv[1].get('spot') or [0, 0, 0])[::-1]):
        print(bag, b.get('spot'), b['kind'], b['maps'])


def main():
    global info
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('bags')
    r = sub.add_parser('reorg')
    r.add_argument('--dry', action='store_true')
    r.add_argument('--check', action='store_true', help='single-click every map before moving it')
    args = parser.parse_args()
    if args.command == 'bags':
        return show_bags()
    global DRY, CHECK
    info = uo.find_bridge(CHAR)
    os.makedirs(WORK, exist_ok=True)
    if args.command == 'reorg':
        DRY = args.dry
        CHECK = args.check
        reorg(args.dry)


if __name__ == '__main__':
    main()
