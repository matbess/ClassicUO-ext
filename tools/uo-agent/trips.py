#!/usr/bin/env python3
"""Clem's trips to the mapmaker in Ocllo (CARTO.md, "Vendor trips"; needs bridge 12, cuo-agent29).

The trick (the user, 2026-11-05 and 2026-11-08): **buy him out first**, every time the process starts over and after
his restock (about an hour): trips with no maps in the pack, buying all his blank maps, until he has none. Then
**sell trips** to the same, now empty, vendor: a bag of drawn maps, sell them all; he stocks every one he bought as a
new blank map, so buy them all back. Home, put away, again. No buy trip while he's known to be empty.

Every trip, from inside the tower:
  1. the pack holds no maps but the bag being sold (a sell trip: the next completed bag, 3rd floor overflow first);
  2. on the ground floor: gold made up to 300 from the chest by the stairs (the user), reagents full (any below 25:
     restock.py, which tops up to the user's Razor restock agent's amounts; if the chest can't make every one 25, he
     parks and the loop stops: the user), spent pouches re-trapped, mana and health up;
  3. Recall (the Ocllo maps rune) to the shop; find the NPC titled "mapmaker" among the shop's NPCs, walk up to him;
  4. buy trip: "<name> buy", every blank he has that fits (125 items in the pack, all of it counted);
     sell trip: "<name> buy" first, only to see he's still empty (blanks there mean he restocked early: nothing is
     sold, the bag goes home and a buyout comes next); then "<name> sell" every drawn map, "<name> buy" them all back;
  5. Magic Reflection, Recall home (the tower rune lands him at 1757,1419, just outside the front door), and in the
     same moment fight.py takes over: every enemy in front of the tower provoked onto another and finished, only the
     gold looted, then in (locked, closed) and parked;
  6. the blanks into a bag (a sell trip: the bag just emptied, which becomes a blank bag on its spot).
A player in town (anyone in sight not known to be an NPC): Recall home at once, fight in, and wait 15 minutes inside
before trying again (the user, 2026-11-08).

  python3 -I trips.py run [--trips N] [--buyout] [--resume]
  python3 -I trips.py status        the vendor's state, the visits so far

Only the user hands Clem back: if they take over, this stops at once (--resume only when they say so). State and logs
in ~/claude/uo-agent-work/carto: vendor.json (the mapmaker, when he was bought out, the shop's NPCs), visits.jsonl
(every visit: stock, prices, what was bought and sold), trips.log.
"""
import argparse
import json
import os
import re
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

CHAR = 'Clem'
WORK = os.path.expanduser('~/claude/uo-agent-work/carto')
LOG = os.path.join(WORK, 'trips.log')
VENDOR = os.path.join(WORK, 'vendor.json')
VISITS = os.path.join(WORK, 'visits.jsonl')

# the runes, found by name in his pack at the start (2026-11-08: the first try took the unmarked rune 0x408F8282 for
# the new one: "That rune is not yet marked.")
RUNES = {'ocllo': 'ocllo maps', 'tower': 'outpost'}
OCLLO_RUNE = '0x408F827E'   # "a recall rune for Ocllo Maps", loose in his reagent bag (the user, 2026-11-08)
TOWER_RUNE = '0x406EDAD9'   # "a recall rune for Outpost": lands at 1757,1419, just outside the front door
OCLLO = (3550, 2400, 3850, 2750)  # his rules' Ocllo area (x1, y1, x2, y2)
GOLD_CHEST = '0x4058ABA9'   # the top left chest by the stairs, ground floor (1752,1402,14): 5,000 gold (the user)
# empty bags for bought-out blanks: any the user leaves on the 3rd floor's west side ("we have more empty bags. I can
# put more bags up there if it's needed", 2026-11-08); 0x409397A3 at 1752,1403,46 was the first
SPARES = (1750, 1402, 1756, 1413, 46, 65)  # x1, y1, x2, y2, z1, z2
GOLD = 0x0EED
MAP = 0x14EB
CARRY_GOLD = 300            # gold he takes to town (the user, 2026-11-08)
PACK_LIMIT = carto.PACK_LIMIT
# places kept free in the pack: none while he carries a stack of gold (outside he loots only gold, which merges onto
# it: the user, 2026-11-08), else one for the gold. So a bag of 100 drawn maps sells and all 100 come back as blanks
RECALL, MAGIC_REFLECTION, HEAL, GREATER_HEAL, MEDITATION = 32, 36, 4, 29, 46
RESTOCK_AFTER = 55 * 60     # the vendor restocks about an hour after he's bought out: a buyout first after this
PLAYER_WAIT = 15 * 60       # a player in town: home, and this long inside before trying again (the user)
LEAVE_MANA = 60             # mana he leaves with at least: Recall (11) out; Reflection (14) and Recall home after
TALK_RANGE = 2              # stand this close to the vendor (he answers from 3)
SIGHT = 18
# an NPC's paperdoll: a title after the name ("Cador the mapmaker", "Lady Melva the town crier"; a single click here shows
# only "Cador", 2026-11-08), or "(invulnerable)" ("Evita (invulnerable)" at a vendor stall). A player's is the name, a
# fame title in front ("The Glorious Lord Bob") and a skill title after a comma ("..., Grandmaster Mage")
NPC_LABEL = re.compile(r"\S\s+the\s+[a-z]|\(invulnerable\)", re.I)

