#!/usr/bin/env python3
"""The places Clem fights at, for fight.py (`--at NAME`, or `fight.use_place(places.get(NAME))`). A place is only
where: the ground he may fight on (his rules' outside areas there), the spot in front of its door, how far out
counts as "in front", lookout routes for a patrol, and how he gets in through the door, locked and closed behind
him. Who to fight and how is fight.py's, the same everywhere (the user, 2026-11-19: "fighting needs to be usable by
every agent ... It needs to be portable").

  tower-front    the tower ("Outpost"): door.py's front door; the user's outside areas and patrol routes (COMBAT.md)
  castle-front   the castle: the front door (castle.py), from where the Castle rune lands him; the ground is his
                 rules' "castle front" box (929-941, 2351-2362); no patrol routes

A new place: its ground in the character's rules (areas), a Place here, and a door routine that calls guard() before
any key or door work and raises door.Stop to give way to the fight.
"""
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import door  # noqa: E402
import fight  # noqa: E402


def castle_go_in(guard):
    """Through the castle's front door (castle.through: unlock, open, in clear of the doorway, lock, close), as the
    user does it. Ends in the entrance room; castle.go_in goes on from there (the rune box, the courtyard, the central
    door)."""
    import castle
    castle.info = fight.info
    try:
        castle.through(castle.FRONT_DOOR, castle.FRONT_KEY, castle.FRONT_SHUT, castle.FRONT_OUT, castle.FRONT_IN,
                       'front door', guard=guard)
    except castle.UserHas as e:
        raise fight.Stop(str(e))
    except castle.Stop as e:
        raise door.Stop(str(e))


def castle_inside(p):
    return 929 <= p[0] <= 941 and p[1] <= 2350


CASTLE_FRONT = fight.Place('the castle', (935, 2353), [(929, 2351, 941, 2362)], castle_go_in, castle_inside,
                           front_range=12)

PLACES = {'tower-front': fight.TOWER_FRONT, 'castle-front': CASTLE_FRONT}


def get(name):
    if name not in PLACES:
        raise SystemExit(f'no place "{name}": ' + ', '.join(sorted(PLACES)))
    return PLACES[name]
