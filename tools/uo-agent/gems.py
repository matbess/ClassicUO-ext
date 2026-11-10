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
  python3 -I gems.py sell [--jewelers N]  phase 2, from inside the tower with the gems and the runebook: Recall to each
                                          jeweler in the Gems runebook in turn (the flag under the rune), sell the gems
                                          5 at a time until he refuses, the buy-window trick once an hour, sell again,
                                          on to the next; then home, fighting in as on the map trips (trips.py)
  python3 -I gems.py cleanup              phase 3 (also the end of every sell): the Gems runebook back in its chest by
                                          the stairs, the gem bag (gems left or not) back in the vault's gems chest,
                                          the vault door locked and checked, parked
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
import signal
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


def open_from_inside():
    """Open the (locked) vault door from inside. 2026-11-10 00:55: his client's auto-open opened it as he stepped up
    ("Opening door...", "That is locked, but is usable from the inside.") but its open graphic never reached his
    client; using it then closed it again, silently (opening from inside always says "usable from the inside"). So a
    use that leaves it shut without a word is taken as having shut it: wait a moment and use it once more."""
    for attempt in range(3):
        a = call('POST', '/use', serial=VAULT_DOOR)
        said = texts(a) or '(no message)'
        end = time.time() + 1.5
        while door_graphic() == SHUT and time.time() < end:
            time.sleep(0.2)
        if door_graphic() != SHUT:
            say(f'vault door opened: {said}')
            return
        say(f'the vault door still shows shut after using it ({said}): again')
    raise Stop(f'the vault door would not open from inside: {hex(door_graphic())}')


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
            open_from_inside()  # "That is locked, but is usable from the inside."
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
    if bags[0].get('x') is not None:
        state['bag_at'] = [bags[0]['x'], bags[0]['y']]  # where it goes back (cleanup)
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
    at = next((i for i in inside if i['serial'] == found), {})
    if at.get('x') is not None:
        state['runebook_at'] = [at['x'], at['y']]  # where it goes back (cleanup)
    pack = status()['backpack']['serial']
    r = call('POST', '/move', serial=found, to=pack)
    if not r.get('moved') and not trips.in_pack(found):
        raise Stop(f'the Gems runebook {found} did not go into his pack: {r}')
    call('POST', '/close', serial=BOOK_CHEST)
    state['runebook'] = found
    save_state(state)
    say(f'the Gems runebook {found} is in his pack')
    return found


# ---- phase 3: cleanup (the user, 2026-11-09) ----
# "The last part is the cleanup. You should go put the runebook back and put the gembag back. That will be the logic
# whether or not there are any gems left over, you just put them back in The Vault."

BOOK_CHEST_FROM = [(1752, 1407), (1752, 1403)]  # the stairs room, then in front of the chest wall (ground floor)
BAG_AT = [18, 105]  # the gem bag's spot in the gems chest (layout.json, 2026-11-09 20:30), when fetch didn't note one


def put_back(serial, chest, at, what):
    r = call('POST', '/move', serial=serial, to=chest, x=at[0], y=at[1])
    if trips.in_pack(serial):
        raise Stop(f'{what} {serial} did not go back into {chest}: {r}')
    say(f'{what} {serial} back in {chest} at {at[0]},{at[1]}')


def cleanup(state):
    """The Gems runebook back in the top left chest by the stairs, the gem bag (gems left in it or not) back in the
    vault's gems chest, the vault door locked and closed and checked; parked."""
    st = status()
    if not trips.inside(st):
        raise Stop(f"cleanup is done inside the tower ({st['x']},{st['y']},{st['z']})")
    book = state.get('runebook')
    if book and trips.in_pack(book):
        trips.go_floor(1)
        st = status()
        if not (st['y'] >= 1410 or st['x'] <= 1753):
            # from the smithy (the gold chest) by way of the hall: a hop straight for the stairs room cut across
            # tiles outside his areas (2026-11-09 21:49, "that spot is outside the agent's area")
            door.walk((1753, 1410))
        # in front of the chest on the ground floor: a walk to "next to the chest" from the hall ended on the top
        # step of the stairs beside it (1751,1403, z 23) and the server said "I can't reach that." (2026-11-09 21:49)
        for p in BOOK_CHEST_FROM:
            door.walk(p)
        st = status()
        if (st['x'], st['y']) != BOOK_CHEST_FROM[-1] or st['z'] > 15:
            raise Stop(f"meant to stand in front of the chest by the stairs at {BOOK_CHEST_FROM[-1]}, but he's at "
                       f"{st['x']},{st['y']},{st['z']}")
        inside = carto.contents(BOOK_CHEST)
        at = state.get('runebook_at')
        if not at:
            books = [i for i in inside if 'book' in kind(i) and i.get('x') is not None]
            last = max(books, key=lambda i: i['x']) if books else {'x': 44, 'y': 70}
            at = [min(last['x'] + 14, 130), last['y']]  # beside the other runebooks
        put_back(book, BOOK_CHEST, at, 'the Gems runebook')
        call('POST', '/close', serial=BOOK_CHEST)
    bag = state.get('bag')
    if bag and trips.in_pack(bag):
        left = gems_carried()
        if not in_vault(status()):
            into_vault()
        call('POST', '/walk', to=GEMS_CHEST, distance=1, run=1)
        spot = uo.on_floor(info, GEMS_CHEST)
        if not spot or spot['distance'] > carto.REACH:
            raise Stop(f'could not get within reach of the gems chest: {spot}')
        call('POST', '/open', serial=GEMS_CHEST)
        put_back(bag, GEMS_CHEST, state.get('bag_at') or BAG_AT, f'the gem bag ({left} gems in it)')
        call('POST', '/close', serial=GEMS_CHEST)
        out_of_vault()
    trips.go_floor(1)
    trips.park()
    st = status()
    _, items = trips.pack_list()
    say(f"cleanup done: parked at {st['x']},{st['y']},{st['z']}, {trips.count_items(items)} items in his pack, "
        f"{st['weight']}/{st['weightMax']} stones")


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


