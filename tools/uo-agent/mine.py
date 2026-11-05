#!/usr/bin/env python3
"""The mining loop (see MINING.md): Icepick digs his way down the route, one 8x8 ore block at a time, and takes his
ore to the forge, where he smelts it and hands the ingots to Burgers; Burgers banks them in Ocllo and brings shovels.

  python3 mine.py [--passes N] [--wait MINUTES] [--from BLOCK] [--to BLOCK] [--no-wait]
  python3 mine.py --bank          only a bank trip for Burgers
  python3 mine.py --incidents     the run-and-hide incidents the user hasn't reviewed (shown at every handoff)
  python3 mine.py --reviewed      the user has reviewed them: the count goes back to 0

It runs on its own (no tokens) and stops after the passes, or the moment something needs the user: a stolen rune, a lost horse, a bridge gone, anything it doesn't understand. Everything it does goes to
~/claude/uo-agent-work/mining/mine.log, and incidents to incidents.jsonl.

The user's rules it follows (all in MINING.md): slow pace except digging strokes (the bridge does the pacing), ride
whenever not digging and never lose McGee, Burgers hidden whenever he isn't dealing with Icepick, a random rock and
spot in each block, the guard: get away from strangers and hide, wait until they've gone, carry on (staff too: the
user, 2026-11-04); the bank is relaxed (Burgers' guard is off there).
"""
import argparse
import json
import os
import random
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import uo  # noqa: E402
import mining  # noqa: E402

WORK = os.path.expanduser('~/claude/uo-agent-work/mining')
LOG = os.path.join(WORK, 'mine.log')
INCIDENTS = os.path.join(WORK, 'incidents.jsonl')
STATE = os.path.join(WORK, 'state.json')
PID_FILE = os.path.join(WORK, 'mine.pid')  # the running loop's process (for --stop and --park)
PARK_FILE = os.path.join(WORK, 'park')     # --park asks the running loop to park both characters and end

HEAVY = 380                 # go to the forge only once the pack weighs more than this (the user, 2026-11-01)
LIMIT = 393                 # never go past this (the user, 2026-11-02): over it every step tires Icepick out. A dig
BIGGEST_DIG = 24            # usually adds 12 but can bring two ore, so he stops digging once the next dig could pass it
SHOVELS_WANTED = 3          # Icepick carries this many (the user: 5 at first, then 2, then 3 after he ran out, 2026-11-02)
BURGERS_SPARES = 20         # Burgers keeps this many in his pack, from the shovel bag in his bank (the user, 2026-11-01)
BANK_AT_INGOTS = 300        # Burgers banks when he holds this many ingots (the user, 2026-11-01; ingots weigh
                            # next to nothing), when he's low on shovels, and at the end of every pass
# Burgers' four reagents (Recall: black pearl, blood moss, mandrake root; Gate Travel: black pearl, mandrake root,
# sulfurous ash). He keeps 35 of each in his pouch and tops up from a bag in his bank (the user, 2026-11-02).
REAGENTS = {'0x0F7A': 'black pearl', '0x0F7B': 'blood moss', '0x0F86': 'mandrake root', '0x0F8C': 'sulfurous ash'}
REAGENTS_WANTED = 35        # the user, 2026-11-02: enough that reagents seldom need a trip of their own
REAGENTS_WARN = 20          # below this the loop warns the user to add more (the user, 2026-11-03)
RECALL_REAGENTS = ('0x0F7A', '0x0F7B', '0x0F86')  # black pearl, blood moss, mandrake root
REAGENTS_RESERVE = 4        # with the bank out of one of these, the loop parks before he could get stuck there
REAGENTS_LOW = {'0x0F7A': 6, '0x0F7B': 6, '0x0F86': 6, '0x0F8C': 3}  # below this a bank trip is a must
SMALL_ORE = '0x19B7'        # a small pile: one on its own is too little to smelt; two of a metal can be combined
FOOT_HOP = 12               # between blocks closer than this, Icepick walks and McGee follows (the user, 2026-11-01)
MCGEE_NEAR = 8              # McGee must be this close a moment after a walk, or Icepick goes back and rides (the user: 8)
MCGEE_STUCK = 5             # seconds McGee may stay more than 2 tiles off without coming closer before he counts as stuck
TAMING = 35                 # Animal Taming: McGee tamed again if he goes wild (the user, 2026-11-02)
TAME_TRIES = 30
TAME_GAP = 10               # seconds between tries (the server wants a pause between skill uses)
                            # (3, checked at once, was too strict: a following horse is a few steps behind)
FLEE = 50                   # tiles to put between Icepick and a stranger before hiding (the user: 30, then 50 on 2026-11-02)
GONE_AFTER = 30             # seconds unseen before a stranger counts as gone (the user, 2026-11-02 18:05; was 3 minutes)
GIVE_UP_WAITING = 1800      # seconds: still not gone after this, stop and tell the user
WATCH_AFTER = 600           # seconds after an incident to keep watching for the same person
GATE = (1141, 1666)         # where Burgers' gate to the "Mining gate location" rune comes out
START = (1130, 1544)        # where the "Mining Start" rune leads (the top of the route)
GATE_ENDS = {'gate': GATE, 'start': START}
MANA_WAIT = 240             # seconds to wait for Burgers' mana for a gate before riding instead
GATE_SAVES = 40             # use the gate only if it saves at least this many waypoints of riding
BURGERS_WAIT = (1140, 1849)  # where Burgers waits hidden: grass at the foot of the mountain 10 tiles from the forge,
                             # which other players use too (the user, 2026-11-02); trades and gates happen here
ICE_MEET = (1141, 1850)      # where Icepick comes up next to him
NEXT_TO = ((1, 1), (0, 1), (1, 0), (-1, 1), (1, -1), (0, -1), (-1, 0), (-1, -1))
GUILD_TAG = re.compile(r'said "\[[^"\]]*\]"$')  # a player's guild tag ("[title, ABBR]"): the server sends it like speech
HIDING = 21
RECALL, GATE_TRAVEL = 32, 52
# what each rune's single-click name must say (the user, 2026-11-01: always check the rune before using it)
OCLLO_BANK = (3686, 2506)   # where the bank rune lands Burgers (2026-11-02)
RUNE_NAMES = {'bank': 'ocllo bank', 'start': 'mining start', 'forge': 'mining forge', 'gate': 'mining gate'}
RUNE_GRAPHICS = ('0x1F14', '0x1F15', '0x1F16', '0x1F17')


AGENT_DIR = uo.AGENT_DIR
BANK_PACING = '"pacing": { "gap": [1100, 1400], "burst": 50, "break": [1100, 1400] }'


def burgers_rules(bank):
    """Burgers' rules in the client's Agent folder: the normal ones, or with quick pacing for the bank (the user,
    2026-11-01: the bank doesn't have to follow the slow pace). The bridge reloads the file when it changes."""
    with open(os.path.join(mining.HERE, 'rules', 'rules-Burgers.json'), encoding='utf-8') as fh:
        text = fh.read()
    if bank:
        import re
        text = re.sub(r'"pacing": \{[^}]*\}', BANK_PACING, text)
    with open(os.path.join(AGENT_DIR, 'rules-Burgers.json'), 'w', encoding='utf-8') as fh:
        fh.write(text)


def learned_npc(serial):
    """Whether the guard has learned this mobile is an NPC (it did an idle fidget only NPCs do), from the bridge's
    Agent/npcs-learned.json."""
    try:
        with open(os.path.join(AGENT_DIR, 'npcs-learned.json'), encoding='utf-8') as fh:
            return any(n.get('serial') == serial for n in json.load(fh))
    except (OSError, ValueError):
        return False


class Stop(Exception):
    """Something the user must hear about now; the loop ends."""


class Alarm(Exception):
    """A guard went off (or a stranger seen again after an incident)."""


class Again(Exception):
    """A world save interrupted a step; run it again from the current state."""


class Parked(Exception):
    """Both characters are mounted and hidden, as --park asked; the loop ends."""


class NoWay(Exception):
    """The client's path finder found no way to a spot to dig from (2026-11-02 14:29: "409: no path to there")."""


class Fizzled(Exception):
    """A spell fizzled (the bridge before cuo-agent14 stops on it; the loop resumes it)."""


def log(text):
    line = time.strftime('%H:%M:%S ') + text
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(time.strftime('%Y-%m-%d ') + line + '\n')


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


LAG_STOPS = []  # times the bridge stopped on a late answer (server lag); three in 10 minutes means real trouble


