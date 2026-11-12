#!/usr/bin/env python3
"""Clem's reagents, before he leaves the tower (the user, 2026-11-06): "Before you leave the tower you have to always
make sure you have enough reagents, if any reagent is below 25 then you need to restock." The user restocks with
Razor's restock-agent-1 (their macro 'restock-clem') at the wooden chest 0x40746D31 in the ground floor stairs room
(1752,1402); this does the same through the bridge: one move per reagent from the chest into his reagent bag, up to
the agent's amounts (recorded 2026-11-06 16:27, combat/restock1.jsonl).

  python3 -I restock.py           check, and restock if any reagent is below 25
  python3 -I restock.py --check   only show the counts (opens the bag to refresh them)
  python3 -I restock.py --force   restock even if nothing is below 25

door.py out runs the check first, every time. The bag is opened (and closed) to refresh the counts: the client had
lost two of its stacks once (sulfurous ash and blood moss didn't show, 2026-11-06). If the user takes over, the
bridge refuses every action and this stops.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import uo  # noqa: E402

LOG = os.path.expanduser('~/claude/uo-agent-work/combat/restock.log')
BAG = '0x407660FB'       # his reagent bag, in his pack (2026-11-11; 0x40677564 before, Razor's restock and
                         # scavenger hot bag): find_bag() finds it by what's in it when this one is gone
PLAIN_BAG = 0x0E76       # only plain bags are looked into for it: his pouches are trapped (opening one sets it off)
CHEST = '0x40746D31'     # the restock chest, ground floor stairs room, 1752,1402,10
MINIMUM = 25             # any below this: restock (the user)
# restock-agent-1's amounts, as it left the bag (2026-11-06 16:27)
TARGET = {0x0F84: ('garlic', 35), 0x0F8D: ("spider's silk", 35), 0x0F85: ('ginseng', 35),
          0x0F86: ('mandrake root', 45), 0x0F8C: ('sulfurous ash', 40), 0x0F7B: ('blood moss', 40),
          0x0F88: ('nightshade', 45), 0x0F7A: ('black pearl', 45)}

info = None


class Stop(Exception):
    pass


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
            raise Stop(e.message)
        raise


def stacks(container):
    """graphic -> (serial, amount) of the biggest stack of each reagent in a container."""
    out = {}
    for i in call('GET', '/contents', serial=container, depth=1)['items']:
        g = int(i['graphic'], 16)
        if g in TARGET and (g not in out or i.get('amount', 1) > out[g][1]):
            out[g] = (i['serial'], i.get('amount', 1))
    return out


def reagents_in(container):
    return sum(i.get('amount', 1) for i in call('GET', '/contents', serial=container, depth=1)['items']
               if int(i['graphic'], 16) in TARGET)


def find_bag():
    """His reagent bag: BAG while it's in his pack, else the plain bag in his pack holding the most reagents
    (2026-11-11: the user moved his reagents to a new bag, 0x407660FB in place of 0x40677564, and the old serial gave
    404s: no counts, and so no spells in a fight). Sets BAG and returns it."""
    global BAG
    pack = call('GET', '/status')['backpack']['serial']
    top = call('GET', '/contents', serial=pack, depth=1)['items']
    if any(i['serial'] == BAG for i in top):
        return BAG
    best = None
    for i in top:
        if int(i['graphic'], 16) != PLAIN_BAG or not i.get('container'):
            continue
        n = reagents_in(i['serial'])
        if not n:  # the client may not know what's in it yet
            call('POST', '/open', serial=i['serial'])
            call('POST', '/close', serial=i['serial'])
            n = reagents_in(i['serial'])
        if n and (not best or n > best[1]):
            best = (i['serial'], n)
    if not best:
        raise Stop(f'no reagent bag in his pack (it was {BAG})')
    say(f'his reagent bag is {best[0]} now (it was {BAG}): {best[1]} reagents in it')
    BAG = best[0]
    return BAG


def counts(refresh=True):
    """graphic -> how many in his reagent bag. refresh: open and close it first, so the client knows every stack."""
    if refresh:
        find_bag()
        call('POST', '/open', serial=BAG)
        call('POST', '/close', serial=BAG)
    have = {g: 0 for g in TARGET}
    for i in call('GET', '/contents', serial=BAG, depth=1)['items']:
        g = int(i['graphic'], 16)
        if g in have:
            have[g] += i.get('amount', 1)
    return have


def show(have):
    return ', '.join(f'{TARGET[g][0]} {n}' for g, n in have.items())


def restock(have):
    """Top every reagent up to restock-agent-1's amount from the chest: one move each."""
    say('restocking from the chest')
    r = call('POST', '/walk', to=CHEST, distance=1)
    if not r.get('arrived'):
        raise Stop(f'could not get to the restock chest: {r}')
    call('POST', '/open', serial=CHEST)
    chest = stacks(CHEST)
    bag = stacks(BAG)
    for g, (name, target) in TARGET.items():
        need = target - have[g]
        if need <= 0:
            continue
        if g not in chest:
            say(f'the chest has no {name}')
            continue
        serial, there = chest[g]
        take = min(need, there)
        if take < need:
            say(f'the chest has only {there} {name}')
        # onto his stack, so it merges (the bridge watches the stack grow); into the bag when he has none
        to = bag[g][0] if g in bag else BAG
        call('POST', '/move', serial=serial, to=to, amount=take if take < there else None)
        say(f'{name}: +{take}')
    call('POST', '/close', serial=CHEST)


def ensure(force=False):
    """Restock if any reagent is below MINIMUM (or force). Returns the counts after."""
    have = counts()
    low = [TARGET[g][0] for g, n in have.items() if n < MINIMUM]
    say(f'reagents: {show(have)}' + (f'; low: {", ".join(low)}' if low else ''))
    if not low and not force:
        return have
    restock(have)
    have = counts()
    say(f'after restocking: {show(have)}')
    still = [TARGET[g][0] for g, n in have.items() if n < MINIMUM]
    if still:
        raise Stop(f'still below {MINIMUM} after restocking: {", ".join(still)}')
    return have


def main():
    global info
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='only show the counts')
    parser.add_argument('--force', action='store_true', help='restock even if nothing is below 25')
    args = parser.parse_args()
    info = uo.find_bridge('Clem')
    st = call('GET', '/status')
    if st.get('takenOver') or st.get('halted'):
        sys.exit(f'the user has him ({st.get("takenOver") or st.get("halted")})')
    try:
        if args.check:
            say(f'reagents: {show(counts())}')
        else:
            ensure(args.force)
    except Stop as e:
        say(f'STOPPED: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