# ---- phase 2: selling to the jewelers (the user, 2026-11-09) ----
#
# "There are 7 jewelers in the book ... First, you recall to the npc, then you find the npc with the jeweler title and
# get near them and say "____ sell" and you sell as many gems as you can, 5 at a time. The npc will run out of money at
# some point and may already be out of money and refuse to buy anything. Once they are out of money you can do a trick
# one time (only works once per hour I think). when they refuse to buy gems you say "____ buy" and wait for the buy
# screen to open, then you close the buy screen. Once it's closed the npc will have a bit more money available to them.
# Then you go back and do "____ sell" again ... until they won't buy anymore. Once they refuse to buy again, it's time
# to move onto the next NPC. Now, it is possible that someone else was just selling and they will refuse to buy even
# if you do the trick ... So you just go to each of the 7 NPCs and do this same thing until all of the gems are gone
# or they all refuse to buy anymore then you come back to the tower (using the same logic carto did)."
# Recall with the flag under each rune in the book (its Recall button), never the book's charges (it has none).

VENDORS = os.path.join(WORK, 'vendors.json')  # the shops' NPCs, the jewelers, when each one's trick was last used
VISITS = os.path.join(WORK, 'visits.jsonl')   # every jeweler visit: what he'd buy and at what price, sold, gold
GEM_GRAPHICS = {0x0F15, 0x0F19, 0x0F26, 0x0F21, 0x0F13, 0x0F10, 0x0F16, 0x0F2D, 0x0F25}
SELL_AT_ONCE = 5             # "5 at a time" (the user; the server, 2026-11-08: "You may only sell 5 items at a time!")
TRICK_EVERY = 60 * 60        # the buy-window trick works once an hour per jeweler (the user: "I think")
JEWELER_RANGE = 12           # jewelers this close after landing are sold to (several in one shop: each of them)
LANDING_SLACK = 20           # he must land this close to the spot the book gives for the rune
RECALL = 3                   # a rune's buttons in the book (RunUO's runebook): 2 + 6 * slot + 0 use a charge, 1 drop
                             # the rune, 2 set default, 3 Recall (the flag under the rune), 4 Gate Travel
ONWARD_MANA = 11 + 14 + 11 + 5  # on to the next town: that Recall, then Magic Reflection and Recall home from there
FRIENDS = ('icepick', 'burgers', "here's johnny", 'johnny', 'isabel', 'clem')  # the user's characters aren't strangers
PLAYER_WAITS = 3             # a player in town: home, 15 minutes inside, again; at most this many times a run
# the gold (the user, 2026-11-09, after the first tour ended at 389 of 390 stones: "As soon as he gets to within 10
# stones of his max weight then recall home and put the gold in the bottom chest next to the forge ... then you can go
# back to the tour starting by returning to the same vendor you were in the middle of talking to")
GOLD_CHEST = '0x4074A4C1'    # the bottom of the three chests stacked by the forge (1757,1407, z 6; the forge is
                             # 0x408A3611 at 1755,1410): its gold stack (0x4079447D, 24,900 after the first tour)
WEIGHT_MARGIN = 10           # stones under his max at which he takes the gold home
COINS_PER_STONE = 50         # 15,517 gold weighed about 310 stones (2026-11-09)
GOLD_RUNS = 6                # at most this many trips home with gold in one run
MAX_STACK = 60000
stopping = {'flag': False}


class PlayerInTown(Exception):
    pass


class LeaveTown(Exception):
    """Something in town that means going home now (landed somewhere else, no Recall onward, ...)."""


class GoldRun(LeaveTown):
    """Within WEIGHT_MARGIN stones of his max: home with the gold, then back to the same jeweler."""


def gold_room():
    """How much more gold he can take before he's within WEIGHT_MARGIN stones of his max."""
    st = status()
    return (st['weightMax'] - WEIGHT_MARGIN - st['weight']) * COINS_PER_STONE


def plain(text):
    import re
    return re.sub('<[^>]+>', '', text or '').strip()


