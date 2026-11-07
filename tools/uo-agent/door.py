#!/usr/bin/env python3
"""Clem through the tower's front door. It must always end locked and closed (the user, 2026-11-06). Bridge 7, with
the door's two halves and the key ring in his rules ("doors", "keys").

  python3 -I door.py out      from inside: reagents first (restock.py: any below 25 means restock at the chest),
                              Magic Reflection, creatures off the front steps, then open, step out right in front of
                              the door, Paralyze at a caster in sight, close, and check
  python3 -I door.py in       from outside: unlock, open, step into the doorway, lock, step in, close
  python3 -I door.py check    from outside: try to get back in through the door (it mustn't let him); if it opens,
                              lock it with the key and close it

Going out needs no key: the door stays locked (the user, 2026-11-06: "you only need to walk out the door, it stays
locked"), so out is open, step out, close, and check. He stays right at the door while he closes it, at 1756,1415
right in front of it (the user, 2026-11-06: "stay right next to the door so that when you close the door it looks
like the door is closing over the top of you"; in the doorway itself it wouldn't shut, 18:32:33): out on the steps
or further, creatures put off the steps to either side get round the forges (x 1755 and 1758, both step rows) and
at him while he's busy with the door. The steps themselves (x 1756-1757, y 1415-1416, between the forges) are
checked first: a creature there gets "remove thyself" and a click, which puts it off to the side. A caster in sight
gets Paralyze as soon as he's out, before the door is closed (the user, 2026-11-07). The key ring is locked down outside at 1758,1415;
it reaches the door from outside (1756,1416) and the doorway (1756,1414), not from inside (1756,1413: "I can't reach
that."). It turns the lock either way ("You unlock it." / "You lock it."). Creatures on the front steps have to go first: the
house command "remove thyself" (not in his rules yet), so `in` stops when any are within 3 tiles of the door.
If the user gives Clem a command themselves, the bridge refuses every action (handOver) and this stops at once.
Only the user hands him back: --resume clears a takeover, and is passed only when they say so.
Logs to ~/claude/uo-agent-work/combat/door.log.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import uo  # noqa: E402
import restock  # noqa: E402

LOG = os.path.expanduser('~/claude/uo-agent-work/combat/door.log')
KEY = '0x4040A302'
DOOR = '0x408AEA54'          # the west half, the one the user uses
DOOR_EAST = '0x408AEA55'
SHUT_AT = {DOOR: (1756, 1414), DOOR_EAST: (1757, 1414)}
INSIDE = (1756, 1413)
DOORWAY = (1756, 1414)       # where the west half stands shut; free when it's open (it swings to 1755,1415)
FRONT = (1756, 1415)         # right in front of the shut door, outside
OUTSIDE = (1756, 1416)
PARK = (1757, 1410)          # where he's left inside: in the safe zone (the user, 2026-11-07: 3 tiles in from the
                             # outside of the tower, marked with red cloth on the ground floor, x 1752-1762, y 1404-1412,
                             # and the same on every floor), in the part of it his rules let him walk (the hall)
STEPS = {(x, y) for x in (1756, 1757) for y in (1415, 1416)}  # the front steps, between the forges at x 1755 and 1758
HOSTILE = ('Gray', 'Criminal', 'Enemy', 'Murderer')

info = None
cast_at = 0.0  # when a spell went off here (Paralyze): the key ring waits for its cursor to be aimed first
guard = None   # called between the steps through the door (fight.py: breaks off when a creature comes near)


class Stop(Exception):
    """The user took over, the bridge stopped, or the door didn't do what it should: leave Clem as he is."""


def say(text):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + text
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def call(method, endpoint, **params):
    try:
        return uo.call(info, method, endpoint, **params)
    except uo.BridgeError as e:
        if e.code == 423:  # the user took over, or the bridge stopped
            raise Stop(e.message)
        raise


def texts(answer):
    return ' | '.join(m['text'] for m in answer.get('messages', []))


def walk(p):
    try:
        return call('POST', '/walk', x=p[0], y=p[1], distance=0)
    except uo.BridgeError as e:
        if e.code in (403, 409):
            return {'arrived': False, 'refused': str(e)}
        raise


def where():
    st = call('GET', '/status')
    return st['x'], st['y']


def door_spot(door):
    item = call('GET', '/item', serial=door)['item']
    return item['x'], item['y']


def key_on(door, want):
    """The key ring aimed at a door until it says "You <want> it." (it turns the lock either way)."""
    if guard and want == 'unlock':
        guard()
    # a spell's cursor still to come (Paralyze, cast and gone on): the key's own cursor would get mixed up with it
    time.sleep(max(0.0, cast_at + 2.5 - time.time()))
    for _ in range(2):
        a = call('POST', '/use', serial=KEY)
        if not a.get('targeting'):
            raise Stop(f'the key ring gave no cursor: {texts(a)!r}')
        t = call('POST', '/target', serial=door)
        low = texts(t).lower()
        if f'you {want} it' in low:
            say(f'{door}: {texts(t)}')
            return
        if 'you lock it' in low or 'you unlock it' in low:
            say(f'{door}: {texts(t)} (the wrong way: it was already {want}ed; again)')
            continue
        raise Stop(f'the key at {door}: {texts(t)!r}')
    raise Stop(f"couldn't {want} {door}")


