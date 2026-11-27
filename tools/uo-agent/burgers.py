#!/usr/bin/env python3
"""Clem tops Burgers up with shovels and reagents at the Ocllo bank (BURGERS.md; the user, 2026-11-26).

The user's job, in their words: "you'll be in charge of giving shovels & reagents to Burgers. This will involve taking
control of burgers, this requires you to coordinate with the mining agent to make sure it's done using Burgers and
will hand him over to you ... You'll take burgers to the ocllo bank (he has a rune to it) and hide him ... You'll
first take clem to the tools room and then fetch the recall rune for the castle courtyard from my chest ... get 1 bag
of shovels from teh tools room and get the reagents Burgers needs (unless you don't have room, then take the reagents
on a separate trip) and go to Ocllo bank and hand them to Burgers, then put them in burgers bank (there is a reagents
bag in his bank), just put the whole bag of shovels in his bank. You'll want to then give Clem the empty bags from
burgers bank and inventory (they were used to hold shovels) so he can bring them back to the castle. Go back to the
castle, (make sure clem has enough reagents before you start btw) put the empty backpacks away, then get another bag
of shovels and take it to burgers again. Then do that once more. You'll give burgers 3 bags of shovels (150
shovels) and then take clem back to the tools room and leave burgers hidden at the bank."
And (2026-11-26): his pack to 50 of each of the four reagents and his bank to 250 of each, unless the mining agent
gives other numbers; the reagents split over the three shovel trips by weight, a trip of their own only if they still
don't fit; a running shovel loop is paused for it and resumed after.

  python3 -I burgers.py run [--bags 3] [--bank-bags 2] [--reagents 'black pearl=200,blood moss=200,...']
                                     the whole job (--reagents: the amounts the mining agent asked for, in place of
                                     filling his pack to 50 and his bank to 250)
  python3 -I burgers.py survey       Burgers to the bank (if he isn't there), hidden; what his pack and bank hold
  python3 -I burgers.py stop         finish the trip he's on (home, bags away), then stop

How it goes:
- Neither character may be another loop's: mine.py, lumber.py and heal.py (Burgers) or shovels.py (Clem) running
  stops it before anything is sent. The mining agent stops and parks Burgers first; a shovel loop is paused first.
- Burgers: his rules in the client's Agent folder get the Ocllo bank as an area (to step out of hiding next to Clem),
  his guard off (the bank is relaxed, MINING.md), the "Ocllo" rune (0x406EDA8E) to the bank, where he lands at
  3686,2506. Clem's bank rune lands him at 3686,2505, so Burgers never stands there. Hidden whenever he isn't
  trading. His rules file as it was is put back at the end (mine.py writes its own when it starts again).
- Clem, from the tools room: his own reagents (any below 25 from the entrance chest), mana; the courtyard ("skara")
  rune from the user's chest if he hasn't got it (the shovel loop's kit may be in his pack); a full bag of 50 shovels
  off the top of a stack (the tools room's record updated); Recall to the bank. After the bags, Burgers' reagents on
  trips of their own (the user, 2026-11-26: a top-up of the entrance chest with the bag in his pack overloaded him),
  from the entrance chest (938 2nd), as piles of their own in his pack, never onto his casting reagents. Never more
  than his max less 10 stones when he leaves.
- The trade: Burgers steps out next to Clem, Clem drops the bag and the reagents on him, Burgers drops the empty
  backpacks (from his bank, taken out beforehand, and from his pack: never the bag mine.py keeps his spare shovels in)
  on Clem, both accept. Burgers: "bank", the first two bags of shovels into the bank box whole (the third stays in his
  pack, for Icepick: the user, 2026-11-26), and before every trip he must have room for a bag (253 stones), or it
  stops; the reagents onto his pack's
  piles up to the pack's amount and the rest onto the bank's reagent bag's piles; hidden again.
- Clem home by the skara rune to the north yard, in by the north door (locked behind him), the empty backpacks into
  the spare backpacks chest (938 3rd), any loose shovel into the tools room, and he waits in the tools room with the
  user's table locked. Next trip.
- At the end the skara rune goes back into the user's chest if it came out for this (not if it's the shovel loop's).
  The FINAL line says what Burgers has: shovels in the bank and pack, the four reagents in each.

A takeover of either stops it at once; nothing more is sent to that character. Problems stop it with Clem home.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import uo  # noqa: E402

RAW_CALL = uo.call  # Burgers' calls: never past Razor's AutoSearch (tools_room.setup swaps uo.call for Clem's)

import carto  # noqa: E402
import castle  # noqa: E402
import castle_site  # noqa: E402
import door  # noqa: E402
import gems  # noqa: E402
import restock  # noqa: E402
import shovels  # noqa: E402
import tools_room  # noqa: E402
import trips  # noqa: E402

WORK = os.path.expanduser('~/claude/uo-agent-work/burgers')
LOG = os.path.join(WORK, 'burgers.log')
STOP_FILE = os.path.join(WORK, 'stop')
SAVED_RULES = os.path.join(WORK, 'rules-Burgers.before.json')
MINING_STATE = os.path.expanduser('~/claude/uo-agent-work/mining/state.json')

CLEM, BURGERS = '0x0004344A', '0x000425CA'
BURGERS_BANK_RUNE = '0x406EDA8E'   # "a recall rune for Ocllo" in Burgers' pack (mining.RUNES['bank'])
CLEM_LANDS = (3686, 2505)          # where Clem's "Ocllo Bank" rune puts him (59 landings in shovels.log)
BURGERS_LANDS = (3686, 2511)       # where Burgers' rune put him, 2026-11-26 15:21:31 (mine.OCLLO_BANK says 2506)
BANK_NEAR = 10
BANK_AREA = '{ "name": "Ocllo bank (burgers.py)", "box": [3676, 2495, 3696, 2517], "z": [-10, 30] }'
FULL_SPEED = '"pacing": { "gap": [1100, 1100], "burst": 1000, "break": [1100, 1100], "aim": [0, 0] }'
REAGENTS = {'0x0F7A': 'black pearl', '0x0F7B': 'blood moss', '0x0F86': 'mandrake root', '0x0F8C': 'sulfurous ash'}
NAMES = {'black pearl': '0x0F7A', 'pearl': '0x0F7A', 'blood moss': '0x0F7B', 'bloodmoss': '0x0F7B', 'moss': '0x0F7B',
         'mandrake root': '0x0F86', 'mandrake': '0x0F86', 'sulfurous ash': '0x0F8C', 'sulphurous ash': '0x0F8C',
         'sulfrous ash': '0x0F8C', 'ash': '0x0F8C'}
PACK_TARGET, BANK_TARGET = 50, 250  # the user, 2026-11-26
BAGS = 3                            # "You'll give burgers 3 bags of shovels (150 shovels)"
# the user, 2026-11-26: "only 2 bags of shovels go into burgers bank, the 3rd bag stays in his inventory so he can hand
# them to icepick"; and "make sure that burgers can hold the shovels and has enough weight available ... he should
# always be able to hold 50 shovels though. If he can't then I guess You'll have to pause it"
BANK_BAGS = 2
PER_BAG = tools_room.PER_BAG
BAG_STONES = tools_room.MAX_STONES + 3  # a full bag of shovels with the backpack
SHOVELS = {'0x0F39', '0x0F3A'}
BACKPACK = tools_room.BACKPACK
REAGENT_STONES = 0.1                # a reagent's weight (Burgers' pouch: 4 piles, ~140 reagents, 16 stones with the bag)
WEIGHT_MARGIN = 10                  # stones kept free under Clem's max
SPOTS = {g: (100 + 14 * k, 120) for k, g in enumerate(REAGENTS)}  # Burgers' piles in Clem's pack (reagents_topup --pack)
BURGERS_LOOPS = r'(mine|lumber|heal)\.py'
HIDING = 21
RECALL = 32

info = None  # Clem's bridge
say_to = {'log': LOG}


# a problem: stop, Clem home if he can be, tell the user; the user took one of them over: nothing more to him. The
# shovel loop's own, so the castle steps borrowed from it (castle_call) raise the same ones.
Stop = shovels.Stop
UserHas = shovels.UserHas


def say(text):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + text
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def stop_asked():
    return os.path.exists(STOP_FILE)


# ---- the amounts ----

def parse_reagents(text):
    """'black pearl=200,blood moss=200' -> {graphic: n}; the four only."""
    want = {}
    for part in (text or '').split(','):
        if not part.strip():
            continue
        name, n = part.rsplit('=', 1)
        g = NAMES.get(name.strip().lower())
        if not g:
            raise SystemExit(f'not one of the four reagents: {name.strip()!r}')
        want[g] = int(n)
    return want


def reagents_needed(pack, bank, asked=None):
    """{graphic: (for his pack, for his bank)}: what brings his pack to PACK_TARGET and his bank to BANK_TARGET; or,
    asked (the mining agent's numbers), that total, the pack's share first."""
    out = {}
    for g in REAGENTS:
        to_pack = max(0, PACK_TARGET - pack.get(g, 0))
        if asked is not None:
            total = asked.get(g, 0)
            to_pack = min(to_pack, total)
            out[g] = (to_pack, total - to_pack)
        else:
            out[g] = (to_pack, max(0, BANK_TARGET - bank.get(g, 0)))
    return out


def share(left, trips_left, room_stones):
    """This trip's reagents: an even part of what's left over the trips left, all of it on the last one, cut down
    (each in proportion) to what his free weight carries."""
    want = {g: (n if trips_left <= 1 else math.ceil(n / trips_left)) for g, n in left.items() if n > 0}
    room = int(max(0, room_stones) / REAGENT_STONES)
    total = sum(want.values())
    if total <= room:
        return want
    scale = room / total if total else 0
    cut = {g: int(n * scale) for g, n in want.items()}
    return {g: n for g, n in cut.items() if n > 0}


# ---- Burgers ----

class Bur:
    def __init__(self):
        try:
            self.info = uo.find_bridge('Burgers')
        except SystemExit as e:
            raise Stop(f'Burgers: {e}')

    def call(self, method, endpoint, **params):
        for _ in range(3):
            try:
                return RAW_CALL(self.info, method, endpoint, **params)
            except uo.TakenOver as e:
                if not self.razor_opened():
                    raise UserHas(f'the user took Burgers over ({e.message})')
            except uo.BridgeError as e:
                raise Stop(f'Burgers {method} {endpoint}: {e.message or e}')
        raise Stop(f'Burgers {method} {endpoint}: Razor kept opening things')

    def razor_opened(self):
        """The takeover is Razor's AutoSearch: a double-click on a bag within half a second of the bridge dropping it
        into his pack (2026-11-26 15:21:41: an empty backpack from his bank, opened 0.09 s after its drop). Then he's
        handed back and True; anything else is the user."""
        events = RAW_CALL(self.info, 'GET', '/events', after=0)['events']
        st = RAW_CALL(self.info, 'GET', '/status')
        took = st.get('takenOver') or ''
        when = took[len('a double-click at '):] if took.startswith('a double-click at ') else None
        clicks = [e for e in events if e.get('kind') == 'sent double-click' and when and e['time'].startswith(when)]
        if not razor_click(events, clicks):
            return False
        RAW_CALL(self.info, 'POST', '/resume', handback=True)
        say(f"Burgers: Razor's AutoSearch opened {clicks[-1]['serial']} as it landed in his pack ({took}): not the "
            f"user; resumed")
        return True

    def status(self):
        return self.call('GET', '/status')

    def pack(self):
        return self.status()['backpack']['serial']

    def contents(self, serial, depth=1):
        return self.call('GET', '/contents', serial=serial, depth=depth)['items']

    def open(self, serial):
        return self.call('POST', '/open', serial=serial)['contents']['items']

    def at_bank(self, st=None):
        st = st or self.status()
        return cheb((st['x'], st['y']), BURGERS_LANDS) <= BANK_NEAR

    def hide(self, tries=4):
        for n in range(tries):
            if self.status()['hidden']:
                return True
            r = self.call('POST', '/skill', id=HIDING)
            if r.get('hidden'):
                say('Burgers: hidden')
                return True
            time.sleep(11)  # skills share a cooldown of about ten seconds
        raise Stop("Burgers couldn't hide (four tries)")

    def recall(self, rune, why):
        for _ in range(3):
            st0 = self.status()
            if st0['mana'] < 11:
                raise Stop(f"Burgers has no mana to Recall ({st0['mana']})")
            r = self.call('POST', '/cast', spell=RECALL, target=rune)
            end = time.time() + 5
            while time.time() < end:
                st = self.status()
                if cheb((st['x'], st['y']), (st0['x'], st0['y'])) > 4:
                    say(f"Burgers: Recall ({why}): at {st['x']},{st['y']},{st['z']}")
                    return st
                time.sleep(0.2)
            say(f"Burgers: Recall ({why}) did not take him: {' | '.join(m['text'] for m in r.get('messages', []))}")
            time.sleep(1.5)
        raise Stop(f'Burgers: Recall ({why}) failed three times')

    def bank(self):
        r = self.call('POST', '/say', text='bank')
        box = (r.get('bank') or {}).get('serial')
        if not box:
            raise Stop(f'''Burgers' "bank" opened no bank box: {' | '.join(m['text'] for m in r.get('messages', []))}''')
        time.sleep(1)
        return box


def razor_click(events, clicks):
    """The last of these clicks came within 0.5 s after the bridge's own drop of the same item."""
    if not clicks:
        return False
    secs = lambda t: sum(float(x) * m for x, m in zip(t.split(':'), (3600, 60, 1)))  # noqa: E731
    c = clicks[-1]
    return any(e.get('kind') == 'sent drop' and e.get('serial') == c.get('serial')
               and 0 <= secs(c['time']) - secs(e['time']) <= 0.5 for e in events)


def rules_with_bank(text):
    """Burgers' rules text with the Ocllo bank added to his areas (to step out of hiding next to Clem) and full speed."""
    if 'burgers.py' in text:
        return text
    new, n = re.subn(r'"areas"\s*:\s*\[', '"areas": [\n    ' + BANK_AREA + ',', text, count=1)
    if not n:
        raise Stop("Burgers' rules have no \"areas\" to add the Ocllo bank to")
    return re.sub(r'"pacing"\s*:\s*\{[^}]*\}', FULL_SPEED, new)


def burgers_rules_for_bank():
    path = os.path.join(uo.AGENT_DIR, 'rules-Burgers.json')
    text = open(path, encoding='utf-8').read()
    if 'burgers.py' not in text:
        with open(SAVED_RULES, 'w', encoding='utf-8') as fh:
            fh.write(text)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(rules_with_bank(text))
    time.sleep(1.5)  # the bridge reloads the file when it changes


def burgers_rules_back():
    path = os.path.join(uo.AGENT_DIR, 'rules-Burgers.json')
    if os.path.exists(SAVED_RULES):
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(open(SAVED_RULES, encoding='utf-8').read())
        os.remove(SAVED_RULES)
        say("Burgers' rules put back as they were")


def reagent_piles(items):
    """{graphic: [(serial, amount, container)]} of the four, at any depth."""
    out = {g: [] for g in REAGENTS}

    def walk(its, inside):
        for i in its:
            if i.get('graphic') in out:
                out[i['graphic']].append((i['serial'], i.get('amount', 1), inside))
            if i.get('items'):
                walk(i['items'], i['serial'])
    walk(items, None)
    return out


def total(piles):
    return {g: sum(p[1] for p in ps) for g, ps in piles.items()}


def mining_shovel_bag():
    try:
        return json.load(open(MINING_STATE)).get('shovel_bag')
    except (OSError, ValueError):
        return None


class BankView:
    """What Burgers has: his pack's and his bank's reagents, the reagent bag, the empty backpacks, the shovels."""

    def __init__(self, b):
        self.b = b
        pack = b.pack()
        self.pack_items = b.contents(pack, depth=2)
        self.pack_piles = reagent_piles(self.pack_items)
        self.box = b.bank()
        top = b.contents(self.box)
        self.reagent_bag, self.bank_piles, self.empties, self.shovels, self.items = None, {g: [] for g in REAGENTS}, [], 0, 0
        for i in top:
            self.items += 1
            if i.get('graphic') in SHOVELS:
                self.shovels += 1
            if not i.get('container'):
                continue
            inside = b.open(i['serial'])
            self.items += count_items(inside)
            self.shovels += sum(1 for x in inside if x.get('graphic') in SHOVELS)
            piles = reagent_piles(inside)
            if any(piles.values()) and not self.reagent_bag:
                self.reagent_bag, self.bank_piles = i['serial'], piles
            elif not inside and i.get('graphic') == BACKPACK:
                self.empties.append(i['serial'])
        # his pack's empty backpacks too ("the empty bags from burgers bank and inventory"), but never the bag mine.py
        # keeps his spare shovels in (MINING.md, the user, 2026-11-04)
        keep = mining_shovel_bag()
        self.pack_empties, self.pack_shovels = [], sum(1 for i in self.pack_items if i.get('graphic') in SHOVELS)
        for i in self.pack_items:
            if i.get('graphic') == BACKPACK and i.get('container'):
                inside = b.open(i['serial'])
                self.pack_shovels += sum(1 for x in inside if x.get('graphic') in SHOVELS)
                if not inside and i['serial'] != keep:
                    self.pack_empties.append(i['serial'])

    def line(self):
        p, k = total(self.pack_piles), total(self.bank_piles)
        return (f"Burgers: {self.shovels} shovels in the bank, {self.pack_shovels} in his pack; reagents pack/bank: "
                + ', '.join(f'{REAGENTS[g]} {p[g]}/{k[g]}' for g in REAGENTS)
                + f'; the bank box holds {self.items} items')


def walk_all(items):
    for i in items:
        yield i
        yield from walk_all(i.get('items') or [])


def count_items(items):
    return sum(1 for _ in walk_all(items))


def burgers_to_bank(b):
    """Burgers to the Ocllo bank (his "Ocllo" rune), off Clem's landing spot, guard off, hidden."""
    st = login_resumed(b.info, b.status(), 'Burgers')
    if st.get('takenOver'):
        raise UserHas(f"the user has Burgers ({st['takenOver']})")
    b.call('POST', '/guard', on=0)
    if not b.at_bank(st):
        st = b.recall(BURGERS_BANK_RUNE, 'the Ocllo bank')
        if not b.at_bank(st):
            raise Stop(f"Burgers' bank rune put him at {st['x']},{st['y']}, not at the Ocllo bank")
    if (st['x'], st['y']) == CLEM_LANDS:
        step_to(b, [s for s in around(CLEM_LANDS) if s != CLEM_LANDS])
    b.hide()


def around(p):
    return [(p[0] + dx, p[1] + dy) for dx, dy in ((0, 1), (1, 1), (-1, 1), (1, 0), (-1, 0), (1, -1), (-1, -1), (0, -1))]


def step_to(b, spots):
    """One step for Burgers onto the first of these tiles he can stand on (shows him: a hidden step reveals)."""
    for sp in spots:
        try:
            b.call('POST', '/walk', x=sp[0], y=sp[1], distance=0)
        except Stop:
            continue
        st = b.status()
        if (st['x'], st['y']) == tuple(sp):
            return sp
    st = b.status()
    raise Stop(f"Burgers couldn't step to any of {spots} (he's at {st['x']},{st['y']})")


# ---- Clem ----

def clem_call(fn, *args):
    return shovels.castle_call(fn, *args)


def clem_status():
    return shovels.status()


def fetch_rune():
    """The courtyard ("skara") rune into his reagent bag from the user's chest, unless he has it. True if fetched."""
    kit = shovels.find_kit({})
    if kit['rune']:
        return False
    clem_call(shovels.to_user_chest)
    items = shovels.call('GET', '/contents', serial=shovels.USER_CHEST, depth=1)['items']
    if not any(i['serial'] == shovels.SKARA_RUNE for i in items):
        shovels.call('POST', '/close', serial=shovels.USER_CHEST)
        shovels.stay_in_tools_room_safe()
        raise Stop(f"the courtyard rune {shovels.SKARA_RUNE} is neither in Clem's pack nor in the user's chest")
    shovels.call('POST', '/move', serial=shovels.SKARA_RUNE, to=restock.BAG)
    shovels.call('POST', '/close', serial=shovels.USER_CHEST)
    say("the courtyard (skara) rune from the user's chest into Clem's reagent bag")
    shovels.stay_in_tools_room_safe()
    return True


def rune_back():
    st = clem_status()
    if not castle.inside((st['x'], st['y'])):
        raise Stop(f"the skara rune goes back from inside the castle; Clem is at {st['x']},{st['y']}")
    tools_room.MOVER = None
    clem_call(shovels.to_user_chest)
    r = shovels.call('POST', '/move', serial=shovels.SKARA_RUNE, to=shovels.USER_CHEST)
    shovels.call('POST', '/close', serial=shovels.USER_CHEST)
    if not r.get('moved', True):
        raise Stop(f"the skara rune didn't go back into the user's chest: {r}")
    say("the skara rune is back in the user's chest (938 top)")
    shovels.stay_in_tools_room_safe()


def inside_of(got):
    """The container an item is directly in, from /item (insideOf is the chain, innermost first), or None."""
    chain = got.get('insideOf') or []
    if isinstance(chain, str):
        return chain
    return chain[0].get('serial') if chain else None


def bag_in_pack(pack):
    """A backpack of PER_BAG shovels and nothing else already in his pack (a run stopped after taking it), or None."""
    for i in shovels.call('GET', '/contents', serial=pack, depth=2)['items']:
        if i.get('graphic') == BACKPACK and i.get('container') and i['serial'] not in tools_room.KEEP:
            inside = i.get('items') or []
            if len(inside) != PER_BAG:
                continue
            items = tools_room.contents(i['serial'])[0]
            if len(items) == PER_BAG and all(x.get('graphic') in SHOVELS for x in items):
                return i['serial']
    return None


def pick_bag(by_spot, cache):
    """The bag to take: the top bag of the highest stack that holds PER_BAG shovels and nothing else (by the record),
    or None."""
    tops = [v[-1] for v in by_spot.values() if v]
    for b in sorted(tops, key=lambda i: (-(i.get('z') or 0), -len(by_spot[(i['x'], i['y'])]))):
        e = cache.get(b['serial'])
        if e and sum(e['items'].values()) == PER_BAG and set(e['items']) <= SHOVELS:
            return b
    return None


def take_bag():
    """A full bag of shovels off the top of a stack into his pack (opened first: 50 shovels, nothing else)."""
    clem_call(tools_room.stand)
    cache = tools_room.load()
    pack = clem_status()['backpack']['serial']
    held = bag_in_pack(pack)
    if held:
        cache.pop(held, None)
        tools_room.save(cache)
        tools_room.to_page(cache)
        say(f'the bag {held} (50 shovels) is in his pack already: that one')
        return held, None
    _, by_spot = tools_room.bags('shovels')
    for _ in range(3):
        b = pick_bag(by_spot, cache)
        if not b:
            raise Stop('no full bag of 50 shovels on top of any stack in the tools room')
        items = tools_room.contents(b['serial'])[0]
        tools_room.record(cache, b, items)
        if len(items) == PER_BAG and all(i.get('graphic') in SHOVELS for i in items):
            break
        say(f"the bag {b['serial']} at {b['x']},{b['y']} z{b.get('z')} holds {len(items)} things, not {PER_BAG} shovels")
    else:
        tools_room.save(cache)
        raise Stop('no full bag of shovels found on the stacks')
    shovels.call('POST', '/move', serial=b['serial'], to=pack, x=44, y=65)
    time.sleep(0.5)  # Razor's AutoSearch opens a bag as it lands: its click shows on the next request, this one
    got = shovels.call('GET', '/item', serial=b['serial'])
    if inside_of(got) != pack:
        raise Stop(f"the bag {b['serial']} didn't come into Clem's pack ({got})")
    cache.pop(b['serial'], None)
    tools_room.save(cache)
    tools_room.to_page(cache)
    left = sum(e['items'].get('0x0F39', 0) + e['items'].get('0x0F3A', 0) for e in cache.values())
    say(f"took the bag {b['serial']} (50 shovels) off the stack at {b['x']},{b['y']} z{b.get('z')}; "
        f"TOOLS ROOM: {left} shovels")
    return b['serial'], (b['x'], b['y'])


def put_bag_back(serial):
    """A bag of shovels that didn't go to Burgers back on the stacks, recorded."""
    clem_call(tools_room.stand)
    b = tools_room.place_bag(serial, 'shovels')
    cache = tools_room.load()
    tools_room.record(cache, b, tools_room.contents(serial)[0])
    tools_room.save(cache)
    tools_room.to_page(cache)
    say(f"the bag {serial} back on the stack at {b['x']},{b['y']}")


def free_stones():
    st = clem_status()
    return st['weightMax'] - WEIGHT_MARGIN - st['weight']


def pack_piles_for_burgers():
    """Burgers' piles in Clem's pack (loose, at SPOTS): {graphic: (serial, amount)}."""
    pack = clem_status()['backpack']['serial']
    out = {}
    for i in shovels.call('GET', '/contents', serial=pack, depth=1)['items']:
        g = i.get('graphic')
        if g in REAGENTS and (i.get('x'), i.get('y')) == SPOTS[g]:
            out[g] = (i['serial'], i.get('amount', 1))
    return out


def take_reagents(want):
    """This trip's reagents for Burgers from the entrance chest (938 2nd) into Clem's pack, each as its own pile at
    SPOTS (never onto his casting reagents), then back to the tools room. The chest short of one: topped up from the
    other chests (reagents_topup.py) and tried once more."""
    if not want:
        return {}
    mover = castle_site.Mover(uo, info, say)
    for attempt in (1, 2):
        mover.walk_near(info, restock.CASTLE_CHEST)
        items = shovels.call('POST', '/open', serial=restock.CASTLE_CHEST)['contents']['items']
        piles = reagent_piles(items)
        have = total(piles)
        short = {g: n for g, n in want.items() if have[g] < n}
        if not short:
            break
        shovels.call('POST', '/close', serial=restock.CASTLE_CHEST)
        if attempt == 2:
            raise Stop('the entrance reagent chest is still short after the top-up: '
                       + ', '.join(f'{REAGENTS[g]} {have[g]} of {n}' for g, n in short.items()))
        clem_call(shovels.topup_entrance_chest, 'for Burgers: ' + ', '.join(
            f'{REAGENTS[g]} {have[g]} of {n}' for g, n in short.items()))
        mover = castle_site.Mover(uo, info, say)
    pack = clem_status()['backpack']['serial']
    mine = {g: s for g, (s, _) in pack_piles_for_burgers().items()}
    for g, n in want.items():
        left = n
        for serial, amount, _ in sorted(piles[g], key=lambda p: -p[1]):
            if left <= 0:
                break
            take = min(left, amount)
            extra = {'amount': take} if take < amount else {}
            if mine.get(g):
                shovels.call('POST', '/move', serial=serial, to=mine[g], **extra)
            else:
                shovels.call('POST', '/move', serial=serial, to=pack, x=SPOTS[g][0], y=SPOTS[g][1], **extra)
                mine[g] = serial
            left -= take
    shovels.call('POST', '/close', serial=restock.CASTLE_CHEST)
    got = pack_piles_for_burgers()
    say('for Burgers, from the entrance chest: ' + ', '.join(f'{REAGENTS[g]} {got.get(g, (0, 0))[1]}' for g in want))
    if mover.table_opened:
        tools_room.MOVER = mover
        shovels.stay_in_tools_room()
    else:
        mover.go(tools_room.OUT, 'back to the tools room')
        tools_room.walk_to(tools_room.STAND, 'into the tools room')
    return got


def return_backpacks(serials):
    """The empty backpacks Burgers gave him into the spare backpacks chest (938 3rd), from the tools room."""
    if not serials:
        return
    pack = clem_status()['backpack']['serial']
    carried = {i['serial'] for i in shovels.call('GET', '/contents', serial=pack, depth=1)['items']}
    serials = [s for s in serials if s in carried]
    if not serials:
        return
    tools_room.walk_to(tools_room.SPARE_STAND, 'to the spare backpacks chest')
    shovels.call('POST', '/open', serial=tools_room.SPARE_BACKPACKS)
    put = []
    for s in serials:
        if tools_room.contents(s)[0]:
            say(f'{s} from Burgers is not empty: it stays in his pack')
            continue
        shovels.call('POST', '/move', serial=s, to=tools_room.SPARE_BACKPACKS)
        put.append(s)
    shovels.call('POST', '/close', serial=tools_room.SPARE_BACKPACKS)
    tools_room.walk_to(tools_room.STAND, 'back to the tools room')
    say(f'{len(put)} empty backpacks into the spare backpacks chest (938 3rd)')


def clem_home(carrying_bag=None, backpacks=()):
    """Recall home by the skara rune; in by the north door, locked; the backpacks away, a bag that didn't go back on
    the stacks, loose shovels into the tools room; waiting in the tools room with the table locked."""
    st = clem_status()
    if st.get('trade'):
        shovels.call('POST', '/trade', cancel=1)
    if st['mana'] < 11:
        clem_call(trips.meditate_to, 15)
    st = clem_call(castle.recall, shovels.SKARA_RUNE, 'skara (the castle courtyard)')
    if shovels.in_north_yard(st):
        shovels.go_in_north()
    elif shovels.in_courtyard(st):
        shovels.go_in()
    else:
        where = f"{st['x']},{st['y']},{st['z']}"
        if 929 <= st['x'] <= 941 and 2351 <= st['y'] <= 2362:
            say(f'the courtyard rune put him at the castle front ({where}): in through the front door')
            shovels.go_in()
        raise Stop(f'the courtyard rune put him at {where}, not in the north yard')
    tools_room.MOVER = None
    clem_call(tools_room.stand)
    clem_call(return_backpacks, list(backpacks))
    if carrying_bag:
        clem_call(put_bag_back, carrying_bag)
    if shovels.shovels_carried():
        try:  # (a loose shovel with no bag to go in, the spare backpacks chest empty: it waits in his pack)
            clem_call(tools_room.put, ['shovels'], (), False)
        except UserHas:
            raise
        except Stop as e:
            say(f'loose shovels stay in his pack: {e}')
    shovels.stay_in_tools_room_safe()


# ---- the trade ----

def clem_sees_burgers():
    for _ in range(20):
        seen = [m for m in shovels.call('GET', '/nearby', range=3)['mobiles'] if m['serial'] == BURGERS]
        if seen and seen[0].get('name'):
            return True
        time.sleep(0.5)
    return False


def trade(b, give_clem, give_burgers):
    """Burgers shows himself next to Clem; Clem drops give_burgers on him, Burgers drops give_clem on Clem, both accept.
    Returns when the trade has gone through."""
    c = clem_status()
    here = (c['x'], c['y'])
    bst = b.status()
    if bst['hidden'] or cheb((bst['x'], bst['y']), here) > 1:
        spots = [s for s in around(here) if s != (bst['x'], bst['y'])]
        step_to(b, spots)
    if not clem_sees_burgers():
        raise Stop("Clem can't see Burgers next to him for the trade")
    for s in give_burgers:
        shovels.call('POST', '/give', serial=s, to=BURGERS)
    for s in give_clem:
        b.call('POST', '/give', serial=s, to=CLEM)
    shovels.call('POST', '/trade', accept=1)
    b.call('POST', '/trade', accept=1)
    for _ in range(10):
        time.sleep(0.5)
        if not clem_status().get('trade') and not b.status().get('trade'):
            break
    else:
        raise Stop('the trade between Clem and Burgers did not go through')
    bpack = b.pack()
    held = {i['serial'] for i in walk_all(b.contents(bpack, depth=1))}
    missing = [s for s in give_burgers if s not in held]
    if missing:
        raise Stop(f'after the trade Burgers does not have {missing}')
    say(f'trade: Clem gave Burgers {len(give_burgers)} things, Burgers gave Clem {len(give_clem)} empty backpacks')


def burgers_put_away(b, view, bag, piles, to_bank=True):
    """At the bank: the bag of shovels into the bank box whole; each reagent onto his pack's pile up to his pack's
    amount (view.pack_target), the rest onto the bank reagent bag's pile; then hidden. Returns where the bag is
    ('bank', or 'pack' when the box wouldn't take it)."""
    box = b.bank()
    where = ('bank' if to_bank else 'pack') if bag else None
    if bag and not to_bank:
        say(f"Burgers: the bag of shovels {bag} stays in his pack, for Icepick")
    elif bag:
        r = b.call('POST', '/move', serial=bag, to=box)
        got = b.call('GET', '/item', serial=bag)
        if inside_of(got) != box:
            where = 'pack'
            say(f"the bank box would not take the bag of shovels {bag} "
                f"({' | '.join(m['text'] for m in r.get('messages', []))}): it stays in Burgers' pack")
        else:
            say(f'Burgers: the bag of shovels {bag} is in his bank box')
    if piles and view.reagent_bag:
        b.open(view.reagent_bag)
    for g, (serial, amount) in piles.items():
        mine = [p for p in reagent_piles(b.contents(b.pack(), depth=2))[g] if p[0] != serial]
        to_pack = max(0, min(amount, view.pack_target.get(g, PACK_TARGET) - sum(p[1] for p in mine)))
        rest = amount - to_pack
        if rest:
            if not view.reagent_bag:
                raise Stop(f"no reagent bag in Burgers' bank for {rest} {REAGENTS[g]} (left in his pack)")
            # the part moved keeps the serial; what's left behind (the pack's share) gets a new one
            onto = view.bank_piles[g][0][0] if view.bank_piles[g] else view.reagent_bag
            b.call('POST', '/move', serial=serial, to=onto, amount=rest if to_pack else None)
            if not view.bank_piles[g]:
                view.bank_piles[g] = [(serial, rest, view.reagent_bag)]
        if to_pack and mine:  # onto his own pile (in his pouch); with none, it stays where the trade put it
            for p in reagent_piles(b.contents(b.pack(), depth=2))[g]:
                if p[0] != mine[0][0]:
                    b.call('POST', '/move', serial=p[0], to=mine[0][0])
    b.hide()
    return where


# ---- the job ----

def loops_running(out=None):
    """(Burgers' loops running, the shovel loop running or None), from `ps`."""
    if out is None:
        out = subprocess.run(['ps', '-axo', 'command'], capture_output=True, text=True).stdout
    lines = [l for l in out.splitlines() if 'python' in l.lower()]
    bur = sorted({m.group(0) for l in lines for m in [re.search(r'\b' + BURGERS_LOOPS, l)] if m})
    clem = 'shovels.py' if any(re.search(r'shovels\.py (run|resume)', l) for l in lines) else None
    return bur, clem


def login_resumed(i, st, name):
    """A takeover that is the client's own login routine (the nightly reboot's double-clicks; 2026-11-27 11:25 Clem
    still showed "a double-click at 04:19:07") is not the user: resumed, as mine.py does. The status after."""
    taken = st.get('takenOver')
    if taken and uo.login_routine(i, taken):
        RAW_CALL(i, 'POST', '/resume')
        say(f"{name}: the client's login routine counted as a takeover ({taken}); resumed")
        return RAW_CALL(i, 'GET', '/status')
    return st


def setup_clem():
    global info
    info = uo.find_bridge('Clem')
    shovels.info = info
    tools_room.setup(info)
    trips.info = carto.info = door.info = restock.info = castle.info = gems.info = info
    trips.LOG = carto.LOG = gems.LOG = castle.LOG = restock.LOG = shovels.LOG = LOG
    tools_room.say = say
    tools_room.castle_move.say = say
    tools_room.TRUST_CACHE = True  # the shovel run's count stands; the bags taken here come off the record
    st = login_resumed(info, uo.call(info, 'GET', '/status'), 'Clem')
    if st.get('takenOver') and tools_room.castle_move.razor_opened(None):  # Razor's AutoSearch (15:24:44), not the user
        st = uo.call(info, 'GET', '/status')
    if st.get('takenOver'):
        raise UserHas(f"the user has Clem ({st['takenOver']})")
    if st.get('halted'):
        raise Stop(f"Clem's bridge has stopped ({st['halted']})")
    return st


def run(bags, asked, bank_bags=BANK_BAGS):
    bur, clem_loop = loops_running()
    if bur:
        raise Stop(f"Burgers' loop is running ({', '.join(bur)}): the mining agent stops and parks him first")
    if clem_loop:
        raise Stop('the shovel loop is running: `shovels.py pause` first (and resume it after)')
    st = setup_clem()
    if not castle.inside((st['x'], st['y'])) and not tools_room.in_room((st['x'], st['y'])):
        if shovels.in_north_yard(st):
            shovels.go_in_north()
        elif shovels.in_courtyard(st) or (935 <= st['x'] <= 936 and 2348 <= st['y'] <= 2350):
            shovels.go_in()  # the courtyard or the entrance room: in by the central door, locked behind him
        else:
            raise Stop(f"Clem starts from inside the castle; he's at {st['x']},{st['y']}")
    b = Bur()
    bst = login_resumed(b.info, b.status(), 'Burgers')
    if bst.get('takenOver'):
        raise UserHas(f"the user has Burgers ({bst['takenOver']})")
    say(f"--- burgers.py run: {bags} bags; Clem at {st['x']},{st['y']},{st['z']} {st['weight']}/{st['weightMax']}; "
        f"Burgers at {bst['x']},{bst['y']},{bst['z']} {bst['weight']}/{bst['weightMax']}, mana {bst['mana']}")
    burgers_rules_for_bank()
    fetched = False
    out = {'clem': False}  # Clem away from the castle: on any stop he's brought home first
    try:
        burgers_to_bank(b)
        view = BankView(b)
        say(view.line())
        need = reagents_needed(total(view.pack_piles), total(view.bank_piles), asked)
        view.pack_target = {g: total(view.pack_piles)[g] + need[g][0] for g in REAGENTS}
        say('Burgers needs: ' + ', '.join(f'{REAGENTS[g]} {p} for his pack, {k} for his bank'
                                          for g, (p, k) in need.items()))
        # the empty backpacks from his bank into his pack, for the first trade
        empties = list(view.pack_empties)
        bpack = b.pack()
        for s in view.empties:
            b.call('POST', '/move', serial=s, to=bpack)
            empties.append(s)
        if empties:
            say(f"Burgers: {len(empties)} empty backpacks ready for Clem ({len(view.empties)} from his bank)")
        b.hide()
        left = {g: p + k for g, (p, k) in need.items()}
        fetched = fetch_rune()
        kit = shovels.find_kit({})
        if not kit['bank']:
            raise Stop('no "Ocllo Bank" rune in Clem\'s pack')
        trip_no, given = 0, 0
        while given < bags or any(left.values()):
            if stop_asked():
                say('asked to stop: no more trips')
                break
            trip_no += 1
            # the bank's bags, then the reagents, then the bag for his pack (he has room for the reagents' trade
            # before it: 253 stones in his pack after it)
            carry_bag = given < bags and not (given >= bank_bags and any(left.values()))
            if carry_bag:
                bst = b.status()
                room = bst['weightMax'] - bst['weight']
                if room < BAG_STONES:
                    raise Stop(f"Burgers can't hold a bag of 50 shovels ({bst['weight']}/{bst['weightMax']} stones, "
                               f"{room} free, a bag is {BAG_STONES}): stopped before the trip, Clem in the tools room")
            clem_call(shovels.prepare, {}, 30)
            bag = None
            if carry_bag:
                bag, _ = clem_call(take_bag)
            # the reagents on trips of their own, after the bags (the user, 2026-11-26 15:32, after Clem was
            # overloaded: the entrance chest ran short and its top-up loaded 52 stones of reagents onto him on top of
            # the bag of shovels: "I thought you were going to do the reagents as a separate trip?")
            want = {}
            if not bag:
                bst = b.status()
                bur_room = bst['weightMax'] - WEIGHT_MARGIN - bst['weight']
                want = share(left, 1, min(free_stones(), bur_room))
            got = clem_call(take_reagents, want)
            st = clem_status()
            if st['weight'] > st['weightMax'] - WEIGHT_MARGIN:
                raise Stop(f"Clem is carrying {st['weight']}/{st['weightMax']} stones before the trip: too much; "
                           f"stopped in the castle")
            if not bag and not got:
                raise Stop(f'trip {trip_no}: nothing fits in his pack ({free_stones()} stones free)')
            try:
                st = clem_call(castle.recall, kit['bank'], 'the Ocllo bank')
            except Stop:
                if bag:
                    clem_call(put_bag_back, bag)
                    shovels.stay_in_tools_room_safe()
                raise
            out.update(clem=True, bag=bag, backpacks=[])
            if cheb((st['x'], st['y']), CLEM_LANDS) > shovels.BANK_SLACK:
                clem_home(bag)
                raise Stop(f"Clem's bank rune put him at {st['x']},{st['y']}, not at the Ocllo bank")
            give = ([bag] if bag else []) + [s for s, _ in got.values()]
            try:
                trade(b, empties, give)
            except Stop:
                try:
                    b.hide()
                except Stop:
                    pass
                raise
            backpacks, empties = empties, []
            out['bag'], out['backpacks'] = None, backpacks
            where = burgers_put_away(b, view, bag, got, to_bank=given < bank_bags)
            for g, (_, n) in got.items():
                left[g] = max(0, left[g] - n)
            if bag:
                given += 1
            say(f"trip {trip_no}: {'a bag of 50 shovels (' + where + ') and ' if bag else ''}"
                + (', '.join(f'{REAGENTS[g]} {n}' for g, (_, n) in got.items()) or 'no reagents')
                + f' to Burgers; still to bring: {bags - given} bags'
                + (', ' + ', '.join(f'{REAGENTS[g]} {n}' for g, n in left.items() if n) if any(left.values()) else ''))
            clem_home(None, backpacks)
            out['clem'] = False
            if where == 'pack' and given <= bank_bags:
                raise Stop("Burgers' bank box is full (it holds 125 things, counting what's in its bags): the last "
                           "bag of shovels is in his pack. Clem is home")
        view = BankView(b)
        b.hide()
        say(f'FINAL: {given * PER_BAG} shovels given in {given} bags this run. ' + view.line())
        if not shovels.find_kit({})['book']:  # (not the shovel loop's kit: it came out for this, maybe on an earlier
            rune_back()                         # run that stopped, 2026-11-26)
    except Stop as e:
        if out['clem'] and not uo.call(info, 'GET', '/status').get('takenOver'):
            say(f'stopping ({e}): Clem home first')
            try:
                held = carried_serials()
                clem_home(out.get('bag') if out.get('bag') in held else None, out.get('backpacks') or [])
            except Stop as e2:
                say(f"couldn't bring Clem home: {e2}")
        raise
    finally:
        burgers_rules_back()


def carried_serials():
    pack = clem_status()['backpack']['serial']
    return {i['serial'] for i in walk_all(shovels.call('GET', '/contents', serial=pack, depth=1)['items'])}


def survey():
    bur, _ = loops_running()
    if bur:
        raise Stop(f"Burgers' loop is running ({', '.join(bur)}): the mining agent stops and parks him first")
    b = Bur()
    burgers_rules_for_bank()
    try:
        burgers_to_bank(b)
        v = BankView(b)
        say(v.line())
        say(f"empty backpacks: {len(v.empties)} in his bank, {len(v.pack_empties)} in his pack")
        b.hide()
    finally:
        burgers_rules_back()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['run', 'survey', 'stop'])
    parser.add_argument('--bags', type=int, default=BAGS)
    parser.add_argument('--bank-bags', type=int, default=BANK_BAGS, help='how many of them go into his bank (the rest '
                        'stay in his pack, for Icepick)')
    parser.add_argument('--reagents', help="the amounts asked for: 'black pearl=200,blood moss=200,...'")
    args = parser.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if args.command == 'stop':
        open(STOP_FILE, 'w').close()
        print('asked: the trip he is on finishes (home, bags away), then it stops')
        return
    try:
        os.remove(STOP_FILE)
    except OSError:
        pass
    asked = parse_reagents(args.reagents) if args.reagents else None
    try:
        if args.command == 'run':
            run(args.bags, asked, args.bank_bags)
        else:
            survey()
    except UserHas as e:
        say(f'STOPPED (the user has him): {e}')
        sys.exit(1)
    except (Stop, shovels.Stop, trips.Stop, gems.Stop, castle.Stop, restock.Stop, tools_room.td.Stop) as e:
        say(f'STOPPED: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