def sextant(lat, lon):
    """The map spot of a runebook entry's sextant coordinates ("5° 21'S", "9° 21'E"; RunUO's Sextant, map 0: the
    centre at 1323,1624, 5120 x 4096 tiles)."""
    import re
    a = re.match(r"(\d+)\D+(\d+)'([NS])", lat or '')
    b = re.match(r"(\d+)\D+(\d+)'([EW])", lon or '')
    if not a or not b:
        return None
    la = (int(a.group(1)) + (int(a.group(2)) + 0.5) / 60) * (-1 if a.group(3) == 'N' else 1)
    lo = (int(b.group(1)) + (int(b.group(2)) + 0.5) / 60) * (-1 if b.group(3) == 'W' else 1)
    return [round(1323 + lo * 5120 / 360) % 5120, round(1624 + la * 4096 / 360) % 4096]


def open_book(state):
    book = state.get('runebook')
    if not book or not trips.in_pack(book):
        raise Stop('the Gems runebook is not in his pack (gems.py fetch first)')
    a = call('POST', '/use', serial=book)
    for d in a.get('dialogs', []) + call('GET', '/gumps')['dialogs']:
        if d.get('kind') == 'gump' and any('rename book' in plain(b.get('label')).lower() for b in d.get('buttons', [])):
            return d
    raise LeaveTown(f'the runebook showed no gump: {texts(a)!r}')


def close_book(g):
    try:
        call('POST', '/gump', serial=g['serial'], id=g['id'], button=0)
    except uo.BridgeError as e:
        say(f'closing the runebook: {e}')


def book_entries(g):
    """The book's runes: slot, name, and the spot its sextant coordinates give."""
    entries = {}
    for b in g.get('buttons', []):
        n, name = b['button'], plain(b.get('label'))
        if n >= 2 and (n - 2) % 6 == 0 and name and name.lower() != 'empty' and (n - 2) // 6 not in entries:
            slot = (n - 2) // 6
            page, x = slot // 2 + 2, 135 if slot % 2 == 0 else 295
            at = {t['y']: plain(t['text']) for t in g.get('texts', []) if t['page'] == page and t['x'] == x}
            entries[slot] = {'slot': slot, 'name': name, 'spot': sextant(at.get(80), at.get(95))}
    return [entries[s] for s in sorted(entries)]


def recall_to(state, entry):
    """Recall with the flag under the rune (never the book's charges); /status once he has landed by the rune."""
    for attempt in range(3):
        st0 = status()
        if st0['mana'] < 11:
            raise LeaveTown(f'no mana to Recall to {entry["name"]} ({st0["mana"]})')
        g = open_book(state)
        before = last_message_id()
        try:
            call('POST', '/gump', serial=g['serial'], id=g['id'], button=2 + 6 * entry['slot'] + RECALL)
        except uo.BridgeError as e:
            say(f'Recall to {entry["name"]}: {e}')
            continue
        end = time.time() + 8
        said = ''
        while time.time() < end:
            st = status()
            if abs(st['x'] - st0['x']) + abs(st['y'] - st0['y']) > 10:
                spot = entry.get('spot')
                off = max(abs(st['x'] - spot[0]), abs(st['y'] - spot[1])) if spot else 0
                say(f"Recall to {entry['name']}: at {st['x']},{st['y']},{st['z']}" +
                    (f' ({off} tiles from the spot the book gives)' if spot else ''))
                if off > LANDING_SLACK:
                    raise LeaveTown(f"landed at {st['x']},{st['y']}, {off} tiles from {entry['name']}'s spot {spot}")
                return st
            msgs = [m['text'] for m in call('GET', '/messages')['messages'] if m['id'] > before]
            said = ' | '.join(msgs)
            if any(w in said.lower() for w in ('fizzle', 'disturbed', 'more reagents', 'insufficient mana',
                                               'not yet recovered', 'already casting', 'cannot')):
                break
            time.sleep(0.15)
        say(f'Recall to {entry["name"]} did not take him: {said or "-"}')
        time.sleep(1.5)
    raise LeaveTown(f'Recall to {entry["name"]} failed three times')


def load_vendors():
    try:
        with open(VENDORS, encoding='utf-8') as fh:
            v = json.load(fh)
    except (OSError, ValueError):
        v = {}
    for k in ('npcs', 'players', 'tricks', 'jewelers'):
        v.setdefault(k, {})
    return v


def titles(v, serials):
    """Paperdoll titles, one person at a time, only for paperdolls that came: someone who has walked off before his
    paperdoll is asked for (the bridge's 404 "no such person nearby", or 409 too far) or whose paperdoll doesn't come is
    left out, not taken for trouble (2026-11-09 21:26:54 in Britain: a 404 ended the tour at once)."""
    out = {}
    for serial in serials:
        try:
            for a in call('POST', '/paperdoll', serial=serial):
                if a.get('answered'):
                    out[a['serial']] = (a.get('title') or '').strip()
        except uo.BridgeError as e:
            if e.code not in (404, 409):
                raise
            say(f'paperdoll of {serial}: {e.message} (skipped)')
    return out


