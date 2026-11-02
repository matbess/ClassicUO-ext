#!/usr/bin/env python3
"""The mining loop (see MINING.md): Icepick digs his way down the route, one 8x8 ore block at a time, and takes his
ore to the forge, where he smelts it and hands the ingots to Burgers; Burgers banks them in Ocllo and brings shovels.

  python3 mine.py [--passes N] [--wait MINUTES] [--from BLOCK] [--to BLOCK] [--no-wait]
  python3 mine.py --bank          only a bank trip for Burgers

It runs on its own (no tokens) and stops after the passes, or the moment something needs the user: staff about,
a stolen rune, a lost horse, a bridge gone, anything it doesn't understand. Everything it does goes to
~/claude/uo-agent-work/mining/mine.log, and incidents to incidents.jsonl.

The user's rules it follows (all in MINING.md): slow pace except digging strokes (the bridge does the pacing), ride
whenever not digging and never lose McGee, Burgers hidden whenever he isn't dealing with Icepick, a random rock and
spot in each block, the guard: get away from strangers and hide, wait until they've gone, carry on; staff: stand
still and stop; the bank is relaxed (Burgers' guard is off there).
"""
import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import uo  # noqa: E402
import mining  # noqa: E402

WORK = os.path.expanduser('~/claude/uo-agent-work/mining')
LOG = os.path.join(WORK, 'mine.log')
INCIDENTS = os.path.join(WORK, 'incidents.jsonl')
STATE = os.path.join(WORK, 'state.json')

WEIGHT_MARGIN = 30          # go to the forge this many stones short of full (a dig adds 12)
SHOVELS_WANTED = 5          # Icepick carries this many (the user, 2026-11-01)
BURGERS_SPARES = 10         # Burgers keeps this many in his pack, from the shovel bag in his bank
BANK_AT_INGOTS = 300        # Burgers banks when he holds this many ingots (the user, 2026-11-01; ingots weigh
                            # next to nothing), when he's low on shovels, and at the end of every pass
SMALL_ORE = '0x19B7'        # a small pile: one on its own is too little to smelt; two of a metal can be combined
FOOT_HOP = 6                # between blocks closer than this, Icepick walks and McGee follows
MCGEE_NEAR = 3              # McGee must stay this close, or Icepick goes back and rides
FLEE = 30                   # tiles to put between Icepick and a stranger before hiding
GONE_AFTER = 180            # seconds unseen before a stranger counts as gone
GIVE_UP_WAITING = 1800      # seconds: still not gone after this, stop and tell the user
WATCH_AFTER = 600           # seconds after an incident to keep watching for the same person
GATE = (1141, 1666)         # where Burgers' gate comes out
GATE_SAVES = 40             # use the gate only if it saves at least this many waypoints of riding
BURGERS_HIDE_SPOT = (1147, 1856)
BURGERS_TRADE_SPOT = (1148, 1856)
HIDING = 21
RECALL, GATE_TRAVEL = 32, 52
# what each rune's single-click name must say (the user, 2026-11-01: always check the rune before using it)
RUNE_NAMES = {'bank': 'ocllo bank', 'start': 'mining start', 'forge': 'mining forge', 'gate': 'mining gate'}
RUNE_GRAPHICS = ('0x1F14', '0x1F15', '0x1F16', '0x1F17')


class Stop(Exception):
    """Something the user must hear about now; the loop ends."""


class Alarm(Exception):
    """A guard went off (or a stranger seen again after an incident)."""


class Again(Exception):
    """A world save interrupted a step; run it again from the current state."""


def log(text):
    line = time.strftime('%H:%M:%S ') + text
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(time.strftime('%Y-%m-%d ') + line + '\n')


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class Char:
    def __init__(self, name):
        self.name = name
        try:
            self.info = uo.find_bridge(name)
        except SystemExit as e:
            raise Stop(f'{name}: {e}')

    def call(self, method, path, **params):
        try:
            return uo.call(self.info, method, path, **params)
        except uo.BridgeError as e:
            text = e.message or ''
            if e.code == 409 and (text.startswith('alarm') or text.startswith('staff')):
                raise Alarm(f'{self.name}: {text}')
            if e.code == 423:
                if uo.wait_out_world_save(self.info, e):
                    log(f'{self.name}: a world save interrupted; carrying on')
                    raise Again()
                raise Stop(f'{self.name}: the bridge stopped because the server went quiet ({text})')
            if e.code in (0, 503):
                raise Stop(f'{self.name}: {text}')
            raise

    def status(self):
        return self.call('GET', '/status')

    def pack(self):
        return self.call('GET', '/contents', serial=self.status()['backpack']['serial'])['items']

    def walk(self, x, y, distance=0):
        r = self.call('POST', '/walk', x=x, y=y, distance=distance)
        return r

    def hide(self, tries=4):
        for n in range(tries):
            if self.status()['hidden']:
                return True
            r = self.call('POST', '/skill', id=HIDING)
            if r['hidden']:
                return True
            time.sleep(11)  # skills share a cooldown of about ten seconds
        log(f'{self.name}: could not hide')
        return False


