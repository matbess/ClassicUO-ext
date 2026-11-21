#!/usr/bin/env python3
"""Clem in and out of the Castle, the user's new house (CASTLE.md), and the south-east table in front of the user's own
chests. Every door ends locked and closed; the table always ends back in its place, locked down.

  python3 -I castle.py in           from anywhere he can cast (the tower, town): Recall with his "Castle" rune, the
                                    front door, Recall on the courtyard rune in the entrance room's secure box, the
                                    central door; ends in the great hall
  python3 -I castle.py out          from inside the castle: Recall with his "Outpost" rune, then in at the tower's
                                    front as every trip home does (fight.py: creatures, the door, parked)
  python3 -I castle.py table open   the south-east table: release it, move it aside, and he's at the user's chests
  python3 -I castle.py table close  put it back on its spot, lock it down, and check it says so
  python3 -I castle.py where        read only: which part of the castle he's in

The user's procedure (2026-11-18, recorded while they walked him through it, "correct!"):
- the Castle rune lands him outside the front, at 935,2356;
- front door (0x40913567, shut at 935,2351): from 935,2353 unlock it with the key ring hanging outside (0x4093D690),
  open it, walk in to 935,2350, lock it from there (the key still reaches), close it;
- the secure wooden box on the table in the entrance room (0x405AEFB8, 935,2349,12): open it, Recall on the rune in
  it, which lands him in the courtyard at 935,2344. The rune stays in the box: he never carries one (the user,
  2026-11-18: "That's a security concern"); bridge 14 recalls on a rune within reach wherever it lies;
- central door (0x40913571, shut at 935,2341): from 935,2343 unlock it with the key ring on the courtyard side
  (0x408CB8EE), open it, walk in to 935,2340, lock it, close it.
The south-east table (0x408793A4, locked down at 943,2349): "I wish to release this" and target it, then it's moved
aside to 945,2350 from 944,2349, as the user did (bridge 15 puts things down anywhere within reach); back the same
way, "I wish to lock this down" and target it. The user's friend's side (the south-west table and chests) is never touched
(offLimits in his rules).

If the user gives Clem a command themselves, the bridge refuses every action and this stops at once; only the user
hands him back (--resume). Logs to ~/claude/uo-agent-work/castle/castle.log.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import uo  # noqa: E402
import restock  # noqa: E402

LOG = os.path.expanduser('~/claude/uo-agent-work/castle/castle.log')
RUNES = (0x1F14, 0x1F15, 0x1F16, 0x1F17)
RECALL = 32

LANDING = (935, 2356)            # where the Castle rune puts him
FRONT_DOOR, FRONT_KEY = '0x40913567', '0x4093D690'
FRONT_SHUT, FRONT_OUT, FRONT_IN = (935, 2351), (935, 2353), (935, 2350)
RUNE_BOX = '0x405AEFB8'          # the secure box in the entrance room, with the courtyard rune
COURTYARD = (935, 2344)
CENTRAL_DOOR, CENTRAL_KEY = '0x40913571', '0x408CB8EE'
CENTRAL_SHUT, CENTRAL_OUT, CENTRAL_IN = (935, 2341), (935, 2343), (935, 2340)
HALL = (935, 2338)               # where he's left inside: the great hall, by the central door

# the tables (2026-11-20, second place): the user moved both to the west end of the forge corner, across the
# corridor at 943,2323 and 943,2324 ("the forge area is blocked off now too"). Behind them: the forge chests, the
# east wall, the user's vault and the east intake chests. Clem moves only the one at 943,2323, on his route's row
# (y 2323): aside to 942,2324, out of that row, and back and locked down at the end; the one at 943,2324 is never
# moved. He works it from in front (941,2323) or from behind (944,2323): both spots within reach from either.
TABLE = '0x405E7C85'             # the table at 943,2323
TABLE_OTHER = '0x408793A4'       # the one at 943,2324, checked locked down
TABLE_HOME, TABLE_ASIDE = (943, 2323), (942, 2324)
TABLE_STAND = (941, 2323)        # in front (the great hall side), on the route
TABLE_STAND_BEHIND = (944, 2323)  # behind (the forge side)

CASTLE = (921, 2321, 950, 2350)  # the inside, ground floor (x1, y1, x2, y2)


info = None


class Stop(Exception):
    """The user took over, the bridge stopped, or something didn't do what it should: leave Clem as he is and tell."""