def strangers(v, me):
    """Players in sight: anyone human who isn't known to be an NPC (trips.strangers, but someone whose paperdoll
    doesn't come back is asked again next time rather than taken for a player; after three tries they count as one).
    Vendors (yellow, invulnerable) and the user's own characters are never strangers."""
    near = call('GET', '/nearby', range=trips.SIGHT)['mobiles']
    people = [m for m in near if m.get('human') and not m.get('dead') and m['serial'] != me
              and m.get('notoriety') != 'Invulnerable' and (m.get('name') or '').strip().lower() not in FRIENDS]
    npcs = trips.known_npcs(v)
    unknown = [m for m in people if m['serial'] not in npcs and m['serial'] not in v['players']]
    if unknown:
        seen = {m['serial']: m['title'] for m in unknown if m.get('title')}
        seen.update(titles(v, [m['serial'] for m in unknown if m['serial'] not in seen]))
        tries = v.setdefault('unanswered', {})
        for m in unknown:
            serial = m['serial']
            if serial not in seen:
                tries[serial] = tries.get(serial, 0) + 1
                if tries[serial] < 3:
                    continue
            title = seen.get(serial) or ''
            if title and trips.NPC_LABEL.search(title):
                v['npcs'][serial] = title
                say(f'NPC: {title} ({serial})')
            else:
                v['players'][serial] = title or m.get('name') or '?'
                say(f'not an NPC: "{title or m.get("name")}" ({serial}, {m.get("distance")} tiles)')
        trips.save_vendor(v)
        npcs = trips.known_npcs(v)
    return [m for m in people if m['serial'] not in npcs and (m['serial'] in v['players']
                                                             or v.get('unanswered', {}).get(m['serial'], 0) >= 3)]


# shops where the jeweler can't be reached straight from where the rune lands (the user, 2026-11-09: "This particular
# vendor is tricky, in trinsic it can go upstairs. It's upstairs so you can't talk to Marnie without coming up the
# stairs"; "Go in the room with marnie"): his room (x1, y1, x2, y2, z1, z2: only in there does he hear "<name> sell";
# from beside his wall he didn't answer), and the way in: "up" from the ground floor, then "in" on his floor, each step
# its own tile (the path finder ends a walk at the goal's x,y on whatever floor it reaches first: a walk straight to
# Marnie from the top of the stairs went back down them, over and over, 2026-11-09 21:35), "door:SERIAL:SHUT" opened
# when its graphic is SHUT (the door has to be in his rules' "doors": the client's path finder takes a shut door for a wall)
SHOP_ROOMS = {
    # Marnie the jeweler, upper floor (z 20): the stairs inside the shop climb north at x 1891 (z 0 at 1891,2807, z 20
    # at 1891,2803), her door 0x4000FCF3 is at 1896,2806 in the wall along x 1896 (shut 0x06AD, open 0x06AE)
    'Trinsic Gems': {'room': (1897, 2801, 1905, 2812, 15, 35),
                     'up': [(1891, 2808), (1891, 2807), (1891, 2805), (1891, 2803)],
                     'in': [(1893, 2804), (1895, 2806), 'door:0x4000FCF3:0x06AD', (1897, 2805)]},
}
here = {'entry': None}  # the rune he's at now (for its shop's way in)


def in_room(st, room):
    x1, y1, x2, y2, z1, z2 = room
    return x1 <= st['x'] <= x2 and y1 <= st['y'] <= y2 and z1 <= st['z'] <= z2


def into_room(shop):
    st = status()
    walk_steps((shop['up'] if st['z'] < shop['room'][4] - 8 else []) + shop['in'])
    st = status()
    if not in_room(st, shop['room']):
        raise trips.GoHome(f"the way in didn't get him into the jeweler's room: he's at {st['x']},{st['y']},{st['z']}")
    say(f"in the jeweler's room: at {st['x']},{st['y']},{st['z']}")


def out_of_room(shop):
    """Back down to the shop floor the way he came up (the jeweler came down while he was up there)."""
    st = status()
    back = list(reversed(shop['in'][:-1])) if in_room(st, shop['room']) else []
    walk_steps(back + list(reversed(shop['up'])))
    st = status()
    if st['z'] >= shop['room'][4] - 8:
        raise trips.GoHome(f"the way down from the jeweler's room left him upstairs at {st['x']},{st['y']},{st['z']}")
    say(f"down from the jeweler's room: at {st['x']},{st['y']},{st['z']}")


def walk_steps(steps):
    for step in steps:
        if isinstance(step, str) and step.startswith('door:'):
            _, serial, shut = step.split(':')
            before = call('GET', '/item', serial=serial)['item']
            if int(before['graphic'], 16) != int(shut, 16):
                say(f"door {serial} is open already ({before['graphic']})")
                continue
            a = call('POST', '/use', serial=serial)
            after = call('GET', '/item', serial=serial)['item']
            say(f"door {serial}: {before['graphic']} -> {after['graphic']}" + (f' ({texts(a)})' if texts(a) else ''))
            continue
        try:
            call('POST', '/walk', x=step[0], y=step[1], distance=0, run=1)
        except uo.BridgeError as e:
            raise trips.GoHome(f'the way to or from the jeweler\'s room, at {step[0]},{step[1]}: {e}')