class Miner:
    def __init__(self, args):
        self.args = args
        self.ice = Char('Icepick')
        self.bur = Char('Burgers')
        self.points = mining.route()
        self.targets = mining.plan(self.points)
        self.forge_index = mining.nearest(self.points, *mining.FORGE_SPOT)
        self.gate_index = mining.nearest(self.points, *GATE)
        self.watch = {}          # serial -> until (time) for strangers seen in an incident
        self.repeats = {}        # serial -> how many incidents in a row with them (each doubles the wait)
        self.stats = {'ore': 0, 'misses': 0, 'blocks': 0, 'empty': 0, 'forge visits': 0, 'ingots': 0,
                      'bank trips': 0, 'gates': 0, 'incidents': 0}
        self.state = self.load_state()
        self.fatigue_seen = self.ice.status()['lastMessageId']
        self.runes = dict(mining.RUNES)   # checked by name at the start and before every use

    # ---- state ----

    def load_state(self):
        try:
            with open(STATE, encoding='utf-8') as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {'next': 0, 'emptied': {}, 'bags': {}}

    def save_state(self):
        with open(STATE, 'w', encoding='utf-8') as fh:
            json.dump(self.state, fh, indent=1)

    # ---- the guard ----

    def check_guard(self):
        for c in (self.ice, self.bur):
            g = c.status().get('guard') or {}
            if g.get('alarm'):
                raise Alarm(f"{c.name}: {g['alarm']['reason']}")
        # someone from an earlier incident turning up again near Icepick
        now = time.time()
        self.watch = {s: t for s, t in self.watch.items() if t > now}
        if self.watch:
            near = self.ice.call('GET', '/nearby', range=18)['mobiles']
            for m in near:
                if m['serial'] in self.watch:
                    raise Alarm(f"Icepick: {m['name'] or m['serial']} is back in sight ({m['distance']} tiles)")

    def safely(self, step, *a):
        """Run a step; on an alarm get away, wait it out and run the step again from where things stand."""
        while True:
            try:
                self.check_guard()
                return step(*a)
            except Alarm as e:
                self.handle_alarm(str(e))
            except Again:
                continue

    def incident(self, record):
        record['time'] = time.strftime('%Y-%m-%d %H:%M:%S')
        self.stats['incidents'] += 1
        with open(INCIDENTS, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(record) + '\n')

    def handle_alarm(self, why):
        si, sb = self.ice.status(), self.bur.status()
        ai, ab = (si.get('guard') or {}).get('alarm'), (sb.get('guard') or {}).get('alarm')
        log(f'ALARM {why}')
        staff = any(a and a.get('staff') for a in (ai, ab))
        if staff:
            self.incident({'what': 'staff', 'icepick': ai, 'burgers': ab})
            raise Stop(f'STAFF: {(ai or ab)["reason"]}. Both characters are standing still; nothing more was done.')
        theft = any(a and 'gone from the backpack' in a['reason'] for a in (ai, ab))
        # whose own alarm it is (the other one only has the partner's)
        own_ice = ai and not ai['reason'].split(' ', 1)[-1].startswith('partner')
        own_bur = ab and not ab['reason'].split(' ', 1)[-1].startswith('partner')
        threat = (ai or {}).get('threat') or (ab or {}).get('threat')
        if not ai and not ab:
            # seen again after an incident: no alarm in the bridges, the script raised it
            threat = None
            for m in self.ice.call('GET', '/nearby', range=18)['mobiles']:
                if m['serial'] in self.watch:
                    threat = {'serial': m['serial'], 'name': m['name'], 'x': m['x'], 'y': m['y']}
            own_ice = True
        self.incident({'what': why, 'icepick': ai, 'burgers': ab})
        serial = (threat or {}).get('serial')
        if serial not in (None, '0x00000000'):
            # the same person again soon after the last time (say, still standing by the forge when Burgers came
            # back): wait twice as long before coming back again
            self.repeats[serial] = self.repeats.get(serial, 0) + 1 if serial in self.watch else 1
            self.watch[serial] = time.time() + WATCH_AFTER

        burgers_away = False
        if own_bur and not own_ice:
            burgers_away = self.burgers_get_away()
            self.hide(self.ice)
        elif own_ice:
            waiting_hidden = si['hidden'] and ai and 'stood within' in ai['reason']
            if not waiting_hidden:
                self.icepick_get_away(threat)
            self.hide(self.bur)
        self.wait_until_gone(threat, GONE_AFTER * 2 ** (self.repeats.get(serial, 1) - 1))
        if burgers_away:
            self.burgers_back()
        # clear the alarms, and make sure the runes are all still there
        for c in (self.ice, self.bur):
            c.call('POST', '/guard', on=1)
        time.sleep(2)
        missing = [w['serial'] for w in self.bur.status()['guard'].get('watching', []) if not w['seen']]
        if theft or missing:
            raise Stop(f'a rune is missing from Burgers\' pack ({", ".join(missing) or "see the alarm"}); '
                       'both are hidden; the loop has stopped')
        log('the stranger has gone; carrying on')

    def icepick_get_away(self, threat):
        """Ride straight away from the stranger (the user, 2026-11-01: not along the route, which can snag) to an
        open spot about FLEE tiles from them inside Icepick's areas (the corridor or the open town east of it),
        trying the directions nearest to straight away first (if the only way out is past them, past them), then
        hide. Never just hide on the spot unless there's nowhere at all to go."""
        import math
        s = self.ice.status()
        if not s['mounted']:
            self.mount()
        s = self.ice.status()
        here = (s['x'], s['y'])
        tx, ty = (threat['x'], threat['y']) if threat else here
        areas = mining.load_rules()['areas']
        away = math.atan2(here[1] - ty, here[0] - tx) if here != (tx, ty) else random.uniform(0, 2 * math.pi)
        tried = set()
        # nearest to straight away first; in the canyon, with the stranger at the mouth, the only way out is past
        # them (deeper in is off limits), so the last tries go round to the far side of them
        for turn in (0, 20, -20, 40, -40, 60, -60, 80, -80, 100, -100, 120, -120, 140, -140, 160, -160, 180):
            for dist in (FLEE + 2, FLEE + 6, FLEE - 2):
                a = away + math.radians(turn)
                spot = (round(tx + math.cos(a) * dist), round(ty + math.sin(a) * dist))
                if spot in tried or not mining.in_areas(areas, *spot) or not mining.walkable(*spot):
                    continue
                tried.add(spot)
                before = self.ice.call('GET', '/status')['lastMessageId']
                r = self.ice.walk(spot[0], spot[1], 1)
                new = self.ice.call('GET', '/messages', after=before)['messages']
                if any('left the protection' in m['text'].lower() for m in new):
                    # the guards' edge is closer than thought: straight back where he was, another direction
                    log(f'left the guards\' protection near {r["x"]},{r["y"]}; going back')
                    self.ice.walk(here[0], here[1], 1)
                    continue
                if cheb((r['x'], r['y']), (tx, ty)) >= FLEE - 4:
                    log(f'Icepick got away to {r["x"]},{r["y"]} ({cheb((r["x"], r["y"]), (tx, ty))} tiles from {tx},{ty})')
                    self.hide(self.ice)
                    return
        log('Icepick found nowhere 30 tiles off; hiding where he is')
        self.hide(self.ice)

    def rune(self, key):
        """The serial of Burgers' rune for `key`, checked by its name first. A single click is refused during an
        alarm (until the bridge allows it); then the name checked earlier in this run stands."""
        want = RUNE_NAMES[key]
        try:
            lines = self.bur.call('POST', '/name', serial=self.runes[key])[0]['lines']
        except Alarm:
            log(f'(rune for {want} not re-checked during the alarm; it was checked at the start)')
            return self.runes[key]
        if any(want in line.lower() for line in lines):
            return self.runes[key]
        log(f"the rune {self.runes[key]} says {lines}, not \"{want}\"; looking for the right one")
        candidates = [i['serial'] for i in self.bur.pack() if i.get('graphic') in RUNE_GRAPHICS]
        for answer in self.bur.call('POST', '/name', serial=','.join(candidates)):
            if any(want in line.lower() for line in answer['lines']):
                self.runes[key] = answer['serial']
                return answer['serial']
        raise Stop(f'Burgers has no rune named "{want}"')

    def recall(self, key):
        serial = self.rune(key)
        return self.bur.call('POST', '/cast', spell=RECALL, target=serial)

    def burgers_get_away(self):
        s = self.bur.status()
        if s['mana'] >= 11:
            log('Burgers recalls away to the Mining Start rune')
            r = self.recall('start')
            self.hide(self.bur)
            return r.get('moved', False)
        self.hide(self.bur)
        return False

    def burgers_back(self):
        while self.bur.status()['mana'] < 11:
            time.sleep(15)
        self.recall('forge')
        self.hide(self.bur)

    def wait_until_gone(self, threat, gone_after=GONE_AFTER):
        log(f"waiting until {(threat or {}).get('name') or 'the stranger'} has been out of sight for {gone_after // 60} minutes")
        start = time.time()
        serial = (threat or {}).get('serial')
        last_seen = time.time()
        while True:
            seen = False
            for c in (self.ice, self.bur):
                s = c.status()
                a = (s.get('guard') or {}).get('alarm') or {}
                t = a.get('threat') or {}
                if t.get('visible'):
                    seen = True
                if serial:
                    for m in c.call('GET', '/nearby', range=18)['mobiles']:
                        if m['serial'] == serial:
                            seen = True
                if not s['hidden']:
                    self.hide(c, tries=1)
            if seen:
                last_seen = time.time()
            if time.time() - last_seen >= gone_after:
                return
            if time.time() - start > GIVE_UP_WAITING + gone_after:
                raise Stop(f'the stranger ({(threat or {}).get("name") or "?"}) still hasn\'t gone after '
                           f'{GIVE_UP_WAITING // 60} minutes; both are hidden; the loop has stopped')
            time.sleep(5)

    def hide(self, c, tries=4):
        """Hide, always mounted first (the user, 2026-11-01: a horse standing next to a hidden rider gives him
        away). Icepick gets back on McGee; Burgers never gets off his horse."""
        if c is self.ice and not self.ice.status()['mounted']:
            self.mount()
        elif c is self.bur and not self.bur.status()['mounted']:
            log('Burgers is not riding; hiding anyway')
        return c.hide(tries)

    # ---- moving Icepick ----

    def mcgee(self):
        for m in self.ice.call('GET', '/nearby', range=18)['mobiles']:
            if m['serial'] == mining.HORSE:
                return m
        return None

    def mount(self):
        if self.ice.status()['mounted']:
            return
        h = self.mcgee()
        if not h:
            raise Stop('McGee is nowhere in sight; Icepick is on foot')
        if h['distance'] > 1:
            self.ice.walk(h['x'], h['y'], 1)
        self.ice.call('POST', '/mount', serial=mining.HORSE)
        if not self.ice.status()['mounted']:
            raise Stop("Icepick couldn't get back on McGee")

    def dismount(self):
        if self.ice.status()['mounted']:
            self.ice.call('POST', '/dismount')
            self.ice.call('POST', '/say', text='all follow me')

    def check_mount_fatigue(self):
        new = [m for m in self.ice.call('GET', '/messages', after=self.fatigue_seen)['messages']]
        if new:
            self.fatigue_seen = max(m['id'] for m in new)
        if any('mount is very fatigued' in m['text'].lower() for m in new) and self.ice.status()['mounted']:
            log('McGee is tired: dismount, "all follow me", mount again')
            self.ice.call('POST', '/dismount')
            self.ice.call('POST', '/say', text='all follow me')
            time.sleep(1)
            self.mount()

    def travel_route(self, target, during_alarm=False):
        """Ride along the route to waypoint `target`, taking short cuts (see mining.walk_route)."""
        if not self.ice.status()['mounted']:
            self.mount()
        s = self.ice.status()
        x, y = s['x'], s['y']
        i = mining.nearest(self.points, x, y)
        step = 1 if target >= i else -1
        while cheb(self.points[target], (x, y)) > 1:
            if not during_alarm:
                self.check_guard()
            ahead = [j for j in range(i + step, target + step, step) if cheb(self.points[j], (x, y)) <= 15]
            ahead.reverse()
            moved = False
            for j in ahead[:6]:
                r = self.ice.walk(self.points[j][0], self.points[j][1], 1)
                x, y = r['x'], r['y']
                if r['arrived']:
                    i, moved = j, True
                    break
            if not moved:
                raise Stop(f"Icepick couldn't ride on from {x},{y} towards waypoint {target} {self.points[target]}")
            if not during_alarm:
                self.check_mount_fatigue()

    def go_to(self, spot):
        """Get Icepick to a spot to dig from: on foot for a short hop (McGee follows), riding for anything longer."""
        s = self.ice.status()
        here = (s['x'], s['y'])
        if here == spot:
            return
        if not s['mounted'] and cheb(here, spot) <= FOOT_HOP:
            r = self.ice.walk(spot[0], spot[1], 0)
            h = self.mcgee()
            if not h or h['distance'] > MCGEE_NEAR:
                log('McGee fell behind; going back for him')
                self.mount()
                r = self.ice.walk(spot[0], spot[1], 0)
            return
        if cheb(here, spot) > 15:
            self.travel_route(mining.nearest(self.points, *spot))
        else:
            self.mount()
        self.ice.walk(spot[0], spot[1], 0)

    # ---- digging ----

    def shovels(self):
        return [i['serial'] for i in self.ice.pack() if i.get('graphic') in mining.SHOVELS]

    def heavy(self):
        s = self.ice.status()
        return s['weight'] >= s['weightMax'] - WEIGHT_MARGIN

    def dig_block(self, n):
        t = self.targets[n]
        if self.heavy():
            self.forge_visit('a full pack')
        if not self.shovels():
            self.forge_visit('no shovels')
        rock, stand, others = mining.choose(t)
        rocks = [rock] + others
        self.go_to(stand)
        self.dismount()
        tried = 0
        for rock in rocks:
            s = self.ice.status()
            if cheb((s['x'], s['y']), rock) > 2:
                # stood somewhere else (blocked spot): find a nearer place for this rock
                stands = [st for r, st in t['pairs'] if r == rock]
                if not stands:
                    continue
                self.go_to(min(stands, key=lambda st: cheb(st, (s['x'], s['y']))))
                self.dismount()
            why = self.dig_rock(rock)
            tried += 1
            if why in ('empty', 'already empty'):
                key = f'{t["block"][0]},{t["block"][1]}'
                if why == 'empty':
                    self.state['emptied'][key] = time.strftime('%Y-%m-%d %H:%M')
                else:
                    log(f'block {key} was still empty (it ran dry at {self.state["emptied"].get(key, "?")})')
                self.save_state()
                return
            if why in ('heavy', 'no shovels'):
                self.forge_visit('a full pack' if why == 'heavy' else 'no shovels')
                return self.dig_block(n)
            if tried >= 4:
                break
        log(f'block {t["block"]}: no rock the server would dig; moving on')

    def dig_rock(self, rock):
        x, y, z = rock
        tools = self.shovels()
        first = True
        while True:
            if not tools:
                return 'no shovels'
            self.check_guard()
            try:
                r = self.ice.call('POST', '/use', serial=tools[0], x=x, y=y, z=z, graphic=0)
            except uo.BridgeError as e:
                if e.code in (403, 409):
                    log(f'dig {x},{y}: {e.message}')
                    return 'refused'
                raise
            texts = [m['text'] for m in r['messages'] if m['type'] != 'Label']
            answer = next((t for t in texts if 'wish to dig' not in t.lower()), '(no answer)')
            low = answer.lower()
            if any('worn out' in t.lower() for t in texts):
                tools = self.shovels()
                log(f'a shovel wore out; {len(tools)} left')
            if 'you dig some' in low:
                self.stats['ore'] += 1
            elif 'loosen some rocks' in low:
                self.stats['misses'] += 1
            elif 'no metal here' in low:
                if first:
                    self.stats['empty'] += 1
                log(f'dig {x},{y}: no metal left' + (' (already empty)' if first else ''))
                return 'already empty' if first else 'empty'
            elif 'riding' in low:
                self.dismount()
                continue
            elif 'worn out' not in low:
                log(f'dig {x},{y}: {answer}')
                return 'refused'
            first = False
            if r['weight'] >= r['weightMax'] - WEIGHT_MARGIN:
                return 'heavy'

    # ---- the forge ----

    def forge_visit(self, why):
        self.stats['forge visits'] += 1
        s = self.ice.status()
        here = mining.nearest(self.points, s['x'], s['y'])
        log(f'to the forge ({why}) from waypoint {here}')
        if self.gate_worth_it(here):
            self.via_gate()
        else:
            self.travel_route(self.forge_index)
            self.ice.walk(*mining.FORGE_SPOT, 0)
        self.smelt_all()
        need = SHOVELS_WANTED - len(self.shovels())
        if need > 0 and self.burgers_spares() < need and self.bur.status()['mana'] >= 22:
            self.bank_trip()  # fetch shovels first
        self.handoff()
        end_of_pass = why == 'the end of the route'
        if end_of_pass:
            # everything goes to the bank at the end of a pass: wait for Burgers' mana if need be
            while self.bur.status()['mana'] < 22 and self.ingots(self.bur):
                time.sleep(20)
        if self.burgers_should_bank(end_of_pass):
            self.bank_trip()
        if not self.shovels():
            self.handoff()  # shovels fetched on that trip
        if not self.shovels():
            raise Stop('Icepick has no shovels left and Burgers has none to give')

    def gate_worth_it(self, here):
        if here >= self.gate_index - GATE_SAVES:
            return False
        b = self.bur.status()
        return b['mana'] >= b['manaMax'] and b['manaMax'] >= 40

    def via_gate(self):
        log('Burgers opens a gate; Icepick rides to the gate spot')
        self.travel_route(self.gate_index)
        self.ice.walk(GATE[0] + 1, GATE[1] + 1, 0)
        r = self.bur.call('POST', '/cast', spell=GATE_TRAVEL, target=self.rune('gate'))
        if not any('magical gate' in m['text'].lower() for m in r['messages']):
            log(f'the gate didn\'t open ({[m["text"] for m in r["messages"]][-1:]}); riding instead')
            self.travel_route(self.forge_index)
            self.ice.walk(*mining.FORGE_SPOT, 0)
            return
        self.stats['gates'] += 1
        # off the gate (it opens on his own tile), so Icepick can come through
        b = self.bur.status()
        off = next(sp for sp in (BURGERS_TRADE_SPOT, (1148, 1855), (1146, 1856), BURGERS_HIDE_SPOT)
                   if sp != (b['x'], b['y']) and sp != mining.FORGE_SPOT)
        self.bur.walk(*off, 0)
        self.ice.walk(*GATE, 0)
        s = self.ice.status()
        if cheb((s['x'], s['y']), mining.FORGE_SPOT) > 3:
            log('didn\'t go through the gate; riding instead')
            self.travel_route(self.forge_index)
        self.ice.walk(*mining.FORGE_SPOT, 0)

    def smelt_all(self):
        """Smelt every pile. A lone small pile is too little ("not enough metal-bearing ore"), so it waits for
        another small pile of the same metal; two of them are combined first (the smelt cursor takes another
        pile as well as the forge)."""
        piles = [i for i in self.ice.pack() if i.get('graphic') in mining.ORE]
        small = {}
        for pile in piles:
            if pile['graphic'] == SMALL_ORE and pile.get('amount', 1) < 2:
                small.setdefault(pile.get('hue', 0), []).append(pile)
        for hue, group in small.items():
            while len(group) >= 2:
                a, b = group.pop(), group.pop()
                r = self.ice.call('POST', '/use', serial=a['serial'], target=b['serial'])
                texts = [m['text'] for m in r['messages'] if 'select the forge' not in m['text'].lower()]
                log(f"combine small piles {a['serial']} + {b['serial']} (hue {hue}): {texts[-1] if texts else 'done'}")
        for item in self.ice.pack():
            if item.get('graphic') not in mining.ORE:
                continue
            if item['graphic'] == SMALL_ORE and item.get('amount', 1) < 2:
                continue  # too little on its own; kept for a later pile of the same metal
            answer = '?'
            for _ in range(2):
                r = self.ice.call('POST', '/use', serial=item['serial'], target=mining.FORGE)
                texts = [m['text'] for m in r['messages'] if 'select the forge' not in m['text'].lower()]
                answer = texts[-1] if texts else '?'
                if 'riding' in answer.lower():
                    self.dismount()
                    continue
                break
            log(f"smelt {item['serial']} (hue {item.get('hue')}, {item.get('amount', 1)}): {answer}")

    def ingots(self, char):
        return [i for i in char.pack() if 'ingot' in (i.get('type') or '')]

    def burgers_spares(self):
        return sum(1 for i in self.bur.pack() if i.get('graphic') in mining.SHOVELS)

    def handoff(self):
        bars = self.ingots(self.ice)
        need = max(0, SHOVELS_WANTED - len(self.shovels()))
        spares = [i['serial'] for i in self.bur.pack() if i.get('graphic') in mining.SHOVELS][:need]
        if not bars and not spares:
            return
        # Burgers shows himself with one step next to Icepick, never onto a gate that may still be open
        b = self.bur.status()
        if b['hidden']:
            gates = {(i['x'], i['y']) for i in self.bur.call('GET', '/nearby', range=4)['items']
                     if 'moongate' in (i.get('type') or '')}
            ice = self.ice.status()
            spot = next(sp for sp in (BURGERS_TRADE_SPOT, BURGERS_HIDE_SPOT, (1146, 1856), (1148, 1857), (1146, 1857))
                        if sp != (b['x'], b['y']) and sp not in gates and sp != (ice['x'], ice['y'])
                        and cheb(sp, (ice['x'], ice['y'])) <= 2)
            self.bur.walk(*spot, 0)
        for bar in bars:
            self.ice.call('POST', '/give', serial=bar['serial'], to=self.bur.status()['serial'])
        for shovel in spares:
            self.bur.call('POST', '/give', serial=shovel, to=self.ice.status()['serial'])
        self.ice.call('POST', '/trade', accept=1)
        self.bur.call('POST', '/trade', accept=1)
        time.sleep(1)
        if self.ice.status().get('trade') or self.bur.status().get('trade'):
            raise Stop('the trade between Icepick and Burgers did not finish')
        n = sum(b.get('amount', 1) for b in bars)
        self.stats['ingots'] += n
        log(f'handed Burgers {n} ingots; gave Icepick {len(spares)} shovels')
        self.hide(self.bur)

    def burgers_should_bank(self, end_of_pass=False):
        if self.bur.status()['mana'] < 22:
            return False
        held = sum(i.get('amount', 1) for i in self.ingots(self.bur))
        return held >= BANK_AT_INGOTS or self.burgers_spares() < SHOVELS_WANTED or end_of_pass and held > 0

    def bank_bags(self, bank):
        bags = self.state.setdefault('bags', {})
        if bags.get('shovels') and bags.get('ingots'):
            return bags
        for item in self.bur.call('GET', '/contents', serial=bank)['items']:
            if not item.get('container'):
                continue
            self.bur.call('POST', '/open', serial=item['serial'])
            inside = self.bur.call('GET', '/contents', serial=item['serial'])['items']
            if any(i.get('graphic') in mining.SHOVELS for i in inside):
                bags['shovels'] = item['serial']
            elif any('ingot' in (i.get('type') or '') for i in inside):
                bags['ingots'] = item['serial']
        if not (bags.get('shovels') and bags.get('ingots')):
            raise Stop(f"couldn't find the shovel bag and the ingot bag in Burgers' bank (found {bags})")
        uo.save_label(bags['shovels'], 'bag: shovels (Burgers\' bank)')
        uo.save_label(bags['ingots'], 'bag: ingots (Burgers\' bank)')
        self.save_state()
        return bags

    def bank_trip(self):
        """Burgers to the Ocllo bank and back. The bank is relaxed (the user): his guard is off while he's there."""
        self.stats['bank trips'] += 1
        log('Burgers takes the ingots to the bank')
        self.bur.call('POST', '/guard', on=0)
        try:
            r = self.recall('bank')
            if not r['moved']:
                raise Stop(f"Burgers' Recall to the bank didn't work: {[m['text'] for m in r['messages']][-2:]}")
            bank = self.bur.call('POST', '/say', text='bank').get('bank', {}).get('serial')
            if not bank:
                raise Stop("Burgers said \"bank\" but no bank box opened")
            bags = self.bank_bags(bank)
            for bag in (bags['shovels'], bags['ingots']):
                self.bur.call('POST', '/open', serial=bag)
            in_bag = self.bur.call('GET', '/contents', serial=bags['ingots'])['items']
            for bar in self.ingots(self.bur):
                same = next((i for i in in_bag if i.get('graphic') == bar.get('graphic') and i.get('hue') == bar.get('hue')), None)
                self.bur.call('POST', '/move', serial=bar['serial'], to=same['serial'] if same else bags['ingots'])
            want = BURGERS_SPARES - self.burgers_spares()
            if want > 0:
                spare = [i['serial'] for i in self.bur.call('GET', '/contents', serial=bags['shovels'])['items']
                         if i.get('graphic') in mining.SHOVELS][:want]
                pack = self.bur.status()['backpack']['serial']
                for shovel in spare:
                    self.bur.call('POST', '/move', serial=shovel, to=pack)
                log(f'Burgers took {len(spare)} shovels from the bank')
            r = self.recall('forge')
            if not r['moved']:
                raise Stop(f"Burgers' Recall back to the forge didn't work: {[m['text'] for m in r['messages']][-2:]}")
        finally:
            self.bur.call('POST', '/guard', on=1)
        time.sleep(2)
        missing = [w['serial'] for w in self.bur.status()['guard'].get('watching', []) if not w['seen']]
        if missing:
            raise Stop(f"a rune is missing from Burgers' pack after the bank trip: {missing}")
        self.hide(self.bur)

    # ---- the pass ----

    def preflight(self):
        si, sb = self.ice.status(), self.bur.status()
        log(f"Icepick at {si['x']},{si['y']} weight {si['weight']}/{si['weightMax']}, {len(self.shovels())} shovels; "
            f"Burgers at {sb['x']},{sb['y']} mana {sb['mana']}/{sb['manaMax']}, {self.burgers_spares()} spare shovels")
        for c in (self.ice, self.bur):
            c.call('POST', '/guard', on=1)
        time.sleep(2)
        missing = [w['serial'] for w in self.bur.status()['guard'].get('watching', []) if not w['seen']]
        if missing:
            raise Stop(f"Burgers' pack doesn't show these runes: {missing} (open his backpack once?)")
        if not self.mcgee() and not si['mounted']:
            raise Stop('McGee is not near Icepick')
        for key in RUNE_NAMES:
            self.rune(key)
        log('runes checked: ' + ', '.join(f'{k} {v}' for k, v in self.runes.items()))
        # Burgers belongs by the forge (an earlier run may have stopped while he was away)
        if cheb((sb['x'], sb['y']), BURGERS_HIDE_SPOT) > 5:
            log(f"Burgers is at {sb['x']},{sb['y']}, not by the forge; recalling him back")
            self.burgers_back()
        self.hide(self.bur)

    def run(self):
        os.makedirs(WORK, exist_ok=True)
        start = time.time()
        self.preflight()
        first = self.args.start if self.args.start is not None else self.state.get('next', 0)
        last = self.args.end if self.args.end is not None else len(self.targets) - 1
        for p in range(self.args.passes):
            log(f'pass {p + 1}: blocks {first} to {last}')
            for n in range(first, last + 1):
                self.state['next'] = n
                self.save_state()
                self.safely(self.dig_block, n)
                self.stats['blocks'] += 1
                self.safely(self.check_mount_fatigue)
            self.safely(self.forge_visit, 'the end of the route')
            self.safely(self.mount)
            self.state['next'] = 0
            self.save_state()
            first, last = 0, len(self.targets) - 1
            if p + 1 < self.args.passes and not self.args.no_wait:
                self.safely(self.travel_route, self.targets[0]['index'])
                self.hide(self.ice)
                log(f'waiting {self.args.wait} minutes for the ore to come back')
                end = time.time() + self.args.wait * 60
                while time.time() < end:
                    self.safely(lambda: None)
                    time.sleep(30)
        self.report(start)

    def report(self, start):
        minutes = (time.time() - start) / 60
        log('done: ' + ', '.join(f'{k} {v}' for k, v in self.stats.items()) + f' in {minutes:.0f} minutes')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--passes', type=int, default=1)
    p.add_argument('--wait', type=int, default=60, help='minutes between passes for the ore to come back')
    p.add_argument('--no-wait', action='store_true')
    p.add_argument('--from', dest='start', type=int, help='first block (default: where the last run stopped)')
    p.add_argument('--to', dest='end', type=int, help='last block')
    p.add_argument('--bank', action='store_true', help='only send Burgers on a bank trip, then stop')
    args = p.parse_args()
    miner = None
    try:
        miner = Miner(args)
        if args.bank:
            os.makedirs(WORK, exist_ok=True)
            start = time.time()
            miner.preflight()
            miner.safely(miner.bank_trip)
            miner.report(start)
            return
        miner.run()
    except Stop as e:
        log(f'STOPPED: {e}')
        if miner:
            miner.report(time.time())
        sys.exit(2)
    except uo.BridgeError as e:
        log(f'STOPPED on an unexpected answer from the bridge: {e}')
        sys.exit(3)


if __name__ == '__main__':
    main()
