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
import collections
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
REAGENT_BAG = '0x40677564'  # Razor's restock and scavenger hot bag in his pack
BLACK_PEARL, BLOOD_MOSS, GARLIC, GINSENG, MANDRAKE, NIGHTSHADE, SPIDERS_SILK, SULFUROUS_ASH = (
    0x0F7A, 0x0F7B, 0x0F84, 0x0F85, 0x0F86, 0x0F88, 0x0F8D, 0x0F8C)
REAGENTS = {CURE: (GARLIC, GINSENG), FIREBALL: (BLACK_PEARL,), GREATER_HEAL: (GARLIC, GINSENG, MANDRAKE, SPIDERS_SILK),
            LIGHTNING: (MANDRAKE, SULFUROUS_ASH), ENERGY_BOLT: (BLACK_PEARL, NIGHTSHADE)}
LAND_TIME = 1.0         # seconds after the aim for a spell to land: no moving (casting freezes him; a step then
                        # gets "You are frozen and cannot move.", which cut the bridge's wait for the cursor short)

SKILL_COOLDOWN = 10.5   # seconds: skills share one (fight 1: 9.8 s too soon, 10.8 s fine)
PROVOKE_RANGE = 8       # both creatures within this of him (fight 1: the llama at 8 worked)
PROVOKE_SPOT = 7        # how close he goes to the creature he'll set the follower on
ON_HIM = 3              # a free creature this close: run, nothing else
CLEAR = 10              # free creatures further than this: he may cast or meditate
BACK_OFF = 9            # after a provoke, and from anything coming: get at least this far away
FIGHT_GAP = 8           # keep this far from creatures fighting each other
KEEP = 3                # one coming at him: get away once it's closer than this (the user: stay about 3 tiles away)
CAST_SPOT = 10          # creatures fighting each other out of spell range (12): ride to this far from them
LONE_CAST = 4           # a lone one coming at him (nothing to set it on): cast at it from this far
PAIR_RANGE = 9          # the two to provoke onto each other: at most this far apart (the server's limit isn't known;
                        # each "too far away from each other" is logged with the distance, to tune)
ORBIT = 5               # bringing a follower near another creature: circle the other one this far off (the user)
SPACE = 3               # and keep at least this far from every creature while doing it (the user: "like 3 tiles")
FOLLOWER_ROOM = 5       # a ride while bringing the follower round keeps this far from it (it closes in meanwhile)
ORBIT_FOR = 40          # seconds circling one pair before giving up on it
KEEP_CASTER = 7         # the same for casters (gargoyles, gazers: dangerous; provoked first, killed first)
DRAW_CASTER = 11        # drawing a caster: they notice him from far off (the user); no nearer than this
LURE = 5                # drawing one: ride to about this far from it and wait for it to target him (the user)
UNSEEN_FOR = 60         # "Target cannot be seen.": left out this long (shut in a building, like the ogre)
LURE_WAIT = 15          # seconds there: one that hasn't turned on him by then is left be (trapped in a building, or
                        # one that doesn't attack)
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
           'ice fiend', 'evil mage', 'lizardman mage', 'wisp', 'dragon', 'drake', 'gazer'}
# casters: dangerous from a distance; stay away, provoke them onto something first and kill them first (the user)
# animals that don't come for anyone: partners to set a creature on, not threats
PASSIVE = {'llama', 'sheep', 'horse', 'cow', 'bull', 'pig', 'boar', 'chicken', 'deer', 'hind', 'great hart', 'rabbit',
           'jack rabbit', 'cat', 'dog', 'bird', 'eagle', 'goat', 'mountain goat', 'rat', 'squirrel', 'ferret',
           'pack horse', 'pack llama', 'walrus', 'dolphin', 'crane', 'raven', 'magpie', 'finch', 'tern', 'swallow',
           'panther', 'timber wolf'}
# the user, 2026-11-06: leave panthers alone unless they attack him (they don't seem to); timber wolves don't attack,
# dire wolves do (deal with those). It's per creature, and the bridge's notoriety doesn't tell (all show Gray). A
# creature from this list that turns on him (war mode, not provoked) counts as a threat after all.
SAY_FOLLOW = 'all follow me'

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


_last_walk = {'p': None, 't': 0.0}


def clamp_area(p):
    return (min(max(p[0], AREA[0]), AREA[2]), min(max(p[1], AREA[1] + 1), AREA[3]))