def approach(vendor):
    """trips.approach, into the jeweler's room first where his shop needs it (SHOP_ROOMS); a jeweler on another
    floor with no known way in: on to the next one (a GoHome there)."""
    m = next((m for m in call('GET', '/nearby', range=trips.SIGHT)['mobiles'] if m['serial'] == vendor), None)
    if not m:
        raise trips.GoHome('the jeweler is out of sight')
    st = status()
    name = (here['entry'] or {}).get('name')
    shop = SHOP_ROOMS.get(name)
    if shop:
        # up to her room only when she's up there: 2026-11-10 01:01 Marnie was downstairs, 2 tiles from the landing,
        # and he went up and called down to her, unheard, until he gave up (her trick used for nothing)
        up_there = (m.get('z') or 0) >= shop['room'][4] - 8
        upstairs = st['z'] >= shop['room'][4] - 8
        if up_there and not in_room(st, shop['room']):
            into_room(shop)
        elif not up_there and upstairs:
            out_of_room(shop)
    elif abs((m.get('z') or 0) - st['z']) > 10:
        raise trips.GoHome(f'{m.get("name")} is on another floor (z {m.get("z")}, he is at {st["z"]}) and no way '
                           f'there is known for {name}')
    m = next((m for m in call('GET', '/nearby', range=trips.SIGHT)['mobiles'] if m['serial'] == vendor), m)
    if m.get('distance', 99) > trips.TALK_RANGE:
        # 2 tiles first; a vendor answers from 3, so from there when there's no path closer (2026-11-09 21:39, the
        # Vesper jeweler 4 tiles off: "no path to there", likely behind his counter)
        for reach in (trips.TALK_RANGE, 3):
            try:
                call('POST', '/walk', x=m['x'], y=m['y'], distance=reach)
                break
            except uo.BridgeError as e:
                if reach == 3:
                    raise trips.GoHome(f'no way to the jeweler at {m["x"]},{m["y"]}: {e}')
                say(f'no path to within {reach} of {m.get("name")} at {m["x"]},{m["y"]} ({e}); trying 3')


def check_town(v, me):
    """A player in sight: home at once (the user, 2026-11-08)."""
    found = strangers(v, me)
    if found:
        who = ', '.join(f'{m.get("name") or "?"} ({m["serial"]}, {m.get("distance")} tiles)' for m in found)
        raise PlayerInTown(f'a player in town: {who}')


def gems_carried():
    _, items = trips.pack_list()
    return sum(i.get('amount') or 1 for i in trips.walk_items(items) if int(i['graphic'], 16) in GEM_GRAPHICS)


def find_jewelers(v, me):
    """The NPCs titled "jeweler" near him, nearest first. Anyone close whose title isn't known yet (NPCs the bridge
    learned by their fidgeting count as NPCs without one) gets their paperdoll looked at."""
    near = [m for m in call('GET', '/nearby', range=trips.SIGHT)['mobiles']
            if m.get('human') and not m.get('dead') and m['serial'] != me]
    untitled = [m['serial'] for m in near if m.get('distance', 99) <= JEWELER_RANGE
                and not trips.NPC_LABEL.search(v['npcs'].get(m['serial'], ''))]
    if untitled:
        for serial, title in titles(v, untitled).items():
            if title and trips.NPC_LABEL.search(title):
                v['npcs'][serial] = title
        trips.save_vendor(v)
    found = [m for m in near if ' the jeweler' in v['npcs'].get(m['serial'], '').lower()
             and m.get('distance', 99) <= JEWELER_RANGE]
    return sorted(found, key=lambda m: m.get('distance', 99))


def sell_round(serial, too_dear):
    """One "<name> sell" and one sale: the most valuable batch (5 of one kind, fewer when the stack is short, then
    single gems) that costs him less than the cheapest sale he has refused so far, `too_dear` (he runs out of money: a
    refused 5 diamonds can still leave enough for rubies or a single gem). Returns (sold, what was said, the prices he
    offered by kind, what the sale tried cost, whether there was anything left to try)."""
    try:
        r = trips.shop(serial, 'sell')
    except trips.GoHome as e:  # no answer at all, three times
        return 0, str(e), {}, 0, False
    rows = [i for i in r.get('items', []) if int(i['graphic'], 16) in GEM_GRAPHICS]
    prices = {i.get('name') or i['graphic']: i.get('price') for i in rows}
    if not rows:
        if r.get('open'):
            call('POST', '/shop', close=1)
        return 0, texts(r) or ('his sell list has no gems' if r.get('open') else 'no sell window'), prices, 0, False
    rows.sort(key=lambda i: -(i.get('price') or 0))
    tries = [(i, min(i['amount'], SELL_AT_ONCE)) for i in rows] + [(i, 1) for i in rows]
    tries = [(i, n) for i, n in tries if (i.get('price') or 0) * n < too_dear]
    room = gold_room()
    pick = next(((i, n) for i, n in tries if (i.get('price') or 0) * n <= room), None)
    if tries and not pick:
        call('POST', '/shop', close=1)
        raise GoldRun(f'his gold is getting heavy ({status()["weight"]} of {status()["weightMax"]} stones): '
                      f'home with it, then back to this jeweler')
    if not pick:
        call('POST', '/shop', close=1)
        return 0, f'not even one {rows[-1].get("name")} (refused at {too_dear} gold)', prices, 0, False
    i, n = pick
    s = trips.at_him(serial, '/sell', items=f"{i['serial']}:{n}")
    sold = s.get('sold', 0)
    if sold:
        say(f"sold {sold} {i.get('name')} at {i.get('price')} ({sold * (i.get('price') or 0)} gold)" +
            (f' of {n} offered' if sold < n else ''))
    return sold, texts(s), prices, (i.get('price') or 0) * n, True