info = None
stopping = {'flag': False}


class Stop(Exception):
    """The user took over, the bridge stopped, or something needs the user: leave Clem as he is."""


class GoHome(Exception):
    """In town and it's time to leave now (a player came, the vendor didn't answer, ...)."""


def say(text):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + text
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def call(method, endpoint, **params):
    try:
        return uo.call(info, method, endpoint, **params)
    except uo.BridgeError as e:
        if e.code == 423:
            raise Stop(e.message)
        raise


def status():
    return call('GET', '/status')


def texts(answer):
    return ' | '.join(m['text'] for m in answer.get('messages', []))


def load_vendor():
    try:
        with open(VENDOR, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {'npcs': {}, 'players': {}}


def save_vendor(v):
    uo.write_json(VENDOR, v, 1)


def visit_row(**fields):
    fields['time'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(VISITS, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(fields) + '\n')


def in_town(st):
    return OCLLO[0] <= st['x'] <= OCLLO[2] and OCLLO[1] <= st['y'] <= OCLLO[3]


def inside(st):
    return 1750 <= st['x'] <= 1763 and 1402 <= st['y'] <= 1413


# ---- his pack ----

def pack_list():
    pack = status()['backpack']['serial']
    return pack, call('GET', '/contents', serial=pack, depth=4)['items']


def count_items(items):
    return sum(1 + count_items(i.get('items', [])) for i in items if int(i['serial'], 16) < 0x7F000000)


def walk_items(items):
    for i in items:
        yield i
        yield from walk_items(i.get('items', []))


def loose_maps():
    """Maps lying loose in his pack (bought ones land there)."""
    _, items = pack_list()
    return [i['serial'] for i in items if int(i['graphic'], 16) == MAP]


def map_bags():
    """Bags in his pack that hold maps, with how many. A backpack in his pack the client knows nothing about (after a
    login, or once the user has clicked about: 19:49 a bag of 62 blanks went unseen and the loop picked up another bag
    on top of it, past 125 items) is opened first; never a pouch (his trapped pouches go off when opened)."""
    _, items = pack_list()
    unknown = [i['serial'] for i in items if i.get('container') and int(i['graphic'], 16) == 0x0E75
               and not i.get('knownItems') and not i.get('items')]
    for serial in unknown:
        carto.contents(serial)
    if unknown:
        _, items = pack_list()
    return {i['serial']: sum(1 for x in i.get('items', []) if int(x['graphic'], 16) == MAP)
            for i in items if i.get('container') and any(int(x['graphic'], 16) == MAP for x in i.get('items', []))}


def in_pack(serial):
    _, items = pack_list()
    return any(i['serial'] == serial for i in items)


def gold_carried():
    _, items = pack_list()
    return sum(i.get('amount', 1) for i in walk_items(items) if int(i['graphic'], 16) == GOLD)


# ---- inside the tower ----

def make_gold(want=CARRY_GOLD):
    """Exactly `want` gold in his pack: the difference from or back into the chest by the stairs."""
    have = gold_carried()
    if have == want:
        return
    go_floor(1)
    carto.come_within_reach(GOLD_CHEST)
    in_chest = [i for i in carto.contents(GOLD_CHEST) if int(i['graphic'], 16) == GOLD]
    pack, items = pack_list()
    # onto a stack of gold where there is one: it merges, and the bridge watches the stack grow (restock.py does the
    # same with reagents); a split-off part dropped loose would merge too, its serial gone, and halt the bridge
    if have < want:
        if sum(i.get('amount', 1) for i in in_chest) < want - have:
            raise Stop(f'not enough gold in the chest by the stairs for {want - have} more')
        stack = max(in_chest, key=lambda i: i.get('amount', 1))
        mine = [i for i in items if int(i['graphic'], 16) == GOLD]
        need = want - have
        carto.act('POST', '/move', serial=stack['serial'], to=mine[0]['serial'] if mine else pack,
                  amount=need if need < stack.get('amount', 1) else None)
        say(f'gold: {have} + {need} from the chest')
    else:
        extra = have - want
        onto = max(in_chest, key=lambda i: i.get('amount', 1))['serial'] if in_chest else GOLD_CHEST
        for g in sorted((i for i in walk_items(items) if int(i['graphic'], 16) == GOLD),
                        key=lambda i: -i.get('amount', 1)):
            take = min(extra, g.get('amount', 1))
            carto.act('POST', '/move', serial=g['serial'], to=onto, amount=take if take < g.get('amount', 1) else None)
            extra -= take
            if extra <= 0:
                break
        say(f'gold: {have}, {have - want} back into the chest')
    now = gold_carried()
    if now != want:
        raise Stop(f'meant to carry {want} gold, but he has {now}')


def ready_to_leave():
    """Reagents full (any below 25: restock), pouches trapped, health and mana up, mounted."""
    go_floor(1)
    try:
        restock.ensure()
    except restock.Stop as e:
        st = status()
        if st.get('takenOver') or st.get('halted'):
            raise Stop(st.get('takenOver') or st.get('halted'))  # the user has him (or the bridge stopped): no parking
        # the chest can't make every reagent 25 (the user, 2026-11-08: "If it ever runs out and you can't get at least
        # 25 of each reagent then just stop the loop when you are safe inside the tower")
        park()
        raise Stop(f'reagents: {e}; parked inside, the loop stops')
    door.retrap()
    st = status()
    if not st.get('mounted'):
        raise Stop('he is not on his horse')
    if st['hits'] < st['hitsMax'] and st['mana'] >= 11:
        spell = GREATER_HEAL if st['hits'] < st['hitsMax'] * 0.8 else HEAL
        a = call('POST', '/cast', spell=spell, target=st['serial'])
        say(f'healed before leaving: {texts(a) or "-"}')
    meditate_to(LEAVE_MANA + 30)


def meditate_to(mana):
    """Inside, safe: meditate until mana is at least `mana` (or 3 minutes)."""
    st = status()
    if st['mana'] >= mana:
        return
    say(f'meditating inside (mana {st["mana"]}, want {mana})')
    end = time.time() + 180
    last_try = 0
    while time.time() < end:
        st = status()
        if st['mana'] >= mana:
            break
        if time.time() - last_try > 12:
            last_try = time.time()
            try:
                call('POST', '/skill', id=MEDITATION)
            except uo.BridgeError as e:
                say(f'meditation: {e}')
        time.sleep(2)
    say(f'mana {status()["mana"]}')


def go_floor(floor):
    """carto's walks between floors, from the ground floor too (go_to_floor only goes up from it)."""
    st = status()
    have = carto.floor_of(st['z'])
    if have == floor:
        return
    if floor >= have:
        carto.go_to_floor(floor)
        return
    if have == 3:
        carto.go_to_floor(2)
    # down from the second floor: the ground floor stairs top out at 1751,1403 (z 23)
    carto.walk(*carto.SECOND_FROM_GROUND)
    for p in (carto.GROUND_STAIRS_TOP, carto.GROUND_STAIRS_FOOT, (1752, 1407)):
        carto.stride(*p)
    st = status()
    if carto.floor_of(st['z']) != 1:
        raise Stop(f"meant to reach the ground floor, but he's at {st['x']},{st['y']},{st['z']}")
    say(f"now on the ground floor at {st['x']},{st['y']},{st['z']}")


def next_completed(state):
    """The next completed bag to sell: the 3rd floor overflow first (storage is the 2nd floor), then the 2nd floor."""
    bags = [(b, v) for b, v in state['bags'].items() if v['kind'] == 'completed' and v.get('spot')]
    if not bags:
        return None
    bags.sort(key=lambda bv: (-bv[1]['spot'][2], bv[1]['spot'][1], bv[1]['spot'][0]))
    return bags[0][0]


def put_blanks_away(state, sold_bag=None):
    """The loose blanks in his pack into bags: first the bag he just sold from (in his pack; it becomes a blank bag
    on its spot), then blank bags with room where they lie (the 3rd floor's first, empty ones the user left there too;
    picking one up would overflow the pack, so each map goes straight into it on the floor)."""
    maps = loose_maps()
    if sold_bag:
        count = len(carto.contents(sold_bag))
        moved = 0
        for serial in maps[:carto.PER_BAG - count]:
            if carto.move(serial, sold_bag):
                moved += 1
        maps = maps[moved:]
        spot = carto.put_down(sold_bag, state['trip_home'])
        carto.note(state, sold_bag, 'blank', count + moved, spot=spot)
        say(f'{moved} blanks into {sold_bag}: it holds {count + moved} (blank) at {spot}')
    if not maps:
        return
    find_spares(state)
    room = sorted((b for b, v in state['bags'].items() if v['kind'] == 'blank' and v['maps'] < carto.PER_BAG
                   and v.get('spot')), key=lambda b: (-state['bags'][b]['spot'][2], b))
    for bag in room:
        count = len(carto.contents(bag))
        moved = 0
        for serial in maps[:carto.PER_BAG - count]:
            if carto.move(serial, bag):
                moved += 1
        maps = maps[moved:]
        carto.note(state, bag, 'blank', count + moved)
        say(f'{moved} blanks into {bag}: it holds {count + moved} (blank) at {state["bags"][bag]["spot"]}')
        if not maps:
            return
    raise Stop(f'{len(maps)} blank maps are left loose in his pack: no blank bag has room (empty bags needed)')


def find_spares(state):
    """Empty bags on the 3rd floor's west side that aren't map bags yet: blank bags with 0 maps from now on. Opening
    one the client knows nothing about takes a walk up, so this runs only when room for blanks is short."""
    x1, y1, x2, y2, z1, z2 = SPARES
    near = call('GET', '/nearby', range=14)['items']
    found = 0
    for i in near:
        if (i.get('container') and i.get('type') in ('backpack', 'bag', 'pouch') and i['serial'] not in state['bags']
                and x1 <= i['x'] <= x2 and y1 <= i['y'] <= y2 and z1 <= i['z'] <= z2):
            if carto.contents(i['serial']):
                continue
            carto.note(state, i['serial'], 'blank', 0, spot=[i['x'], i['y'], i['z']])
            say(f"an empty bag upstairs: {i['serial']} at {i['x']},{i['y']},{i['z']}: a blank bag now")
            found += 1
    return found


def blank_room(state):
    return sum(carto.PER_BAG - b['maps'] for b in state['bags'].values()
               if b['kind'] == 'blank' and b.get('spot') and b['maps'] < carto.PER_BAG)


def pick_up(bag):
    """A bag into his pack (carto.pick_up), getting past Razor's auto-search: Razor double-clicks every bag that lands
    in his pack (its "AutoSearch"), and the bridge takes that double-click for the user taking over (2026-11-08 19:01:29).
    The user, 2026-11-08: "add the script fix for now" (they keep AutoSearch on for their counters)."""
    carto.come_within_reach(bag)
    pack = status()['backpack']['serial']
    try:
        moved = uo.call(info, 'POST', '/move', serial=bag, to=pack).get('moved')
    except uo.BridgeError as e:
        if e.code != 423 or not forgive_razor(bag):
            raise Stop(e.message)
        moved = True
    if not moved:
        raise Stop(f"couldn't pick up {bag}")
    for endpoint in ('/open', '/close'):
        try:
            uo.call(info, 'POST', endpoint, serial=bag)
        except uo.BridgeError as e:
            if e.code != 423 or not forgive_razor(bag):
                raise Stop(e.message)
            uo.call(info, 'POST', endpoint, serial=bag)


def forgive_razor(bag):
    """Razor's auto-search double-click on the bag just picked up (or its auto-open of a corpse) taken for the user
    taking over: fight.razor_click resumes only those."""
    return fight.razor_click(bag)


def put_back(state, bag):
    """A bag of maps taken along but not sold (the vendor had restocked): back on its spot, as it was."""
    spot = carto.put_down(bag, state['trip_home'])
    carto.note(state, bag, state['bags'][bag]['kind'], len(carto.contents(bag)), spot=spot)


# ---- recall ----

def recall(rune, why):
    """Recall on a rune; returns /status once he has landed. A fizzle is tried again (three times)."""
    for attempt in range(3):
        st0 = status()
        if st0['mana'] < 11:
            raise Stop(f'no mana to Recall ({st0["mana"]})')
        try:
            r = call('POST', '/cast', spell=RECALL, target=rune)
        except uo.BridgeError as e:
            say(f'Recall ({why}): {e}')
            time.sleep(2)
            continue
        end = time.time() + 4
        while True:
            st = status()
            if abs(st['x'] - st0['x']) + abs(st['y'] - st0['y']) > 10:
                say(f'Recall ({why}): at {st["x"]},{st["y"]},{st["z"]}')
                return st
            if r.get('moved') is False and any(w in texts(r).lower() for w in ('fizzle', 'disturbed', 'mana', 'reagent')):
                break
            if time.time() > end:
                break
            time.sleep(0.1)
        say(f'Recall ({why}) did not take him: {texts(r) or "-"}')
        time.sleep(1.5)
    raise Stop(f'Recall ({why}) failed three times')


def home_and_in():
    """Recall home and, the moment he lands, fight.py: everything in front of the tower, then in and parked."""
    st = status()
    if st['mana'] >= 14 + 11:
        try:
            call('POST', '/cast', spell=MAGIC_REFLECTION, target=st['serial'], wait=0, cursor=0)
            time.sleep(fight.land_time(MAGIC_REFLECTION) + 0.3)  # the words have to end before Recall's start
        except uo.BridgeError as e:
            say(f'Magic Reflection: {e}')
    recall(TOWER_RUNE, 'home')
    old = signal.signal(signal.SIGTERM, fight.on_term)  # a stop now means: finish going in
    try:
        fight.Fight(10, front=True).run()
    except fight.Stop as e:
        raise Stop(f'during the fight at the tower: {e}')
    finally:
        signal.signal(signal.SIGTERM, old)
    say('home: in, the door locked and closed, parked')


# ---- in town ----

def known_npcs(v):
    learned = set()
    try:
        with open(os.path.join(uo.AGENT_DIR, 'npcs-learned.json'), encoding='utf-8') as fh:
            learned = {e['serial'] for e in json.load(fh)}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return learned | set(v['npcs'])


def titles(v, serials):
    """Paperdoll titles for these people (asked for once each; the bridge closes the paperdolls again)."""
    out = {}
    for i in range(0, len(serials), 6):
        for a in call('POST', '/paperdoll', serial=','.join(serials[i:i + 6])):
            out[a['serial']] = (a.get('title') or '').strip()
    return out


def strangers(v, me):
    """Players in sight: anyone human who isn't known to be an NPC. Someone new gets their paperdoll looked at once: a
    title ("Cador the mapmaker", "the guard") or "(invulnerable)" makes them an NPC, remembered in vendor.json."""
    near = call('GET', '/nearby', range=SIGHT)['mobiles']
    people = [m for m in near if m.get('human') and not m.get('dead') and m['serial'] != me]
    npcs = known_npcs(v)
    unknown = [m for m in people if m['serial'] not in npcs and m.get('notoriety') != 'Invulnerable'
               and m['serial'] not in v['players']]
    if unknown:
        seen = {m['serial']: m['title'] for m in unknown if m.get('title')}
        seen.update(titles(v, [m['serial'] for m in unknown if m['serial'] not in seen]))
        for m in unknown:
            title = seen.get(m['serial']) or ''
            if title and NPC_LABEL.search(title):
                v['npcs'][m['serial']] = title
                say(f'NPC: {title} ({m["serial"]})')
            else:
                v['players'][m['serial']] = title or m.get('name') or '?'
                say(f'not an NPC: "{title or m.get("name")}" ({m["serial"]}, {m.get("distance")} tiles)')
        save_vendor(v)
        npcs = known_npcs(v)
    return [m for m in people if m['serial'] not in npcs and m.get('notoriety') != 'Invulnerable']


def check_town(v, me):
    found = strangers(v, me)
    if found:
        who = ', '.join(f'{m.get("name") or "?"} ({m["serial"]}, {m.get("distance")} tiles)' for m in found)
        raise GoHome(f'a player in town: {who}')


def find_mapmaker(v, me):
    """The NPC titled "mapmaker" (the user: there are several NPCs in the shop)."""
    near = {m['serial']: m for m in call('GET', '/nearby', range=SIGHT)['mobiles']}
    known = v.get('mapmaker')
    if known and known['serial'] in near:
        # the client forgets his paperdoll's title once Clem has left Ocllo (the mobile is made anew), and the bridge
        # only deals with a vendor whose title it knows (19:09-19:13: "Cador" refused three times): look again
        if not near[known['serial']].get('title'):
            titles(v, [known['serial']])
        return near[known['serial']], known['name']
    # NPCs known only by their name so far (a single click): their paperdolls
    untitled = [s for s, line in v['npcs'].items() if s in near and not NPC_LABEL.search(line)]
    if untitled:
        for serial, title in titles(v, untitled).items():
            if title:
                v['npcs'][serial] = title
        save_vendor(v)
    for serial, line in v['npcs'].items():
        if ' the mapmaker' in line.lower() and serial in near:
            v['mapmaker'] = {'serial': serial, 'name': line}
            save_vendor(v)
            say(f'the mapmaker: {line} ({serial})')
            return near[serial], line
    return None, None


SELL_AT_ONCE = 5  # "You may only sell 5 items at a time!" (the server, 2026-11-08; the user: "sell over and over")


def approach(vendor):
    """Up to him again: he wanders about the shop (19:15:31, 5 tiles off between selling and buying)."""
    m = next((m for m in call('GET', '/nearby', range=SIGHT)['mobiles'] if m['serial'] == vendor), None)
    if not m:
        raise GoHome('the mapmaker is out of sight')
    if m.get('distance', 99) > TALK_RANGE:
        try:
            call('POST', '/walk', x=m['x'], y=m['y'], distance=TALK_RANGE)
        except uo.BridgeError as e:
            raise GoHome(f'no way to the mapmaker at {m["x"]},{m["y"]}: {e}')


def at_him(who, endpoint, **params):
    """A request to the vendor, walking up to him again when he has wandered off meanwhile (19:28:03: "too far from
    the vendor (4 tiles; at most 3)" between the walk and the words)."""
    for attempt in range(4):
        approach(who)
        try:
            return call('POST', endpoint, **params)
        except uo.BridgeError as e:
            if e.code != 409 or 'too far' not in e.message or attempt == 3:
                raise


def shop(vendor, mode):
    """His window (buy or sell). Words but no window: he has nothing for that (no items); no answer at all: home."""
    r = at_him(vendor, '/shop', vendor=vendor, mode=mode)
    if r.get('open') and r.get('mode') == mode:
        return r
    if r.get('answered'):
        say(f'no {mode} window, he said: {texts(r)}')
        return dict(r, items=[])
    raise GoHome(f'no answer from the mapmaker to "{r.get("said")}"')


def blank(name):
    n = (name or '').lower()
    return 'blank' in n or n.strip() in ('map', 'maps') or carto.kind_of(n) == 'blank'


def buy_blanks(vendor, stock_rows, limit=None):
    """Every blank he has that fits (and, on a buy trip, that the bags at home have room for) and that the gold
    covers. Returns (bought, his stock before, price, left)."""
    offer = [i for i in stock_rows if int(i['graphic'], 16) == MAP and blank(i.get('name'))]
    other = [i for i in stock_rows if int(i['graphic'], 16) == MAP and not blank(i.get('name'))]
    if other:
        say('maps he sells that are not blank (left): ' + ', '.join(f'{i.get("amount")} {i.get("name")}' for i in other))
    stock = sum(i['amount'] for i in offer)
    if not offer:
        call('POST', '/shop', close=1)
        return 0, 0, None, 0
    price = max(i['price'] for i in offer)
    _, items = pack_list()
    keep_free = 0 if any(int(i['graphic'], 16) == GOLD for i in items) else 1
    room = PACK_LIMIT - count_items(items) - keep_free
    gold = gold_carried()
    want, deal = min(stock, room, gold // max(price, 1), limit if limit is not None else stock), []
    for i in offer:
        take = min(i['amount'], want - sum(a for _, a in deal))
        if take > 0:
            deal.append((i['serial'], take))
    if not deal:
        call('POST', '/shop', close=1)
        say(f'buys nothing: {stock} blanks at {price}, room {room}, gold {gold}')
        return 0, stock, price, stock
    r = at_him(vendor, '/buy', items=','.join(f'{s}:{a}' for s, a in deal))
    bought = r.get('bought', 0)
    say(f'bought {bought} of his {stock} blanks at {price} ({r.get("goldBefore")} -> {r.get("gold")} gold; room was '
        f'{room})' + (f': {texts(r)}' if texts(r) else ''))
    return bought, stock, price, stock - bought


def sell_drawn(vendor, v=None, me=None):
    """Every drawn map he carries (the sell list covers the bags in his pack), SELL_AT_ONCE a time, his sell window
    opened again for each. Returns (sold, price, unsold)."""
    sold, prices, odd_seen = 0, set(), False
    while True:
        if v is not None:
            check_town(v, me)
        r = shop(vendor, 'sell')
        rows = r.get('items', [])
        drawn = [i for i in rows if int(i['graphic'], 16) == MAP and carto.kind_of(i.get('name')) == 'completed']
        odd = [i for i in rows if i not in drawn and int(i['graphic'], 16) == MAP]
        if odd and not odd_seen:
            odd_seen = True
            say('maps in his sell list not sold (blank or unknown): ' + ', '.join(sorted({i.get('name') or '?' for i in odd})))
        if not drawn:
            call('POST', '/shop', close=1)
            break
        batch, n = [], 0
        for i in drawn:
            take = min(i['amount'], SELL_AT_ONCE - n)
            if take <= 0:
                break
            batch.append((i['serial'], take))
            n += take
        s = at_him(vendor, '/sell', items=','.join(f'{serial}:{a}' for serial, a in batch))
        prices.update(i['price'] for i in drawn)
        if not s.get('sold'):
            say(f'selling {n} got nothing: {texts(s) or "no answer"}')
            break
        sold += s['sold']
    left = len([1 for b in map_bags().values() for _ in range(b)])
    say(f'sold {sold} drawn maps at {sorted(prices)} ({gold_carried()} gold now); {left} still in his pack')
    return sold, max(prices) if prices else None, left


def at_vendor(v, me, phase, bag, limit=None):
    """In the shop: the buyout, or a sell trip. Returns what happened, for the visit log."""
    check_town(v, me)
    vendor, label = find_mapmaker(v, me)
    if not vendor:
        raise GoHome('no NPC titled "mapmaker" in sight')
    if vendor.get('distance', 99) > TALK_RANGE:
        call('POST', '/walk', x=vendor['x'], y=vendor['y'], distance=TALK_RANGE)
        vendor = next((m for m in call('GET', '/nearby', range=SIGHT)['mobiles'] if m['serial'] == vendor['serial']),
                      vendor)
    check_town(v, me)
    serial = vendor['serial']
    look = shop(serial, 'buy')
    rows = look.get('items', [])
    stock = sum(i['amount'] for i in rows if int(i['graphic'], 16) == MAP and blank(i.get('name')))
    say(f'{label}: {stock} blank maps in stock' + (f' ({", ".join(sorted({i["name"] for i in rows}))})' if rows else ''))
    result = {'phase': phase, 'vendor': serial, 'stock': stock}
    if phase == 'buyout':
        bought, stock, price, left = buy_blanks(serial, rows, limit)
        result.update(bought=bought, price=price, left=left)
        if left == 0:
            v['empty_since'] = time.time()
            say('he is bought out')
        else:
            v['empty_since'] = None
        save_vendor(v)
        return result
    # a sell trip: only to a vendor with no blanks (else he restocked early: the buyout comes first, nothing sold)
    if stock > 0:
        call('POST', '/shop', close=1)
        v['empty_since'] = None
        v['restocked_seen'] = time.time()
        save_vendor(v)
        say(f'he has restocked ({stock}): nothing sold; the bag goes home and a buyout comes next')
        result.update(restocked=True)
        return result
    check_town(v, me)
    sold, sell_price, unsold = sell_drawn(serial, v, me)
    result.update(sold=sold, sell_price=sell_price, unsold=unsold)
    check_town(v, me)
    look = shop(serial, 'buy')
    bought, stock2, price, left = buy_blanks(serial, look.get('items', []))
    result.update(stock_after_sale=stock2, bought=bought, price=price, left=left)
    if left:
        v['empty_since'] = None  # blanks left with him: a buyout next
        save_vendor(v)
    return result


def town_trip(v, phase, bag, limit=None):
    """Recall to the shop, deal, home again (fighting in). Returns the visit's result."""
    st = recall(OCLLO_RUNE, 'to the mapmaker')
    me = st['serial']
    result = {'phase': phase}
    try:
        if not in_town(st):
            raise GoHome(f'landed at {st["x"]},{st["y"]}, outside his Ocllo area')
        result = at_vendor(v, me, phase, bag, limit)
    except GoHome as e:
        say(f'leaving town: {e}')
        result['left_early'] = str(e)
        if str(e).startswith('a player'):
            v['wait_until'] = time.time() + PLAYER_WAIT
            save_vendor(v)
        try:
            call('POST', '/shop', close=1)
        except uo.BridgeError:
            pass
    except uo.BridgeError as e:
        say(f'in town: {e}; going home')
        result['error'] = str(e)
    visit_row(**result, gold=gold_carried())
    home_and_in()
    return result


# ---- the loop ----

def one_trip(v, state, force_buyout=False):
    if state.get('trip'):
        say(f'the last trip stopped before its maps were put away: finishing it ({state["trip"]})')
        finish_trip(state)
    wait = (v.get('wait_until') or 0) - time.time()
    if wait > 0:
        say(f'a player was in town: waiting {wait / 60:.0f} more minutes inside')
        while time.time() < v['wait_until']:
            if stopping['flag']:
                return False
            st = status()
            if st.get('takenOver') or st.get('halted'):
                raise Stop(st.get('takenOver') or st.get('halted'))
            time.sleep(10)
    empty = v.get('empty_since')
    phase = 'buyout' if force_buyout or not empty or time.time() - empty > RESTOCK_AFTER else 'sell'
    say(f'--- {phase} trip' + (f' (bought out {(time.time() - empty) / 60:.0f} min ago)' if empty else ''))

    st = status()
    if not inside(st):
        raise Stop(f'he is not inside the tower ({st["x"]},{st["y"]},{st["z"]})')
    # nothing but the bag to sell: loose maps go into bags first (blanks from a trip that stopped half way)
    if loose_maps():
        put_blanks_away(state)
    carried = map_bags()
    bag = None
    # a trip that stopped half way left a completed bag in his pack: a sell trip goes on with it, anything else puts
    # it back on its spot first
    for b in list(carried):
        known = state['bags'].get(b)
        if phase == 'sell' and len(carried) == 1 and known and known['kind'] == 'completed':
            bag = b
            state['trip_home'] = known.get('spot') or state.get('trip_home')
            carto.save_state(state)
            say(f'{b} ({carried[b]} drawn maps) is in his pack already: this trip sells it')
        elif known and (known.get('spot') or state.get('trip_home')):
            state['trip_home'] = known.get('spot') or state['trip_home']
            put_back(state, b)
        else:
            raise Stop(f'a bag of maps in his pack that has no spot to go back to: {b}')
    if phase == 'sell':
        if not bag:
            bag = next_completed(state)
            if not bag:
                # every drawn map sold: back to drawing (the user, 2026-11-08: "once all of the drawn maps are sold
                # then you should return to drawing maps to raise his cartography skill")
                say('no completed bag left to sell: every drawn map is sold; next comes drawing (work.py)')
                return False
            state['trip_home'] = state['bags'][bag]['spot']
            carto.save_state(state)
            pick_up(bag)
        n = len(carto.contents(bag))
        carto.note(state, bag, 'completed', n, spot=None)
        say(f'took {bag} ({n} drawn maps) from {state["trip_home"]}')
    limit = None
    if phase == 'buyout':
        # what he buys has to go into bags at home: blank bags with room, and empty bags left on the 3rd floor
        limit = blank_room(state)
        if limit < carto.PER_BAG:
            find_spares(state)
            limit = blank_room(state)
        if limit <= 0:
            raise Stop('a buyout is due, but no blank bag at home has room: empty bags needed on the 3rd floor, '
                       'west side')
        say(f'room at home for {limit} blanks')

    make_gold()
    ready_to_leave()
    _, items = pack_list()
    say(f'leaving: {count_items(items)} items in the pack, {gold_carried()} gold, mana {status()["mana"]}')
    result = town_trip(v, phase, bag, limit)
    # kept until the maps are put away, so a run stopped meanwhile (the user, 2026-11-08: "pause it and resume from
    # where he is") finishes the job first when it starts again
    # maps all look alike to the client: what's still in the bag now (before any blank goes in) is what wasn't sold
    state['trip'] = {'bag': bag, 'sold': result.get('sold', 0), 'unsold': map_bags().get(bag, 0) if bag else 0,
                     'phase': phase}
    carto.save_state(state)
    finish_trip(state)
    return True


def finish_trip(state):
    """Home from a trip: the blanks put away (into the bag he sold from, which becomes a blank bag on its spot), gold
    back to 300, parked. Also where a stopped run picks up again."""
    trip = state.get('trip') or {}
    bag = trip.get('bag')
    # (in his pack at all: a bag sold empty holds no maps, so map_bags() leaves it out; 19:58 its blanks went to the
    # bags upstairs and the empty bag stayed in his pack)
    if bag and in_pack(bag):
        unsold = trip.get('unsold', 0)
        if unsold and not trip.get('sold'):
            put_back(state, bag)          # not sold (he had restocked, or we left early): as it was
            put_blanks_away(state)
        elif unsold:
            say(f'{unsold} drawn maps were not sold and stay in {bag}; the blanks go elsewhere')
            put_back(state, bag)
            put_blanks_away(state)
        else:
            put_blanks_away(state, sold_bag=bag)
    else:
        put_blanks_away(state)
    state.pop('trip', None)
    carto.save_state(state)
    make_gold()
    go_floor(1)
    park()


def park():
    """Into the safe zone: from the stairs room by way of the hall (a straight walk from the chest by the stairs
    stopped at the foot of the stairs, 1750,1408, outside the red line, 2026-11-08 19:00)."""
    st = status()
    if not door.in_safe_zone((st['x'], st['y'])):
        door.walk((1752, 1410))
    door.park()


def find_runes():
    """His runes by their names (single-clicked): the Ocllo Maps rune and the tower's ("Outpost")."""
    global OCLLO_RUNE, TOWER_RUNE
    carto.contents(restock.BAG)  # after a login the client knows nothing inside bags: open it first (runes live there)
    _, items = pack_list()
    runes = [i['serial'] for i in walk_items(items) if int(i['graphic'], 16) in (0x1F14, 0x1F15, 0x1F16, 0x1F17)]
    found = {}
    for a in call('POST', '/name', serial=','.join(runes)) if runes else []:
        text = ' '.join(a.get('lines', [])).lower()
        for key, want in RUNES.items():
            if want in text:
                found[key] = a['serial']
    missing = [RUNES[k] for k in RUNES if k not in found]
    if missing:
        raise Stop(f'no rune for {", ".join(missing)} in his pack')
    OCLLO_RUNE, TOWER_RUNE = found['ocllo'], found['tower']
    say(f'runes: Ocllo Maps {OCLLO_RUNE}, home (Outpost) {TOWER_RUNE}')


def show():
    v = load_vendor()
    print(json.dumps({k: v[k] for k in v if k not in ('npcs', 'players')}, indent=1))
    print('NPCs known:', len(v.get('npcs', {})), ' not NPCs:', v.get('players'))
    try:
        with open(VISITS, encoding='utf-8') as fh:
            for line in fh.readlines()[-10:]:
                print(line.rstrip())
    except OSError:
        pass


def on_term(signum, frame):
    stopping['flag'] = True
    say('asked to stop: finishing this trip first (home, in, the maps put away)')


def main():
    global info
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    r = sub.add_parser('run')
    r.add_argument('--trips', type=int, default=1, help='how many trips (default 1)')
    r.add_argument('--buyout', action='store_true', help='start with a buyout whatever the state says')
    r.add_argument('--resume', action='store_true', help='clear a takeover; only when the user hands him back')
    sub.add_parser('status')
    args = parser.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if args.command == 'status':
        return show()
    info = uo.find_bridge(CHAR)
    carto.info = door.info = restock.info = info
    st = fight.setup(info)
    if st.get('bridge', 0) < 12:
        sys.exit('needs bridge 12 (cuo-agent29): vendors')
    stopped = st.get('takenOver') or st.get('halted')
    if stopped and not args.resume:
        sys.exit(f'the user has him ({stopped}); --resume only once they hand him back')
    if stopped:
        call('POST', '/resume')
        say(f'resumed, as the user said (was: {stopped})')
    signal.signal(signal.SIGTERM, on_term)
    v = load_vendor()
    v.setdefault('npcs', {})
    v.setdefault('players', {})
    state = carto.load_state()
    done = 0
    try:
        find_runes()
        while done < args.trips and not stopping['flag']:
            if not one_trip(v, state, force_buyout=args.buyout and done == 0):
                break
            done += 1
    except (Stop, door.Stop, restock.Stop, fight.Stop) as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
    say(f'{done} trip(s) done')


if __name__ == '__main__':
    main()