class UserHas(Stop):
    """423: the user took over (or the bridge stopped). Nothing more is sent to him."""


def say(text):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + text
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def call(method, endpoint, **params):
    try:
        return uo.call(info, method, endpoint, **params)
    except uo.BridgeError as e:
        if e.code == 423:  # the user took over, or the bridge stopped
            raise UserHas(e.message)
        raise


def texts(answer):
    return ' | '.join(m['text'] for m in answer.get('messages', []))


def status():
    return call('GET', '/status')


def where():
    st = status()
    return st['x'], st['y']


def step(p, what):
    """Walk to p and check he's really on it (three tries): on 2026-11-19 19:49 he stopped in the front doorway."""
    r = None
    for _ in range(3):
        try:
            r = call('POST', '/walk', x=p[0], y=p[1], distance=0)
        except UserHas:
            raise
        except uo.BridgeError as e:
            raise Stop(f'could not {what} ({p[0]},{p[1]}): {e}')
        time.sleep(0.3)
        if where() == tuple(p):
            return
    raise Stop(f'could not {what} ({p[0]},{p[1]}): he is at {where()} ({r})')


def spot(serial):
    item = call('GET', '/item', serial=serial)['item']
    return item['x'], item['y']


def inside(p=None):
    """In the castle behind both doors: the halls, the corridor, the forge corner, the south-east rooms."""
    x, y = p or where()
    if not (CASTLE[0] <= x <= CASTLE[2] and CASTLE[1] <= y <= CASTLE[3]):
        return False
    if 930 <= x <= 941 and 2341 <= y <= 2346:  # the courtyard
        return False
    return not (934 <= x <= 936 and 2347 <= y <= 2350)  # the entrance room


def key_on(key, door, want):
    """The key ring aimed at a door until it says "You <want> it." (it turns the lock either way)."""
    for _ in range(2):
        a = call('POST', '/use', serial=key)
        if not a.get('targeting'):
            raise Stop(f'the key ring {key} gave no cursor: {texts(a)!r}')
        low = texts(call('POST', '/target', serial=door)).lower()
        if f'you {want} it' in low:
            say(f'{door}: you {want} it')
            return
        if 'you lock it' in low or 'you unlock it' in low:
            say(f'{door}: the wrong way (it was already {want}ed); again')
            continue
        raise Stop(f'the key at {door}: {low!r}')
    raise Stop(f"couldn't {want} {door}")


def set_door(door, shut_at, shut):
    time.sleep(0.8)  # walking up to a door can open it already (the client opens a door he faces)
    if (spot(door) == shut_at) == shut:
        say(f'{door} {"closed" if shut else "open"} already')
        return
    a = call('POST', '/use', serial=door)
    # the door takes a moment to swing in his client: on 2026-11-19 19:45 it was looked at at once, still stood open,
    # and that was taken for a failure. Wait up to 3 s, and try the double-click once more before giving up.
    for attempt in range(2):
        end = time.time() + 3
        while time.time() < end:
            if (spot(door) == shut_at) == shut:
                say(f'{door} {"closed" if shut else "open"}')
                return
            time.sleep(0.2)
        if attempt == 0:
            say(f'{door} did not {"close" if shut else "open"} yet: again')
            a = call('POST', '/use', serial=door)
    raise Stop(f'{door} should be {"shut" if shut else "open"} but stands at {spot(door)}: {texts(a)!r}')