def walk(p, keep=1.5):
    """Run to p, coming back as soon as he's on his way. False when there's no way there. The same spot again (or
    one next to it) within `keep` seconds isn't sent: every new walk is more riding, and back-and-forth tires the
    horse (2026-11-06)."""
    if _last_walk['p'] and dist(p, _last_walk['p']) <= 1 and time.time() - _last_walk['t'] < keep:
        return True
    try:
        ok = bool(call('POST', '/walk', x=p[0], y=p[1], distance=0, run=1, wait=0))
    except uo.BridgeError as e:
        if e.code in (403, 409):  # outside the area, or no path
            return False
        raise
    _last_walk['p'], _last_walk['t'] = p, time.time()
    return ok


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
    # no wiggling (the user, 2026-11-06): keep riding to the spot picked a moment ago unless it has become clearly
    # worse or unsafe; picking afresh every tick sent him back and forth between two tiles and tired the horse
    g = _last_walk['p']
    if (g and spots and time.time() - _last_walk['t'] < 2.5 and dist(me, g) > 1 and in_area(g)
            and (not allowed or allowed(g)) and score(g) >= spots[0][0] - 4):
        return g
    for _, p in spots[:6]:
        if walk(p):
            return p
    return None


def path_clear(me, p, spots, space):
    """Every tile of the straight ride from me to p stays at least `space` from each of `spots` (beyond those he's
    already closer to than that, which he's getting away from)."""
    n = max(dist(me, p), 1)
    for i in range(1, n + 1):
        q = (round(me[0] + (p[0] - me[0]) * i / n), round(me[1] + (p[1] - me[1]) * i / n))
        for t in spots:
            if dist(q, t) < space and dist(q, t) < dist(me, t):
                return False
    return True


