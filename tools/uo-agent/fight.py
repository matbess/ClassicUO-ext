#!/usr/bin/env python3
"""Clem, the bard-mage, fights the way the user does (COMBAT.md). He never trades blows and never stands among
creatures. The user's rules (2026-11-06):
- If you see creatures, stay back: they come for him once they see him. He never walks up to one; to draw one he
  goes only as close as it can see him (about 12 tiles).
- With one following him, he goes only as close to another as provoking needs (about 7 tiles; the first stays
  behind him) and provokes the follower onto it; then he gets back away until nothing is coming after him.
- Standing there doing nothing is always the wrong thing: when nothing better can be done, he runs away from all of
  them, toward the tower. Never too far from the tower: every run leans toward it, more the further out he is.
- Casters first; similar creatures paired up; at an uneven pair, spells at the stronger one before it's freed.
  Spells only when nothing free is near (casting freezes him): Energy Bolt while it has plenty of health,
  Lightning when it's low, Fireball when it's very low; one at a time, waiting for each to land.
- Meditate when mana is short and everything is busy fighting; heal once clear; a trapped pouch when paralysed.

  python3 -I fight.py [--minutes N] [--resume]

Starts where he is outside (door.py out takes him there). He only leaves the fight by going home: when nothing is
left or coming, when nothing is found, after N minutes (10), or when this is interrupted, he makes his way back to
the front door in short hops, still watching and dealing with anything that comes, and goes in (door.go_in: locked and
closed). An error or a creature vanishing never ends it with him outside. The only other end is the user taking over
(the bridge then refuses every action: handOver): it stops at once and leaves him to them. Only the user hands him
back: --resume clears a takeover, and is passed only when they say so.
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

AREA = (1715, 1414, 1810, 1485)   # "outside" in his rules (x1, y1, x2, y2); the door is at y 1414
HOME = door.OUTSIDE               # in front of the door (1756,1416)
NEAR_HOME = 25                    # further out than this, every move pulls him back toward the tower
# where to look for creatures: south first, back where the ratmen were, then east (the user, 2026-11-06)
PATROL = [(1745, 1440), (1738, 1455), (1750, 1468), (1770, 1450), (1788, 1440)]
LOOK_AROUND = 3                   # seconds at each lookout point

TAMBOURINE = 0x0E9D
POUCH = 0x0E79
PROVOKE, MEDITATE = 22, 46
CURE, FIREBALL, GREATER_HEAL, LIGHTNING, ENERGY_BOLT = 11, 18, 29, 30, 42
MANA = {CURE: 6, FIREBALL: 9, GREATER_HEAL: 11, LIGHTNING: 11, ENERGY_BOLT: 20}
NAMES = {CURE: 'Cure', FIREBALL: 'Fireball', GREATER_HEAL: 'Greater Heal', LIGHTNING: 'Lightning',
         ENERGY_BOLT: 'Energy Bolt'}
LAND_TIME = 1.0         # seconds after the aim for a spell to land: no moving (casting freezes him; a step then
                        # gets "You are frozen and cannot move.", which cut the bridge's wait for the cursor short)

SKILL_COOLDOWN = 10.5   # seconds: skills share one (fight 1: 9.8 s too soon, 10.8 s fine)
PROVOKE_RANGE = 8       # both creatures within this of him (fight 1: the llama at 8 worked)
PROVOKE_SPOT = 7        # how close he goes to the creature he'll set the follower on
ON_HIM = 3              # a free creature this close: run, nothing else
CLEAR = 10              # free creatures further than this: he may cast or meditate
BACK_OFF = 9            # after a provoke, and from anything coming: get at least this far away
FIGHT_GAP = 8           # keep this far from creatures fighting each other
LURE = 12               # drawing one: no closer than this to any creature
LURE_WAIT = 20          # seconds: one that hasn't come for him by then is left be
PROVOKED_BUSY = 6       # seconds after a provoke the pair counts as busy even before they meet
HURT = 0.6              # his share of health: get clear, then heal
LOW, VERY_LOW = 0.15, 0.05   # a target's share: Lightning below LOW, Fireball below VERY_LOW (the user, 2026-11-06)

ATTACKABLE = {'Gray', 'Criminal', 'Enemy', 'Murderer'}
# how hard creatures are, for pairing (T2A; to tune with the user). Unlisted ones count as middling.
WEAK = {'mongbat', 'headless one', 'skeleton', 'zombie', 'giant rat', 'sewer rat', 'slime', 'rat', 'jack rabbit',
        'rabbit', 'hind', 'sheep', 'goat', 'mountain goat', 'pig', 'chicken', 'bird', 'cat', 'dog', 'llama', 'horse',
        'deer', 'eagle', 'crow', 'raven', 'ferret', 'squirrel', 'giant toad', 'bullfrog', 'snake', 'imp'}
STRONG = {'ogre', 'troll', 'frost troll', 'ettin', 'water elemental', 'earth elemental', 'air elemental',
          'fire elemental', 'ogre lord', 'orc lord', 'gargoyle', 'wyvern', 'drake', 'lich', 'giant serpent',
          'ice fiend', 'daemon', 'dragon', 'cyclops', 'titan'}
CASTERS = {'water elemental', 'air elemental', 'lich', 'orc mage', 'ratman mage', 'gargoyle', 'imp', 'daemon',
           'ice fiend', 'evil mage', 'lizardman mage', 'wisp', 'dragon', 'drake'}
# animals that don't come for anyone: partners to set a creature on, not threats
PASSIVE = {'llama', 'sheep', 'horse', 'cow', 'bull', 'pig', 'boar', 'chicken', 'deer', 'hind', 'great hart', 'rabbit',
           'jack rabbit', 'cat', 'dog', 'bird', 'eagle', 'goat', 'mountain goat', 'rat', 'squirrel', 'ferret',
           'pack horse', 'pack llama', 'walrus', 'dolphin', 'crane', 'raven', 'magpie', 'finch', 'tern', 'swallow'}

info = None


class Stop(Exception):
    """The user took over (or the bridge stopped): nothing more is sent."""


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
            raise Stop(e.message)
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


def kind(m):
    name = (m.get('name') or '').lower()
    for article in ('a ', 'an '):
        if name.startswith(article):
            return name[len(article):]
    return name


def tier(m):
    k = kind(m)
    return 0 if k in WEAK else 2 if k in STRONG else 1


def passive(m):
    return kind(m) in PASSIVE


def attackable(m):
    return (m.get('notoriety') in ATTACKABLE and not m.get('human') and not m.get('yourPet') and not m.get('dead')
            and not m.get('hidden') and bool(m.get('name')))


def in_area(p):
    return AREA[0] <= p[0] <= AREA[2] and AREA[1] + 1 <= p[1] <= AREA[3]


def look():
    """His status and the creatures within 18 tiles, by serial."""
    st = call('GET', '/status')
    near = call('GET', '/nearby', range=18)
    return st, {m['serial']: m for m in near['mobiles']}


def walk(p):
    """Run to p, coming back as soon as he's on his way. False when there's no way there."""
    try:
        return bool(call('POST', '/walk', x=p[0], y=p[1], distance=0, run=1, wait=0))
    except uo.BridgeError as e:
        if e.code in (403, 409):  # outside the area, or no path
            return False
        raise


def go_somewhere(me, score, radii=(5, 8), allowed=None):
    """Run to the best-scoring spot around him (higher is better) that a walk can start for; only spots `allowed`
    passes, when given (and any spot if none does)."""
    spots = []
    for r in radii:
        for i in range(16):
            a = i * math.pi / 8
            p = (round(me[0] + r * math.cos(a)), round(me[1] + r * math.sin(a)))
            if in_area(p):
                spots.append((score(p), p))
    if allowed and any(allowed(p) for _, p in spots):
        spots = [(v, p) for v, p in spots if allowed(p)]
    spots.sort(reverse=True)
    for _, p in spots[:6]:
        if walk(p):
            return p
    return None


def homeward(p):
    """How much a spot leans toward the tower: a little near it, a lot once he's out past NEAR_HOME."""
    d = dist(p, HOME)
    return -0.3 * d - (1.5 * (d - NEAR_HOME) if d > NEAR_HOME else 0)


