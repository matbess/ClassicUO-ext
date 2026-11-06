#!/usr/bin/env python3
"""Clem, the bard-mage, fights the way the user does (COMBAT.md). He never trades blows. Every creature he can see
is taken to be coming for him (the user, 2026-11-06: "they're going to come at you and attack when you see them and
get close"), so he keeps his distance from all of them and watches them all the time. He provokes them onto each
other (similar ones paired up, or onto an animal), and finishes them off with spells while they fight: Energy Bolt
while one has plenty of health, Lightning when it's low, Fireball when it's very low; at an uneven pair, the
stronger one first, before its partner dies and frees it. He meditates when mana runs short and everything is busy,
heals once clear when hurt, and uses a trapped pouch when paralysed. Bridge 7 (cuo-agent21 on), with "fight" and
"handOver" in his rules.

  python3 -I fight.py [--minutes N] [--resume]

Starts where he is in the front yard (door.py out takes him there) and ends the fight when nothing has been left
for 5 s, when there's no creature in the yard, or after N minutes (10). Then he goes straight back inside through the
door, locked and closed (door.go_in): he's never left out in the yard (the user, 2026-11-06: more creatures come
along); if creatures block the door, it's back to the fight. The same when it's interrupted or something goes wrong:
first clear of the creatures, then inside. If
the user gives him a command themselves the bridge refuses every action (handOver) and this stops at once, leaving him
to them. Only the user hands him back: --resume clears a takeover, and is passed only when they say so.
Logs to fight.log, and every cast (with the target's health before and after) and provoke to fights.jsonl, in
~/claude/uo-agent-work/combat.
"""
import argparse
import json
import math
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import uo  # noqa: E402
import door  # noqa: E402

WORK = os.path.expanduser('~/claude/uo-agent-work/combat')
LOG = os.path.join(WORK, 'fight.log')
ROWS = os.path.join(WORK, 'fights.jsonl')

YARD = (1738, 1414, 1780, 1450)          # the front yard in his rules (x1, y1, x2, y2); the door is at y 1414
PATROL = [(1759, 1426), (1770, 1438), (1748, 1428), (1758, 1444)]

TAMBOURINE = 0x0E9D
POUCH = 0x0E79
PROVOKE, MEDITATE = 22, 46
CURE, FIREBALL, GREATER_HEAL, LIGHTNING, ENERGY_BOLT = 11, 18, 29, 30, 42
MANA = {CURE: 6, FIREBALL: 9, GREATER_HEAL: 11, LIGHTNING: 11, ENERGY_BOLT: 20}
NAMES = {CURE: 'Cure', FIREBALL: 'Fireball', GREATER_HEAL: 'Greater Heal', LIGHTNING: 'Lightning',
         ENERGY_BOLT: 'Energy Bolt'}

SKILL_COOLDOWN = 10.5   # seconds: skills share one (fight 1: 9.8 s too soon, 10.8 s fine)
PROVOKE_RANGE = 8       # both creatures within this of him (fight 1: the llama at 8 worked)
ON_HIM = 2              # a free creature this close: run, nothing else
PROVOKE_FROM = 3        # provoke only when no free creature is closer than this
KEEP = 6                # otherwise keep free creatures at least this far off
CAST_FROM = 7           # a spell takes about 2 s: only when no free creature is closer than this
SAFE = 5                # and this far from creatures fighting each other
LURE = 11               # hunting: no closer than this to any creature; they see him and come
PROVOKED_BUSY = 6       # seconds after a provoke the pair counts as busy even before they meet
HURT, VERY_HURT = 0.6, 0.35  # his share of health: heal once clear / run far
LOW, VERY_LOW = 0.40, 0.15   # a target's share: Lightning below LOW, Fireball below VERY_LOW (to tune)

ATTACKABLE = {'Gray', 'Criminal', 'Enemy', 'Murderer'}
# animals that don't come for anyone: partners to set a creature on, not threats
PASSIVE = {'llama', 'sheep', 'horse', 'cow', 'bull', 'pig', 'boar', 'chicken', 'deer', 'hind', 'great hart', 'rabbit',
           'jack rabbit', 'cat', 'dog', 'bird', 'eagle', 'goat', 'mountain goat', 'rat', 'squirrel', 'ferret',
           'pack horse', 'pack llama', 'walrus', 'dolphin', 'crane', 'raven', 'magpie', 'finch', 'tern', 'swallow'}

info = None


