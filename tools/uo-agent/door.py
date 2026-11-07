#!/usr/bin/env python3
"""Clem through the tower's front door. It must always end locked and closed (the user, 2026-11-06). Bridge 7, with
the door's two halves and the key ring in his rules ("doors", "keys").

  python3 -I door.py out      from inside: reagents first (restock.py: any below 25 means restock at the chest),
                              then open, step out, close, and check
  python3 -I door.py in       from outside: unlock, open, step into the doorway, lock, step in, close
  python3 -I door.py check    from outside: try to get back in through the door (it mustn't let him); if it opens,
                              lock it with the key and close it

Going out needs no key: the door stays locked (the user, 2026-11-06: "you only need to walk out the door, it stays
locked"), so out is open, step out, close, and check from outside. The key ring is locked down outside at 1758,1415;
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

info = None


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


def step(p, what):
    r = walk(p)
    if not r.get('arrived'):
        raise Stop(f'could not {what} ({p[0]},{p[1]}): {r}')


def go_out():
    if where()[1] >= 1415:
        say('already outside')
        return
    # never out without enough reagents (the user, 2026-11-06: restock if any is below 25)
    restock.info = info
    try:
        restock.ensure()
    except restock.Stop as e:
        raise Stop(f'reagents: {e}')
    step(INSIDE, 'get to the door')
    set_door(DOOR, False)
    try:
        step(OUTSIDE, 'step out')
    finally:
        # never leave it open, wherever he ended up
        set_door(DOOR, True)
    say('out; the door is closed')
    check()


def go_in():
    if where()[1] <= 1413:
        say('already inside')
        return
    step(OUTSIDE, 'get to the door')
    near = call('GET', '/nearby', range=6)['mobiles']
    close = [m for m in near if m.get('notoriety') in ('Gray', 'Criminal', 'Enemy', 'Murderer') and not m.get('dead')
             and max(abs(m['x'] - OUTSIDE[0]), abs(m['y'] - OUTSIDE[1])) <= 3]
    if close:
        raise Stop('creatures at the door: ' + ', '.join(m['name'] or '?' for m in close) + ' ("remove thyself")')
    step(FRONT, 'get right in front of the door')  # straight on from here: a diagonal into the doorway catches on the frame
    key_on(DOOR, 'unlock')
    set_door(DOOR, False)
    try:
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
    say('in; the door is locked and closed')


def check():
    """Try to get back in, as the user does by walking into the door. His client's path walker treats a shut door as
    a wall (smooth_doors off), and walking into one by hand only makes the client send "open door" (auto_open_doors),
    which the server takes as using the door; so this uses it from right in front. A locked door says so and stays
    shut. One that opens wasn't locked (someone forgot when they came in): lock it with the key and close it."""
    if where()[1] <= 1413:
        raise Stop('check is done from outside')
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