def set_door(door, shut):
    # walking up to the door can open it already: his client opens a door he faces (auto_open_doors), and a
    # double-click on top of that shuts it again (2026-11-06 15:57)
    time.sleep(0.8)
    if (door_spot(door) == SHUT_AT[door]) == shut:
        say(f'{door} {"closed" if shut else "open"} already')
        return
    a = call('POST', '/use', serial=door)
    spot = door_spot(door)
    if (spot == SHUT_AT[door]) != shut:
        raise Stop(f'{door} should be {"shut" if shut else "open"} but stands at {spot[0]},{spot[1]}: {texts(a)!r}')
    say(f'{door} {"closed" if shut else "open"}')


def close_east():
    """Only the west half is ever used (the user, 2026-11-07: "don't go through both doors, only one of them"). His
    client opens a door he walks up to by itself (auto_open_doors: "Opening door..." at 18:48:47, the east half), and
    that half was left open: shut it whenever it's open."""
    try:
        if door_spot(DOOR_EAST) != SHUT_AT[DOOR_EAST]:
            say('the east half is open (his client opened it): closing it')
            call('POST', '/use', serial=DOOR_EAST)
            time.sleep(0.6)
            if door_spot(DOOR_EAST) != SHUT_AT[DOOR_EAST]:
                raise Stop('the east half of the door stays open')
    except uo.BridgeError as e:
        if e.code == 423:
            raise
        say(f'the east half: {e}')


def park():
    """Into the safe zone, away from the door."""
    if where() != PARK:
        r = walk(PARK)
        say('parked in the safe zone' if r.get('arrived') else f'could not get to the safe zone: {r}')


def step(p, what):
    if guard:
        guard()
    r = walk(p)
    if not r.get('arrived'):
        raise Stop(f'could not {what} ({p[0]},{p[1]}): {r}')


def on_steps():
    """Creatures on the front steps (between the forges)."""
    return [m for m in call('GET', '/nearby', range=8)['mobiles']
            if m.get('notoriety') in HOSTILE and not m.get('dead') and not m.get('human') and not m.get('yourPet')
            and (m['x'], m['y']) in STEPS]


def remove(m):
    """The house command "remove thyself" on one creature: the words, then the house's cursor on it."""
    a = call('POST', '/say', text='remove thyself')
    end = time.time() + 1.5  # the cursor comes a moment after the words
    while time.time() < end and not call('GET', '/status').get('targeting'):
        time.sleep(0.1)
    if not call('GET', '/status').get('targeting'):
        say(f'"remove thyself": no cursor ({texts(a) or "-"})')
        return
    try:
        t = call('POST', '/target', serial=m['serial'])
        say(f'"remove thyself" on {m.get("name") or m["serial"]} at {m["x"]},{m["y"]}: {texts(t) or "-"}')
    except uo.BridgeError as e:
        say(f'"remove thyself" on {m["serial"]}: {e}')
        try:
            call('POST', '/target', cancel=1)
        except uo.BridgeError:
            pass


def clear_steps(tries):
    """Put every creature on the steps off them (remove), up to `tries` rounds. True when the steps are clear."""
    for _ in range(tries):
        there = on_steps()
        if not there:
            return True
        for m in there:
            remove(m)
        time.sleep(1.0)
    return not on_steps()


def reflect():
    """Magic Reflection on him before the door opens (the user, 2026-11-06: "use reflect before you go out the door,
    reflect will help with the first spell it casts at you"); it never fizzles (the user). Bridge 8 answers at once
    (a short wait here for the server's word); bridge 7 waits for a cursor that never comes, up to 6 s: harmless
    inside."""
    st = call('GET', '/status')
    if st.get('mana', 0) < 14:
        say(f'no mana for Magic Reflection ({st.get("mana")})')
        return
    extra = {'wait': 0, 'cursor': 0} if st.get('bridge', 0) >= 8 else {}
    call('POST', '/cast', spell=36, target=st['serial'], **extra)
    if extra:
        time.sleep(1.5)
    words = call('GET', '/messages', after=st['lastMessageId'])['messages']
    say('Magic Reflection: ' + (' | '.join(m['text'] for m in words) or '-'))


def paralyze_caster():
    """Paralyze at a caster in sight as soon as he's out of the door, before the door is closed (the user,
    2026-11-07: "Since you know a magic caster is out there, as soon as you step out of the door, cast paralyze on
    him, then proceed with locking and closing the door"). Bridge 8 casts and goes on (the bridge aims the cursor
    itself); the door is shut meanwhile."""
    global cast_at
    import fight  # the creature lists live there
    st = call('GET', '/status')
    near = [m for m in call('GET', '/nearby', range=12)['mobiles']
            if fight.attackable(m) and fight.kind(m) in fight.CASTERS and m['distance'] <= fight.SPELL_RANGE]
    if not near:
        return
    m = min(near, key=lambda m: m['distance'])
    if st.get('mana', 0) < 14:
        say(f'no mana for Paralyze at {m["name"]}')
        return
    extra = {'wait': 0} if st.get('bridge', 0) >= 8 else {}
    try:
        a = call('POST', '/cast', spell=38, target=m['serial'], **extra)
    except uo.BridgeError as e:
        say(f'Paralyze at {m["name"]}: {e}')
        return
    cast_at = time.time()
    say(f'Paralyze at {m["name"]} ({m["distance"]} tiles)' + (f': {texts(a)}' if texts(a) else ''))