def through(door, key, shut_at, outside, indoors, what, guard=None):
    """Unlock, open, walk in, lock, close: the way the user does both of the castle's doors. Whatever happens once
    it's unlocked, it ends locked and closed. guard: fight.py's check before any key work (the front door, with the
    fight around him); it raises to give way to the fight. The central door is inside the walls: no guard."""
    if where() != outside:
        step(outside, f'get to the {what}')
    if guard:
        guard()
    key_on(key, door, 'unlock')
    try:
        set_door(door, shut_at, False)
        step(indoors, f'walk in through the {what}')
    finally:
        try:
            key_on(key, door, 'lock')
        finally:
            # never close it on him: he can't stand in the doorway (the user, 2026-11-19: "you have to walk through
            # further!! you can't close it when you're still standing in the way"). In if he can, else back out.
            if where() not in (indoors, outside):
                try:
                    step(indoors, f'get clear of the {what}')
                except UserHas:
                    raise
                except Stop:
                    step(outside, f'get clear of the {what}')
            set_door(door, shut_at, True)
    say(f'through the {what}: locked and closed behind him')


def find_rune(name):
    """His rune whose name says `name` ("Castle", "Outpost"), in his pack or his reagent bag."""
    try:
        call('POST', '/open', serial=restock.BAG)  # after a login the client knows nothing inside bags
        call('POST', '/close', serial=restock.BAG)
    except uo.BridgeError:
        pass
    pack = status()['backpack']['serial']

    def walk(items):
        for i in items:
            yield i
            yield from walk(i.get('items', []))
    runes = [i['serial'] for i in walk(call('GET', '/contents', serial=pack, depth=4)['items'])
             if int(i['graphic'], 16) in RUNES]
    for a in call('POST', '/name', serial=','.join(runes)) if runes else []:
        if name.lower() in ' '.join(a.get('lines', [])).lower():
            return a['serial']
    raise Stop(f'no "{name}" rune in his pack')


def recall(rune, why):
    """Recall on a rune; /status once he has landed. A fizzle is tried again (three times)."""
    for _ in range(3):
        st0 = status()
        if st0['mana'] < 11:
            raise Stop(f'no mana to Recall ({st0["mana"]})')
        try:
            r = call('POST', '/cast', spell=RECALL, target=rune)
        except uo.BridgeError as e:
            raise Stop(f'Recall ({why}): {e}')
        end = time.time() + 4
        while time.time() < end:
            st = status()
            if abs(st['x'] - st0['x']) + abs(st['y'] - st0['y']) > 4:
                say(f'Recall ({why}): at {st["x"]},{st["y"]},{st["z"]}')
                return st
            time.sleep(0.1)
        say(f'Recall ({why}) did not take him: {texts(r) or "-"}')
        time.sleep(1.5)
    raise Stop(f'Recall ({why}) failed three times')


TOWER = (1745, 1400, 1765, 1414)  # the tower ("Outpost"), where the restock chest is


def reagents_ok():
    """Before he leaves anywhere (the user, 2026-11-06 and again 2026-11-19: always check the reagents before
    leaving): in the tower, restock.ensure() tops up from the chest when any is below 25; anywhere else there's no
    chest, so a low one stops him (he stays where he is, safe inside)."""
    x, y = where()
    try:
        if TOWER[0] <= x <= TOWER[2] and TOWER[1] <= y <= TOWER[3]:
            try:
                restock.ensure()
            except restock.Stop as e:
                # the tower's chest has run out of one (2026-11-19 21:34: no mandrake root left, he had 24): on to the
                # castle all the same if none is under 20; its reagents chest tops him up as soon as he's inside
                have = restock.counts()
                if min(have.values()) < 20:
                    raise
                say(f'reagents: {e}; going on, the castle reagents chest tops him up')
            return
        if inside((x, y)):  # the castle: its reagents chest (2026-11-19, the tower's stock moved in) is his chest here
            import castle_site
            tower_chest = restock.CHEST
            restock.CHEST = castle_site.targets('reagents', 'east')[0]
            try:
                restock.ensure()
            except restock.Stop as e:
                # the castle chest is out of one too (22:44: black pearl 24, none in the chest): on to the tower if
                # none is under 20, where its restock chest tops him up
                if min(restock.counts().values()) < 20:
                    raise
                say(f'reagents: {e}; going on, the tower restock chest tops him up')
            finally:
                restock.CHEST = tower_chest
            return
        have = restock.counts()
    except restock.Stop as e:
        raise Stop(f'reagents: {e}')
    low = [restock.TARGET[g][0] for g, n in have.items() if n < restock.MINIMUM]
    if low:
        raise Stop(f'reagents low ({", ".join(low)}) and no restock chest here: he stays inside')
    say(f'reagents: {restock.show(have)}')