def buy_trick(serial, label):
    """The user's trick: "<name> buy", wait for the buy window, close it: he has a bit more money after."""
    r = trips.at_him(serial, '/shop', vendor=serial, mode='buy')
    say(f'the trick at {label}: "{r.get("said")}": ' +
        (f'his buy window ({len(r.get("items", []))} items)' if r.get('open') else 'no buy window') +
        (f'; he said: {texts(r)}' if texts(r) else '') + '; closing it')
    call('POST', '/shop', close=1)


def sell_to(v, me, jeweler, entry):
    serial = jeweler['serial']
    label = v['npcs'].get(serial, serial)
    v['jewelers'][serial] = {'title': label, 'rune': entry['name'], 'at': [jeweler['x'], jeweler['y']]}
    if not jeweler.get('title'):
        titles(v, [serial])  # the client forgets his title once Clem has left town; the bridge needs it
    last = v['tricks'].get(serial, 0)
    trick_ok = time.time() - last > TRICK_EVERY
    gold0, gems0 = trips.gold_carried(), gems_carried()
    say(f'{label} ({serial}, {jeweler.get("distance")} tiles), {entry["name"]}: {gems0} gems to sell, {gold0} gold; '
        f'the trick ' + ('free' if trick_ok else f'used {(time.time() - last) / 60:.0f} min ago'))
    tricked, sold, refusals, prices = False, 0, [], {}
    too_dear = float('inf')
    try:
        while not stopping['flag']:
            if gems_carried() == 0:
                say('every gem is sold')
                break
            check_town(v, me)
            n, why, offered, cost, more = sell_round(serial, too_dear)
            prices.update(offered)
            if n:
                sold += n
                continue
            if more:
                # refused a sale of `cost` gold: something cheaper next. He says what he can still pay ("Sorry, I
                # cannot afford but 203 gold at this time.", 2026-11-09): then straight to a sale within that
                import re
                can = re.search(r'cannot afford but (\d+) gold', why or '')
                too_dear = min(cost, int(can.group(1)) + 1) if can else cost
                say(f'{label} refused a sale of {cost} gold: {why or "(nothing said)"}; trying cheaper')
                continue
            refusals.append(why)
            say(f'{label} buys nothing more: {why or "(nothing said)"}')
            if tricked or not trick_ok:
                break
            if 'no answer' in (why or '').lower():
                # he never heard "<name> sell" (another floor, a wall): asking "<name> buy" won't reach him either,
                # and the trick is once an hour (2026-11-10 01:01, Marnie: used for nothing)
                say(f'{label} never answered: keeping the trick for when he can hear')
                break
            buy_trick(serial, label)
            tricked = True
            too_dear = float('inf')
            v['tricks'][serial] = time.time()
            trips.save_vendor(v)
    except trips.GoHome as e:  # he wandered out of sight, or no way to him: on to the next jeweler
        refusals.append(str(e))
        say(f'{label}: {e}; on to the next')
    except (GoldRun, PlayerInTown) as e:  # leaving town in the middle of this one: logged all the same
        refusals.append(f'left: {e}')
        raise
    finally:
        try:
            gold = trips.gold_carried()
            say(f'{label}: sold {sold} gems for {gold - gold0} gold' + (' (the trick used)' if tricked else ''))
            row = {'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'rune': entry['name'], 'jeweler': serial,
                   'title': label, 'sold': sold, 'gold': gold - gold0, 'gold_carried': gold,
                   'gems_left': gems_carried(), 'prices': prices, 'trick': tricked, 'trick_was_free': trick_ok,
                   'refusals': refusals}
            with open(VISITS, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(row) + '\n')
            trips.save_vendor(v)
        except Exception as e:  # the log mustn't get in the way of leaving town
            say(f'logging the visit: {e!r}')
    return sold


