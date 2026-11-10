#!/usr/bin/env python3
"""Clem sells the gems (GEMS.md; the user, 2026-11-09). This is every trip's first phase, getting ready, as the user
laid it out; every step is logged to ~/claude/uo-agent-work/gems/gems.log.

  python3 -I gems.py fetch [--resume]     from anywhere inside the tower:
    1. up to the second floor and into the vault (the locked door 0x408AEA59 at 1757,1412; its key ring 0x404099E0
       hangs in the bag room at 1756,1410): unlock, open, into the doorway, lock, in, close (as Icepick goes in,
       SMITHING.md);
    2. the gems chest (column 5, bottom: 0x408FE3A0 at 1762,1402,26): the loose gem in it (the marker that shows
       what the bag holds) into the gem bag, onto its own kind's stack; then the whole gem bag into his pack;
    3. out of the vault, no key (the user, 2026-11-09: it's locked but usable from the inside, and stays locked: the
       key would only unlock it, and can't be reached from inside anyway): the door opened from inside (his client
       often opens it as he walks up), through the doorway, closed behind him from the bag room; then tried from
       there: it must say "That is locked." and stay shut (the vault door always ends locked and closed);
    4. down to the ground floor: the Gems runebook from the top left chest by the stairs (0x4058ABA9, 1752,1402,14,
       right above the reagents chest) into his pack;
    5. reagents: any below 25, restock from the chest under it (restock.py);
    6. parked in the safe zone.
  python3 -I gems.py vault-out            only step 3 (he's in the vault): out, locked and closed
  python3 -I gems.py vault-test           steps 1 and 3 only (the user, 2026-11-09: show the door works first): in,
                                          straight out again, and he stays at the door in the bag room
  python3 -I gems.py runebook             step 4 only (the user, 2026-11-09: try the runebook first): the Gems
                                          runebook into his pack, and he stays by the chest

Only the user hands Clem back: if they have taken him over, this refuses to start (--resume only when they say so),
and if they take over meanwhile, it stops at once.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import uo  # noqa: E402
import carto  # noqa: E402
import door  # noqa: E402
import fight  # noqa: E402
import restock  # noqa: E402
import trips  # noqa: E402

CHAR = 'Clem'
WORK = os.path.expanduser('~/claude/uo-agent-work/gems')
LOG = os.path.join(WORK, 'gems.log')
STATE = os.path.join(WORK, 'state.json')

# the vault (SMITHING.md, "Smelting in the vault"): a metal door that stays on its tile and changes graphic
VAULT_DOOR = '0x408AEA59'
VAULT_KEY = '0x404099E0'     # locked down in the bag room at 1756,1410 (z 38); reaches the door from both sides
SHUT, OPEN = 0x0681, 0x0682
BAG_ROOM_SIDE = (1756, 1412)  # in front of the door, in the bag room
DOORWAY = (1757, 1412)
VAULT_SIDE = (1758, 1412)     # just inside
GEMS_CHEST = '0x408FE3A0'     # column 5, bottom (1762,1402,26): the gem bag and the loose gem that marks it
BOOK_CHEST = '0x4058ABA9'     # ground floor, the top left chest by the stairs (1752,1402,14): the Gems runebook
GEMS = ('amber', 'amethyst', 'citrine', 'diamond', 'emerald', 'ruby', 'sapphire', 'star sapphire', 'tourmaline')

info = None


class Stop(Exception):
    """Something needs the user, or they took over: leave Clem as he is."""


def say(text):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + text
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def load_state():
    try:
        with open(STATE, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(state):
    uo.write_json(STATE, state, 1)


def call(method, endpoint, **params):
    try:
        return trips.call(method, endpoint, **params)
    except trips.Stop as e:
        raise Stop(str(e))


def status():
    return call('GET', '/status')


def texts(answer):
    return ' | '.join(m['text'] for m in answer.get('messages', []))


def kind(i):
    return (i.get('name') or i.get('type') or '').lower()


def is_gem(i):
    k = kind(i)
    return any(g in k for g in GEMS)


# ---- the vault door ----

def in_vault(st):
    return st['x'] >= 1758 and carto.floor_of(st['z']) == 2


def door_graphic():
    return int(call('GET', '/item', serial=VAULT_DOOR)['item']['graphic'], 16)


def step(p, why):
    """A plain walk on the second floor (carto.walk's hops go round the bag room's wall, which isn't here)."""
    call('POST', '/walk', x=p[0], y=p[1], distance=0, run=1)
    st = status()
    if (st['x'], st['y']) != p or carto.floor_of(st['z']) != 2:
        raise Stop(f"{why}: meant to be at {p[0]},{p[1]} on the second floor, but he's at {st['x']},{st['y']},{st['z']}")
    say(f'{why}: at {p[0]},{p[1]}')


def key(want):
    """The vault's key ring aimed at its door until the door says "You <want> it." (it turns the lock either way)."""
    for _ in range(2):
        a = call('POST', '/use', serial=VAULT_KEY)
        if not a.get('targeting'):
            raise Stop(f'the vault key ring gave no cursor: {texts(a)!r}')
        t = call('POST', '/target', serial=VAULT_DOOR)
        low = texts(t).lower()
        if f'you {want} it' in low:
            say(f'vault door: {texts(t)}')
            return
        if 'you lock it' in low or 'you unlock it' in low:
            say(f'vault door: {texts(t)} (it was already {want}ed; again)')
            continue
        raise Stop(f'the key at the vault door: {texts(t)!r}')
    raise Stop(f"couldn't {want} the vault door")


def use_door(shut):
    """Open or close the vault door; returns what was said. Leaves it as it is when it's that way already."""
    if (door_graphic() == SHUT) == shut:
        return 'already ' + ('shut' if shut else 'open')
    a = call('POST', '/use', serial=VAULT_DOOR)
    said = texts(a) or '(no message)'
    if (door_graphic() == SHUT) != shut:
        raise Stop(f'the vault door should be {"shut" if shut else "open"} but is {hex(door_graphic())}: {said}')
    say(f'vault door {"closed" if shut else "opened"}: {said}')
    return said


def lock_up(unlocked):
    """After anything going wrong at the door: the vault door locked and closed if at all possible. The key only when
    it's known to be unlocked (it turns the lock either way: on a locked door it would unlock it)."""
    try:
        st = status()
        if st.get('takenOver') or st.get('halted'):
            return
        if (st['x'], st['y']) not in (BAG_ROOM_SIDE, DOORWAY, VAULT_SIDE):
            return
        if unlocked:
            if (st['x'], st['y']) == VAULT_SIDE:  # the key can't be reached from inside the vault
                step(DOORWAY, 'into the doorway to lock up')
            key('lock')
        if (st['x'], st['y']) == DOORWAY or status()['x'] == DOORWAY[0]:
            step(BAG_ROOM_SIDE, 'out of the doorway')
        use_door(True)
    except (Stop, uo.BridgeError) as e:
        say(f'locking up after a problem: {e}')


def into_vault():
    trips.go_floor(2)
    carto.walk(*BAG_ROOM_SIDE)
    st = status()
    if (st['x'], st['y']) != BAG_ROOM_SIDE:
        step(BAG_ROOM_SIDE, 'to the vault door')
    if door_graphic() != SHUT:
        say(f'the vault door stands open ({hex(door_graphic())})')
    unlocked = False
    try:
        key('unlock')
        unlocked = True
        use_door(False)
        step(DOORWAY, 'into the doorway')
        key('lock')
        unlocked = False
        step(VAULT_SIDE, 'into the vault')
        use_door(True)
    except Stop:
        lock_up(unlocked)
        raise
    say('in the vault; its door locked and closed')


def last_message_id():
    msgs = call('GET', '/messages')['messages']
    return msgs[-1]['id'] if msgs else 0


def opening_since(after):
    """His client opened the door by itself as he walked up to it (auto_open_doors: "Opening door...", and the
    server's "That is locked, but is usable from the inside.")."""
    return any(m['id'] > after and ('opening door' in m['text'].lower() or 'usable from the inside' in m['text'].lower())
               for m in call('GET', '/messages')['messages'])


def out_of_vault():
    """The user, 2026-11-09: the vault door is locked, but usable from the inside: open it, go through, and it stays
    locked when it closes. No key on the way out: the key ring turns the lock either way, so aiming it at the locked
    door would unlock it (and from inside the vault it can't be reached anyway: "I can't reach that.", the wall)."""
    st = status()
    before = last_message_id()
    if (st['x'], st['y']) != VAULT_SIDE:
        step(VAULT_SIDE, 'to the vault door')
    try:
        # walking up to it, his client may have opened it already (20:48:03); its open graphic can come a moment
        # after the words, and using it then would shut it again (which happened once)
        if door_graphic() == SHUT and opening_since(before):
            end = time.time() + 2
            while door_graphic() == SHUT and time.time() < end:
                time.sleep(0.1)
        if door_graphic() == SHUT:
            use_door(False)  # "That is locked, but is usable from the inside."
        else:
            say('the vault door is open (his client opened it as he walked up)')
        step(DOORWAY, 'into the doorway')
        step(BAG_ROOM_SIDE, 'out of the vault')
        use_door(True)
        # the check, as the user does by walking into it: it must stay shut
        a = call('POST', '/use', serial=VAULT_DOOR)
        if door_graphic() != SHUT:
            say(f'the vault door OPENED from the bag room ({texts(a)!r}): locking and closing it again')
            key('lock')
            use_door(True)
            a = call('POST', '/use', serial=VAULT_DOOR)
            if door_graphic() != SHUT:
                use_door(True)
                raise Stop(f'the vault door still opens from the bag room: {texts(a)!r}')
        say(f'out of the vault; the door is locked and closed ({texts(a) or "no message"})')
    except Stop:
        lock_up(False)
        raise


# ---- the gems ----

def take_gem_bag(state):
    """The loose gem into the gem bag (onto its stack), then the bag into his pack. Returns the bag's serial."""
    call('POST', '/walk', to=GEMS_CHEST, distance=1, run=1)
    spot = uo.on_floor(info, GEMS_CHEST)
    if not spot or spot['distance'] > carto.REACH:
        raise Stop(f'could not get within reach of the gems chest: {spot}')
    call('POST', '/open', serial=GEMS_CHEST)
    items = call('GET', '/contents', serial=GEMS_CHEST, depth=1)['items']
    bags = [i for i in items if i.get('container')]
    loose = [i for i in items if not i.get('container')]
    say('gems chest: ' + ', '.join(f"{i['serial']} {kind(i) or i['graphic']}" + (f" x{i['amount']}" if i.get('amount') else '')
                                   for i in items))
    if len(bags) != 1:
        raise Stop(f'expected one gem bag in the gems chest, found {len(bags)}: {[b["serial"] for b in bags]}')
    bag = bags[0]['serial']
    call('POST', '/open', serial=bag)
    inside = call('GET', '/contents', serial=bag, depth=1)['items']
    gems_before = sum(i.get('amount') or 1 for i in inside)
    say(f'gem bag {bag}: ' + ', '.join(f"{i.get('amount') or 1} {kind(i) or i['graphic']}" for i in inside))
    for g in loose:
        same = [i for i in inside if i['graphic'] == g['graphic'] and i.get('hue') == g.get('hue')]
        if not same and not is_gem(g):
            say(f"left in the chest (not a gem): {g['serial']} {kind(g) or g['graphic']}")
            continue
        to = same[0]['serial'] if same else bag
        r = call('POST', '/move', serial=g['serial'], to=to)
        if not r.get('moved'):
            raise Stop(f"the loose {kind(g)} {g['serial']} didn't go into the gem bag: {r}")
        say(f"the loose {kind(g) or g['graphic']} ({g.get('amount') or 1}) into the gem bag" +
            (f" onto its stack {to}" if same else ''))
    call('POST', '/close', serial=GEMS_CHEST)
    trips.pick_up(bag)  # gets past Razor's auto-search of a bag landing in his pack
    if not trips.in_pack(bag):
        raise Stop(f'the gem bag {bag} is not in his pack')
    inside = call('GET', '/contents', serial=bag, depth=1)['items']
    count = sum(i.get('amount') or 1 for i in inside)
    tally = {}
    for i in inside:
        k = kind(i) or i['graphic']
        tally[k] = tally.get(k, 0) + (i.get('amount') or 1)
    state['bag'] = bag
    state['gems'] = tally
    save_state(state)
    say(f'the gem bag {bag} is in his pack: {count} gems ({gems_before} before the loose one): ' +
        ', '.join(f'{n} {k}' for k, n in state['gems'].items()))
    return bag


def take_runebook(state):
    trips.go_floor(1)
    _, items = trips.pack_list()
    known = state.get('runebook')
    if known and any(i['serial'] == known for i in trips.walk_items(items)):
        say(f'the Gems runebook {known} is in his pack already')
        return known
    carto.come_within_reach(BOOK_CHEST)
    call('POST', '/open', serial=BOOK_CHEST)
    inside = call('GET', '/contents', serial=BOOK_CHEST, depth=1)['items']
    books = [i['serial'] for i in inside if 'book' in kind(i)] or \
            [i['serial'] for i in inside if int(i['graphic'], 16) != trips.GOLD and not i.get('container')]
    if not books:
        raise Stop('no runebook in the top left chest by the stairs: ' + ', '.join(kind(i) or i['graphic'] for i in inside))
    found = None
    for a in call('POST', '/name', serial=','.join(books)):
        text = ' '.join(a.get('lines', []))
        say(f"in the chest: {a['serial']} \"{text}\"")
        if 'gem' in text.lower():
            found = a['serial']
    if not found:
        raise Stop('no runebook named for gems in the top left chest by the stairs')
    pack = status()['backpack']['serial']
    r = call('POST', '/move', serial=found, to=pack)
    if not r.get('moved') and not trips.in_pack(found):
        raise Stop(f'the Gems runebook {found} did not go into his pack: {r}')
    call('POST', '/close', serial=BOOK_CHEST)
    state['runebook'] = found
    save_state(state)
    say(f'the Gems runebook {found} is in his pack')
    return found


def fetch():
    state = load_state()
    st = status()
    if not trips.inside(st):
        raise Stop(f"he is not inside the tower ({st['x']},{st['y']},{st['z']})")
    _, items = trips.pack_list()
    say(f"--- getting ready to sell gems: at {st['x']},{st['y']},{st['z']}, {trips.count_items(items)} items in his "
        f"pack, {st.get('weight')}/{st.get('weightMax')} stones")
    bag = state.get('bag')
    if bag and trips.in_pack(bag):
        say(f'the gem bag {bag} is in his pack already')
        if in_vault(status()):
            out_of_vault()
    else:
        if not in_vault(status()):
            into_vault()
        take_gem_bag(state)
        out_of_vault()
    take_runebook(state)
    trips.go_floor(1)
    restock.ensure()
    trips.park()
    st = status()
    _, items = trips.pack_list()
    say(f"ready to sell: parked at {st['x']},{st['y']},{st['z']}, {trips.count_items(items)} items in his pack, "
        f"{st.get('weight')}/{st.get('weightMax')} stones, health {st['hits']}/{st['hitsMax']}, mana {st['mana']}")


def main():
    global info
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['fetch', 'vault-out', 'vault-test', 'runebook'])
    parser.add_argument('--resume', action='store_true', help='clear a takeover; only when the user hands him back')
    args = parser.parse_args()
    os.makedirs(WORK, exist_ok=True)
    info = uo.find_bridge(CHAR)
    trips.info = carto.info = door.info = restock.info = info
    st = fight.setup(info)
    stopped = st.get('takenOver') or st.get('halted')
    if stopped and not args.resume:
        sys.exit(f'the user has him ({stopped}); --resume only once they hand him back')
    if stopped:
        call('POST', '/resume')
        say(f'resumed: the user handed him back (was: {stopped})')
    try:
        if args.command == 'fetch':
            fetch()
        elif args.command == 'vault-test':
            if not in_vault(status()):
                into_vault()
            out_of_vault()
            st = status()
            say(f"vault test done: he stays at {st['x']},{st['y']},{st['z']}; the door's graphic {hex(door_graphic())} "
                f"(shut is {hex(SHUT)})")
        elif args.command == 'runebook':
            take_runebook(load_state())
            st = status()
            say(f"runebook test done: he stays at {st['x']},{st['y']},{st['z']}")
        else:
            out_of_vault()
    except (Stop, trips.Stop, door.Stop, restock.Stop) as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
    except SystemExit as e:
        if e.code not in (0, None):
            say(f'STOPPED: {e.code}')
        raise


if __name__ == '__main__':
    main()