def run_from(me, threats):
    """Away from every threat, toward the tower: never past or closer to anything within 12 tiles of him."""
    near = [t for t in threats if dist(me, t) <= 12]

    def score(p):
        nearest = min((dist(p, t) for t in threats), default=20)
        return 2.0 * min(nearest, 14) + homeward(p)

    def allowed(p):
        return all(dist(p, t) > dist(me, t) for t in near)
    return go_somewhere(me, score, allowed=allowed)


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
        self.deadline = time.time() + minutes * 60
        self.pairs = {}          # provoked: serial -> the serial it was set on
        self.provoked_at = {}    # serial -> when
        self.unseen = {}         # serial -> until when it's skipped ("Target cannot be seen.")
        self.history = {}        # serial -> [(time, distance to him)]
        self.last_skill = 0.0
        self.cast_until = 0.0    # a spell is on its way: no other until then
        self.instrument = None
        self.meditating = False
        self.fought = False
        self.quiet_since = None
        self.homeward = False    # going home: the fight is done, or time's up, or interrupted
        self.patrol = list(PATROL)
        self.goal = None
        self.goal_sent = 0.0
        self.arrived_at = None
        self.pending = None      # the last cast, for its damage once it has landed
        self.ignored = set()     # creatures that never came when drawn
        self.luring = None
        self.lure_since = 0.0

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

    def coming(self, m):
        """After him: in war mode, or getting closer."""
        h = self.history.get(m['serial'], [])
        closing = len(h) >= 3 and h[-1][1] < h[-3][1]
        return bool(m.get('warMode')) or closing

    def visible(self, serial):
        return self.unseen.get(serial, 0) < time.time()

    def remember(self, me, mobs):
        now = time.time()
        for s, m in mobs.items():
            h = self.history.setdefault(s, [])
            h.append((now, dist(me, xy(m))))
            del h[:-8]
        gone = {s for s in set(self.pairs) | set(self.pairs.values()) if not (mobs.get(s) and attackable(mobs[s]))}
        if gone:
            self.pairs = {a: b for a, b in self.pairs.items() if a not in gone and b not in gone}

    def skill_ready(self):
        return time.time() - self.last_skill >= SKILL_COOLDOWN

    # ---- provoking ----

    def partner_for(self, me, a, mobs, reach):
        """Something to set a on, within reach of him: like it first (the same tier), free before busy, then
        nearest to a; an animal will do."""
        cands = [m for m in mobs.values() if attackable(m) and m['serial'] != a['serial']
                 and self.visible(m['serial']) and dist(me, xy(m)) <= reach]
        if not cands:
            return None
        return min(cands, key=lambda m: (abs(tier(m) - tier(a)), self.busy(m['serial'], mobs), dist(xy(a), xy(m))))

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
                    say('no tambourine in his pack: no provoking')
                    self.last_skill = time.time() + 3600
                    return False
                self.instrument = found[0]
            r = aim(self.instrument)
        if not r.get('targeting'):
            say(f'provoke: no cursor ({texts(r)!r})')
            return False
        try:
            r1 = aim(a['serial'])
            if not r1.get('targeting'):
                if said(r1, 'cannot be seen', 'line of sight', 'too far'):
                    self.unseen[a['serial']] = time.time() + 3
                say(f'provoke {a["name"]}: {texts(r1)!r}')
                cancel_cursor()
                return False
            r2 = aim(b['serial'])
        except uo.BridgeError as e:
            say(f'provoke refused: {e}')
            cancel_cursor()
            return False
        if said(r2, 'cannot be seen', 'line of sight', 'too far'):
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

    # ---- spells ----

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
        """Casters first; at an uneven pair (one nearly dead, the other well), the stronger, before it's freed; else
        the one with the least health, to finish it."""
        reach = [m for m in busy if dist(me, xy(m)) <= 12 and self.visible(m['serial'])]
        if not reach:
            return None
        casters = [m for m in reach if kind(m) in CASTERS]
        if casters:
            return min(casters, key=lambda m: share(m) if share(m) is not None else 1.0)
        by = {m['serial']: m for m in busy}
        for m in reach:
            o = by.get(self.partner_of(m['serial']) or '')
            if o and share(o) is not None and share(m) is not None and share(o) < 0.35 and share(m) - share(o) > 0.2:
                return m
        return min(reach, key=lambda m: share(m) if share(m) is not None else 1.0)

    def cast_at(self, m, spell):
        self.meditating = False
        try:
            a = call('POST', '/cast', spell=spell, target=m['serial'])  # comes back once it's aimed (about 2 s)
        except uo.BridgeError as e:  # it died or went out of sight meanwhile
            say(f'{NAMES[spell]} at {m["name"]}: {e}')
            return
        finally:
            self.cast_until = time.time() + LAND_TIME
        if said(a, 'cannot be seen', 'line of sight', 'too far'):
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
        try:
            a = call('POST', '/cast', spell=spell, target=st['serial'])
        except uo.BridgeError as e:
            say(f'{NAMES[spell]} on himself: {e}')
            return
        finally:
            self.cast_until = time.time() + LAND_TIME
        say(f'{NAMES[spell]} on himself ({st["hits"]}/{st["hitsMax"]}): {texts(a) or "-"}')

    # ---- the loop ----

    def run(self):
        """Until he's inside (returns) or the user takes over (Stop)."""
        say('fight: watching for creatures')
        while True:
            if not self.homeward and time.time() > self.deadline:
                self.go_home('time is up')
            try:
                if self.tick():
                    return
            except Stop:
                raise
            except KeyboardInterrupt:
                if self.homeward:
                    raise
                self.go_home('interrupted')
            except Exception as e:  # never leave him standing: log it and carry on
                say(f'error (carrying on): {e!r}')
                time.sleep(0.3)

    def go_home(self, why):
        if not self.homeward:
            say(f'going home: {why}')
        self.homeward = True
        self.goal = None

    def tick(self):
        st, mobs = look()
        me = (st['x'], st['y'])
        hp = st['hits'] / max(st['hitsMax'], 1)
        self.remember(me, mobs)
        self.note_damage(mobs)
        casting = time.time() < self.cast_until

        if st.get('paralyzed') and not casting:
            found = carried(POUCH)
            if found:
                a = call('POST', '/use', serial=found[0])
                say(f'paralysed: pouch {found[0]}: {texts(a)!r}')
                return False
            say('paralysed, and no pouch left')

        threats = [m for m in mobs.values() if attackable(m) and not passive(m)]
        busy = [m for m in threats if self.busy(m['serial'], mobs)]
        busy_ids = {m['serial'] for m in busy}
        free = [m for m in threats if m['serial'] not in busy_ids]
        coming = [m for m in free if self.coming(m)]
        dfree = min((dist(me, xy(m)) for m in free), default=99)
        dbusy = min((dist(me, xy(m)) for m in busy), default=99)
        if coming or busy:
            self.quiet_since = None
        if casting:
            time.sleep(0.15)  # frozen while the spell goes off: just watch
            return False

        # anything free close to him: run, away from all of them and toward the tower
        if dfree <= ON_HIM:
            self.meditating = False
            run_from(me, [xy(m) for m in threats])
            return False

        # hurt: away from whatever's near first, then heal
        if hp < HURT:
            if dfree <= CLEAR or dbusy < FIGHT_GAP:
                self.meditating = False
                run_from(me, [xy(m) for m in threats])
                return False
            if st['mana'] >= MANA[GREATER_HEAL]:
                self.heal_self(st, GREATER_HEAL)
                return False
        if st.get('poisoned') and dfree > CLEAR and st['mana'] >= MANA[CURE]:
            self.heal_self(st, CURE)
            return False

        # one coming for him: set it on something, from no closer than provoking needs
        if coming:
            a = sorted(coming, key=lambda m: (kind(m) not in CASTERS, dist(me, xy(m))))[0]
            if self.skill_ready() and dist(me, xy(a)) <= PROVOKE_RANGE and self.visible(a['serial']):
                b = self.partner_for(me, a, mobs, PROVOKE_RANGE)
                if b:
                    if self.provoke(a, b):
                        run_from(me, [xy(m) for m in threats])  # and back off from both
                    return False
            b = self.partner_for(me, a, mobs, 18)
            if b and self.skill_ready():
                # lead it toward b: to about PROVOKE_SPOT from b, keeping away from a and the rest
                def score(p):
                    others = [t for t in threats if t['serial'] not in (a['serial'], b['serial'])]
                    return (-2.0 * abs(dist(p, xy(b)) - PROVOKE_SPOT) + min(dist(p, xy(a)), 8)
                            + 0.5 * min((dist(p, xy(t)) for t in others), default=8) + 0.5 * homeward(p))
                go_somewhere(me, score)
                return False
            # nothing to set it on, or the skill isn't ready: keep well away from it, toward the tower
            if dist(me, xy(a)) < LURE:
                run_from(me, [xy(m) for m in threats])
            else:
                time.sleep(0.15)
            return False

        # nothing coming: stay clear of the fighting
        if dbusy < FIGHT_GAP or dfree < BACK_OFF:
            self.meditating = False
            run_from(me, [xy(m) for m in threats])
            return False

        # clear of everything: spells at the fighting, then meditation
        if busy and dfree > CLEAR:
            m = self.cast_target(me, busy)
            spell = self.spell_for(m, st['mana']) if m else None
            if spell and not (self.meditating and st['mana'] < 60):
                self.cast_at(m, spell)
                return False
            nearly_dead = any(share(b) is not None and share(b) < 0.25 for b in busy)
            if not self.meditating and not nearly_dead and st['mana'] < 60 and self.skill_ready():
                self.last_skill = time.time()
                a = call('POST', '/skill', id=MEDITATE)
                self.meditating = said(a, 'meditative trance', 'at peace')
                say(f'meditate (mana {st["mana"]}): {texts(a)!r}')
                return False
            time.sleep(0.15)
            return False

        # nothing coming and nothing fighting
        if self.fought and not self.homeward:
            if self.quiet_since is None:
                self.quiet_since = time.time()
            if time.time() - self.quiet_since >= 5:
                self.go_home('nothing is coming after him')
            time.sleep(0.15)
            return False

        if self.homeward:
            return self.step_home(me, threats)

        # drawing one: as close as it can see him, no closer; one that doesn't come within LURE_WAIT is left be
        lurable = [m for m in free if m['serial'] not in self.ignored]
        if lurable:
            nearest = min(lurable, key=lambda m: dist(me, xy(m)))
            if self.luring != nearest['serial']:
                self.luring, self.lure_since = nearest['serial'], time.time()
            elif time.time() - self.lure_since > LURE_WAIT:
                say(f'{nearest["name"]} never came for him; leaving it be')
                self.ignored.add(nearest['serial'])
                return False
            if dist(me, xy(nearest)) > LURE + 1:
                def score(p):
                    closest = min((dist(p, xy(t)) for t in threats), default=20)
                    return -2.0 * abs(dist(p, xy(nearest)) - LURE) + 3 * min(closest - LURE, 0) + homeward(p)
                go_somewhere(me, score, radii=(4, 7))
            else:
                time.sleep(0.2)  # in its sight: wait for it to come
            return False

        return self.search(me)

    def step_home(self, me, threats):
        """Short hops to the front door, then in (door.go_in). True once he's inside."""
        if dist(me, HOME) <= 1:
            door.info = info
            try:
                door.go_in()
                return True
            except door.Stop as e:
                st = call('GET', '/status')
                if st.get('takenOver') or st.get('halted'):
                    raise Stop(f'{st.get("takenOver") or st.get("halted")} (on the way in: {e})')
                say(f'could not get in yet: {e}')
                run_from(me, [xy(t) for t in threats])
                return False
        d = dist(me, HOME)
        f = min(8, d) / d
        p = (round(me[0] + (HOME[0] - me[0]) * f), round(me[1] + (HOME[1] - me[1]) * f))
        if not walk(p if dist(p, HOME) > 1 else HOME):
            go_somewhere(me, lambda q: -dist(q, HOME), radii=(3, 6))
        time.sleep(0.3)
        return False

    def search(self, me):
        """No creature in sight: ride to each lookout point (watching all the way), look around, the next."""
        if self.goal is None:
            if not self.patrol:
                self.go_home('no creature anywhere he looked')
                return False
            self.goal = self.patrol.pop(0)
            self.goal_sent = time.time()
            self.arrived_at = None
            say(f'riding to {self.goal[0]},{self.goal[1]} to look around')
            if not walk(self.goal):
                say(f'no way to {self.goal[0]},{self.goal[1]}')
                self.goal = None
            return False
        if dist(me, self.goal) > 1:
            if time.time() - self.goal_sent > 4:  # stopped short: send him on
                self.goal_sent = time.time()
                if not walk(self.goal):
                    say(f'no way on to {self.goal[0]},{self.goal[1]}')
                    self.goal = None
            time.sleep(0.2)
            return False
        if self.arrived_at is None:
            self.arrived_at = time.time()
        if time.time() - self.arrived_at >= LOOK_AROUND:
            self.goal = None
        time.sleep(0.2)
        return False


def on_term(signum, frame):
    raise KeyboardInterrupt


def main():
    global info
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--minutes', type=float, default=10, help='then home')
    parser.add_argument('--resume', action='store_true',
                        help='clear a takeover; only when the user has said they hand him back')
    args = parser.parse_args()
    os.makedirs(WORK, exist_ok=True)
    signal.signal(signal.SIGTERM, on_term)
    info = uo.find_bridge('Clem')
    st = call('GET', '/status')
    if st.get('bridge', 0) < 7:
        sys.exit('needs bridge 7 (cuo-agent22)')
    stopped = st.get('takenOver') or st.get('halted')
    if stopped and not args.resume:
        sys.exit(f'the user has him ({stopped}); --resume only once they hand him back')
    if st['y'] < AREA[1] + 1:
        sys.exit('he is not outside (door.py out first)')
    if stopped:
        call('POST', '/resume')
        say(f'resumed, as the user said (was: {stopped})')
    try:
        Fight(args.minutes).run()
        say('parked inside; the door is locked and closed')
    except Stop as e:
        say(f'STOPPED: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