def go_in():
    here = where()
    if inside(here):
        say(f'already inside the castle, at {here[0]},{here[1]}')
        return
    if not (930 <= here[0] <= 941 and 2341 <= here[1] <= 2362):
        reagents_ok()  # leaving wherever he is for the castle's front
    if not (930 <= here[0] <= 941 and 2341 <= here[1] <= 2362):  # not at the castle yet: the Castle rune
        st = recall(find_rune('Castle'), 'the Castle')
        if max(abs(st['x'] - LANDING[0]), abs(st['y'] - LANDING[1])) > 3:
            raise Stop(f'the Castle rune put him at {st["x"]},{st["y"]}, not in front of the castle ({LANDING})')
        here = (st['x'], st['y'])
    if here[1] >= 2351:  # outside the front: the shared fight (fight.py at places.py's castle-front, as at the tower)
        # deals with what's in front of the door and takes him through it (the user, 2026-11-19: outside, use the fight
        # logic; "You should be using the fighting code that was used for Carto"). A door that won't behave stops him
        # where he is, never a retreat that leaves it behind (2026-11-19 19:45)
        import fight
        import places
        fight.setup(info)
        fight.use_place(places.get('castle-front'))
        try:
            fight.Fight(10, front=True).run()
        except fight.Stop as e:
            raise Stop(f'at the castle front: {e}')
        here = where()
        if not (2347 <= here[1] <= 2350):
            raise Stop(f'the fight ended with him at {here}, not in the entrance room')
    if 2347 <= here[1] <= 2350:  # the entrance room: the courtyard rune in the secure box
        call('POST', '/open', serial=RUNE_BOX)
        items = call('GET', '/contents', serial=RUNE_BOX)['items']
        runes = [i['serial'] for i in items if int(i['graphic'], 16) in RUNES]
        call('POST', '/close', serial=RUNE_BOX)
        if len(runes) != 1:
            raise Stop(f'the secure box {RUNE_BOX} holds {len(runes)} runes, not the one courtyard rune')
        st = recall(runes[0], 'the courtyard')
        if max(abs(st['x'] - COURTYARD[0]), abs(st['y'] - COURTYARD[1])) > 3:
            raise Stop(f'the courtyard rune put him at {st["x"]},{st["y"]}, not in the courtyard ({COURTYARD})')
        here = (st['x'], st['y'])
    if 2341 <= here[1] <= 2346:  # the courtyard
        through(CENTRAL_DOOR, CENTRAL_KEY, CENTRAL_SHUT, CENTRAL_OUT, CENTRAL_IN, 'central door')
    step(HALL, 'get into the great hall')
    say(f'in the castle, in the great hall at {HALL[0]},{HALL[1]}; both doors locked and closed')


def go_out():
    """Recall to the tower from inside, then in at its front the way every trip home goes (trips.home_and_in)."""
    if not inside():
        raise Stop('out is done from inside the castle')
    reagents_ok()  # he lands in front of the tower, among its creatures
    import door, fight, trips, carto  # noqa: E401 (only for the way home)
    trips.info = carto.info = door.info = restock.info = info
    fight.setup(info)
    trips.TOWER_RUNE = find_rune('Outpost')
    trips.home_and_in()