def deposit_gold(tour):
    """All the gold he carries onto the gold in the bottom chest by the forge (the user, 2026-11-09), then parked."""
    gold = trips.gold_carried()
    if not gold:
        return 0
    trips.go_floor(1)
    call('POST', '/walk', to=GOLD_CHEST, distance=1, run=1)
    spot = uo.on_floor(info, GOLD_CHEST)
    if not spot or spot['distance'] > carto.REACH:
        raise Stop(f'could not get within reach of the gold chest by the forge: {spot}')
    piles = [i for i in carto.contents(GOLD_CHEST) if int(i['graphic'], 16) == trips.GOLD]
    _, items = trips.pack_list()
    mine = sorted((i for i in trips.walk_items(items) if int(i['graphic'], 16) == trips.GOLD),
                  key=lambda i: -(i.get('amount') or 1))
    for g in mine:
        amount = g.get('amount') or 1
        fits = [p for p in piles if (p.get('amount') or 1) + amount <= MAX_STACK]
        onto = max(fits, key=lambda p: p.get('amount') or 1)['serial'] if fits else GOLD_CHEST
        r = call('POST', '/move', serial=g['serial'], to=onto)
        if not r.get('moved'):
            raise Stop(f'his gold {g["serial"]} ({amount}) did not go into the chest by the forge: {r}')
    call('POST', '/close', serial=GOLD_CHEST)
    left = trips.gold_carried()
    put = gold - left
    tour['deposited'] = tour.get('deposited', 0) + put
    st = status()
    in_chest = sum(i.get('amount') or 1 for i in carto.contents(GOLD_CHEST) if int(i['graphic'], 16) == trips.GOLD)
    say(f"put {put} gold in the chest by the forge ({in_chest} there now); he weighs {st['weight']} of {st['weightMax']}")
    trips.park()
    return put


def meditate_in_town(v, me, want):
    say(f'meditating in the shop (mana {status()["mana"]}, want {want} to go on)')
    end, last = time.time() + 180, 0
    while status()['mana'] < want and time.time() < end:
        check_town(v, me)
        if time.time() - last > 11:
            last = time.time()
            try:
                call('POST', '/skill', id=trips.MEDITATION)
            except uo.BridgeError as e:
                say(f'meditation: {e}')
        time.sleep(2)
    say(f'mana {status()["mana"]}')


def tower_rune():
    """His rune home ("a recall rune for Outpost", in his reagent bag), found by its name."""
    carto.contents(restock.BAG)
    _, items = trips.pack_list()
    runes = [i['serial'] for i in trips.walk_items(items) if int(i['graphic'], 16) in (0x1F14, 0x1F15, 0x1F16, 0x1F17)]
    for a in call('POST', '/name', serial=','.join(runes)) if runes else []:
        if 'outpost' in ' '.join(a.get('lines', [])).lower():
            trips.TOWER_RUNE = a['serial']
            return a['serial']
    raise Stop('no rune home ("Outpost") in his pack')