def answered_late(info, error):
    """The bridge stops when the server doesn't answer within a few seconds. If an answer turned up afterwards
    (2026-11-02 02:08: "Where do you wish to dig?" came 13 s late), it was lag: cancel the cursor it left, resume,
    and return how late it was; None otherwise."""
    if error.code != 423:
        return None
    import re
    m = re.search(r'at (\d\d:\d\d:\d\d)\)', error.message or '')
    if not m:
        return None
    stopped = m.group(1)
    for _ in range(15):  # give it half a minute
        # the server's own messages (name "System"), from the moment the bridge stopped on
        late = [x for x in uo.call(info, 'GET', '/messages')['messages'][-10:]
                if x['type'] != 'Label' and x['time'][:8] >= stopped and (x.get('name') or 'System') == 'System']
        if late:
            uo.call(info, 'POST', '/cancel')
            uo.call(info, 'POST', '/resume')
            h, mi, se = (int(v) for v in stopped.split(':'))
            h2, m2, s2 = (int(v) for v in late[0]['time'][:8].split(':'))
            return (h2 * 3600 + m2 * 60 + s2) - (h * 3600 + mi * 60 + se)
        time.sleep(2)
    return None


class Char:
    def __init__(self, name):
        self.name = name
        try:
            self.info = uo.find_bridge(name)
        except SystemExit as e:
            raise Stop(f'{name}: {e}')

    def call(self, method, endpoint, **params):
        try:
            return uo.call(self.info, method, endpoint, **params)
        except uo.BridgeError as e:
            text = e.message or ''
            if e.code == 409 and text.startswith('alarm'):
                raise Alarm(f'{self.name}: {text}')
            if e.code == 423:
                late = answered_late(self.info, e)
                if late is not None:
                    now = time.time()
                    LAG_STOPS[:] = [t for t in LAG_STOPS if now - t < 600] + [now]
                    if len(LAG_STOPS) >= 3:
                        raise Stop(f'{self.name}: the server is lagging badly (three late answers in 10 minutes, the '
                                   f'last {late} s late); stopped to be safe')
                    log(f'{self.name}: the server answered {late} s late (lag); carrying on')
                    raise Again()
                if uo.resume_after_fizzle(self.info, e):
                    log(f'{self.name}: the spell fizzled')
                    raise Fizzled()
                if uo.wait_out_world_save(self.info, e):
                    log(f'{self.name}: a world save interrupted; carrying on')
                    raise Again()
                raise Stop(f'{self.name}: the bridge stopped because the server went quiet ({text})')
            if e.code == 503 and 'not responding' in text:
                # the game was busy for a few seconds (the bridge waits 5 s for it); if it answers again, carry on
                time.sleep(3)
                try:
                    uo.call(self.info, 'GET', '/status')
                except uo.BridgeError:
                    raise Stop(f'{self.name}: {text}')
                log(f'{self.name}: the game was slow to answer; carrying on')
                raise Again()
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
        self.burgers_away = False  # Burgers recalled away during an alarm (only when he was seen)
        self.mcgee_far = None      # (tiles, since when) while McGee is more than 2 tiles off (keep_mcgee)
        self.stats = {'ore': 0, 'misses': 0, 'blocks': 0, 'empty': 0, 'forge visits': 0, 'ingots': 0,
                      'bank trips': 0, 'gates': 0, 'incidents': 0}
        self.state = self.load_state()
        self.fatigue_seen = self.ice.status()['lastMessageId']
        self.biggest_dig = BIGGEST_DIG
        self.runes = dict(mining.RUNES)   # checked by name at the start and before every use

    # ---- state ----

    def load_state(self):
        try:
            with open(STATE, encoding='utf-8') as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {'next': 0, 'emptied': {}, 'bags': {}}

    def save_state(self):
        # incidents marked reviewed from the command line (mine.py --reviewed) while this loop runs stay reviewed
        try:
            with open(STATE, encoding='utf-8') as fh:
                theirs = json.load(fh).get('reviewed') or []
        except (OSError, ValueError):
            theirs = []
        if len(theirs) > len(self.state.get('reviewed') or []):
            self.state['reviewed'] = theirs
            self.state['unreviewed'] = [i for i in self.state.get('unreviewed', []) if i['time'] > theirs[-1]['time']]
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
        self.watch = {s: t for s, t in self.watch.items() if t > now and not learned_npc(s)}
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
        # kept until the user says they've reviewed them (the user, 2026-11-02), shown with every handoff
        s = self.ice.status()
        alarm = (record.get('icepick') or record.get('burgers') or {})
        threat = alarm.get('threat') or {}
        self.state.setdefault('unreviewed', []).append({
            'time': record['time'], 'what': record.get('what'),
            'who': f"{threat.get('name') or '?'} {threat.get('serial') or ''}".strip(),
            'where': f"Icepick at {s['x']},{s['y']}"})
        self.save_state()

    def handle_alarm(self, why):
        si, sb = self.ice.status(), self.bur.status()
        ai, ab = (si.get('guard') or {}).get('alarm'), (sb.get('guard') or {}).get('alarm')
        reasons = [a['reason'] for a in (ai, ab) if a]
        if reasons and all(GUILD_TAG.search(r) for r in reasons):
            # the guard took a guild tag over someone's name for speech (the user, 2026-11-02: ignore those); someone
            # standing close still sets off the loiter alarm
            log(f'(a guild tag, not speech; carrying on: {reasons[-1]})')
            for c in (self.ice, self.bur):
                c.call('POST', '/guard', on=1)
            return
        log(f'ALARM {why}')
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

        self.burgers_away = False
        if own_bur and not own_ice:
            # hidden, he stays where he is and waits it out: a Recall would show him (the user, 2026-11-02); he goes
            # only if he's in plain sight (or is revealed while waiting, see wait_until_gone)
            if sb['hidden']:
                log('Burgers is hidden: he stays put and waits it out')
            else:
                self.burgers_away = self.burgers_get_away()
            self.hide(self.ice)
        elif own_ice:
            waiting_hidden = si['hidden'] and ai and 'stood within' in ai['reason']
            if not waiting_hidden:
                self.icepick_get_away(threat)
            self.hide(self.bur)
        self.wait_until_gone(threat, GONE_AFTER * 2 ** (self.repeats.get(serial, 1) - 1))
        if self.burgers_away:
            self.burgers_back()
            self.burgers_away = False
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
                try:
                    r = self.ice.walk(spot[0], spot[1], 1)
                except uo.BridgeError as e:
                    # no way there from here (the client's path finder): the next spot (2026-11-03 08:43, by the
                    # forge, this ended the loop with Icepick part way)
                    if e.code == 409:
                        continue
                    raise
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
        log(f'Icepick found nowhere {FLEE} tiles off; hiding where he is')
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
        for attempt in range(3):
            try:
                b = self.bur.status()
                r = self.bur.call('POST', '/cast', spell=RECALL, target=serial)
                # the bridge can answer on a message (Razor's "Black Pearl amount is now 4!") a moment before the
                # teleport lands; that once read as a failed recall and stopped the loop (2026-11-03 18:57)
                for _ in range(8):
                    if r.get('moved'):
                        break
                    time.sleep(0.5)
                    s = self.bur.status()
                    r['moved'] = cheb((s['x'], s['y']), (b['x'], b['y'])) > 5
                return r
            except Fizzled:
                time.sleep(2)
        raise Stop(f"Burgers' Recall ({RUNE_NAMES[key]}) fizzled three times")

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
        self.burgers_to_wait()

    def burgers_to_wait(self):
        """Burgers to his waiting spot (the forge rune lands him by the forge), and hidden."""
        b = self.bur.status()
        if (b['x'], b['y']) != BURGERS_WAIT:
            self.bur.walk(*BURGERS_WAIT, 0)
        self.hide(self.bur)

    def to_burgers(self):
        """Icepick up next to Burgers, for a trade or a gate."""
        b = self.bur.status()
        s = self.ice.status()
        if cheb((s['x'], s['y']), (b['x'], b['y'])) <= 1 and (s['x'], s['y']) != (b['x'], b['y']):
            return
        spot = ICE_MEET if cheb(ICE_MEET, (b['x'], b['y'])) == 1 else next(
            (b['x'] + dx, b['y'] + dy) for dx, dy in NEXT_TO if mining.walkable(b['x'] + dx, b['y'] + dy, learned=False))
        self.travel(spot)
        self.ice.walk(*spot, 0)

    def step_aside(self, c, avoid):
        """One step for Burgers to a free tile next to him (off a gate, or to show himself for a trade)."""
        s = c.status()
        here = (s['x'], s['y'])
        for dx, dy in NEXT_TO:
            sp = (here[0] + dx, here[1] + dy)
            if sp not in avoid and mining.walkable(*sp, learned=False) and all(cheb(sp, a) <= 2 for a in avoid[:1]):
                c.walk(*sp, 0)
                return sp
        return None

    def wait_until_gone(self, threat, gone_after=GONE_AFTER):
        log(f"waiting until {(threat or {}).get('name') or 'the stranger'} has been out of sight for {gone_after} seconds")
        start = time.time()
        serial = (threat or {}).get('serial')
        last_seen = time.time()
        while True:
            if serial and learned_npc(serial):
                # it did an NPC's idle fidget and the guard learned it (Sheridan and Chandra, 2026-11-03): no stranger
                log(f"{(threat or {}).get('name') or serial} turned out to be a town NPC (the guard learned it); carrying on")
                self.watch.pop(serial, None)
                return
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
                    if c is self.bur and not self.burgers_away and cheb((s['x'], s['y']), BURGERS_WAIT) <= 15:
                        # revealed while waiting it out (detect hidden, say): now he goes
                        log('Burgers has been revealed; he recalls away')
                        self.burgers_away = self.burgers_get_away()
                    else:
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

    def mount(self, retame=True):
        if self.ice.status()['mounted']:
            return
        h = self.mcgee()
        if not h:
            raise Stop('McGee is nowhere in sight; Icepick is on foot')
        # (not on the "yourPet" flag alone: the client only learns it from a status the server may not have sent
        # since a login.) He stops listening: keep_mcgee comes back for him and the mount below tells.
        if h['distance'] > 1:
            self.ice.walk(h['x'], h['y'], 1)
        r = {'messages': []}
        try:
            r = self.ice.call('POST', '/mount', serial=mining.HORSE)
        except uo.BridgeError as e:
            if 'already riding' not in (e.message or ''):
                raise
        if not self.ice.status()['mounted']:
            said = [m['text'] for m in r.get('messages', [])][-1:]
            h = self.mcgee()
            if h and h['distance'] > 1:
                # a step away when the mount came (he wanders): not wild, try once more
                self.ice.walk(h['x'], h['y'], 1)
                try:
                    self.ice.call('POST', '/mount', serial=mining.HORSE)
                except uo.BridgeError as e:
                    if 'already riding' not in (e.message or ''):
                        raise
                if self.ice.status()['mounted']:
                    return
            if retame:
                # he won't let Icepick ride: gone wild (the user, 2026-11-02)
                return self.retame_mcgee(f"he won't let Icepick ride {said}")
            raise Stop(f"Icepick couldn't get back on McGee {said}")

    # the server's answers to Animal Taming
    TAMED = ('accept you as master', 'looks tame already')
    TAME_AGAIN = ('fail to tame', 'too far', "can't see", 'cannot be seen', 'angry', 'anger', 'must wait', 'busy')
    TAME_NEVER = ('no chance', 'cannot be tamed', "can't tame", 'too many owners', 'someone else', 'not tamable')

    def retame_mcgee(self, why):
        """McGee has gone wild: he stops listening or won't let Icepick ride. Icepick tames him again with Animal Taming
        (the user, 2026-11-02: even at his low skill it works), then gets on and carries on. That needs bridge 3 (a
        target for /skill, from build cuo-agent16); before that the loop stops with Icepick next to him for the user."""
        log(f'McGee has gone wild: {why}')
        self.stats['retames'] = self.stats.get('retames', 0) + 1
        if self.ice.status().get('bridge', 0) < 3:
            h = self.mcgee()
            if h and h['distance'] > 1:
                try:
                    self.ice.walk(h['x'], h['y'], 1)
                except uo.BridgeError:
                    pass
            raise Stop(f"McGee has gone wild ({why}). Icepick is standing next to him, on foot; tame him by hand "
                       "(Animal Taming), then tell me to carry on. From the next client build Icepick does it himself")
        for attempt in range(1, TAME_TRIES + 1):
            self.check_guard()
            h = self.mcgee()
            if not h:
                raise Stop('McGee has gone wild and wandered out of sight; Icepick is on foot')
            if h['distance'] > 1:
                self.ice.walk(h['x'], h['y'], 1)
            start = self.ice.status()['lastMessageId']
            try:
                self.ice.call('POST', '/skill', id=TAMING, target=mining.HORSE)
            except uo.BridgeError as e:
                if e.code == 409:  # he wandered off a step: after him again
                    continue
                raise
            # taming takes a few seconds of coaxing after the start; the answer comes as a system message
            result, deadline = None, time.time() + 25
            while result is None and time.time() < deadline:
                time.sleep(1)
                for m in self.ice.call('GET', '/messages', after=start)['messages']:
                    low = m['text'].lower()
                    if any(k in low for k in self.TAMED):
                        result = 'tamed'
                    elif any(k in low for k in self.TAME_NEVER):
                        result = 'never'
                    elif any(k in low for k in self.TAME_AGAIN):
                        result = result or 'again'
            if result == 'tamed':
                log(f'Icepick tamed McGee again (try {attempt})')
                self.mount(retame=False)
                self.ice.call('POST', '/say', text='all follow me')
                return
            if result == 'never':
                raise Stop(f"McGee has gone wild ({why}) and the server says Icepick can't tame him; he's on foot")
            time.sleep(TAME_GAP)
        raise Stop(f'McGee has gone wild ({why}); {TAME_TRIES} taming tries failed. Icepick is next to him, on foot')

    def keep_mcgee(self):
        """The user, 2026-11-02 23:00: if McGee is stuck, or more than MCGEE_NEAR tiles away, Icepick goes and gets
        him at once (a horse left too far behind may go wild), then carries on with what he was doing. Stuck: more
        than 2 tiles off and no closer for MCGEE_STUCK seconds. He once stood on the rocks 6 tiles off and 13 higher
        while Icepick dug and walked on, and the check after each walk didn't see it (22:56)."""
        s = self.ice.status()
        if s['mounted']:
            self.mcgee_far = None
            return
        h = self.mcgee()
        now = time.time()
        if h and h['distance'] <= 2:
            self.mcgee_far = None
            return
        if h and h['distance'] <= MCGEE_NEAR:
            if self.mcgee_far is None or h['distance'] < self.mcgee_far[0]:
                self.mcgee_far = (h['distance'], now)  # off a little, or coming closer: give him a moment
                return
            if now - self.mcgee_far[1] < MCGEE_STUCK:
                return
            why = f"McGee is stuck {h['distance']} tiles away at {h['x']},{h['y']}"
        else:
            why = f"McGee is {h['distance']} tiles away" if h else 'McGee is out of sight'
        log(why + '; Icepick goes to get him')
        back = (s['x'], s['y'])
        self.mount()
        self.mcgee_far = None
        # back to where he was, and off again to carry on (the horse is then on his own tile)
        self.walk_to(back)
        self.dismount()

    def dismount(self):
        if self.ice.status()['mounted']:
            self.ice.call('POST', '/dismount')
            self.ice.call('POST', '/say', text='all follow me')

    def check_mount_fatigue(self):
        new = [m for m in self.ice.call('GET', '/messages', after=self.fatigue_seen)['messages']]
        if new:
            self.fatigue_seen = max(m['id'] for m in new)
        # "Your mount is very fatigued." (a warning) or "Your mount is too fatigued to move." (it has stopped)
        s = self.ice.status()
        if s['stamina'] < s['staminaMax'] // 4:
            # Icepick himself is worn out (overloaded, every step costs him stamina): the horse trick doesn't help;
            # rest hidden on the horse until he's fresh
            log(f"Icepick is worn out (stamina {s['stamina']}/{s['staminaMax']}, weight {s['weight']}/"
                f"{s['weightMax']}); resting hidden until he's fresh")
            self.hide(self.ice)
            for _ in range(60):
                self.check_guard()
                time.sleep(5)
                s = self.ice.status()
                if s['stamina'] >= s['staminaMax']:
                    break
            # the horse's complaints from before the rest are old news
            later = self.ice.call('GET', '/messages', after=self.fatigue_seen)['messages']
            if later:
                self.fatigue_seen = max(m['id'] for m in later)
            return
        if any('fatigued' in m['text'].lower() for m in new) and s['mounted']:
            log('McGee is tired: dismount, "all follow me", mount again')
            self.ice.call('POST', '/dismount')
            self.ice.call('POST', '/say', text='all follow me')
            time.sleep(1)
            self.mount()

    def travel_route(self, target, during_alarm=False, reach=15):
        """Ride along the route to waypoint `target`, taking short cuts (see mining.walk_route)."""
        if not self.ice.status()['mounted']:
            self.mount()
        self.back_into_area(mining.load_rules()['areas'])
        s = self.ice.status()
        x, y = s['x'], s['y']
        i = mining.nearest(self.points, x, y)
        step = 1 if target >= i else -1
        while cheb(self.points[target], (x, y)) > 1:
            if not during_alarm:
                self.check_guard()
            ahead = [j for j in range(i + step, target + step, step) if cheb(self.points[j], (x, y)) <= reach]
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

    def learn_obstacles(self):
        """Record any building made of items the client can see (the map files don't show them; the user,
        2026-11-01, after Icepick rode into one): the planner then goes round it."""
        new = mining.add_obstacles(self.ice.call('GET', '/nearby', range=18)['items'])
        if new:
            log(f'learned {new} more tiles of buildings the map doesn\'t show')

    def travel(self, spot):
        """Ride to a spot along a path planned in advance on the map (mining.plan_path), in one smooth ride by the
        bridge (/travel: the next stretch starts before the current one ends). The user, 2026-11-01: not along the
        mountain, and not stopping every ten tiles. If the ride gets stuck (a house the map doesn't show), plan again
        from where he got to; after that, short straight hops."""
        self.mount()
        areas = mining.load_rules()['areas']
        for attempt in range(3):
            self.learn_obstacles()
            s = self.ice.status()
            here = (s['x'], s['y'])
            if cheb(here, spot) <= 1:
                self.check_mount_fatigue()
                return
            # a long trip follows the user's recorded ride where it can; otherwise a path planned on the map. Not the
            # ride while a gate is open: its points aren't checked against the map, and one ran over the gate's far end
            ride = attempt == 0 and not mining.gates_open()
            path = (mining.ride_path(here, spot, areas) if ride else None) or mining.plan_path(here, spot, areas)
            if not path and mining.gates_open():
                log(f'no way round the open gate from {here}; waiting for it to close')
                time.sleep(mining.gates_open() + 1)
                continue
            if not path:
                log(f'the map shows no way from {here} to {spot}')
                break
            r = self.ice.call('POST', '/travel', path=';'.join(f'{x},{y}' for x, y in path[:200]))
            # a tired horse stalls a ride: after every ride, arrived or not, see to him (the user, 2026-11-02)
            self.check_mount_fatigue()
            if r['arrived']:
                return
            log(f"ride to {spot} stopped at {r['x']},{r['y']} ({r.get('stopped')}); planning again")
            if r.get('stopped') == 'left the area':
                self.back_into_area(areas)
        self.hop_to(spot)

    def back_into_area(self, areas):
        """The client's path finder can step a tile out of Icepick's areas going round something, and the bridge
        stops every walk the moment it sees him outside, even one back in (2026-11-05 09:38: stuck at 1099,1649 and
        the loop stopped). Step back onto the nearest walkable tile inside, one tile at a time, a few tries."""
        for _ in range(12):
            s = self.ice.status()
            here = (s['x'], s['y'])
            if mining.in_areas(areas, *here):
                return True
            for ring in (1, 2, 3):
                inside = [(here[0] + dx, here[1] + dy) for dx in range(-ring, ring + 1) for dy in range(-ring, ring + 1)
                          if max(abs(dx), abs(dy)) == ring and mining.in_areas(areas, here[0] + dx, here[1] + dy)
                          and mining.walkable(here[0] + dx, here[1] + dy)]
                if inside:
                    break
            if not inside:
                return False
            try:
                self.ice.walk(*random.choice(inside), 0)
            except uo.BridgeError as e:
                if e.code not in (403, 409):
                    raise
            time.sleep(0.5)
        s = self.ice.status()
        ok = mining.in_areas(areas, s['x'], s['y'])
        log(f"back inside the area at {s['x']},{s['y']}" if ok else f"couldn't get back inside the area from {s['x']},{s['y']}")
        return ok

    def hop_to(self, spot):
        """The fallback: short straight hops of up to 16 tiles, each to a walkable tile inside Icepick's areas."""
        import math
        areas = mining.load_rules()['areas']
        self.back_into_area(areas)
        s = self.ice.status()
        here = (s['x'], s['y'])
        for _ in range(40):
            if cheb(here, spot) <= 1:
                return
            if cheb(here, spot) <= 16:
                hops = [spot]
            else:
                a = math.atan2(spot[1] - here[1], spot[0] - here[0])
                hops = []
                for length in (16, 12, 8):
                    for turn in (0, 15, -15, 30, -30, 45, -45):
                        p = (round(here[0] + math.cos(a + math.radians(turn)) * length),
                             round(here[1] + math.sin(a + math.radians(turn)) * length))
                        if mining.in_areas(areas, *p) and mining.walkable(*p) and p not in hops:
                            hops.append(p)
            moved = False
            for hop in hops[:6]:
                try:
                    r = self.ice.walk(hop[0], hop[1], 1)
                except uo.BridgeError as e:
                    if e.code not in (403, 409):
                        raise
                    continue
                if (r['x'], r['y']) != here and cheb((r['x'], r['y']), spot) < cheb(here, spot):
                    here, moved = (r['x'], r['y']), True
                    break
            if not moved:
                break
        if cheb(here, spot) > 1:
            log(f'no way on from {here} to {spot}; along the route instead')
            self.travel_route(mining.nearest(self.points, *spot), reach=15)
            self.ice.walk(spot[0], spot[1], 1)

    def gate_to(self, end):
        """From the forge: Burgers opens a gate on a rune (checked by name) and Icepick rides through to its far end.
        Returns False (and nothing is cast) if Burgers' mana doesn't come back to full within MANA_WAIT."""
        deadline = time.time() + MANA_WAIT
        while True:
            b = self.bur.status()
            if b['mana'] >= b['manaMax'] >= 40:
                break
            if time.time() > deadline:
                log(f"Burgers' mana is {b['mana']}/{b['manaMax']}; no gate")
                return False
            self.check_guard()
            time.sleep(10)
        self.to_burgers()
        b = self.bur.status()
        gate_tile = (b['x'], b['y'])
        r = None
        for attempt in range(2):
            try:
                r = self.bur.call('POST', '/cast', spell=GATE_TRAVEL, target=self.rune(end))
                break
            except Fizzled:
                continue
        if r is None:
            log('the gate fizzled twice; riding instead')
            self.hide(self.bur)
            return False
        if not any('magical gate' in m['text'].lower() for m in r['messages']):
            log(f"the gate didn't open ({[m['text'] for m in r['messages']][-1:]})")
            self.hide(self.bur)
            return False
        self.stats['gates'] += 1
        mining.gate_opened(gate_tile, GATE_ENDS[end])
        # off the gate (it opens on his own tile), so Icepick can come through
        s = self.ice.status()
        self.step_aside(self.bur, [(s['x'], s['y']), gate_tile])
        self.ice.walk(gate_tile[0], gate_tile[1], 0)
        # the jump through the gate lands a moment after the step onto it
        for _ in range(8):
            s = self.ice.status()
            arrived = cheb((s['x'], s['y']), GATE_ENDS[end]) <= 3
            if arrived:
                break
            time.sleep(0.5)
        log(f"gate to {end}: Icepick {'came out at' if arrived else 'did not go through; still at'} {s['x']},{s['y']}")
        self.hide(self.bur)
        if arrived:
            # off the far end of the gate, so he doesn't step back through it
            self.ice.walk(GATE_ENDS[end][0] + 1, GATE_ENDS[end][1] + 1, 0)
        return arrived

    def to_start(self):
        """To the top of the route: straight to Burgers at the forge and through his gate to the Mining Start rune
        (the user, 2026-11-01); ride only if there's no gate."""
        s = self.ice.status()
        if cheb((s['x'], s['y']), START) <= 4:
            return
        if not self.gate_to('start'):
            self.travel(START)

    def go_to(self, spot):
        """Get Icepick to a spot to dig from: on foot for a short hop (McGee follows), riding for anything longer."""
        s = self.ice.status()
        here = (s['x'], s['y'])
        if here == spot:
            return
        self.check_mount_fatigue()
        if not s['mounted'] and cheb(here, spot) <= FOOT_HOP:
            self.walk_to(spot)
            h = self.mcgee()
            if h and h['distance'] > 2:
                time.sleep(3)  # give him time to catch up (the user, 2026-11-01: 3 seconds; 5 was more than needed)
                h = self.mcgee()
            if not h or h['distance'] > MCGEE_NEAR:
                log('McGee fell behind; going back for him')
                self.mount()
                self.walk_to(spot)
            return
        if cheb(here, spot) > 15:
            # a long way (back from the forge, say): through a gate to the nearer end if Burgers can, else ride
            if cheb(here, mining.FORGE_SPOT) <= 3 or cheb(here, BURGERS_WAIT) <= 3:
                # the gate end nearest the spot on the map (the route winds too much to compare along it)
                end = min(GATE_ENDS, key=lambda e: cheb(GATE_ENDS[e], spot))
                b = self.bur.status()
                if cheb(GATE_ENDS[end], spot) + 40 < cheb(here, spot) and b['mana'] >= b['manaMax'] >= 40 \
                        and not self.saving_mana_for_bank():
                    self.gate_to(end)
            self.travel(spot)
        else:
            self.mount()
        self.walk_to(spot)

    def walk_to(self, spot):
        try:
            return self.ice.walk(spot[0], spot[1], 0)
        except uo.BridgeError as e:
            if e.code == 409 and 'no path' in e.message:
                raise NoWay(spot)
            raise

    def go_to_any(self, t, rocks):
        """The chosen spot can't be reached: try the block's other spots, nearest first. Returns the spot, or None."""
        s = self.ice.status()
        stands = sorted({st for r, st in t['pairs'] if r in rocks}, key=lambda st: cheb(st, (s['x'], s['y'])))
        for st in stands[:4]:
            try:
                self.go_to(st)
                return st
            except NoWay:
                continue
        return None

    # ---- digging ----

    def shovels(self):
        return [i['serial'] for i in self.ice.pack() if i.get('graphic') in mining.SHOVELS]

    def too_heavy_to_dig(self, weight):
        return weight > HEAVY or weight + self.biggest_dig > LIMIT

    def heavy(self):
        return self.too_heavy_to_dig(self.ice.status()['weight'])

    def dig_block(self, n):
        t = self.targets[n]
        if self.heavy():
            self.forge_visit('a full pack')
        if not self.shovels():
            self.forge_visit('no shovels')
        rock, stand, others = mining.choose(t)
        rocks = [rock] + others
        try:
            self.go_to(stand)
        except NoWay:
            if self.go_to_any(t, rocks) is None:
                log(f'block {t["block"]}: no way to any spot to dig it from; moving on')
                return
        self.dismount()
        tried = 0
        for rock in rocks:
            s = self.ice.status()
            if cheb((s['x'], s['y']), rock) > 2:
                # stood somewhere else (blocked spot): find a nearer place for this rock
                stands = [st for r, st in t['pairs'] if r == rock]
                if not stands:
                    continue
                try:
                    self.go_to(min(stands, key=lambda st: cheb(st, (s['x'], s['y']))))
                except NoWay:
                    continue
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

    # what the server says to a dig; anything else (the weather, someone's name) is ignored
    DIG_ANSWERS = ('you dig some', 'loosen some rocks', 'no metal here', 'worn out', 'riding', 'mine there',
                   'cannot be seen', "can't mine", 'too far', "can't dig", 'you cannot', 'not able')

    def dig_rock(self, rock):
        x, y, z = rock
        tools = self.shovels()
        first = True
        quiet = 0
        before = self.ice.status()['weight']
        while True:
            if not tools:
                return 'no shovels'
            self.check_guard()
            self.keep_mcgee()
            if os.path.exists(PARK_FILE):
                # the user, 2026-11-03: "park it" means now, not after the block (this one left him digging on)
                self.park()
            try:
                r = self.ice.call('POST', '/use', serial=tools[0], x=x, y=y, z=z, graphic=0)
            except uo.BridgeError as e:
                if e.code == 404:
                    tools = self.shovels()  # that shovel is gone (worn out while another message came first)
                    continue
                if e.code in (403, 409):
                    log(f'dig {x},{y}: {e.message}')
                    return 'refused'
                raise
            texts = [m['text'] for m in r['messages'] if m['type'] != 'Label']
            answers = [t for t in texts if any(k in t.lower() for k in self.DIG_ANSWERS)]
            if any('worn out' in t.lower() for t in texts):
                tools = self.shovels()
                log(f'a shovel wore out; {len(tools)} left')
            if not answers:
                # only other messages ("It begins to rain."): the dig's own answer came later; dig on
                quiet += 1
                if quiet > 3:
                    log(f'dig {x},{y}: no answer to the dig ({texts[-1:]}); moving on')
                    return 'refused'
                continue
            quiet = 0
            low = answers[0].lower()
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
                log(f'dig {x},{y}: {answers[0]}')
                return 'refused'
            first = False
            weight = r['weight']
            if 'you dig some' in low and weight <= before:
                # the weight update can come a moment after the dig's answer; deciding on the old weight let one
                # more dig take him to 404, overloaded, and every step then tired him out (2026-11-02 13:58)
                for _ in range(10):
                    time.sleep(0.2)
                    weight = self.ice.status()['weight']
                    if weight > before:
                        break
            if weight - before > self.biggest_dig:
                self.biggest_dig = weight - before
                log(f'a dig added {self.biggest_dig} stones; digging stops {self.biggest_dig} below {LIMIT} from now on')
            before = weight
            if weight > LIMIT:
                log(f'over the weight limit: {weight}/{LIMIT}')
            if self.too_heavy_to_dig(weight):
                return 'heavy'

    # ---- the forge ----

    def forge_visit(self, why):
        self.stats['forge visits'] += 1
        s = self.ice.status()
        here = mining.nearest(self.points, s['x'], s['y'])
        log(f'to the forge ({why}) from waypoint {here}')
        if here < self.gate_index - GATE_SAVES:
            # north of the middle: the middle gate spot is on the way to the forge; gate from there if Burgers'
            # mana has come back by then (it takes about 5 minutes from empty), else ride on
            self.travel((GATE[0] + 1, GATE[1] + 1))
            b = self.bur.status()
            if b['mana'] < b['manaMax'] and b['manaMax'] - b['mana'] <= 6:
                time.sleep((b['manaMax'] - b['mana']) * 8 + 2)  # nearly full: worth the wait
            if self.gate_worth_it(0):
                self.via_gate()
            else:
                self.travel(mining.FORGE_SPOT)
                self.ice.walk(*mining.FORGE_SPOT, 0)
        else:
            self.travel(mining.FORGE_SPOT)
            self.ice.walk(*mining.FORGE_SPOT, 0)
        self.smelt_all()
        need = SHOVELS_WANTED - len(self.shovels())
        if need > 0 and self.burgers_spares() < need and self.bur.status()['mana'] >= 22 and not self.bank_known_empty():
            self.bank_trip()  # fetch shovels first
        self.handoff()
        # at the end of a pass Burgers keeps his mana for the gate to the top (the user, 2026-11-02: the bank can
        # wait until it suits, in the south half of the next pass), so only a bank trip he can't do without
        end_of_pass = why == 'the end of the route'
        if self.burgers_should_bank(where=None if end_of_pass else here):
            self.bank_trip()
        if not self.shovels():
            self.handoff()  # shovels fetched on that trip
        if not self.shovels():
            how = self.leave_safe()  # parked, both mounted and hidden, until the user brings more
            raise Stop('Icepick has no shovels left and Burgers has none to give'
                       + (' (the shovel bag in his bank is empty)' if self.state.get('bank_out_of_shovels') else '')
                       + f'. Parked: {how}')
        self.reagents_stop(REAGENTS_RESERVE)

    def saving_mana_for_bank(self):
        """Out of spare shovels, Burgers keeps his mana for the bank (two Recalls) instead of a gate: in the north half
        every gate takes all of it, so the bank trip never came (2026-11-02 20:15, Icepick down to 2 shovels)."""
        if self.burgers_spares() > 0 or self.bank_known_empty():
            return False
        log("no gate: Burgers keeps his mana for a bank trip (he has no spare shovels)")
        return True

    def gate_worth_it(self, here):
        if here >= self.gate_index - GATE_SAVES:
            return False
        b = self.bur.status()
        return b['mana'] >= b['manaMax'] and b['manaMax'] >= 40 and not self.saving_mana_for_bank()

    def via_gate(self):
        log('Burgers opens a gate; Icepick rides to the gate spot')
        self.travel((GATE[0] + 1, GATE[1] + 1))
        self.ice.walk(GATE[0] + 1, GATE[1] + 1, 0)
        try:
            r = self.bur.call('POST', '/cast', spell=GATE_TRAVEL, target=self.rune('gate'))
        except Fizzled:
            r = {'messages': [{'text': 'The spell fizzles.'}]}
        if not any('magical gate' in m['text'].lower() for m in r['messages']):
            log(f'the gate didn\'t open ({[m["text"] for m in r["messages"]][-1:]}); riding instead')
            self.travel(mining.FORGE_SPOT)
            self.ice.walk(*mining.FORGE_SPOT, 0)
            return
        self.stats['gates'] += 1
        # off the gate (it opens on his own tile), so Icepick can come through
        b = self.bur.status()
        gate_tile = (b['x'], b['y'])
        mining.gate_opened(gate_tile, GATE)
        self.step_aside(self.bur, [gate_tile])
        self.ice.walk(*GATE, 0)
        for _ in range(8):
            s = self.ice.status()
            if cheb((s['x'], s['y']), gate_tile) <= 3:
                break
            time.sleep(0.5)
        self.hide(self.bur)
        if cheb((s['x'], s['y']), gate_tile) > 3:
            log('didn\'t go through the gate; riding instead')
        self.travel(mining.FORGE_SPOT)
        self.ice.walk(*mining.FORGE_SPOT, 0)

    FORGE_AT = (1148, 1859)  # the forge item itself; smelting works from within 2 tiles

    def at_forge(self):
        """Make sure Icepick stands within reach of the forge (2026-11-02: a ride that ended a tile off his spot left
        every smelt "too far away"): his usual spot, else the other free tiles around the forge."""
        for spot in (mining.FORGE_SPOT, (1148, 1857), (1149, 1857), (1146, 1858), (1146, 1859), (1150, 1858)):
            s = self.ice.status()
            if cheb((s['x'], s['y']), self.FORGE_AT) <= 2:
                return True
            try:
                self.ice.walk(spot[0], spot[1], 0)
            except uo.BridgeError as e:
                if e.code not in (403, 409):
                    raise
        s = self.ice.status()
        return cheb((s['x'], s['y']), self.FORGE_AT) <= 2

    def smelt_all(self):
        """Smelt every pile. A lone small pile is too little ("not enough metal-bearing ore"), so it waits for
        another small pile of the same metal; two of them are combined first (the smelt cursor takes another
        pile as well as the forge)."""
        if not self.at_forge():
            raise Stop("Icepick can't get within reach of the forge")
        piles = [i for i in self.ice.pack() if i.get('graphic') in mining.ORE]
        small = {}
        for pile in piles:
            if pile['graphic'] == SMALL_ORE and pile.get('amount', 1) < 2:
                small.setdefault(pile.get('hue', 0), []).append(pile)
        for hue, group in small.items():
            while len(group) >= 2:
                a, b = group.pop(), group.pop()
                try:
                    r = uo.call(self.ice.info, 'POST', '/use', serial=a['serial'], target=b['serial'])
                    texts = [m['text'] for m in r['messages'] if 'select the forge' not in m['text'].lower()]
                    answer = texts[-1] if texts else 'done'
                except uo.BridgeError as e:
                    # the server combines piles without a word, so the bridge (before cuo-agent14) takes it for
                    # silence and stops: if the first pile has gone into the second, it worked
                    if e.code != 423 or any(i['serial'] == a['serial'] for i in self.ice.pack()):
                        raise
                    uo.call(self.ice.info, 'POST', '/resume')
                    answer = 'combined (no reply from the server)'
                log(f"combine small piles {a['serial']} + {b['serial']} (hue {hue}): {answer}")
        for item in self.ice.pack():
            if item.get('graphic') not in mining.ORE:
                continue
            if item['graphic'] == SMALL_ORE and item.get('amount', 1) < 2:
                continue  # too little on its own; kept for a later pile of the same metal
            answer = '?'
            for _ in range(5):
                r = self.ice.call('POST', '/use', serial=item['serial'], target=mining.FORGE)
                texts = [m['text'] for m in r['messages'] if 'select the forge' not in m['text'].lower()]
                answer = texts[-1] if texts else '?'
                if 'riding' in answer.lower():
                    self.dismount()
                    continue
                if 'too far away' in answer.lower():
                    if not self.at_forge():
                        raise Stop("Icepick can't get within reach of the forge")
                    continue
                log(f"smelt {item['serial']} (hue {item.get('hue')}, {item.get('amount', 1)}): {answer}")
                # a failed smelt ("You burn away the impurities but are left with less useable metal", the harder
                # metals like golden) leaves some ore: smelt what's left again (the user, 2026-11-01)
                if 'burn away' not in answer.lower():
                    break
                left = next((i for i in self.ice.pack() if i['serial'] == item['serial']), None)
                if not left or left['graphic'] == SMALL_ORE and left.get('amount', 1) < 2:
                    break
                item = left

    def ingots(self, char):
        return [i for i in char.pack() if 'ingot' in (i.get('type') or '')]

    def burgers_reagents(self):
        """Burgers' reagents: {graphic: (amount, pile serial or None)}, and the container they're kept in."""
        pack = self.bur.status()['backpack']['serial']
        found, home = {g: (0, None) for g in REAGENTS}, pack
        for item in self.bur.call('GET', '/contents', serial=pack, depth=2)['items']:
            for inner in [item] + item.get('items', []):
                g = inner.get('graphic')
                if g in REAGENTS:
                    found[g] = (found[g][0] + inner.get('amount', 1), inner['serial'])
                    if inner is not item:
                        home = item['serial']
        return found, home

    def burgers_shovels(self):
        """Burgers' spare shovels, loose in his pack or in a bag inside it (the user keeps them in a bag from
        2026-11-04): (serials, the bag holding most of them or None)."""
        pack = self.bur.status()['backpack']['serial']
        loose, bags = [], {}
        for item in self.bur.call('GET', '/contents', serial=pack, depth=2)['items']:
            if item.get('graphic') in mining.SHOVELS:
                loose.append(item['serial'])
            inside = [i['serial'] for i in item.get('items', []) if i.get('graphic') in mining.SHOVELS]
            if inside:
                bags[item['serial']] = inside
        bag = max(bags, key=lambda b: len(bags[b])) if bags else None
        if bag and bag != self.state.get('shovel_bag'):
            self.state['shovel_bag'] = bag  # remembered for when it's empty
            self.save_state()
        elif not bag and self.state.get('shovel_bag') in {i['serial'] for i in self.bur.pack() if i.get('container')}:
            bag = self.state['shovel_bag']
        return loose + [sv for b in bags.values() for sv in b], bag

    def burgers_spares(self):
        return len(self.burgers_shovels()[0])

    def handoff(self, extra=()):
        # shovels beyond the ones he carries go back to Burgers too (the user cut Icepick's from 5 to 2)
        surplus = [i for i in self.ice.pack() if i.get('graphic') in mining.SHOVELS][SHOVELS_WANTED:]
        bars = self.ingots(self.ice) + list(extra) + surplus
        need = max(0, SHOVELS_WANTED - len(self.shovels()))
        spares = self.burgers_shovels()[0][:need] if need else []
        if not bars and not spares:
            return
        # Icepick rides up to Burgers' spot, away from the forge (the user, 2026-11-02)
        self.to_burgers()
        # Burgers shows himself with one step next to Icepick, never onto a gate that may still be open
        b = self.bur.status()
        if b['hidden']:
            gates = [(i['x'], i['y']) for i in self.bur.call('GET', '/nearby', range=4)['items']
                     if 'moongate' in (i.get('type') or '')]
            ice = self.ice.status()
            if self.step_aside(self.bur, [(ice['x'], ice['y'])] + gates) is None:
                raise Stop(f"Burgers found no free tile next to him to step out to for the trade (at {b['x']},{b['y']})")
        # Icepick's client must see Burgers again, by name, before he can hand him anything
        bur_serial = self.bur.status()['serial']
        for _ in range(10):
            seen = [m for m in self.ice.call('GET', '/nearby', range=3)['mobiles'] if m['serial'] == bur_serial]
            if seen and seen[0].get('name'):
                break
            time.sleep(0.5)
        for bar in bars:
            self.ice.call('POST', '/give', serial=bar['serial'], to=self.bur.status()['serial'])
        for shovel in spares:
            self.bur.call('POST', '/give', serial=shovel, to=self.ice.status()['serial'])
        self.ice.call('POST', '/trade', accept=1)
        self.bur.call('POST', '/trade', accept=1)
        time.sleep(1)
        if self.ice.status().get('trade') or self.bur.status().get('trade'):
            raise Stop('the trade between Icepick and Burgers did not finish')
        given = [b for b in bars if 'ingot' in (b.get('type') or '')]
        n = sum(b.get('amount', 1) for b in given)
        iron = sum(b.get('amount', 1) for b in given if not b.get('hue'))
        self.stats['ingots'] += n
        # running totals for the user (2026-11-01): all ingots, and iron (the uncoloured ones) on its own
        totals = self.state.setdefault('totals', {'ingots': 0, 'iron': 0})
        totals['ingots'] += n
        totals['iron'] += iron
        self.save_state()
        log(f'handed Burgers {n} ingots ({iron} iron)' + (f' and {len(extra)} small ore piles' if extra else '')
            + f"; gave Icepick {len(spares)} shovels. Total: {totals['ingots']} ingots, {totals['iron']} iron."
            + f" Run and hide: {len(self.state.get('unreviewed', []))} to review. Reagents: {self.reagent_counts()}")
        ice = self.ice.status()
        if (ice['x'], ice['y']) != BURGERS_WAIT:
            self.bur.walk(*BURGERS_WAIT, 0)
        self.hide(self.bur)

    def burgers_should_bank(self, end_of_pass=False, where=None):
        """A bank trip costs Burgers 22 of his 40 mana, and a gate needs all 40 (the user, 2026-11-01: banking must
        not cost Icepick a gate). So he banks in the south half of the route, where gates don't help, and at the
        end of a pass; in the north half only when he must (almost out of spare shovels, or a nearly full pack)."""
        b = self.bur.status()
        if b['mana'] < 22:
            return False
        held = sum(i.get('amount', 1) for i in self.ingots(self.bur))
        spares = self.burgers_spares()
        reagents, _ = self.burgers_reagents()
        if any(reagents[g][0] < low for g, low in REAGENTS_LOW.items()):
            return True  # too few for more than a trip or two: a must, wherever Icepick is
        # shovels alone are only a reason to go once he has none left to give (the user, 2026-11-01); when he's
        # at the bank anyway he tops up to BURGERS_SPARES
        out = spares == 0 and not self.bank_known_empty()
        if end_of_pass:
            return held > 0 or out
        if where is not None and where >= self.gate_index:
            return held >= BANK_AT_INGOTS or out
        return out or b['weight'] >= b['weightMax'] - 40

    def bank_shovels(self, bags):
        if not bags.get('shovels'):
            return []
        return [i['serial'] for i in self.bur.call('GET', '/contents', serial=bags['shovels'])['items']
                if i.get('graphic') in mining.SHOVELS]

    def bank_known_empty(self):
        t = self.state.get('bank_out_of_shovels')
        return bool(t) and time.time() - t < 1800

    def bank_bags(self, bank):
        bags = self.state.setdefault('bags', {})
        in_bank = self.bur.call('GET', '/contents', serial=bank)['items']
        # a bag the user has taken out (an empty shovel bag swapped for a full one, 2026-11-02) is looked for again
        here = {i['serial'] for i in in_bank}
        for kind in [k for k, s in bags.items() if s not in here]:
            bags.pop(kind)
        # and their labels: the user swaps in new bags rather than emptying the old ones (2026-11-04)
        uo.forget_labels([s for s, text in uo.load_labels().items() if text.endswith("(Burgers' bank)") and s not in here])
        if bags.get('shovels') and bags.get('ingots') and bags.get('reagents'):
            return bags
        for item in in_bank:
            if not item.get('container') or item['serial'] in bags.values():
                continue
            self.bur.call('POST', '/open', serial=item['serial'])
            inside = self.bur.call('GET', '/contents', serial=item['serial'])['items']
            if any(i.get('graphic') in mining.SHOVELS for i in inside):
                bags['shovels'] = item['serial']
            elif any('ingot' in (i.get('type') or '') for i in inside):
                bags['ingots'] = item['serial']
            elif any(i.get('graphic') in REAGENTS for i in inside):
                bags['reagents'] = item['serial']
        if not bags.get('ingots'):
            raise Stop(f"couldn't find the ingot bag in Burgers' bank (found {bags})")
        if bags.get('shovels'):
            uo.save_label(bags['shovels'], 'bag: shovels (Burgers\' bank)')
        uo.save_label(bags['ingots'], 'bag: ingots (Burgers\' bank)')
        if bags.get('reagents'):
            uo.save_label(bags['reagents'], 'bag: reagents (Burgers\' bank)')
        self.save_state()
        return bags

    def restock_reagents(self, bag):
        """At the bank: each of Burgers' four reagents back up to REAGENTS_WANTED, split off the bank's piles onto the
        piles in his pouch."""
        have, home = self.burgers_reagents()
        stock = self.bur.call('GET', '/contents', serial=bag)['items']
        took, short = [], []
        for g, name in REAGENTS.items():
            want = REAGENTS_WANTED - have[g][0]
            pile = next((i for i in stock if i.get('graphic') == g), None)
            if want <= 0 or not pile:
                if want > 0:
                    log(f'no {name} left in the bank bag')
                    short.append(g)
                continue
            amount = min(want, pile.get('amount', 1))
            to = have[g][1] or home
            self.bur.call('POST', '/move', serial=pile['serial'], to=to, amount=amount if amount < pile.get('amount', 1) else None)
            took.append(f'{amount} {name}')
        if took:
            log('Burgers took ' + ', '.join(took) + ' from the bank')
        self.state['bank_short'] = short  # what the bank bag had none of, this visit
        self.save_state()
        self.warn_reagents()

    def reagents_stop(self, minimum, only_if_bank_short=True):
        """Park both and stop before Burgers can't recall back from the bank (2026-11-03: the bank ran out of black
        pearl and mandrake root). `minimum` of each recall reagent; with only_if_bank_short, only for the ones his bank
        had none of on the last visit (otherwise the next bank trip restocks them)."""
        have, _ = self.burgers_reagents()
        short = self.state.get('bank_short') or []
        low = [f'{have[g][0]} {REAGENTS[g]}' for g in RECALL_REAGENTS
               if have[g][0] < minimum and (g in short or not only_if_bank_short)]
        if low:
            how = self.leave_safe()
            raise Stop(f"Burgers is down to {', '.join(low)}" + (' and his bank has none' if only_if_bank_short else '')
                       + f'; parked before he could get stuck at the bank. {how}. Reagents: {self.reagent_counts()}')

    def reagent_counts(self):
        """Burgers' four reagents, for every handoff line (the user, 2026-11-03)."""
        try:
            have, _ = self.burgers_reagents()
        except uo.BridgeError:
            return '?'
        return ', '.join(f'{name} {have[g][0]}' for g, name in REAGENTS.items())

    def warn_reagents(self):
        """The user, 2026-11-03: say when any of Burgers' reagents is below REAGENTS_WARN, so there's warning to add
        more to his bank (checked after every bank trip and at the start)."""
        have, _ = self.burgers_reagents()
        if any(have[g][0] < REAGENTS_WARN for g in REAGENTS):
            log('reagents low: Burgers has ' + ', '.join(f'{name} {have[g][0]}' for g, name in REAGENTS.items())
                + f' (warning below {REAGENTS_WARN}; add more to his bank)')

    def bank_trip(self):
        """Burgers to the Ocllo bank and back. The bank is relaxed (the user): his guard is off while he's there."""
        self.stats['bank trips'] += 1
        self.reagents_stop(2, only_if_bank_short=False)  # a recall there and one back
        log('Burgers takes the ingots to the bank')
        self.bur.call('POST', '/guard', on=0)
        try:
            burgers_rules(bank=True)
            self.bur.call('GET', '/rules')  # the bridge reads the quick pacing now
            b = self.bur.status()
            if cheb((b['x'], b['y']), OCLLO_BANK) > 10:  # (he's there already if a run stopped during a bank trip)
                r = self.recall('bank')
                if not r['moved']:
                    raise Stop(f"Burgers' Recall to the bank didn't work: {[m['text'] for m in r['messages']][-2:]}")
            bank = self.bur.call('POST', '/say', text='bank').get('bank', {}).get('serial')
            if not bank:
                raise Stop("Burgers said \"bank\" but no bank box opened")
            bags = self.bank_bags(bank)
            for bag in (bags.get('shovels'), bags['ingots'], bags.get('reagents')):
                if bag:
                    self.bur.call('POST', '/open', serial=bag)
            in_bag = self.bur.call('GET', '/contents', serial=bags['ingots'])['items']
            for bar in self.ingots(self.bur):
                same = next((i for i in in_bag if i.get('graphic') == bar.get('graphic') and i.get('hue') == bar.get('hue')), None)
                self.bur.call('POST', '/move', serial=bar['serial'], to=same['serial'] if same else bags['ingots'])
            for pile in [i for i in self.bur.pack() if i.get('graphic') in mining.ORE]:
                self.bur.call('POST', '/move', serial=pile['serial'], to=bank)
            want = BURGERS_SPARES - self.burgers_spares()
            if want > 0:
                spare = self.bank_shovels(bags)
                if not spare:
                    # that bag is empty: look again for one with shovels in it (the user may have put in a new bag)
                    self.state['bags'].pop('shovels', None)
                    bags = self.bank_bags(bank)
                    spare = self.bank_shovels(bags)
                spare = spare[:want]
                # into the bag he keeps his shovels in, if there is one (the user, 2026-11-04)
                to = self.burgers_shovels()[1] or self.bur.status()['backpack']['serial']
                for shovel in spare:
                    self.bur.call('POST', '/move', serial=shovel, to=to)
                log(f'Burgers took {len(spare)} shovels from the bank'
                    + ('' if spare else '; the bank has none left (the user needs to put more in)'))
                # an empty bank isn't worth a trip at every handoff: look again in half an hour (2026-11-02 20:15)
                self.state['bank_out_of_shovels'] = None if spare else time.time()
                self.save_state()
            if bags.get('reagents'):
                self.restock_reagents(bags['reagents'])
            burgers_rules(bank=False)  # the slow pace again before he leaves the bank
            self.bur.call('GET', '/rules')
            r = self.recall('forge')
            if not r['moved']:
                raise Stop(f"Burgers' Recall back to the forge didn't work: {[m['text'] for m in r['messages']][-2:]}")
            self.bur.walk(*BURGERS_WAIT, 0)
        finally:
            burgers_rules(bank=False)
            self.bur.call('POST', '/guard', on=1)
        time.sleep(2)
        missing = [w['serial'] for w in self.bur.status()['guard'].get('watching', []) if not w['seen']]
        if missing:
            raise Stop(f"a rune is missing from Burgers' pack after the bank trip: {missing}")
        self.hide(self.bur)

    def empty_pack(self):
        """Icepick's pack emptied before a full test: smelt what can be smelted and hand Burgers the ingots. The
        small one-ore piles stay with Icepick (the user: they may combine with more of the same metal later), and
        Burgers banks on his usual rule (about 300 ingots, few shovels left, the end of a pass), not now."""
        log("to the forge (emptying Icepick's pack)")
        self.travel(mining.FORGE_SPOT)
        self.ice.walk(*mining.FORGE_SPOT, 0)
        self.smelt_all()
        self.handoff()

    # ---- the pass ----

    def preflight(self):
        burgers_rules(bank=False)  # in case a run stopped in the middle of a bank trip
        # after a login (a server reboot, say) the client knows nothing inside bags until they're opened
        for c in (self.ice, self.bur):
            pack = c.status()['backpack']
            if not pack.get('knownItems'):
                c.call('POST', '/open', serial=pack['serial'])
        for item in self.bur.pack():
            if item.get('container') and not item.get('knownItems'):
                self.bur.call('POST', '/open', serial=item['serial'])  # his reagent pouch
        si, sb = self.ice.status(), self.bur.status()
        log(f"Icepick at {si['x']},{si['y']} weight {si['weight']}/{si['weightMax']}, {len(self.shovels())} shovels; "
            f"Burgers at {sb['x']},{sb['y']} mana {sb['mana']}/{sb['manaMax']}, {self.burgers_spares()} spare shovels")
        # the bank is relaxed: at the bank Burgers' guard stays off until the bank trip brings him back (2026-11-04
        # 00:46: turned on there, it raised an alarm over Sharri by the bank), and the trip checks his runes then
        at_bank = cheb((sb['x'], sb['y']), OCLLO_BANK) <= 10
        for c in (self.ice, self.bur):
            if not (c is self.bur and at_bank):
                c.call('POST', '/guard', on=1)
        time.sleep(2)
        missing = [w['serial'] for w in self.bur.status()['guard'].get('watching', []) if not w['seen']]
        if missing and not at_bank:
            raise Stop(f"Burgers' pack doesn't show these runes: {missing} (open his backpack once?)")
        if not self.mcgee() and not si['mounted']:
            raise Stop('McGee is not near Icepick')
        for key in RUNE_NAMES:
            self.rune(key)
        log('runes checked: ' + ', '.join(f'{k} {v}' for k, v in self.runes.items()))
        self.warn_reagents()
        # Burgers belongs at his spot by the forge (an earlier run may have stopped while he was away)
        if at_bank:
            log('Burgers is at the bank (a run stopped during a bank trip); he finishes the trip')
            self.bank_trip()
        elif cheb((sb['x'], sb['y']), BURGERS_WAIT) > 15:
            log(f"Burgers is at {sb['x']},{sb['y']}, not by the forge; recalling him back")
            self.burgers_back()
        self.burgers_to_wait()

    def run(self):
        os.makedirs(WORK, exist_ok=True)
        start = time.time()
        self.preflight()
        first = self.args.start if self.args.start is not None else self.state.get('next', 0)
        last = self.args.end if self.args.end is not None else len(self.targets) - 1
        for p in range(self.args.passes):
            # when the pass began at the top, kept in the state so a restart in the middle doesn't reset it
            if first == 0:
                self.state['pass_started'] = time.time()
                self.save_state()
            pass_start = self.state.get('pass_started', time.time())
            log(f'pass {p + 1}: blocks {first} to {last} (this pass began at the top at '
                f"{time.strftime('%H:%M', time.localtime(pass_start))})")
            if first == 0:
                self.safely(self.to_start)
            for n in range(first, last + 1):
                self.state['next'] = n
                self.save_state()
                self.safely(self.dig_block, n)
                self.stats['blocks'] += 1
                self.safely(self.check_mount_fatigue)
                if os.path.exists(PARK_FILE):
                    self.state['next'] = n + 1
                    self.save_state()
                    self.safely(self.park)
            self.safely(self.forge_visit, 'the end of the route')
            self.safely(self.mount)
            self.state['next'] = 0
            self.save_state()
            first, last = 0, len(self.targets) - 1
            if p + 1 < self.args.passes and not self.args.no_wait:
                self.safely(self.to_start)
                self.hide(self.ice)
                # the hour runs from when the pass started (the user, 2026-11-01): that's when the top was dug
                end = pass_start + self.args.wait * 60
                log(f"waiting until {time.strftime('%H:%M', time.localtime(end))} for the ore to come back"
                    if end > time.time() else 'the ore at the top has had its time already; on we go')
                while time.time() < end:
                    self.safely(lambda: None)
                    if os.path.exists(PARK_FILE):
                        self.safely(self.park)
                    time.sleep(5)
        self.report(start)

    def park(self):
        """--park (the user, 2026-11-02, before an install): between blocks, Icepick back on McGee and hidden,
        Burgers at his spot and hidden, then the loop ends. The next run starts at the next block."""
        how = self.leave_safe()
        try:
            os.remove(PARK_FILE)
        except OSError:
            pass
        raise Parked(how)

    def leave_safe(self):
        """Both characters mounted and hidden, Burgers at his spot, before the loop ends (a park, or out of shovels:
        the user, 2026-11-03). Returns how they were left."""
        self.mount()
        self.hide(self.ice)
        b = self.bur.status()
        if cheb((b['x'], b['y']), BURGERS_WAIT) > 15:
            self.burgers_back()
        self.burgers_to_wait()
        si, sb = self.ice.status(), self.bur.status()
        # hidden, they don't need the guard, and with it off the user can play them (the user, 2026-11-03 20:17);
        # one left in sight keeps his (the next run's preflight turns both back on)
        for c, s in ((self.ice, si), (self.bur, sb)):
            if s['hidden']:
                c.call('POST', '/guard', on=0)
        return (f"Icepick at {si['x']},{si['y']} {'mounted' if si['mounted'] else 'ON FOOT'} and "
                f"{'hidden, guard off' if si['hidden'] else 'NOT HIDDEN, guard on'}; Burgers at {sb['x']},{sb['y']} "
                f"{'mounted' if sb['mounted'] else 'ON FOOT'} and "
                f"{'hidden, guard off' if sb['hidden'] else 'NOT HIDDEN, guard on'}")

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
    p.add_argument('--empty', action='store_true', help="only empty Icepick's pack (smelt, hand over the ingots), then stop")
    p.add_argument('--incidents', action='store_true', help='list the run-and-hide incidents the user has not reviewed')
    p.add_argument('--reviewed', action='store_true', help='the user has reviewed them: clear the list (kept in incidents.jsonl)')
    p.add_argument('--park', action='store_true',
                   help='ask the running loop to stop after the block it is on, both characters mounted and hidden; '
                        'waits until it has')
    p.add_argument('--stop', action='store_true',
                   help='stop the running loop at once (an emergency: nobody is parked or hidden)')
    args = p.parse_args()
    if args.park or args.stop:
        return park_or_stop(args.park)
    if args.incidents or args.reviewed:
        try:
            with open(STATE, encoding='utf-8') as fh:
                state = json.load(fh)
        except (OSError, ValueError):
            state = {}
        items = state.get('unreviewed', [])
        if args.incidents:
            print(f'{len(items)} run-and-hide incidents to review' + (':' if items else ''))
            for i in items:
                print(f"  {i['time']}  {i['who']}  {i['where']}  ({i['what']})")
        else:
            state['unreviewed'] = []
            state.setdefault('reviewed', []).append({'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'count': len(items)})
            with open(STATE, 'w', encoding='utf-8') as fh:
                json.dump(state, fh, indent=1)
            print(f'marked {len(items)} incidents reviewed')
        return
    if running_loop():
        sys.exit(f'a mining loop is already running (pid {running_loop()}); --park or --stop it first')
    os.makedirs(WORK, exist_ok=True)
    with open(PID_FILE, 'w', encoding='utf-8') as fh:
        fh.write(str(os.getpid()))
    try:
        os.remove(PARK_FILE)  # an old request, from a run that ended before it got to it
    except OSError:
        pass
    miner = None
    try:
        miner = Miner(args)
        if args.bank or args.empty:
            start = time.time()
            miner.preflight()
            miner.safely(miner.bank_trip if args.bank else miner.empty_pack)
            miner.report(start)
            return
        miner.run()
    except Parked as e:
        log(f'PARKED: {e}')
        miner.report(time.time())
    except Stop as e:
        log(f'STOPPED: {e}')
        if miner:
            miner.report(time.time())
        sys.exit(2)
    except uo.BridgeError as e:
        log(f'STOPPED on an unexpected answer from the bridge: {e}')
        sys.exit(3)
    finally:
        if running_loop() == os.getpid():
            os.remove(PID_FILE)


def running_loop():
    """The pid of the mining loop that's running, or None. Checked by its command line, so a stale file or a
    reused pid doesn't count."""
    import subprocess
    try:
        with open(PID_FILE, encoding='utf-8') as fh:
            pid = int(fh.read().strip())
    except (OSError, ValueError):
        return None
    if pid == os.getpid():
        return pid
    ps = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True)
    return pid if 'mine.py' in ps.stdout and '--park' not in ps.stdout and '--stop' not in ps.stdout else None


def park_or_stop(park):
    """--park: ask the loop to park both characters after its current block, and wait for it to end.
    --stop: end it now. Either way, check the process has gone (2026-11-02: a pkill on the wrong name missed the
    loop, and it carried on through a forge visit)."""
    import signal
    pid = running_loop()
    if not pid:
        print('no mining loop is running')
        return
    with open(LOG, encoding='utf-8') as fh:
        seen = len(fh.readlines())
    if park:
        open(PARK_FILE, 'w').close()
        print(f'asked the loop (pid {pid}) to park after the block it is on; waiting')
        deadline = time.time() + 20 * 60
        while running_loop() and time.time() < deadline:
            time.sleep(2)
        if running_loop():
            print('the loop is still running after 20 minutes; it never got to the end of a block (stuck?)')
            sys.exit(1)
    else:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            if not running_loop():
                break
            time.sleep(0.5)
        else:
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)
        print(f'stopped the loop (pid {pid}); ' + ('it is gone' if not running_loop() else 'IT IS STILL RUNNING'))
        print('nobody was parked: check where Icepick and Burgers are, and hide them')
    with open(LOG, encoding='utf-8') as fh:
        for line in fh.readlines()[seen:][-6:]:
            print(line.rstrip())


if __name__ == '__main__':
    main()