def table(action):
    at = spot_or_none(TABLE)
    if action == 'open':
        if at == TABLE_ASIDE:
            say('the table is aside already: the way to the chests is open')
            return
        if at != TABLE_HOME:
            raise Stop(f'the table stands at {at}, neither in its place {TABLE_HOME} nor aside {TABLE_ASIDE}')
        if where() not in (TABLE_STAND, TABLE_STAND_BEHIND):
            step(TABLE_STAND, 'get next to the table')
        try:
            house_command('i wish to release this', 'no longer locked down')
        except Stop as e:
            if "isn't locked down" not in str(e):  # released already (left unlocked, 2026-11-20 20:35): go on
                raise
            say('the table was not locked down: moving it aside as it is')
        put_table(TABLE_ASIDE)
        say('the table is aside: the way to the chests is open (close it again when done)')
    else:
        if at not in (TABLE_ASIDE, TABLE_HOME):
            raise Stop(f'the table stands at {at}, neither aside {TABLE_ASIDE} nor in its place {TABLE_HOME}')
        if where() not in (TABLE_STAND, TABLE_STAND_BEHIND):
            step(TABLE_STAND, 'get next to the table')
        if at == TABLE_ASIDE:
            put_table(TABLE_HOME)
        house_command('i wish to lock this down', 'locked down')
        for t, at in ((TABLE, TABLE_HOME), (TABLE_OTHER, None)):
            lines = ' '.join(a for r in call('POST', '/name', serial=t) for a in r.get('lines', [])).lower()
            if 'locked down' not in lines:
                raise Stop(f'the table {t} ({at or spot_or_none(t)}) does not say "locked down": {lines!r}')
        say('both tables are in their places and locked down')


def put_table(to):
    """The table picked up and put down on `to`, from where he stands (both within reach)."""
    r = call('POST', '/move', serial=TABLE, ground=1, x=to[0], y=to[1])
    if spot_or_none(TABLE) != to:
        raise Stop(f'the table did not go down at {to}: {texts(r) or r}')
    say(f'the table is at {to[0]},{to[1]}')


def house_command(words, want):
    """An owner command: the words, then the house's cursor on the table."""
    a = call('POST', '/say', text=words)
    end = time.time() + 2
    while time.time() < end and not status().get('targeting'):
        time.sleep(0.1)
    if not status().get('targeting'):
        raise Stop(f'"{words}": no cursor ({texts(a) or "-"})')
    t = call('POST', '/target', serial=TABLE)
    if want not in (texts(t) + ' ' + texts(a)).lower():
        raise Stop(f'"{words}" on the table: {texts(t) or "no answer"}')
    say(f'"{words}": {texts(t)}')


def spot_or_none(serial):
    """Where it stands on the ground, or None while it's in a container (his pack)."""
    r = call('GET', '/item', serial=serial)
    return None if r.get('insideOf') else (r['item']['x'], r['item']['y'])


def main():
    global info
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('step', choices=['in', 'out', 'table', 'where'])
    parser.add_argument('action', nargs='?', choices=['open', 'close'])
    parser.add_argument('--resume', action='store_true',
                        help='clear a takeover; only when the user has said they hand him back')
    args = parser.parse_args()
    info = uo.find_bridge('Clem')
    restock.info = info
    st = status()
    if args.step == 'where':
        print(f"{st['x']},{st['y']},{st['z']}: {'inside the castle' if inside((st['x'], st['y'])) else 'not inside'}")
        return
    if st.get('bridge', 0) < 14:
        sys.exit('needs bridge 14 (cuo-agent33): Recall on the rune in the secure box')
    if args.step == 'table' and st.get('bridge', 0) < 15:
        sys.exit('needs bridge 15 (cuo-agent34): putting the table down beside him')
    stopped = st.get('takenOver') or st.get('halted')
    if stopped and not args.resume:
        sys.exit(f'the user has him ({stopped}); --resume only once they hand him back')
    if stopped:
        call('POST', '/resume', handback=True)
        say(f'resumed, as the user said (was: {stopped})')
    if args.step == 'table' and not args.action:
        sys.exit('table open or table close')
    try:
        if args.step == 'in':
            go_in()
        elif args.step == 'out':
            go_out()
        else:
            table(args.action)
    except Stop as e:
        say(f'STOPPED: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