def sell(state, limit=None):
    """The tour: every jeweler in the book in turn until the gems are gone or every one refuses, then home."""
    trips.VENDOR = VENDORS
    v = load_vendors()
    st = status()
    if gems_carried() == 0 and trips.inside(st):
        raise Stop('no gems in his pack (gems.py fetch first)')
    home = tower_rune()
    g = open_book(state)
    entries = book_entries(g)
    close_book(g)
    say('the Gems runebook: ' + ', '.join(f"{e['name']} {e['spot']}" for e in entries) + f'; home: {home}')
    # handed back in town (the user took over at a jeweler): carry on from there, no Recall to it
    start_here = None
    if not trips.inside(st):
        start_here = next((e for e in entries if e.get('spot') and max(abs(st['x'] - e['spot'][0]),
                                                                      abs(st['y'] - e['spot'][1])) <= LANDING_SLACK), None)
        if not start_here:
            raise Stop(f"he is neither inside the tower nor at a jeweler in the book ({st['x']},{st['y']},{st['z']})")
        say(f"starting in town, at {start_here['name']} ({st['x']},{st['y']},{st['z']})")
    tour = state.get('tour') or {'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'done': [], 'gold0': trips.gold_carried(),
                                 'gems0': gems_carried()}
    state['tour'] = tour
    save_state(state)
    waits = 0
    while True:
        todo = [e for e in entries if e['slot'] not in tour['done']]
        if start_here:
            todo = [start_here] + [e for e in todo if e['slot'] != start_here['slot']]
        todo = todo[:limit]
        if not todo or (gems_carried() == 0 and not start_here) or stopping['flag']:
            break
        if not start_here:
            trips.ready_to_leave()
        _, items = trips.pack_list()
        say(f"--- off to sell: {gems_carried()} gems, {trips.gold_carried()} gold, {trips.count_items(items)} items, "
            f"mana {status()['mana']}; jewelers to go: {', '.join(e['name'] for e in todo)}")
        away, player, gold_run = bool(start_here), None, False
        me = status()['serial']
        try:
            for entry in todo:
                if gems_carried() == 0 or stopping['flag']:
                    break
                if entry is start_here:
                    start_here = None
                    st = status()
                else:
                    if away and gold_room() < SELL_AT_ONCE * 150:
                        raise GoldRun(f'his gold is getting heavy ({status()["weight"]} of {status()["weightMax"]} '
                                      f'stones): home with it before the next jeweler')
                    if away and status()['mana'] < ONWARD_MANA:
                        meditate_in_town(v, me, ONWARD_MANA)
                        if status()['mana'] < ONWARD_MANA:
                            raise LeaveTown(f'not enough mana to go on ({status()["mana"]})')
                    try:
                        st = recall_to(state, entry)
                    except LeaveTown:
                        if away:
                            raise
                        raise Stop(f'could not Recall to {entry["name"]} from the tower')
                away, me = True, st['serial']
                here['entry'] = entry
                check_town(v, me)
                jewelers = find_jewelers(v, me)
                if not jewelers:
                    say(f'no jeweler near where {entry["name"]} lands')
                for j in jewelers:
                    if gems_carried() == 0 or stopping['flag']:
                        break
                    sell_to(v, me, j, entry)
                tour['done'].append(entry['slot'])
                save_state(state)
        except PlayerInTown as e:
            player = str(e)
            say(f'leaving town: {e}')
        except GoldRun as e:
            gold_run = True
            say(f'leaving town: {e}')
        except (LeaveTown, trips.GoHome) as e:
            say(f'leaving town: {e}')
        except uo.BridgeError as e:
            if not away:
                raise
            say(f'in town: {e}; going home')
        except (Stop, trips.Stop) as e:
            if not away:
                raise
            st = uo.call(info, 'GET', '/status')
            if st.get('takenOver') or not st.get('halted'):
                raise  # the user has him (or something else): leave him as he is
            # a stop the bridge made itself (no answer from the server) mustn't leave him standing in town
            uo.call(info, 'POST', '/resume')
            say(f'in town the bridge stopped ({st.get("halted")}): resumed, going home')
        except Exception as e:  # anything unforeseen (a bug too) mustn't leave him standing in town
            if not away:
                raise
            import traceback
            say(f'in town, something unexpected: {e!r}; going home\n{traceback.format_exc()}')
        if away:
            try:
                call('POST', '/shop', close=1)
            except uo.BridgeError:
                pass
            trips.home_and_in()
        if gold_run:
            deposit_gold(tour)
            save_state(state)
            tour['gold_runs'] = tour.get('gold_runs', 0) + 1
            if tour['gold_runs'] > GOLD_RUNS:
                say('too many trips home with gold in one run: the tour stops here')
                break
            say('back to the jeweler he was selling to')
            continue
        if not player:
            break
        waits += 1
        if waits > PLAYER_WAITS:
            say('players in town again and again: the tour stops here')
            break
        say(f'a player was in town: {trips.PLAYER_WAIT // 60} minutes inside before going on')
        end = time.time() + trips.PLAYER_WAIT
        while time.time() < end and not stopping['flag']:
            st = status()
            if st.get('takenOver') or st.get('halted'):
                raise Stop(st.get('takenOver') or st.get('halted'))
            time.sleep(10)
    deposit_gold(tour)  # the gold goes into the chest by the forge at the end too
    gold, left = trips.gold_carried() + tour.get('deposited', 0), gems_carried()
    say(f"=== tour over: sold {tour['gems0'] - left} of {tour['gems0']} gems for {gold - tour['gold0']} gold "
        f"({tour.get('deposited', 0)} put in the chest by the forge); "
        f"{left} gems left; jewelers visited: {', '.join(e['name'] for e in entries if e['slot'] in tour['done'])}")
    if not stopping['flag'] or not left:
        state.pop('tour', None)
        save_state(state)
    st = status()
    say(f"parked at {st['x']},{st['y']},{st['z']}, health {st['hits']}/{st['hitsMax']}, mana {st['mana']}")
    cleanup(state)  # the runebook and the gem bag back where they came from, gems left or not (the user)


def on_term(signum, frame):
    stopping['flag'] = True
    say('asked to stop: finishing with this jeweler, then home')



def main():
    global info
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['fetch', 'sell', 'cleanup', 'vault-out', 'vault-test', 'runebook'])
    parser.add_argument('--jewelers', type=int, help='sell: only the first N jewelers in the book not yet done')
    parser.add_argument('--resume', action='store_true', help='clear a takeover; only when the user hands him back')
    args = parser.parse_args()
    os.makedirs(WORK, exist_ok=True)
    info = uo.find_bridge(CHAR)
    trips.info = carto.info = door.info = restock.info = info
    trips.LOG = carto.LOG = LOG  # the trip code borrowed from the map trips logs into gems.log
    trips.approach = approach    # up to a jeweler on another floor (Trinsic) by the shop's way up
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
        elif args.command == 'cleanup':
            cleanup(load_state())
        elif args.command == 'sell':
            signal.signal(signal.SIGTERM, on_term)
            sell(load_state(), args.jewelers)
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
    except (Stop, trips.Stop, door.Stop, restock.Stop, fight.Stop) as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
    except SystemExit as e:
        if e.code not in (0, None):
            say(f'STOPPED: {e.code}')
        raise


if __name__ == '__main__':
    main()