class Stop(Exception):
    """Stop the fight. took_over: the user has him (or the bridge stopped), so nothing more is sent."""

    def __init__(self, message, took_over=False):
        super().__init__(message)
        self.took_over = took_over


def say(text):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + text
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def row(**fields):
    fields['time'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(ROWS, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(fields) + '\n')


def call(method, endpoint, **params):
    try:
        return uo.call(info, method, endpoint, **params)
    except uo.BridgeError as e:
        if e.code == 423:  # the user took over, or the bridge stopped
            raise Stop(e.message, took_over=True)
        raise


def texts(answer):
    return ' | '.join(m['text'] for m in answer.get('messages', []))


def said(answer, *words):
    low = texts(answer).lower()
    return any(w in low for w in words)


def dist(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def xy(m):
    return (m['x'], m['y'])


def share(m):
    return m['hits'] / m['hitsMax'] if m and m.get('hitsMax') else None


def health(m):
    return f"{m.get('hits')}/{m.get('hitsMax')}" if m and m.get('hitsMax') else '?'


def clamp(p):
    return (min(max(p[0], YARD[0]), YARD[2]), min(max(p[1], YARD[1] + 1), YARD[3]))


def look():
    """His status and the creatures within 18 tiles, by serial."""
    st = call('GET', '/status')
    near = call('GET', '/nearby', range=18)
    return st, {m['serial']: m for m in near['mobiles']}


def attackable(m):
    return (m.get('notoriety') in ATTACKABLE and not m.get('human') and not m.get('yourPet') and not m.get('dead')
            and not m.get('hidden') and bool(m.get('name')))


def passive(m):
    name = (m.get('name') or '').lower()
    return (name[2:] if name.startswith('a ') else name) in PASSIVE


def walk(p):
    """Run to p, coming back as soon as he's on his way. None when there's no way there."""
    try:
        return call('POST', '/walk', x=p[0], y=p[1], distance=0, run=1, wait=0)
    except uo.BridgeError as e:
        if e.code in (403, 409):  # outside the yard, or no path
            return None
        raise


def run_from(me, threats, far=8):
    """Run about `far` tiles away from the threats, staying in the yard."""
    if not threats:
        return None
    cx = sum(t[0] for t in threats) / len(threats)
    cy = sum(t[1] for t in threats) / len(threats)
    angle = math.atan2(me[1] - cy, me[0] - cx) if (me[0], me[1]) != (cx, cy) else 0.0
    for turn in (0, 0.5, -0.5, 1.0, -1.0, 1.6, -1.6, 2.3, -2.3, math.pi):
        a = angle + turn
        p = clamp((round(me[0] + far * math.cos(a)), round(me[1] + far * math.sin(a))))
        if dist(p, me) >= 3 and all(dist(p, t) >= dist(me, t) for t in threats) and walk(p):
            return p
    return None


def toward(me, goal, stop_short):
    """Run to a spot stop_short tiles before goal."""
    d = dist(me, goal)
    if d <= stop_short:
        return None
    f = (d - stop_short) / d
    p = clamp((round(me[0] + (goal[0] - me[0]) * f), round(me[1] + (goal[1] - me[1]) * f)))
    return p if walk(p) else None


def aim(serial):
    return call('POST', '/target', serial=serial)


def cancel_cursor():
    try:
        call('POST', '/target', cancel=1)
    except uo.BridgeError:
        pass


def carried(graphic):
    pack = call('GET', '/status')['backpack']['serial']
    return [i['serial'] for i in call('GET', '/contents', serial=pack, depth=1)['items']
            if int(i['graphic'], 16) == graphic]


class Fight:
    def __init__(self, minutes):
        self.minutes = minutes
        self.started = time.time()
        self.pairs = {}          # provoked: serial -> the serial it was set on
        self.provoked_at = {}    # serial -> when
        self.unseen = {}         # serial -> until when it's skipped ("Target cannot be seen.")
        self.last_skill = 0.0
        self.instrument = None
        self.meditating = False
        self.fought = False
        self.quiet_since = None
        self.patrol = list(PATROL)
        self.pending = None      # the last cast, for its damage once it has landed

    # ---- who's who ----

    def partner_of(self, serial):
        if serial in self.pairs:
            return self.pairs[serial]
        for a, b in self.pairs.items():
            if b == serial:
                return a
        return None

    def busy(self, serial, mobs):
        """Provoked onto (or by) a creature that's still alive: just provoked, or next to it."""
        other = self.partner_of(serial)
        m, o = mobs.get(serial), mobs.get(other or '')
        if not (m and o and attackable(o)):
            return False
        recent = time.time() - max(self.provoked_at.get(serial, 0), self.provoked_at.get(other, 0)) < PROVOKED_BUSY
        return recent or dist(xy(m), xy(o)) <= 3

    def visible(self, serial):
        return self.unseen.get(serial, 0) < time.time()

    def forget_dead(self, mobs):
        gone = {s for s in set(self.pairs) | set(self.pairs.values()) if not (mobs.get(s) and attackable(mobs[s]))}
        if gone:
            self.pairs = {a: b for a, b in self.pairs.items() if a not in gone and b not in gone}

    # ---- actions ----

    def skill_ready(self):
        return time.time() - self.last_skill >= SKILL_COOLDOWN

    def choose_pair(self, me, free, mobs):
        """The nearest free creature (within range) and something to set it on: another free one like it, else any
        free one, an animal, or a creature already fighting."""
        firsts = sorted((m for m in free if dist(me, xy(m)) <= PROVOKE_RANGE and self.visible(m['serial'])),
                        key=lambda m: dist(me, xy(m)))
        for a in firsts:
            others = [m for m in mobs.values() if attackable(m) and m['serial'] != a['serial']
                      and dist(me, xy(m)) <= PROVOKE_RANGE and self.visible(m['serial'])]
            if not others:
                continue
            free_ids = {f['serial'] for f in free}

            def rank(m):
                kind = 0 if m['serial'] in free_ids and m['body'] == a['body'] else \
                    1 if m['serial'] in free_ids else 2 if passive(m) else 3
                return (kind, dist(xy(a), xy(m)))
            return a, min(others, key=rank)
        return None

    def provoke(self, a, b):
        """a onto b; True when the music worked."""
        self.last_skill = time.time()
        self.meditating = False
        r = call('POST', '/skill', id=PROVOKE, cursor=1)
        if said(r, 'must wait'):
            self.last_skill = time.time() - SKILL_COOLDOWN + 1.5
            return False
        if said(r, 'what instrument') and r.get('targeting'):
            if not self.instrument:
                found = carried(TAMBOURINE)
                if not found:
                    cancel_cursor()
                    raise Stop('no tambourine in his pack')
                self.instrument = found[0]
            r = aim(self.instrument)
        if not r.get('targeting'):
            say(f'provoke: no cursor ({texts(r)!r})')
            return False
        try:
            r1 = aim(a['serial'])
            if not r1.get('targeting'):
                if said(r1, 'cannot be seen', 'line of sight'):
                    self.unseen[a['serial']] = time.time() + 3
                say(f'provoke {a["name"]}: {texts(r1)!r}')
                cancel_cursor()
                return False
            r2 = aim(b['serial'])
        except uo.BridgeError as e:
            say(f'provoke refused: {e}')
            cancel_cursor()
            return False
        if said(r2, 'cannot be seen', 'line of sight'):
            self.unseen[b['serial']] = time.time() + 3
        ok = said(r2, 'your music succeeds')
        row(event='provoke', a=a['name'], a_serial=a['serial'], a_health=health(a), b=b['name'], b_serial=b['serial'],
            b_health=health(b), ok=ok, text=texts(r1) + ' || ' + texts(r2))
        say(f'provoke {a["name"]} onto {b["name"]}: {"worked" if ok else "failed"} ({texts(r2)!r})')
        if ok:
            self.pairs[a['serial']] = b['serial']
            self.provoked_at[a['serial']] = time.time()
            self.fought = True
        return ok

    def spell_for(self, m, mana):
        s = share(m)
        choice = ENERGY_BOLT if s is None or s > LOW else LIGHTNING if s > VERY_LOW else FIREBALL
        if mana >= MANA[choice]:
            return choice
        for cheaper in (LIGHTNING, FIREBALL):
            if MANA[cheaper] < MANA[choice] and mana >= MANA[cheaper]:
                return cheaper
        return None

    def cast_target(self, me, busy):
        """At an uneven pair (one nearly dead, the other well), the stronger, before it's freed; else the one with
        the least health, to finish it."""
        reach = [m for m in busy if dist(me, xy(m)) <= 12 and self.visible(m['serial'])]
        by = {m['serial']: m for m in busy}
        for m in reach:
            o = by.get(self.partner_of(m['serial']) or '')
            if o and share(o) is not None and share(m) is not None and share(o) < 0.35 and share(m) - share(o) > 0.2:
                return m
        return min(reach, key=lambda m: share(m) if share(m) is not None else 1.0) if reach else None

    def cast_at(self, m, spell):
        self.meditating = False
        a = call('POST', '/cast', spell=spell, target=m['serial'])
        if said(a, 'cannot be seen', 'line of sight'):
            self.unseen[m['serial']] = time.time() + 3
        self.pending = {'spell': NAMES[spell], 'serial': m['serial'], 'name': m['name'], 'before': m.get('hits'),
                        'max': m.get('hitsMax'), 'at': time.time(), 'aimed': a.get('aimed'), 'text': texts(a),
                        'mana': a.get('mana')}
        say(f'{NAMES[spell]} at {m["name"]} ({health(m)}), mana {a.get("mana")}: {texts(a) or "-"}')

    def note_damage(self, mobs):
        p = self.pending
        if p and time.time() - p['at'] >= 1.5:
            after = mobs.get(p['serial'])
            p['after'] = after.get('hits') if after and attackable(after) else 0
            row(event='cast', **{k: v for k, v in p.items() if k != 'at'})
            self.pending = None

    def heal_self(self, st, spell):
        self.meditating = False
        a = call('POST', '/cast', spell=spell, target=st['serial'])
        say(f'{NAMES[spell]} on himself ({st["hits"]}/{st["hitsMax"]} -> {a.get("hits")}): {texts(a) or "-"}')

    # ---- the loop ----

    def run(self):
        say('fight: watching for creatures')
        while True:
            if time.time() - self.started > self.minutes * 60:
                raise Stop(f'{self.minutes} minutes are up')
            self.tick()

    def tick(self):
        st, mobs = look()
        me = (st['x'], st['y'])
        hp = st['hits'] / max(st['hitsMax'], 1)
        self.note_damage(mobs)
        self.forget_dead(mobs)

        if st.get('paralyzed'):
            found = carried(POUCH)
            if not found:
                raise Stop('paralysed, and no pouch left')
            a = call('POST', '/use', serial=found[0])
            say(f'paralysed: pouch {found[0]}: {texts(a)!r}')
            return

        threats = [m for m in mobs.values() if attackable(m) and not passive(m)]
        busy = [m for m in threats if self.busy(m['serial'], mobs)]
        busy_ids = {m['serial'] for m in busy}
        free = [m for m in threats if m['serial'] not in busy_ids]
        dmin = min((dist(me, xy(m)) for m in free), default=99)
        coming = [m for m in free if m.get('warMode')]
        if threats:
            self.quiet_since = None

        # something on him: run, nothing else
        if dmin <= ON_HIM:
            self.meditating = False
            run_from(me, [xy(m) for m in free if dist(me, xy(m)) <= KEEP + 2])
            return

        # badly hurt: run well clear; hurt: heal once clear
        if hp < HURT:
            if dmin <= KEEP + 2:
                self.meditating = False
                run_from(me, [xy(m) for m in free if dist(me, xy(m)) <= 12], far=10 if hp < VERY_HURT else 8)
                return
            if st['mana'] >= MANA[GREATER_HEAL]:
                self.heal_self(st, GREATER_HEAL)
                return
        if st.get('poisoned') and dmin > KEEP and st['mana'] >= MANA[CURE]:
            self.heal_self(st, CURE)
            return

        # set the nearest free one on something while there's room to
        if free and dmin >= PROVOKE_FROM and self.skill_ready():
            pair = self.choose_pair(me, free, mobs)
            if pair:
                self.provoke(*pair)
                return

        # free ones too close: keep away
        if dmin < KEEP:
            self.meditating = False
            run_from(me, [xy(m) for m in free if dist(me, xy(m)) <= KEEP + 3])
            return

        # clear of everything free: keep clear of the fighting too, then spells, then meditation
        close_busy = [xy(m) for m in busy if dist(me, xy(m)) < SAFE]
        if close_busy:
            self.meditating = False
            run_from(me, close_busy + [xy(m) for m in free if dist(me, xy(m)) <= 10], far=7)
            return
        if busy and dmin >= CAST_FROM:
            m = self.cast_target(me, busy)
            spell = self.spell_for(m, st['mana']) if m else None
            if spell and not (self.meditating and st['mana'] < 60):
                self.cast_at(m, spell)
                return
            nearly_dead = any(share(b) is not None and share(b) < 0.25 for b in busy)
            if not self.meditating and not coming and not nearly_dead and st['mana'] < 60 and self.skill_ready():
                self.last_skill = time.time()
                a = call('POST', '/skill', id=MEDITATE)
                self.meditating = said(a, 'meditative trance', 'at peace')
                say(f'meditate (mana {st["mana"]}): {texts(a)!r}')
                return

        if coming or busy:
            time.sleep(0.2)  # they're on their way or fighting: hold here, keep watching
            return

        # nothing coming and nothing fighting
        if free:
            if self.fought and self.quiet():
                raise Stop('the fight is over (only creatures that never came are left)', took_over=False)
            # hunting: close in until they can see him, no nearer
            if dmin > LURE:
                nearest = min(free, key=lambda m: dist(me, xy(m)))
                toward(me, xy(nearest), stop_short=LURE)
            time.sleep(0.3)
            return
        if self.fought:
            if self.quiet():
                raise Stop('the fight is over', took_over=False)
            time.sleep(0.3)
            return
        if not self.patrol:
            raise Stop('no creature in the yard', took_over=False)
        p = self.patrol.pop(0)
        say(f'looking around from {p[0]},{p[1]}')
        walk(p)
        time.sleep(1.5)

    def quiet(self):
        """Nothing coming or fighting for 5 s."""
        if self.quiet_since is None:
            self.quiet_since = time.time()
        return time.time() - self.quiet_since >= 5


def get_clear():
    """Leaving a fight for any reason but the user taking over: run well clear of every creature first, so he's not
    left standing among them."""
    try:
        st, mobs = look()
        me = (st['x'], st['y'])
        near = [xy(m) for m in mobs.values() if attackable(m) and not passive(m) and dist(me, xy(m)) <= 12]
        if near and run_from(me, near, far=12):
            say('ran clear before stopping')
    except (Stop, uo.BridgeError, OSError) as e:
        say(f'could not get clear: {e}')


def on_term(signum, frame):
    raise KeyboardInterrupt


def main():
    global info
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--minutes', type=float, default=10, help='give up after this long')
    parser.add_argument('--resume', action='store_true',
                        help='clear a takeover; only when the user has said they hand him back')
    args = parser.parse_args()
    os.makedirs(WORK, exist_ok=True)
    signal.signal(signal.SIGTERM, on_term)
    info = uo.find_bridge('Clem')
    st = call('GET', '/status')
    if st.get('bridge', 0) < 7:
        sys.exit('needs bridge 7 (cuo-agent21)')
    stopped = st.get('takenOver') or st.get('halted')
    if stopped and not args.resume:
        sys.exit(f'the user has him ({stopped}); --resume only once they hand him back')
    if st['y'] < YARD[1] + 1:
        sys.exit('he is not out in the front yard (door.py out first)')
    if stopped:
        call('POST', '/resume')
        say(f'resumed, as the user said (was: {stopped})')
    try:
        fight_then_home(args.minutes)
    except Stop as e:
        # only the user taking over (or the bridge stopping) gets here: he's theirs, nothing more is sent
        say(f'STOPPED: {e}')
        sys.exit(1)
    except KeyboardInterrupt:
        say('STOPPED (interrupted): getting him clear and home')
        leave_safely()
        sys.exit(1)
    except Exception as e:  # anything unexpected: still don't leave him out there
        say(f'STOPPED by an error: {e!r}; getting him clear and home')
        leave_safely()
        raise


def go_home():
    """Back inside through the front door, locked and closed (door.py). True when he's in."""
    door.info = info
    try:
        door.go_in()
        return True
    except door.Stop as e:
        st = call('GET', '/status')
        if st.get('takenOver') or st.get('halted'):
            raise Stop(f'{st.get("takenOver") or st.get("halted")} (on the way in: {e})', took_over=True)
        say(f'could not get in: {e}')
        return False


def fight_then_home(minutes):
    """Fight, then park him inside (the user, 2026-11-06: never leave him outside, more creatures come along). When
    the way in is blocked (creatures at the door), it's back to the fight."""
    for attempt in range(3):
        try:
            Fight(minutes).run()
        except Stop as e:
            if e.took_over:
                raise
            say(f'fight done: {e}')
        if go_home():
            say('parked inside; the door is locked and closed')
            return
    raise Stop('could not get him inside after 3 tries; he is out in the yard', took_over=False)


def leave_safely():
    get_clear()
    try:
        if go_home():
            say('parked inside; the door is locked and closed')
    except (Stop, uo.BridgeError, OSError) as e:
        say(f'could not get him home: {e}')

if __name__ == '__main__':
    main()