class Mover:
    """One destination at a time (the user, 2026-11-06: "Stop wiggling!!", it tires the horse). He stands still unless
    there's a reason to move; when he moves he rides straight to one spot, and another is only picked when he's
    there, the reason changes, or the caller forces it (getting away from something on him)."""

    def __init__(self):
        self.goal, self.why, self.at = None, None, 0.0

    def going(self, me):
        return self.goal is not None and dist(me, self.goal) > 1 and time.time() - self.at < 8

    def go(self, me, p, why, force=False):
        if not force and self.why == why and self.going(me):
            return True
        if walk(p, keep=0):
            self.goal, self.why, self.at = p, why, time.time()
            return True
        return False

    def clear(self):
        self.goal, self.why = None, None


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
        self.mover = Mover()
        self.killing = None      # the one he's killing with spells (no partner to set it on): all the way
        self.reagents_at = 0.0
        self.reagent_counts = collections.Counter()
        self.orbit_dir = {}      # (follower, partner): which way round he circles the partner (kept: never back)
        self.orbit_since = {}    # (follower, partner): when he started circling
        self.gave_up = set()     # (follower, partner): circled ORBIT_FOR without getting them close
        self.ignored = set()     # creatures that never came when drawn
        self.luring = None
        self.lure_since = 0.0
        self.seen_message = call('GET', '/status')['lastMessageId']
        self.tired = None        # the horse said it's tired: 'very' (a warning) or 'too' (it won't move)
        mounts = call('GET', '/rules').get('mounts', [])
        self.horse = mounts[0] if mounts else None

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
        """After him: it has turned Criminal. The user, 2026-11-06: "I can see the creature turn completely grey when
        they target me, that means they're going to come at me. And they stay grey" (Clem's criminal_hue is a grey;
        attackable creatures are notoriety Gray, another colour). The gargoyle that day: Gray, then Criminal at 14
        tiles, then straight at him; war mode never came on."""
        return m.get('notoriety') == 'Criminal'

    def visible(self, serial):
        return self.unseen.get(serial, 0) < time.time()

    def still(self, me):
        """Standing still: the same tile on the last two looks and no ride under way. Casting while a step is under
        way gets "You are frozen and cannot move." and the spell goes astray."""
        h = self.positions[-2:]
        return len(h) == 2 and all(p == me for p in h) and not self.mover.going(me)

    def remember(self, me, mobs):
        self.positions = (getattr(self, 'positions', []) + [me])[-5:]
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

    def partner_for(self, me, a, mobs, reach, pair=None):
        """Something to set a on, within reach of him: like it first (the same tier), free before busy, then
        nearest to a; an animal will do."""
        cands = [m for m in mobs.values() if attackable(m) and m['serial'] != a['serial']
                 and self.visible(m['serial']) and m['serial'] not in self.ignored and dist(me, xy(m)) <= reach
                 and (pair is None or dist(xy(a), xy(m)) <= pair)]
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
                if said(r1, 'cannot be seen', 'line of sight'):
                    self.unseen[a['serial']] = time.time() + UNSEEN_FOR
                say(f'provoke {a["name"]}: {texts(r1)!r}')
                cancel_cursor()
                return False
            r2 = aim(b['serial'])
        except uo.BridgeError as e:
            say(f'provoke refused: {e}')
            cancel_cursor()
            return False
        if said(r2, 'cannot be seen', 'line of sight'):
            self.unseen[b['serial']] = time.time() + UNSEEN_FOR
        ok = said(r2, 'your music succeeds')
        row(event='provoke', a=a['name'], a_serial=a['serial'], a_health=health(a), b=b['name'], b_serial=b['serial'],
            b_health=health(b), ok=ok, apart=dist(xy(a), xy(b)), text=texts(r1) + ' || ' + texts(r2))
        if said(r2, 'too far away from each other'):
            say(f'too far apart at {dist(xy(a), xy(b))} tiles')
        say(f'provoke {a["name"]} onto {b["name"]}: {"worked" if ok else "failed"} ({texts(r2)!r})')
        if ok:
            self.pairs[a['serial']] = b['serial']
            self.provoked_at[a['serial']] = time.time()
            self.fought = True
        return ok

    # ---- spells ----

    def reagents(self):
        """What's in his reagent bag, by graphic (read at most every 3 s; the client keeps the counts current)."""
        if time.time() - self.reagents_at > 3:
            self.reagents_at = time.time()
            counts = collections.Counter()
            try:
                for i in call('GET', '/contents', serial=REAGENT_BAG, depth=1)['items']:
                    counts[int(i['graphic'], 16)] += i.get('amount', 1)
                self.reagent_counts = counts
            except uo.BridgeError as e:
                say(f'reagent bag: {e}')
        return self.reagent_counts

    def can_cast(self, spell, mana):
        have = self.reagents()
        return mana >= MANA[spell] and all(have[r] >= 1 for r in REAGENTS[spell])

    def spell_for(self, m, mana):
        """Energy Bolt while it has plenty of health, Lightning when it's low, Fireball when it's very low (the user);
        another one when that's short of mana or reagents (black pearls run out first)."""
        s = share(m)
        choice = ENERGY_BOLT if s is None or s > LOW else LIGHTNING if s > VERY_LOW else FIREBALL
        for spell in (choice, ENERGY_BOLT, LIGHTNING, FIREBALL):
            if self.can_cast(spell, mana):
                return spell
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
            if not a.get('aimed'):
                # the bridge came back on a message before the cursor ("You are frozen and cannot move." when a step
                # was still under way, 2026-11-06): the cursor still comes; aim it, or the next cast gets "You must
                # wait for that spell to have an effect."
                end = time.time() + 2.5
                while time.time() < end:
                    if call('GET', '/status').get('targeting'):
                        try:
                            aim(m['serial'])
                            a['aimed'] = 'late'
                        except uo.BridgeError as e:
                            say(f'{NAMES[spell]}: the late cursor: {e}')
                            cancel_cursor()
                        break
                    time.sleep(0.1)
        except uo.BridgeError as e:  # it died or went out of sight meanwhile
            say(f'{NAMES[spell]} at {m["name"]}: {e}')
            return
        finally:
            self.cast_until = time.time() + LAND_TIME
        if said(a, 'cannot be seen', 'line of sight'):
            self.unseen[m['serial']] = time.time() + UNSEEN_FOR
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

        self.read_messages()
        if self.tired and not casting:
            return self.rest_horse(me, mobs, st)

        if st.get('paralyzed') and not casting:
            found = carried(POUCH)
            if found:
                a = call('POST', '/use', serial=found[0])
                say(f'paralysed: pouch {found[0]}: {texts(a)!r}')
                return False
            say('paralysed, and no pouch left')

        threats = [m for m in mobs.values() if attackable(m) and (not passive(m) or self.coming(m))]
        busy = [m for m in threats if self.busy(m['serial'], mobs)]
        busy_ids = {m['serial'] for m in busy}
        free = [m for m in threats if m['serial'] not in busy_ids]
        coming = [m for m in free if self.coming(m)]
        dfree = min((dist(me, xy(m)) for m in free), default=99)
        dbusy = min((dist(me, xy(m)) for m in busy), default=99)
        # free creatures that matter for casting: not ones left be (shut in a building, never came)
        dloose = min((dist(me, xy(m)) for m in free if m['serial'] not in self.ignored), default=99)
        if coming or busy:
            self.quiet_since = None
        if casting:
            time.sleep(0.15)  # frozen while the spell goes off: just watch
            return False

        # something right on him: get away, away from all of them and toward the tower
        if dfree <= ON_HIM:
            self.meditating = False
            self.flee(me, [xy(m) for m in threats])
            return False

        # hurt: away from whatever's near first, then heal
        if hp < HURT:
            if dloose <= CLEAR or dbusy < FIGHT_GAP:
                self.meditating = False
                self.flee(me, [xy(m) for m in threats])
                return False
            if self.can_cast(GREATER_HEAL, st['mana']):
                self.heal_self(st, GREATER_HEAL)
                return False
        if st.get('poisoned') and dloose > CLEAR and self.can_cast(CURE, st['mana']):
            self.heal_self(st, CURE)
            return False

        # coming at him (turned Criminal): casters first. Provoke it onto something as soon as both are in range;
        # too close (casters: closer than KEEP_CASTER) means get away, toward something to set it on if there is one;
        # otherwise stand still and let it come
        if coming:
            self.luring = None
            # once he has started on one with spells, he doesn't go half way (the user, 2026-11-06): the next spell
            # as soon as the last has landed, until it's dead; between spells only a short hop when it's right on him
            k = mobs.get(self.killing or '')
            if k and attackable(k):
                spell = self.spell_for(k, st['mana'])
                if spell:
                    if dist(me, xy(k)) <= 2:
                        self.flee(me, [xy(m) for m in threats], radii=(4, 3))
                        return False
                    if self.mover.going(me) or not self.still(me):
                        time.sleep(0.1)  # the hop first: no casting on the move
                        return False
                    self.cast_at(k, spell)
                    return False
                say(f'no mana or reagents left for {k["name"]}')
            self.killing = None
            a = sorted(coming, key=lambda m: (kind(m) not in CASTERS, dist(me, xy(m))))[0]
            # both within PROVOKE_RANGE of him and within PAIR_RANGE of each other ("The creatures you are trying to
            # provoke are too far away from each other for your music to have an effect.": an orc 15 from a panther)
            b = self.partner_for(me, a, mobs, PROVOKE_RANGE, pair=PAIR_RANGE)
            if self.skill_ready() and dist(me, xy(a)) <= PROVOKE_RANGE and b:
                self.mover.clear()
                if self.provoke(a, b):
                    self.flee(me, [xy(m) for m in threats], fresh=True)  # and back off from both
                return False
            keep = KEEP_CASTER if kind(a) in CASTERS else KEEP
            if self.mover.why == 'flee' and self.mover.going(me):
                # a getaway is ridden to the end (switching between getting away and leading was the wiggle)
                self.flee(me, [xy(m) for m in threats])
                return False
            if not b and dist(me, xy(a)) >= keep:
                far = self.partner_for(me, a, mobs, 18)
                if far and time.time() - self.orbit_since.setdefault((a['serial'], far['serial']), time.time()) > ORBIT_FOR:
                    self.gave_up.add((a['serial'], far['serial']))
                if far and (a['serial'], far['serial']) in self.gave_up:
                    far = None  # circled long enough without getting them close: given up on that pair
                if far and self.circle(me, a, far, threats):
                    return False
            if dist(me, xy(a)) < keep:
                far = b or self.partner_for(me, a, mobs, 18)
                self.flee(me, [xy(m) for m in threats], toward=xy(far) if far else None)
                return False
            # nothing anywhere to set it on: the last one keeps coming; cast at it once a getaway has left it
            # LONE_CAST tiles behind (the user: keep running away while casting spells)
            spell = self.spell_for(a, st['mana'])
            usable = self.partner_for(me, a, mobs, 18)
            if usable and (a['serial'], usable['serial']) in self.gave_up:
                usable = None
            if (spell and not usable and dist(me, xy(a)) >= LONE_CAST and self.still(me)
                    and min((dist(me, xy(m)) for m in coming if m is not a), default=99) >= LONE_CAST):
                self.mover.clear()
                self.killing = a['serial']
                say(f'killing {a["name"]} with spells, all the way')
                self.cast_at(a, spell)
                return False
            time.sleep(0.15)
            return False

        # stay clear of the fighting
        if dbusy < FIGHT_GAP:
            self.meditating = False
            self.flee(me, [xy(m) for m in busy] + [xy(m) for m in free if dist(me, xy(m)) <= 10])
            return False

        # fights going on and nothing loose near him: spells (casters first), then meditation
        if busy:
            if dloose > CLEAR and dbusy > 12:
                # too far off to cast at them: one ride to about CAST_SPOT tiles from the nearest of them
                n = min(busy, key=lambda b: dist(me, xy(b)))
                d = dist(me, xy(n))
                f = (d - CAST_SPOT) / d
                spot = clamp_area((round(me[0] + (n['x'] - me[0]) * f), round(me[1] + (n['y'] - me[1]) * f)))
                if path_clear(me, spot, [xy(t) for t in threats], FIGHT_GAP) and self.mover.go(me, spot, 'to cast'):
                    return False
            if dloose > CLEAR:
                m = self.cast_target(me, busy)
                spell = self.spell_for(m, st['mana']) if m else None
                if spell and not (self.meditating and st['mana'] < 60):
                    if not self.still(me):
                        time.sleep(0.15)  # let the ride finish first: no casting on the move
                        return False
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

        # drawing one (the user): ride straight to where it'll notice him (5 tiles; casters notice from far, 11) and
        # stand still there until it targets him (turns Criminal); left be if it hasn't by LURE_WAIT (shut in a
        # building, or it doesn't attack). No moving about while waiting.
        lurable = [m for m in free if m['serial'] not in self.ignored and self.visible(m['serial'])]
        if lurable:
            current = [m for m in lurable if m['serial'] == self.luring]
            target = current[0] if current else min(lurable, key=lambda m: dist(me, xy(m)))
            if self.luring != target['serial']:
                self.luring, self.lure_since = target['serial'], None
                self.mover.clear()
                say(f'drawing {target["name"]} at {target["x"]},{target["y"]} ({dist(me, xy(target))} tiles)')
            near_enough = DRAW_CASTER if kind(target) in CASTERS else LURE
            d = dist(me, xy(target))
            if self.lure_since is None:
                if d > near_enough + 1:
                    f = (d - near_enough) / d
                    spot = clamp_area((round(me[0] + (target['x'] - me[0]) * f),
                                       round(me[1] + (target['y'] - me[1]) * f)))
                    if not self.mover.go(me, spot, 'draw ' + target['serial']):
                        say(f'no way toward {target["name"]}; leaving it be')
                        self.ignored.add(target['serial'])
                    time.sleep(0.2)
                    return False
                self.lure_since = time.time()
                say(f'standing {d} tiles from {target["name"]}, waiting for it to come')
            if time.time() - self.lure_since > LURE_WAIT:
                say(f'{target["name"]} never turned on him from {d} tiles; leaving it be')
                self.ignored.add(target['serial'])
                self.luring = None
                return False
            time.sleep(0.2)
            return False

        return self.search(me)

    def flee(self, me, threats, toward=None, fresh=False, radii=(8, 5)):
        """Get away: one spot about 8 tiles off, never nearer anything within 12, leaning toward the tower (or toward
        `toward`, something to set the follower on). The spot is kept until he's there; a new one only when something
        is right on him and the spot doesn't take him away from it (or `fresh`)."""
        m = self.mover
        if not fresh and m.why == 'flee' and m.going(me):
            on_him = [t for t in threats if dist(me, t) <= ON_HIM - 1]
            if all(dist(m.goal, t) > dist(me, t) for t in on_him):
                return
        near = [t for t in threats if dist(me, t) <= 12]

        def score(p):
            nearest = min((dist(p, t) for t in threats), default=20)
            v = 2.0 * min(nearest, 14) + homeward(p)
            if toward:
                v -= 1.5 * abs(dist(p, toward) - PROVOKE_SPOT)
            return v
        spots = []
        for r in radii:
            for i in range(16):
                a = i * math.pi / 8
                p = clamp_area((round(me[0] + r * math.cos(a)), round(me[1] + r * math.sin(a))))
                if dist(p, me) >= 3:
                    spots.append((all(dist(p, t) > dist(me, t) for t in near) and path_clear(me, p, near, SPACE),
                                  score(p), p))
        spots.sort(reverse=True)
        for _, _, p in spots[:8]:
            if m.go(me, p, 'flee', force=True):
                return

    def circle(self, me, a, b, threats):
        """Bring follower a near b without going near either (the user, 2026-11-06): ride to about ORBIT tiles from b,
        then circle b at that distance, always the same way round, a stretch at a time, at least SPACE tiles from every
        creature; a, chasing him, gets dragged round close to b, and the provoke (checked first every tick) goes off as
        soon as both are in range. One stretch at a time, kept until he's there: no back and forth."""
        m = self.mover
        why = 'circle ' + b['serial']
        if m.why == why and m.going(me):
            return True
        key = (a['serial'], b['serial'])
        bx, by = xy(b)
        here = math.atan2(me[1] - by, me[0] - bx)
        if key not in self.orbit_dir:
            # the way round that takes him further from the follower to start with
            def gap(sign):
                p = (round(bx + ORBIT * math.cos(here + sign * 0.8)), round(by + ORBIT * math.sin(here + sign * 0.8)))
                return dist(p, xy(a))
            self.orbit_dir[key] = 1 if gap(1) >= gap(-1) else -1
        sign = self.orbit_dir[key]
        approaching = dist(me, xy(b)) > ORBIT + 2
        steps = (0.0, 0.4, -0.4, 0.8, -0.8, 1.2, -1.2, 1.6, -1.6) if approaching else (0.8, 1.1, 0.5)
        for step in steps:
            ang = here + (sign * step if not approaching else step)
            p = clamp_area((round(bx + ORBIT * math.cos(ang)), round(by + ORBIT * math.sin(ang))))
            if dist(p, me) < 2:
                continue
            # getting there never brings him nearer the follower; circling keeps a bit more room from it
            if approaching and dist(p, xy(a)) < dist(me, xy(a)):
                continue
            if not approaching and dist(p, xy(a)) < SPACE + 1:
                continue
            # the whole ride clear of every creature, and with more room from the follower, which closes in meanwhile
            if (all(dist(p, xy(t)) >= SPACE for t in threats + [a, b])
                    and path_clear(me, p, [xy(t) for t in threats + [b]], SPACE)
                    and path_clear(me, p, [xy(a)], FOLLOWER_ROOM)):
                if m.go(me, p, why, force=True):
                    return True
        return False

    def read_messages(self):
        """The server's word since the last look: the horse tiring."""
        new = call('GET', '/messages', after=self.seen_message)['messages']
        if new:
            self.seen_message = max(m['id'] for m in new)
        for m in new:
            low = m['text'].lower()
            if 'too fatigued' in low:
                self.tired = 'too'
            elif 'fatigued' in low and self.tired is None:
                self.tired = 'very'
            if 'fatigued' in low:
                say(f'the horse: {m["text"]!r}')

    def rest_horse(self, me, mobs, st):
        """The user's trick for a tired horse (MINING.md): get away from every creature first while the horse can
        still move, then dismount, say "all follow me", wait a second, mount again. Too tired to move: straight away."""
        threats = [m for m in mobs.values() if attackable(m) and not passive(m) and not self.busy(m['serial'], mobs)]
        dfree = min((dist(me, xy(m)) for m in threats), default=99)
        if self.tired == 'very' and dfree <= CLEAR and st['mounted']:
            run_from(me, [xy(m) for m in threats])
            time.sleep(0.3)
            return False
        if not self.horse:
            say('the horse is tired, and his rules name no horse to get back on: going home as he is')
            self.tired = None
            self.go_home('tired horse')
            return False
        if st['mounted']:
            call('POST', '/dismount')
        call('POST', '/say', text=SAY_FOLLOW)
        time.sleep(1)
        horse = mobs.get(self.horse) or next((m for m in call('GET', '/nearby', range=6)['mobiles']
                                              if m['serial'] == self.horse), None)
        if horse and dist(me, xy(horse)) > 1:
            try:
                call('POST', '/walk', x=horse['x'], y=horse['y'], distance=1)
            except uo.BridgeError as e:
                say(f'to the horse: {e}')
        try:
            call('POST', '/mount', serial=self.horse)
        except uo.BridgeError as e:
            say(f'mounting: {e}')
        mounted = call('GET', '/status')['mounted']
        say('horse rested: ' + ('back on' if mounted else 'NOT back on the horse'))
        if mounted:
            self.tired = None
            self.mount_tries = 0
            _last_walk['p'] = None
        else:
            self.mount_tries = getattr(self, 'mount_tries', 0) + 1
            if self.mount_tries >= 3:
                self.tired = None
                self.go_home('could not get back on the horse')
        return False

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
        if not self.mover.go(me, p if dist(p, HOME) > 1 else HOME, 'home'):
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
