#!/usr/bin/env python3
"""Clem draws world maps from the blank map bags, bag after bag, to raise his Cartography (CARTO.md; draw.py and
work.py of 2026-11-05/06, brought into the repo 2026-11-08). trips.py runs it once every drawn map is sold (the user,
2026-11-08: "you're supposed to start using the blank maps. draw maps on all of them to raise his skill").

Each round, as the user did it by hand (carto/draw1.jsonl, 2026-11-05 21:58): use Cartography (skill 12); the server
shows "What do you want to make?" (1 local map, 2 city map, 3 sea chart, 4 world map); choose world map; about 6 s
later "With great care, thou dost make a chart of the geography." (a world map lands loose in his pack) or "Thy
trembling hand results in an unusable map." (the blank is used up). The blank comes from the bag in his pack.

A bag: picked up (its spot kept), drawn until no blank is left, the loose drawn maps put into it (a completed bag
now), and it goes down on the next blank bag's tile before that one is picked up (his pack never holds two bags of
maps: the 125-item limit). The last one goes on the spot the first one left empty, so every spot keeps one bag. Order: the 3rd floor first, then the 2nd floor by row, tiles he can't stand on last.
Logs to draw.log and every round to draws.jsonl in ~/claude/uo-agent-work/carto.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import uo  # noqa: E402
import carto  # noqa: E402

WORK = os.path.expanduser('~/claude/uo-agent-work/carto')
LOG = os.path.join(WORK, 'draw.log')
ROUNDS = os.path.join(WORK, 'draws.jsonl')
SKILL = 12              # Cartography
MAP = 0x14EB
MENU_TITLE = 'what do you want to make'
CHOICE = 'world map'
SUCCESS = 'thou dost make a chart'
FAILURE = 'trembling hand'
WAIT = ('must wait', 'already doing')
NOISE = ('world will save', 'world is saving', 'world save', 'save complete')

info = None


GM = 100.0  # the goal (the user, 2026-11-08: "That's all we're trying to do here is reach 100 cartography skill")


class Stop(Exception):
    pass


class Grandmaster(Exception):
    """Cartography has reached 100: stop drawing, put everything away, park (the user, 2026-11-08: "If you do make it
    to 100 you should stop and just park Clem safe inside the tower")."""


def say(text):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + text
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def blanks(bag):
    """Maps left in the bag in his pack. After a login (the nightly reboot) the client knows nothing inside bags and
    an unopened bag would read as empty: carto.contents opens it first."""
    return len(carto.contents(bag))


def loose_maps():
    pack = uo.call(info, 'GET', '/status')['backpack']['serial']
    return [i['serial'] for i in uo.call(info, 'GET', '/contents', serial=pack, depth=1)['items']
            if int(i['graphic'], 16) == MAP]


def skill():
    s = uo.call(info, 'GET', '/skills', name='Cartography')['skills'][0]
    return s['base'], s['value']


def server_texts(answer):
    return [m for m in answer.get('messages', []) if not m.get('serial')
            and not any(n in m['text'].lower() for n in NOISE)]


def find_menu(answer):
    for d in answer.get('dialogs', []):
        if d['kind'] != 'gump' and MENU_TITLE in (d.get('title') or '').lower():
            return d
    end = time.time() + 5
    while time.time() < end:
        for d in uo.call(info, 'GET', '/gumps').get('dialogs', []):
            if d['kind'] != 'gump' and MENU_TITLE in (d.get('title') or '').lower():
                return d
        time.sleep(0.5)
    return None


def result_of(answer):
    """The server's word on the draw: from the menu's answer, or (when a world save held it up) the next one."""
    for m in server_texts(answer):
        low = m['text'].lower()
        if SUCCESS in low or FAILURE in low:
            return m['text']
    last = max([m['id'] for m in answer.get('messages', [])] or [0])
    end = time.time() + 60
    while time.time() < end:
        for m in uo.call(info, 'GET', '/messages', after=last)['messages']:
            last = m['id']
            low = m['text'].lower()
            if not m.get('serial') and (SUCCESS in low or FAILURE in low):
                return m['text']
        time.sleep(0.5)
    texts = [m['text'] for m in server_texts(answer)]
    return texts[-1] if texts else None


def draw_once():
    """One world map. Returns ('drawn' | 'failed' | 'wait', the server's text)."""
    answer = carto.act('POST', '/skill', id=SKILL)
    for m in server_texts(answer):
        if any(w in m['text'].lower() for w in WAIT):
            return 'wait', m['text']
    menu = find_menu(answer)
    if not menu:
        raise Stop(f"no menu after using Cartography: {[m['text'] for m in answer.get('messages', [])]}")
    index = next((i['index'] for i in menu['items'] if i['name'].split(':')[0].strip().lower() == CHOICE), None)
    if not index:
        carto.act('POST', '/menu', serial=menu['serial'], id=menu['id'], index=0)
        raise Stop(f"no world map on the menu: {[i['name'] for i in menu['items']]}")
    answer = carto.act('POST', '/menu', serial=menu['serial'], id=menu['id'], index=index)
    text = result_of(answer)
    low = (text or '').lower()
    if SUCCESS in low:
        return 'drawn', text
    if FAILURE in low:
        return 'failed', text
    if any(w in low for w in WAIT):
        return 'wait', text
    raise Stop(f'unknown result: {text!r}')


def draw_bag(bag, should_stop=lambda: False):
    """Draw until the bag in his pack has no blank left (or a stop is asked for). Returns the tally."""
    tally = {'drawn': 0, 'failed': 0, 'wait': 0}
    left = blanks(bag)
    while left > 0 and not should_stop():
        if skill()[0] >= GM:
            raise Grandmaster()
        kind, text = draw_once()
        tally[kind] += 1
        left = blanks(bag)
        base, value = skill()
        with open(ROUNDS, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps({'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'bag': bag, 'result': kind,
                                 'text': text, 'blanks': left, 'base': base, 'value': value}) + '\n')
        say(f'{kind}: {text} | blanks {left}, Cartography {base}')
    return tally


def stash(state, bag):
    """The loose drawn maps into the (empty of blanks) bag in his pack: a completed bag now."""
    loose = loose_maps()
    moved = 0
    for serial in loose:
        if carto.move(serial, bag):
            moved += 1
    count = len(carto.contents(bag))
    carto.note(state, bag, 'completed', count, spot=None)
    say(f'{moved} drawn maps into {bag}; it holds {count}')
    return count


def standable(spot):
    """Whether Clem can stand on a bag's tile: at x 1752, y 1404-1408 on the second floor the bags lie on something
    about 5 higher than the floor (z 31, 32), which he can't step up onto (2026-11-06 01:18)."""
    return spot[2] <= carto.FLOOR_Z[carto.floor_of(spot[2])] + 2


def next_blank(state, exclude=()):
    """The next blank bag with blanks in it: the third floor first, then the second floor by row; bags on tiles he
    can't stand on last."""
    bags = [(b, v) for b, v in state['bags'].items() if v['kind'] == 'blank' and v.get('spot') and v['maps'] > 0
            and b not in exclude]
    bags.sort(key=lambda bv: (not standable(bv[1]['spot']), carto.floor_of(bv[1]['spot'][2]) != 3,
                              bv[1]['spot'][1], bv[1]['spot'][0]))
    return bags[0][0] if bags else None


def spot_beside(state, done, nxt, spot):
    """A bag on a tile he can't stand on: the completed bag goes on a neighbouring tile that already holds a bag."""
    near = [v['spot'] for b, v in state['bags'].items() if b not in (done, nxt) and v.get('spot')
            and standable(v['spot']) and carto.floor_of(v['spot'][2]) == carto.floor_of(spot[2])
            and max(abs(v['spot'][0] - spot[0]), abs(v['spot'][1] - spot[1])) <= 1]
    if not near:
        raise Stop(f'no tile to stand on next to {nxt} at {spot}')
    say(f'{nxt} lies where he cannot stand ({spot}); {done} goes on {near[0]} beside it')
    return near[0]


def draw_next(state, pick_up, should_stop=lambda: False):
    """One bag drawn (picked up first if none is in his pack). False when no blank bag is left (the last bag drawn
    has gone back on its spot)."""
    d = state.setdefault('drawing', {})
    bag = d.get('bag')
    if bag and state['bags'].get(bag, {}).get('spot'):
        bag = None  # it's on the floor already (a stop after it was put down)
    if not bag:
        nxt = next_blank(state)
        if not nxt:
            return False
        # the one spot left empty while the chain of swaps runs (each completed bag takes the next one's tile): the
        # last bag goes back there
        d['free'] = state['bags'][nxt]['spot']
        d['bag'] = nxt
        carto.save_state(state)
        pick_up(nxt)
        carto.note(state, nxt, 'blank', blanks_known(nxt), spot=None)
        bag = nxt
        say(f'drawing {bag} ({state["bags"][bag]["maps"]} blanks) from {d["free"]}')
    if state['bags'][bag]['kind'] == 'blank':
        base, _ = skill()
        say(f'drawing {bag}: {blanks(bag)} blanks, Cartography {base}')
        tally = draw_bag(bag, should_stop)
        if should_stop() and blanks(bag):
            say(f'stopping with {blanks(bag)} blanks left in {bag} (it stays in his pack)')
            return True
        say(f"{bag} drawn: {tally['drawn']} world maps, {tally['failed']} ruined; Cartography {skill()[0]}")
        stash(state, bag)
    # the completed bag goes down: on the next blank bag's tile, which is then picked up; or home if none is left
    nxt = next_blank(state, exclude=(bag,))
    if not nxt:
        put = carto.put_down(bag, d['free'])
        carto.note(state, bag, 'completed', len(carto.contents(bag)), spot=put)
        state.pop('drawing', None)
        carto.save_state(state)
        say(f'{bag} (completed) back at {put}; no blank bag left')
        return False
    spot = state['bags'][nxt]['spot']
    if not standable(spot):
        spot = spot_beside(state, bag, nxt, spot)
    put = carto.put_down(bag, spot)
    carto.note(state, bag, 'completed', len(carto.contents(bag)), spot=put)
    d['bag'] = nxt
    carto.save_state(state)
    pick_up(nxt)
    carto.note(state, nxt, 'blank', blanks_known(nxt), spot=None)
    say(f'{bag} (completed) down at {put}; {nxt} picked up with {state["bags"][nxt]["maps"]} blanks')
    return True


def put_away_at_gm(state):
    """At 100: the loose drawn maps into a bag of drawn maps with room (or an empty bag) where it lies, the bag in his
    pack (blanks left in it) back on the spot left free, and nothing more drawn."""
    d = state.get('drawing') or {}
    bag = d.get('bag')
    loose = loose_maps()
    if loose:
        room = sorted((b for b, v in state['bags'].items() if v.get('spot') and b != bag
                       and (v['kind'] == 'completed' and v['maps'] < carto.PER_BAG or v['maps'] == 0)),
                      key=lambda b: (state['bags'][b]['maps'] == 0, -state['bags'][b]['spot'][2]))
        for target in room:
            count = len(carto.contents(target))
            moved = 0
            for serial in loose[:carto.PER_BAG - count]:
                if carto.move(serial, target):
                    moved += 1
            loose = loose[moved:]
            carto.note(state, target, 'completed', count + moved)
            say(f'{moved} drawn maps into {target}: it holds {count + moved}')
            if not loose:
                break
        if loose:
            say(f'{len(loose)} drawn maps stay loose in his pack: no bag had room')
    if bag and not state['bags'].get(bag, {}).get('spot'):
        left = len(carto.contents(bag))
        put = carto.put_down(bag, d.get('free') or state['bags'][bag].get('spot'))
        carto.note(state, bag, 'blank' if left else 'completed', left, spot=put)
        say(f'{bag} back at {put} with {left} blanks')
    state.pop('drawing', None)
    state['mode'] = 'done'
    carto.save_state(state)


def blanks_known(bag):
    return len(carto.contents(bag))