def go_out(with_reflection=True):
    if where()[1] >= 1414:
        say('already outside')
        return
    # never out without enough reagents (the user, 2026-11-06: restock if any is below 25)
    restock.info = info
    try:
        restock.ensure()
    except restock.Stop as e:
        raise Stop(f'reagents: {e}')
    if with_reflection:
        reflect()
    step(INSIDE, 'get to the door')
    close_east()
    # creatures on the steps first (the user, 2026-11-06): with the door shut if the click gets through, else with it
    # open; still there after that, he stays in
    clear = clear_steps(2)
    set_door(DOOR, False)
    try:
        if not clear and not clear_steps(3):
            raise Stop('creatures still on the front steps: ' + ', '.join(m.get('name') or '?' for m in on_steps()))
        # right in front of the door (1756,1415), straight through the doorway; the door wouldn't shut over him in
        # the doorway itself (2026-11-06 18:32:33)
        step(FRONT, 'step out, right in front of the door')
        paralyze_caster()
    finally:
        # never leave it open, wherever he ended up, either half
        set_door(DOOR, True)
        close_east()
    say(f'out at {where()[0]},{where()[1]}, right at the door; the door is closed')
    check()


def go_in():
    here = where()
    if here[1] <= 1413:
        say('already inside')
        park()
        return
    if here != DOORWAY:  # in the doorway already (just out, the door shut over him): straight to the key
        step(OUTSIDE, 'get to the door')
        near = call('GET', '/nearby', range=6)['mobiles']
        close = [m for m in near if m.get('notoriety') in HOSTILE and not m.get('dead')
                 and max(abs(m['x'] - OUTSIDE[0]), abs(m['y'] - OUTSIDE[1])) <= 3]
        if close:
            raise Stop('creatures at the door: ' + ', '.join(m['name'] or '?' for m in close) + ' ("remove thyself")')
        step(FRONT, 'get right in front of the door')  # straight on: a diagonal into the doorway catches on the frame
    key_on(DOOR, 'unlock')
    set_door(DOOR, False)
    try:
        if where() != DOORWAY:
            step(DOORWAY, 'step into the doorway')
        key_on(DOOR, 'lock')
        step(INSIDE, 'step in')
    finally:
        # never leave it open or unlocked: from outside or the doorway the key reaches it
        if where()[1] >= 1414 and door_spot(DOOR) != SHUT_AT[DOOR]:
            try:
                key_on(DOOR, 'lock')
            except Stop:
                pass
        set_door(DOOR, True)
        close_east()
    say('in; the door is locked and closed')
    park()


def check():
    """Try to get back in, as the user does by walking into the door. His client's path walker treats a shut door as
    a wall (smooth_doors off), and walking into one by hand only makes the client send "open door" (auto_open_doors),
    which the server takes as using the door; so this uses it from right in front. A locked door says so and stays
    shut. One that opens wasn't locked (someone forgot when they came in): lock it with the key and close it."""
    if where()[1] <= 1413:
        raise Stop('check is done from outside')
    if where() not in (DOORWAY, FRONT):  # right at the door: from the doorway (going out) or right in front
        step(FRONT, 'get in front of the door')
    a = call('POST', '/use', serial=DOOR)
    if door_spot(DOOR) == SHUT_AT[DOOR]:
        say(f'it won\'t let him in: {texts(a) or "(no message)"}; the door is locked')
        return
    say(f'the door OPENED: it was not locked ({texts(a)!r}); locking and closing it')
    key_on(DOOR, 'lock')
    set_door(DOOR, True)
    a = call('POST', '/use', serial=DOOR)
    if door_spot(DOOR) != SHUT_AT[DOOR]:
        set_door(DOOR, True)
        raise Stop(f'the door still opens after locking it: {texts(a)!r}')
    say(f'locked now: {texts(a) or "(no message)"}')


def main():
    global info
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('step', choices=['out', 'in', 'check'])
    parser.add_argument('--resume', action='store_true',
                        help='clear a takeover; only when the user has said they hand him back')
    args = parser.parse_args()
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    info = uo.find_bridge('Clem')
    st = call('GET', '/status')
    if st.get('bridge', 0) < 7:
        sys.exit('needs bridge 7 (cuo-agent23)')
    stopped = st.get('takenOver') or st.get('halted')
    if stopped and not args.resume:
        sys.exit(f'the user has him ({stopped}); --resume only once they hand him back')
    if stopped:
        call('POST', '/resume')
        say(f'resumed, as the user said (was: {stopped})')
    try:
        {'out': go_out, 'in': go_in, 'check': check}[args.step]()
    except Stop as e:
        say(f'STOPPED: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
