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

  python3 -I fight.py [--minutes N] [--front] [--resume]

--front (and trips.py, coming home from town, the user 2026-11-08): only the creatures within FRONT_RANGE of the front
door are drawn and dealt with, none further out looked for, no meditating outside after the fight (he does that
inside); then in. With his pack full of maps, looting takes only what stacks onto what he carries.

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
import random
import re
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
TRAPPED = os.path.join(HERE, 'trapped.json')  # creatures never to draw again (kept in the repo)

AREA = (1745, 1414, 1830, 1485)   # "outside" in his rules (x1, y1, x2, y2); the door is at y 1414
# never north, west or north-west of the tower: that's toward the road, where there may be other players (the user,
# 2026-11-06); south-west is fine ("Southwest is fine though"): the second box, west of x 1745 only south of y 1430
AREAS = [AREA, (1715, 1430, 1745, 1485)]
HOME = door.OUTSIDE               # in front of the door (1756,1416)
FRONT_YARD = 10                   # the front yard: this close to the door, no fights (lead them away)
NEAR_HOME = 25                    # further out than this, every move pulls him back toward the tower
# where to look for creatures: a route picked at random each run (the user, 2026-11-06: "why is he always going right
# over to that same tower ... sometimes he can head south east or east ... go a little further straight east and
# then go down to south east"); --route picks one
ROUTES = {
    'east': [(1772, 1420), (1792, 1420), (1812, 1422), (1820, 1440), (1808, 1458), (1790, 1468)],
    'southeast': [(1768, 1430), (1782, 1442), (1796, 1454), (1808, 1466), (1818, 1478)],
    'southwest': [(1752, 1436), (1740, 1448), (1728, 1460), (1740, 1474), (1756, 1470)],
}
PATROL = ROUTES['east']
LOOK_AROUND = 3                   # seconds at each lookout point
# home from town (trips.py, the user, 2026-11-08): Recall lands him at 1757,1419; every enemy in front of the tower is
# dealt with before he goes in, and none further out is looked for: this far from the front door counts as in front
FRONT_RANGE = 15
PACK_LIMIT = 125                  # items his pack holds, everything inside bags counted (CARTO.md)

TAMBOURINE = 0x0E9D
GOLD = 0x0EED           # the only thing looted (the user, 2026-11-08)
POUCH = 0x0E79          # his trapped pouches (Magic Trap): opening one breaks paralysis
USED_POUCHES = set()    # pouches already opened (their trap is spent)
PROVOKE, MEDITATE = 22, 46
HEAL, CURE, FIREBALL, GREATER_HEAL, LIGHTNING, MAGIC_REFLECTION, ENERGY_BOLT = 4, 11, 18, 29, 30, 36, 42
MANA = {HEAL: 4, CURE: 6, FIREBALL: 9, GREATER_HEAL: 11, LIGHTNING: 11, MAGIC_REFLECTION: 14, ENERGY_BOLT: 20}
NAMES = {HEAL: 'Heal', CURE: 'Cure', FIREBALL: 'Fireball', GREATER_HEAL: 'Greater Heal', LIGHTNING: 'Lightning',
         MAGIC_REFLECTION: 'Magic Reflection', ENERGY_BOLT: 'Energy Bolt'}
REAGENT_BAG = '0x40677564'  # Razor's restock and scavenger hot bag in his pack
BLACK_PEARL, BLOOD_MOSS, GARLIC, GINSENG, MANDRAKE, NIGHTSHADE, SPIDERS_SILK, SULFUROUS_ASH = (
    0x0F7A, 0x0F7B, 0x0F84, 0x0F85, 0x0F86, 0x0F88, 0x0F8D, 0x0F8C)
REAGENTS = {HEAL: (GARLIC, GINSENG, SPIDERS_SILK), CURE: (GARLIC, GINSENG), FIREBALL: (BLACK_PEARL,), GREATER_HEAL: (GARLIC, GINSENG, MANDRAKE, SPIDERS_SILK),
            LIGHTNING: (MANDRAKE, SULFUROUS_ASH), ENERGY_BOLT: (BLACK_PEARL, NIGHTSHADE),
            MAGIC_REFLECTION: (GARLIC, MANDRAKE, SPIDERS_SILK)}
# a spell's outcome, read from the messages that follow it (bridge 8 casts and goes on; the user, 2026-11-06: "Cast ..
# then do all the other normal stuff and when a result from the spell shows up result=success/fail")
SPELL_FAILS = ('fizzles', 'concentration is disturbed', 'too far away', 'cannot be seen', 'line of sight',
               'insufficient mana', 'more reagents', 'already casting', 'must wait', 'not yet recovered',
               'will not adhere', 'target is not')
SPELL_SETTLE = 3.0      # seconds: a spell with no word against it by then went off
CIRCLE = {HEAL: 1, CURE: 2, FIREBALL: 3, GREATER_HEAL: 4, LIGHTNING: 4, MAGIC_REFLECTION: 5, 38: 5, ENERGY_BOLT: 6}


def land_time(spell):
    """Seconds from sending a spell to it landing, by its circle: seen 2.7-3.0 s for Energy Bolt, 2.3 for Lightning,
    1.9-2.2 for Fireball (2026-11-06 19:01-19:03). The next spell waits for it (18:49:49-55, one a second: every other
    one "You are already casting a spell."; 19:02:48, 2 s after a bolt: "You must wait for that spell to have an
    effect."), and a target's health falling well before it is someone else's doing (it was fighting an orc)."""
    return 1.25 + 0.25 * CIRCLE.get(spell, 6)
PARTNER = None          # --partner KIND: set creatures on this kind first when there's one (the user, 2026-11-06 18:33:
                        # "put him on the panther")
ROUND = 10              # leading a caster round to a partner when it's in the way: waypoints this far from the caster
BRIDGE = 7              # the bridge's version (from /status), set in main
ASYNC = False           # bridge 8 (cuo-agent24): /cast wait=0, the cursor aimed by the bridge when it comes
LAND_TIME = 1.0         # seconds after the aim for a spell to land: no moving (casting freezes him; a step then
                        # gets "You are frozen and cannot move.", which cut the bridge's wait for the cursor short)

SKILL_COOLDOWN = 10.5   # seconds: skills share one (fight 1: 9.8 s too soon, 10.8 s fine)
PROVOKE_RANGE = 8       # both creatures within this of him (fight 1: the llama at 8 worked)
PROVOKE_SPOT = 7        # how close he goes to the creature he'll set the follower on
ON_HIM = 3              # a free creature this close: run, nothing else
CLEAR = 10              # free creatures further than this: he may cast or meditate
FULL = 0.85             # health and mana at least this share count as full: then spells to speed up an even fight
MANA_RESERVE = 30       # attack spells never take him below this: mana for healing (the user, 2026-11-06: "don't use
                        # all your mana! save mana for healing and for attacking when it's opportune, but mostly
                        # provoke"); two Greater Heals and a Heal
CASTER_CLEAR = 15       # a caster after him with nothing to set it on: keep this far (the user, 2026-11-06: "for a
                        # spellcaster when there's no other enemy to provoke it to, you need to get like 15+ tiles
                        # away and pull him to someone else quickly")
CASTER_PULL_FOR = 60    # seconds of that with nobody turning up to set it on: then spells at it, as with any other
PULL_SPOT = 4           # pulling a caster to another creature: wait this far beyond it, on the far side from the caster
MEDITATE_FOR = 150      # after a fight, at most this long getting mana back before going home
BACK_OFF = 9            # after a provoke, and from anything coming: get at least this far away
FIGHT_GAP = 6           # keep this far from creatures fighting each other (spells need 6 clear: CAST_CLEAR)
HEAL_CLEAR = 10         # healing only with every creature this far off; hurt, he rides 10 away first (the user)
KEEP = 4                # one coming at him: get away once it's closer than this (the user: stay about 3 tiles away;
                        # at 3 an orc on his heels still hit him twice, 2026-11-06 18:49)
UNEVEN = 0.2            # a fight is uneven (bolt the one winning) when its health share leads by this much
CAST_WHEN = 0.40        # a creature fighting another: spells only once it's down to this share (or a caster, or
                        # the stronger of an uneven pair); until then they wear each other down and he meditates
LOOT_CLEAR = 6          # no looting with any creature this close to the corpse or to him
LOOT_RANGE = 24          # corpses from this fight this far off get looted (the bridge sees 24): a skeleton killed
                        # 19 tiles off by the door, 2026-11-08, was left with its gold ("you walked over the
                        # skeleton a bunch"); was 16 (20:08: the gargoyle and hart lay ~11 off)
                        # from where he meditated, and he went home without them)
SPELL_RANGE = 10        # a spell from further: "That is too far away." (Energy Bolt at 11 tiles, 2026-11-06 16:31)
CAST_SPOT = 8           # out of spell range (or "That is too far away."): ride to this far from it first
LONE_CLEAR = 8          # a creature not busy with another: no spell at it closer than this (8-10, the user)
CAST_CLEAR = 6          # no spell starts with any free creature closer than this (it would close in and hit him)
LONE_CAST = 4           # a lone one coming at him (nothing to set it on): cast at it from this far
PAIR_RANGE = 9          # the two to provoke onto each other: at most this far apart (the server's limit isn't known;
                        # each "too far away from each other" is logged with the distance, to tune)
ORBIT = 5               # bringing a follower near another creature: circle the other one this far off (the user)
NO_TURN_BACK = 5        # seconds: with nothing coming at him, no ride back the way he just came
SPACE = 3               # and keep at least this far from every creature while doing it (the user: "like 3 tiles")
FOLLOWER_ROOM = 5       # a ride while bringing the follower round keeps this far from it (it closes in meanwhile)
ORBIT_FOR = 40          # seconds circling one pair before giving up on it
KEEP_CASTER = 7         # the same for casters (gargoyles, gazers: dangerous; provoked first, killed first)
DRAW_CASTER = 11        # drawing a caster: they notice him from far off (the user); no nearer than this
LURE = 4                # drawing one: ride to about this far from it and wait for it to target him (the user)
UNSEEN_FOR = 60         # "Target cannot be seen.": left out this long (shut in a building, like the ogre)
LURE_WAIT = 30          # seconds there: one that hasn't turned on him by then is left be (trapped in a building, or
                        # one that doesn't attack)
ENGAGED_AFTER = 2       # seconds within a tile of another creature: locked in a fight with it
PROVOKED_BUSY = 6       # seconds after a provoke the pair counts as busy even before they meet
BADLY = 0.5             # below this, heal even without 10 clear, once nothing is right next to him
HURT = 0.75             # below this: ride 10 tiles from every creature at once, then Greater Heal (the user)
SCRATCHED = 0.85        # below this: Heal where he is (quick; only a step away first if something is within 3)
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
# animals that never bite: no need to keep away from them (he swerved round a llama all the way home, 2026-11-06);
# panthers, timber wolves and bears aren't on this list (a timber wolf bit him at his feet)
HARMLESS = {'llama', 'sheep', 'goat', 'mountain goat', 'cow', 'pig', 'chicken', 'rabbit', 'jack rabbit', 'hind', 'deer',
            'great hart', 'bird', 'eagle', 'cat', 'dog', 'horse', 'pack horse', 'pack llama', 'squirrel', 'ferret',
            'crane', 'raven', 'magpie', 'finch', 'tern', 'swallow', 'walrus', 'dolphin'}
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


DROP_HALT = re.compile(r'no answer after dropping (0x[0-9A-Fa-f]+)')
USE_HALT = re.compile(r'no answer when using (0x[0-9A-Fa-f]+)')


def call(method, endpoint, **params):
    """A bridge request. 423 (the user took over, or the bridge stopped) ends the run with Stop, except for the one
    stop that is safe to get past alone: a dropped item that did land (recover_drop)."""
    try:
        return uo.call(info, method, endpoint, **params)
    except uo.BridgeError as e:
        if e.code != 423:
            raise
        if razor_click():
            return uo.call(info, method, endpoint, **params)
        if not recover_drop():
            raise Stop(e.message)
    if endpoint == '/move':
        return {'moved': True, 'recovered': True}  # the drop that stopped the bridge landed
    if endpoint == '/use':
        return {'used': True, 'recovered': True}   # the pouch went off; not again
    try:
        return uo.call(info, method, endpoint, **params)
    except uo.BridgeError as e:
        if e.code == 423:
            raise Stop(e.message)
        raise


def razor_click(bag=None):
    """The bridge's "the user took over" was really one of Razor's own double-clicks: on a corpse (Razor's
    AutoOpenCorpses; it reads the server's packets before the client, so its click goes out before the client knows
    the corpse, and the bridge's own "a corpse isn't the user" check misses it: 2026-11-08 19:13:17, a skeleton's
    corpse by the door as he landed) or on `bag`, just put into his pack (Razor's AutoSearch, within a second of the
    drop). Only if nothing that counts as a command was sent after it. Then resumes and returns True."""
    try:
        st = uo.call(info, 'GET', '/status')
    except uo.BridgeError:
        return False
    took = st.get('takenOver') or ''
    if not took.startswith('a double-click at ') or st.get('halted'):
        return False
    when = took[len('a double-click at '):]
    try:
        events = uo.call(info, 'GET', '/events', after=0)['events']
    except uo.BridgeError:
        return False
    clicks = [e for e in events if e.get('kind') == 'sent double-click' and e['time'].startswith(when)]
    if not clicks:
        return False
    click = clicks[0]
    later = [e for e in events if e['id'] > click['id'] and e.get('kind', '').startswith('sent ')
             and e['kind'] not in ('sent single-click', 'sent pick up', 'sent drop')]
    if later:
        return False

    def secs(t):
        h, m, rest = t.split(':')
        return int(h) * 3600 + int(m) * 60 + float(rest)
    why = None
    if (click.get('name') or '').lower().startswith('corpse') or 'corpse' in (click.get('name') or '').lower():
        why = f'Razor opening a corpse ({click["serial"]})'
    else:
        try:
            item = uo.call(info, 'GET', '/item', serial=click['serial'])['item']
            if int(item['graphic'], 16) == 0x2006:
                why = f'Razor opening a corpse ({click["serial"]})'
        except uo.BridgeError:
            pass
    if not why and bag and click.get('serial') == bag:
        drops = [e for e in events if e.get('kind') == 'sent drop' and e.get('serial') == bag and e['id'] < click['id']]
        if drops and 0 <= secs(click['time']) - secs(drops[-1]['time']) <= 1.0:
            why = f"Razor's auto-search of {bag} as it landed in his pack"
    if not why:
        return False
    try:
        uo.call(info, 'POST', '/resume')
    except uo.BridgeError:
        return False
    say(f'the bridge took {why} for the user taking over ({took}): resumed')
    return True


def recover_drop():
    """The bridge stops itself when a dropped item never comes back, and then refuses everything: out in the wild that
    left him standing with nothing running him (2026-11-06 17:10:46: looted gold dropped into his pack merged into his
    gold there, the coins' serial vanished, the bridge took it for the server going quiet; a gargoyle walked up and hit
    him from 100 to 69 before the user took over). Resumed here only when nobody took over, the stop is that drop's,
    and the item landed: gone (merged into a stack) or in his pack. Anything else stays stopped."""
    try:
        st = uo.call(info, 'GET', '/status')
    except uo.BridgeError:
        return False
    if st.get('takenOver'):
        return False
    used = USE_HALT.search(st.get('halted') or '')
    if used and used.group(1).upper() in {p.upper() for p in USED_POUCHES}:
        # a trapped pouch goes off without a word, and bridge 8 stopped waiting for one
        try:
            uo.call(info, 'POST', '/resume')
        except uo.BridgeError:
            return False
        say(f'the bridge stopped after the trapped pouch ({st["halted"]}); resumed')
        return True
    found = DROP_HALT.search(st.get('halted') or '')
    if not found:
        return False
    serial = found.group(1)
    try:
        where = uo.call(info, 'GET', '/item', serial=serial).get('insideOf') or []
        landed = any(c.get('serial') == st['backpack']['serial'] for c in where)
    except uo.BridgeError as e:
        landed = e.code == 404  # gone: merged into a stack
    if not landed:
        return False
    try:
        uo.call(info, 'POST', '/resume')
    except uo.BridgeError:
        return False
    say(f'the bridge stopped after a drop that landed ({st["halted"]}); resumed')
    return True


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
    return any(a[0] <= p[0] <= a[2] and a[1] + 1 <= p[1] <= a[3] for a in AREAS)


def pack_count(pack):
    """Items in his pack, everything inside bags counted (not a spellbook's spell icons)."""
    def count(items):
        return sum(1 + count(i.get('items', [])) for i in items if int(i['serial'], 16) < 0x7F000000)
    return count(call('GET', '/contents', serial=pack, depth=4)['items'])


def look():
    """His status and the creatures within 18 tiles, by serial."""
    st = call('GET', '/status')
    near = call('GET', '/nearby', range=18)
    return st, {m['serial']: m for m in near['mobiles']}


_last_walk = {'p': None, 't': 0.0}


def clamp_area(p):
    """The nearest spot inside his areas."""
    if in_area(p):
        return p
    spots = [(min(max(p[0], a[0]), a[2]), min(max(p[1], a[1] + 1), a[3])) for a in AREAS]
    return min(spots, key=lambda q: dist(q, p))


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


def path_in_area(me, p):
    """Every tile of the straight ride from me to p inside his areas (a getaway cut across 1742,1424, west of the
    tower, 19:50: never north, west or north-west of it)."""
    n = max(dist(me, p), 1)
    return all(in_area((round(me[0] + (p[0] - me[0]) * i / n), round(me[1] + (p[1] - me[1]) * i / n)))
               for i in range(1, n + 1))


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
        self.last_pos, self.moved_at = None, 0.0  # where he was last seen and when he last moved
        self.last_dir, self.last_at = None, 0.0   # the direction of the last ride, and when it was sent
        self.danger = False   # something is coming at him (set every tick): then he may turn whichever way he needs

    def going(self, me):
        """On his way to the goal. Not when he has stood still over 1.5 s since the ride was sent: a spell freezes him
        ("You are frozen and cannot move.") and the ride stops for good (19:50:14-22: 8 s standing still under a
        gargoyle's blows while this said he was riding away)."""
        now = time.time()
        if me != self.last_pos:
            self.last_pos, self.moved_at = me, now
        if self.goal is None or dist(me, self.goal) <= 1 or now - self.at >= 8:
            return False
        return not (now - max(self.moved_at, self.at) > 1.5)

    def go(self, me, p, why, force=False, urgent=False):
        """Ride to p. With nothing coming at him, never back the way he just came within NO_TURN_BACK seconds of the
        last ride: there's no reason to (the user, 2026-11-06: "sometimes you have to go back if a mob is actually
        coming at you. You DONT need to go back when no mobs are even coming at you"), and going back and forth tires
        the horse. With something coming at him (danger) or `urgent`, any way he needs. A refused ride counts as
        standing still. Every ride is logged with its reason."""
        if not force and self.why == why and self.going(me):
            return True
        d = (p[0] - me[0], p[1] - me[1])
        if (not urgent and not self.danger and self.last_dir and time.time() - self.last_at < NO_TURN_BACK
                and d[0] * self.last_dir[0] + d[1] * self.last_dir[1] < 0):
            return True  # would be turning back: stay put
        if walk(p, keep=0):
            self.goal, self.why, self.at = p, why, time.time()
            self.last_dir, self.last_at = d, time.time()
            say(f'ride {me[0]},{me[1]} -> {p[0]},{p[1]} ({why}{", urgent" if urgent else ""})')
            return True
        return False

    def clear(self):
        self.goal, self.why = None, None


def load_trapped(walled_only=False):
    """Creatures never to draw again: shut inside a building (the ogre in the castle south-west of the tower, which
    he drew run after run: the user, 2026-11-06, "again with the Ogre that's behind the wall????"), or ones that
    never come."""
    try:
        with open(TRAPPED, encoding='utf-8') as fh:
            known = json.load(fh)
    except (OSError, ValueError):
        return set()
    return {s for s, v in known.items() if not walled_only or 'wall' in (v.get('why') or '')}


def remember_trapped(m):
    try:
        with open(TRAPPED, encoding='utf-8') as fh:
            known = json.load(fh)
    except (OSError, ValueError):
        known = {}
    known[m['serial']] = {'name': m.get('name'), 'at': [m['x'], m['y']], 'since': time.strftime('%Y-%m-%d %H:%M')}
    with open(TRAPPED, 'w', encoding='utf-8') as fh:
        json.dump(known, fh, indent=1)


def homeward(p):
    """Where a spot sits for a fight: not in the front yard (the user, 2026-11-06: keep the front yard clear, lead
    creatures away from the door and kill them there), and not far from the tower either (out past NEAR_HOME every
    tile counts against it)."""
    d = dist(p, HOME)
    return -3.0 * max(FRONT_YARD - d, 0) - (1.5 * (d - NEAR_HOME) if d > NEAR_HOME else 0)


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
    def __init__(self, minutes, route=None, front=False):
        self.front = front       # home from town: only the creatures in front of the tower, then in (trips.py)
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
        self.route = route or random.choice(sorted(ROUTES))
        self.patrol = list(ROUTES[self.route])
        self.goal = None
        self.goal_sent = 0.0
        self.arrived_at = None
        self.pending = None      # the last cast, for its damage once it has landed
        self.spell = None        # the spell on its way: what, at whom, since when, the last message before it
        self.nearest_any = 99    # the nearest creature that could hurt him, this look
        self.frozen_at = 0.0     # the last "You are frozen and cannot move." (a step refused)
        self.pouch_at = 0.0      # when a trapped pouch was last used
        self.hits_before = None  # his health on the last look
        self.last_cast = 0.0
        self.last_gap = 0.0
        self.reflect_up = False  # Magic Reflection on him (the next spell at him bounces); down when a creature casts
        self.caster_since = {}   # caster serial -> since when it has been after him
        self.fought_with = set() # creatures he set fighting or cast at: threats from then on, however harmless their
                                 # kind (the great hart left at 1/25 next to the orc's corpse: "any normal mob would
                                 # have" attacked him, the user, 2026-11-07); finished before looting
        self.mover = Mover()
        self.killing = None      # the one he's killing with spells (no partner to set it on): all the way
        self.looted = set()      # corpses already looted
        self.looting = None      # the corpse being looted: serial, name, what's been taken, since when
        self.removed_at = {}     # serial -> when "remove thyself" was last used on it
        try:  # corpses lying about before the fight aren't his to loot
            self.corpses_before = {i['serial'] for i in call('GET', '/nearby', range=18)['items']
                                   if int(i['graphic'], 16) == 0x2006}
        except uo.BridgeError:
            self.corpses_before = set()
        self.together_since = {}  # frozenset of two serials -> since when they've been within a tile of each other
        self.engaged_with = {}   # serial -> the creature it's locked in a fight with (one he didn't start)
        self.hits_seen = {}      # serial -> [(time, hits)]
        self.cast_at_time = {}   # serial -> when he last cast at it
        self.too_far = {}        # serial -> when a spell at it got "That is too far away." 
        self.reagents_at = 0.0
        self.reagent_counts = collections.Counter()
        self.orbit_dir = {}      # (follower, partner): which way round he circles the partner (kept: never back)
        self.orbit_since = {}    # (follower, partner): when he started circling
        self.gave_up = set()     # (follower, partner): circled ORBIT_FOR without getting them close
        self.ignored = set(load_trapped())  # never drawn again: they never came (remembered in trapped.json)
        # never a partner either: shut behind a wall (a provoke onto one: "Target cannot be seen."); ones that just
        # don't attack (a bear, a panther) still make good partners
        self.walled = set(load_trapped(walled_only=True))
        self.luring = None
        self.lure_since = 0.0
        st0 = call('GET', '/status')
        self.seen_message = st0['lastMessageId']
        self.me_serial = st0.get('serial')
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
        return self.engaged_with.get(serial)

    def approaching(self, serial):
        """Getting nearer him: 2 tiles or more nearer over the last 3 seconds."""
        h = [d for t, d in self.history.get(serial, []) if time.time() - t <= 3]
        return len(h) >= 2 and h[-1] <= h[0] - 2

    def busy(self, serial, mobs):
        """Fighting something else: provoked onto (or by) a creature that's still alive (just provoked, or next to
        it), or a fight he didn't start: locked together with another creature (within a tile of it for ENGAGED_AFTER
        seconds), or losing health he didn't take (the user, 2026-11-06: he stood waiting for a dire wolf to come at
        him while it was fighting a bear, the wolf he had provoked onto it the run before; a busy one is the chance to
        bolt it)."""
        # locked with one that's still alive and next to it (an entry left from a dead partner kept the gargoyle "busy"
        # with a dead goat, so he cast with it 1-5 tiles off, 19:50)
        e = mobs.get(self.engaged_with.get(serial) or '')
        if e and attackable(e) and serial in mobs and dist(xy(mobs[serial]), xy(e)) <= 3:
            return True
        if self.losing_health(serial):
            return True
        other = self.partner_of(serial)
        m, o = mobs.get(serial), mobs.get(other or '')
        if not (m and o and attackable(o)):
            return False
        recent = time.time() - max(self.provoked_at.get(serial, 0), self.provoked_at.get(other, 0)) < PROVOKED_BUSY
        return recent or dist(xy(m), xy(o)) <= 3

    def losing_health(self, serial):
        """Its health fell in the last few seconds while he wasn't casting at it."""
        h = self.hits_seen.get(serial, [])
        now = time.time()
        recent = [v for t, v in h if now - t <= 5]
        mine = self.pending and self.pending.get('serial') == serial or now - self.cast_at_time.get(serial, 0) < 4
        return len(recent) >= 2 and recent[-1] < max(recent) and not mine

    def watch_fights(self, mobs):
        """Which creatures are locked together (within a tile of each other) and since when; a pair together
        ENGAGED_AFTER seconds counts as fighting."""
        now = time.time()
        att = [m for m in mobs.values() if attackable(m)]
        seen = set()
        for i, a in enumerate(att):
            for b in att[i + 1:]:
                if dist(xy(a), xy(b)) <= 1:
                    key = frozenset((a['serial'], b['serial']))
                    seen.add(key)
                    self.together_since.setdefault(key, now)
        self.together_since = {k: t for k, t in self.together_since.items() if k in seen}
        self.engaged_with = {}
        for key, t in self.together_since.items():
            if now - t >= ENGAGED_AFTER:
                a, b = tuple(key)
                self.engaged_with[a], self.engaged_with[b] = b, a
        for s, m in mobs.items():
            if m.get('hitsMax'):
                h = self.hits_seen.setdefault(s, [])
                h.append((now, m['hits']))
                del h[:-10]

    def coming(self, m):
        """After him: it has turned Criminal. The user, 2026-11-06: "I can see the creature turn completely grey when
        they target me, that means they're going to come at me. And they stay grey" (Clem's criminal_hue is a grey;
        attackable creatures are notoriety Gray, another colour). The gargoyle that day: Gray, then Criminal at 14
        tiles, then straight at him; war mode never came on."""
        return m.get('notoriety') == 'Criminal'

    def visible(self, serial):
        return self.unseen.get(serial, 0) < time.time()

    def cast_ready(self, me):
        """Bridge 8 casts on the move (the user, 2026-11-06: "You cast and keep moving at the same time"); bridge 7
        only standing still (casting during a step lost the cursor)."""
        return ASYNC or self.still(me)

    def still(self, me):
        """Standing still: the same tile on the last two looks and no ride under way. Casting while a step is under
        way gets "You are frozen and cannot move." and the spell goes astray."""
        h = self.positions[-2:]
        return len(h) == 2 and all(p == me for p in h) and not self.mover.going(me)

    def remember(self, me, mobs):
        self.watch_fights(mobs)
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
        # not with a spell on its way: its cursor and the skill's would get mixed up (bridge 8 refuses then)
        return time.time() - self.last_skill >= SKILL_COOLDOWN and not self.spell

    # ---- provoking ----

    def partner_for(self, me, a, mobs, reach, pair=None):
        """Something to set a on, within reach of him: like it first (the same tier), free before busy, then
        nearest to a; an animal will do."""
        cands = [m for m in mobs.values() if attackable(m) and m['serial'] != a['serial']
                 and self.visible(m['serial']) and m['serial'] not in self.walled and dist(me, xy(m)) <= reach
                 and (pair is None or dist(xy(a), xy(m)) <= pair)]
        if not cands:
            return None
        return min(cands, key=lambda m: (PARTNER is not None and PARTNER not in kind(m), abs(tier(m) - tier(a)),
                                         self.busy(m['serial'], mobs), dist(xy(a), xy(m))))

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
            self.fought_with.update((a['serial'], b['serial']))
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
            if mana - MANA[spell] >= MANA_RESERVE and self.can_cast(spell, mana):
                return spell
        return None

    def cast_target(self, me, busy, mobs, st=None):
        """A spell at a pair fighting each other, or None to let them fight on. **Keep the fight equal** (the user,
        2026-11-07: "When 2 mobs are focused on each other you don't have to worry about their magic at that moment,
        you need to worry about keeping them 'about equal' in HP ... You want them to die at almost the same time so
        that when one of them dies it's a 1-shot for you to kill the other one, that is a higher priority than 'always
        kill magic user first' .. that is true when the magic user is targeting YOU but not true when it's targeting
        another monster"; 19:01: every spell went at the gargoyle, it died, the dire wolf was freed at 18/25 with his
        mana at the reserve). So, at a pair within reach:
        - both nearly dead (15% or less): finish them, the one after him first;
        - one clearly ahead (UNEVEN): a spell at it, the one winning, never the one losing;
        - about even: let them wear each other down (mana sparingly; the user, 2026-11-06), unless his health and
          mana are full: then at the healthier, so both come down together faster (the user, 2026-11-07);
        - one whose partner is gone (dead, out of sight) is left to the other branches (it's free now)."""
        # a little past spell range too: the caller rides closer to cast (the one ahead was 11 off and nothing was cast)
        reach = [m for m in busy if dist(me, xy(m)) <= SPELL_RANGE + 4 and self.visible(m['serial'])]
        pairs = []
        for m in reach:
            o = mobs.get(self.partner_of(m['serial']) or '')
            if o and attackable(o) and (o, m) not in pairs:
                pairs.append((m, o))
        full = (st is not None and st['mana'] >= FULL * st.get('manaMax', 100)
                and st['hits'] >= FULL * st.get('hitsMax', 100))
        choices = []
        for m, o in pairs:
            sm, so = share(m) or 0, share(o) or 0
            ahead, behind = (m, o) if sm >= so else (o, m)
            gap = abs(sm - so)
            if gap < 0.05 and tier(behind) > tier(ahead):
                # a tie goes to the stronger: the same share of a goat's health is far less than a gargoyle's (19:49:00:
                # the bolt went at the goat, it died at once and the gargoyle was free)
                ahead, behind = behind, ahead
            if sm <= LOW and so <= LOW:
                pick = min((m, o), key=lambda x: (not self.coming(x), share(x) or 0))
                choices.append((0, pick))
            elif gap >= UNEVEN or full:
                choices.append((1, ahead))
        for _, m in sorted(choices, key=lambda c: c[0]):
            if dist(me, xy(m)) <= SPELL_RANGE + 4 and self.visible(m['serial']):
                return m
        return None

    def cast(self, spell, target, name, kind):
        """Send a spell. Bridge 8: it answers at once, aims the cursor itself when it comes, and the outcome turns up
        in the messages (settle_spell), so he goes on moving and looking meanwhile. Bridge 7: it answers once the
        cursor is aimed (a late cursor is aimed here). Either way self.spell holds it until it's settled. The answer,
        or None when the bridge refused."""
        if self.spell or time.time() - self.last_cast < self.last_gap:
            time.sleep(0.1)  # one spell at a time ("You are already casting a spell."): this one settles first
            return None
        if kind == 'attack' and self.nearest_any < CAST_CLEAR:
            # never with any creature within 6, busy or not (the user, 2026-11-06); the spell freezes him where he is
            time.sleep(0.1)
            return None
        self.meditating = False
        before = self.seen_message
        try:
            if ASYNC:
                a = call('POST', '/cast', spell=spell, target=target, wait=0,
                         cursor=0 if spell == MAGIC_REFLECTION else None)
                before = a.get('messageId', before)
            else:
                a = call('POST', '/cast', spell=spell, target=target)  # comes back once it's aimed (about 2 s)
                if not a.get('aimed') and spell != MAGIC_REFLECTION:
                    # the bridge came back on a message before the cursor ("You are frozen and cannot move." when a
                    # step was still under way, 2026-11-06): the cursor still comes; aim it, or the next cast gets
                    # "You must wait for that spell to have an effect."
                    end = time.time() + 2.5
                    while time.time() < end:
                        if call('GET', '/status').get('targeting'):
                            try:
                                aim(target)
                                a['aimed'] = 'late'
                            except uo.BridgeError as e:
                                say(f'{NAMES[spell]}: the late cursor: {e}')
                                cancel_cursor()
                            break
                        time.sleep(0.1)
        except uo.BridgeError as e:  # it died or went out of sight meanwhile, or the bridge said not now
            say(f'{NAMES[spell]} at {name}: {e}')
            return None
        finally:
            if not ASYNC:
                self.cast_until = time.time() + LAND_TIME
        self.spell = {'spell': spell, 'target': target, 'name': name, 'kind': kind, 'at': time.time(),
                      'before': before}
        self.last_cast = time.time()
        self.last_gap = land_time(spell) + 0.2
        return a

    def cast_at(self, m, spell):
        self.cast_at_time[m['serial']] = time.time()
        self.fought_with.add(m['serial'])
        a = self.cast(spell, m['serial'], m['name'], 'attack')
        if a is None:
            return
        if self.spell:
            self.spell['hits'] = m.get('hits')
        self.pending = {'spell': NAMES[spell], 'serial': m['serial'], 'name': m['name'], 'before': m.get('hits'),
                        'max': m.get('hitsMax'), 'at': time.time(), 'aimed': a.get('aimed'), 'text': texts(a),
                        'mana': a.get('mana')}
        say(f'{NAMES[spell]} at {m["name"]} ({health(m)}), mana {a.get("mana")}' + (f': {texts(a)}' if texts(a) else ''))

    def note_damage(self, mobs):
        p = self.pending
        if p and time.time() - p['at'] >= 1.5:
            after = mobs.get(p['serial'])
            p['after'] = after.get('hits') if after and attackable(after) else 0
            row(event='cast', **{k: v for k, v in p.items() if k != 'at'})
            self.pending = None

    def heal_self(self, st, spell):
        a = self.cast(spell, st['serial'], 'himself', 'heal')
        if a is not None:
            say(f'{NAMES[spell]} on himself ({st["hits"]}/{st["hitsMax"]})' + (f': {texts(a)}' if texts(a) else ''))

    def settle_spell(self, mobs, new):
        """The spell on its way, settled from what followed it (the user: "when a result from the spell shows up
        result=success/fail"): a word against it (fizzled, too far, can't be seen, concentration disturbed ...) is a
        fail; "already in effect" (Magic Reflection), a heal's "points of damage have been healed", or the target's
        health falling is a success; nothing against it within SPELL_SETTLE, a success too."""
        p = self.spell
        if not p:
            return
        result = why = None
        for m in new:
            if m['id'] <= p['before']:
                continue
            low = m['text'].lower()
            if 'already in effect' in low or 'have been healed' in low:
                result, why = 'success', m['text']
                break
            fail = next((f for f in SPELL_FAILS if f in low), None)
            if fail:
                result, why = 'fail', m['text']
                break
        if result is None and p['kind'] == 'attack':
            t = mobs.get(p['target'])
            if t is None or not attackable(t):
                result, why = 'success', 'it is dead or gone'
            elif (p.get('hits') is not None and t.get('hits') is not None and t['hits'] < p['hits']
                  and time.time() - p['at'] >= land_time(p['spell']) - 0.6):
                result, why = 'success', f'{p["hits"]} -> {t["hits"]}/{t.get("hitsMax")}'
        if result is None and time.time() - p['at'] >= SPELL_SETTLE:
            result, why = 'success', 'nothing against it'
        if result is None:
            return
        low = why.lower()
        if 'cannot be seen' in low or 'line of sight' in low:
            self.unseen[p['target']] = time.time() + UNSEEN_FOR
        if 'too far away' in low:
            # the user: "get closer to cast if it says 'that is too far away'": ride to CAST_SPOT from it first
            self.too_far[p['target']] = time.time()
        if p['spell'] == MAGIC_REFLECTION and result == 'success':
            self.reflect_up = True
        say(f'{NAMES[p["spell"]]} at {p["name"]}: result={result} ({why}, {time.time() - p["at"]:.1f} s)')
        self.spell = None

    def keep_reflect(self, st, mobs, dany):
        """Magic Reflection whenever a caster is about and it isn't up (the user, 2026-11-06: "use reflect before you
        go out the door, reflect will help with the first spell it casts at you, reapply reflect as much as you have
        time to"). Never fizzles (the user). Bridge 7 holds every request for up to 6 s on it (no cursor ever comes),
        so there only with nothing within CASTER_CLEAR. Like any spell, never with a creature within FIGHT_GAP (the
        user: closer than 6 is not the time for any spell). True when cast."""
        if self.reflect_up or self.spell or dany < FIGHT_GAP:
            return False
        if not any(attackable(m) and kind(m) in CASTERS for m in mobs.values()):
            return False
        if st['mana'] < MANA[MAGIC_REFLECTION] + MANA[GREATER_HEAL] or not self.can_cast(MAGIC_REFLECTION, st['mana']):
            return False
        if not ASYNC and dany < CASTER_CLEAR:
            return False
        a = self.cast(MAGIC_REFLECTION, st['serial'], 'himself', 'reflect')
        if a is not None:
            say(f'Magic Reflection (mana {st["mana"]})' + (f': {texts(a)}' if texts(a) else ''))
        return a is not None

    # ---- the loop ----

    def run(self):
        """Until he's inside (returns) or the user takes over (Stop)."""
        say('fight: home from town, dealing with everything in front of the tower' if self.front
            else f'fight: watching for creatures (route: {self.route})')
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
        new = self.read_messages()
        self.settle_spell(mobs, new)
        # bridge 7: frozen while the spell goes off (it came back once aimed); bridge 8 goes on moving and looking
        casting = time.time() < self.cast_until
        if self.tired and not casting:
            return self.rest_horse(me, mobs, st)

        # paralysed: a trapped pouch at once, first thing (the user, 2026-11-07: "You forgot about using the trapped
        # pouch to get unfrozen, that's a high priority. As soon as you see it say you're frozen you should have an
        # event kicked off to open the trapped pouch"; 19:50:16-22 a gargoyle's Paralyze held him 6 s under its blows
        # until the user did it). The server says nothing when it paralyses him and the paralysed flag doesn't come
        # on here; a step refused with "You are frozen and cannot move." does, and his own spell's freeze is told
        # apart by its timing
        own_cast = time.time() - self.last_cast < self.last_gap + 0.5
        if (st.get('paralyzed') or (time.time() - self.frozen_at < 2.0 and not own_cast)) and \
                time.time() - self.pouch_at > 2.5:
            spent = {k for k, v in door.pouch_state().items() if v.get('state') == 'spent'}
            found = [p for p in carried(POUCH) if p not in USED_POUCHES and p not in spent]
            if found:
                self.pouch_at = time.time()
                USED_POUCHES.add(found[0])
                door.mark_pouch(found[0], 'spent')  # re-trapped when he's parked (door.retrap)
                try:
                    a = call('POST', '/use', serial=found[0], wait=0 if BRIDGE >= 9 else None)
                    say(f'PARALYSED: trapped pouch {found[0]}' + (f': {texts(a)}' if texts(a) else ''))
                except uo.BridgeError as e:
                    say(f'PARALYSED: pouch {found[0]}: {e}')
                self.frozen_at = 0.0
                self.mover.clear()  # the ride died: send it again
                return False
            say('paralysed, and no trapped pouch left')

        threats = [m for m in mobs.values() if attackable(m)
                   and (not passive(m) or self.coming(m) or m['serial'] in self.fought_with)]
        busy = [m for m in threats if self.busy(m['serial'], mobs)]
        busy_ids = {m['serial'] for m in busy}
        free = [m for m in threats if m['serial'] not in busy_ids]
        coming = [m for m in free if self.coming(m)]
        dfree = min((dist(me, xy(m)) for m in free), default=99)
        self.mover.danger = bool(coming) or dfree <= ON_HIM
        dbusy = min((dist(me, xy(m)) for m in busy), default=99)
        # free creatures that matter for casting: not ones left be (shut in a building, never came)
        # every free creature counts for safety, left be or not (a dire wolf "left be" for not coming followed him to
        # the door and bit him to 33 while he cast Greater Heal next to it, 2026-11-06 16:51)
        dloose = dfree
        if coming or busy:
            self.quiet_since = None
        if casting:
            time.sleep(0.15)  # frozen while the spell goes off: just watch
            return False

        # something right on him, any creature at all (a timber wolf "left alone" bit him at his feet, 2026-11-06):
        # get away first (the user: "#1 priority is always maintain distance")
        biters = [m for m in mobs.values() if attackable(m)
                  and (kind(m) not in HARMLESS or m['serial'] in self.fought_with)]
        dany_creature = min((dist(me, xy(m)) for m in biters), default=99)
        self.nearest_any = dany_creature
        # hurt with nothing next to him: a spell got through, so his Magic Reflection is down (the gargoyle's words
        # weren't always heard from 14 tiles, and he went on thinking it was up, 19:49:51)
        if self.hits_before is not None and st['hits'] < self.hits_before and dany_creature > 1 and self.reflect_up:
            self.reflect_up = False
            say(f'hurt from a distance ({self.hits_before} -> {st["hits"]}): Magic Reflection is down')
        self.hits_before = st['hits']
        if dfree <= ON_HIM or dany_creature <= ON_HIM - 1:
            threats = threats + [m for m in biters if dist(me, xy(m)) <= ON_HIM and m not in threats]
            self.meditating = False
            self.flee(me, [xy(m) for m in threats], radii=(10, 8))
            return False

        # hurt: ride 10 tiles away from every creature, fighting or not, then heal (the user, 2026-11-06: "If you need
        # to heal run 10 tiles away and heal")
        dany = min(dfree, dbusy)
        # the user, 2026-11-06: "If you get below 85% health you should use heal on yourself where you are, if you get
        # below 75% HP it is important that you immediately run away 10 tiles and heal yourself with greater heal"
        if hp < HURT:
            # badly hurt and the creature keeps up, so 10 clear never comes: heal as soon as nothing is right next to
            # him (19:50:16-22: 40 -> 29 with a gargoyle on him, no heal)
            badly = hp < BADLY and dany_creature >= 2 and self.can_cast(GREATER_HEAL, st['mana'])
            if dany < HEAL_CLEAR and not badly:
                self.meditating = False
                self.flee(me, [xy(m) for m in threats], radii=(12, 10, 8), need=HEAL_CLEAR)
                return False
            if self.can_cast(GREATER_HEAL, st['mana']):
                self.heal_self(st, GREATER_HEAL)
                return False
        elif hp < SCRATCHED and self.can_cast(HEAL, st['mana']) and self.cast_ready(me):
            self.heal_self(st, HEAL)
            return False
        if st.get('poisoned') and dany >= HEAL_CLEAR and self.can_cast(CURE, st['mana']):
            self.heal_self(st, CURE)
            return False

        # one nearly dead (15% or less) in spell range: finish it now, before anything else (the user, 2026-11-07: "You
        # didn't kill the dire wolf? You just left him alive and started running from the gargoyle?": it ran off at
        # 0/25, one Fireball, and the gargoyle came on meanwhile)
        dying = [m for m in threats if share(m) is not None and share(m) <= LOW and self.visible(m['serial'])
                 and CAST_CLEAR <= dist(me, xy(m)) <= SPELL_RANGE]
        if dying and not self.spell and self.nearest_any >= CAST_CLEAR:
            m = min(dying, key=lambda m: share(m))
            spell = self.spell_for(m, st['mana'])
            if spell:
                say(f'finishing {m["name"]} ({health(m)})')
                self.cast_at(m, spell)
                return False

        # Magic Reflection up while a caster is about, unless a provoke can go off right now (that first: it gets the
        # caster "off of him", the user)
        provoke_now = False
        if coming:
            a0 = sorted(coming, key=lambda m: (kind(m) not in CASTERS, dist(me, xy(m))))[0]
            provoke_now = (dist(me, xy(a0)) <= PROVOKE_RANGE and self.skill_ready()
                           and self.partner_for(me, a0, mobs, PROVOKE_RANGE, pair=PAIR_RANGE) is not None)
        if not provoke_now and self.keep_reflect(st, mobs, min(dfree, dbusy)):
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
                    # never a spell with anything close: it closes in during the words, hits him and ruins it (the
                    # user, 2026-11-06); a full getaway first, then the spell
                    # one that isn't busy with another keeps coming during the words: 8-10 tiles first (the user,
                    # 2026-11-06: the ettin got a bit close while he was casting)
                    if dfree < LONE_CLEAR:
                        # a getaway to 10 clear: one that kept within spell range had it catch him up every time
                        # in fight_sim (it follows while he rides) and he never got to cast
                        self.flee(me, [xy(m) for m in threats], radii=(12, 10), need=LONE_CLEAR + 2)
                        return False
                    if dist(me, xy(k)) > SPELL_RANGE or time.time() - self.too_far.get(k['serial'], 0) < 5:
                        if self.closer(me, k, threats):
                            return False
                    if not ASYNC and (self.mover.going(me) or not self.still(me)):
                        time.sleep(0.1)  # the hop first: no casting on the move
                        return False
                    self.cast_at(k, spell)
                    return False
                say(f'no mana to spare (keeping {MANA_RESERVE} for healing) or no reagents for {k["name"]}')
            self.killing = None
            a = sorted(coming, key=lambda m: (kind(m) not in CASTERS, dist(me, xy(m))))[0]
            # both within PROVOKE_RANGE of him and within PAIR_RANGE of each other ("The creatures you are trying to
            # provoke are too far away from each other for your music to have an effect.": an orc 15 from a panther)
            b = self.partner_for(me, a, mobs, PROVOKE_RANGE, pair=PAIR_RANGE)
            if self.skill_ready() and dist(me, xy(a)) <= PROVOKE_RANGE and b:
                self.mover.clear()
                if self.provoke(a, b):
                    # back off only as far as he needs to cast at them: out of FIGHT_GAP, still within spell range (a
                    # long getaway meant riding back in to cast)
                    if min(dist(me, xy(a)), dist(me, xy(b))) < FIGHT_GAP:
                        self.flee(me, [xy(a), xy(b)], fresh=True, radii=(4, 3))
                return False
            keep = KEEP_CASTER if kind(a) in CASTERS else KEEP
            if self.mover.why == 'flee' and self.mover.going(me):
                # a getaway is ridden to the end (switching between getting away and leading was the wiggle)
                self.flee(me, [xy(m) for m in threats])
                return False
            if kind(a) in CASTERS and self.caster_moves(me, a, mobs, threats):
                return False
            # bringing it round to a partner only once it's close and following him; one that turned on him from
            # far off is met standing still (the user, 2026-11-06: circling when nothing is attacking him only tires
            # the horse)
            if not b and keep <= dist(me, xy(a)) <= PROVOKE_RANGE:
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
            if spell and not usable:
                if dist(me, xy(a)) > SPELL_RANGE:
                    time.sleep(0.15)  # still out of spell range: stand and let it come (a bolt from 24 tiles: too far)
                    return False
                if dfree >= LONE_CLEAR and self.cast_ready(me):
                    self.mover.clear()
                    self.killing = a['serial']
                    self.fought = True
                    say(f'killing {a["name"]} with spells, all the way')
                    self.cast_at(a, spell)
                    return False
                if dfree < LONE_CLEAR:
                    # room to cast first: away to 10 (standing while it closed back in left him never 8 clear)
                    self.flee(me, [xy(m) for m in threats], radii=(12, 10), need=LONE_CLEAR + 2)
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
            if dloose > CLEAR and dbusy > SPELL_RANGE:
                # too far off to cast at them: one ride to about CAST_SPOT tiles from the nearest of them
                n = min(busy, key=lambda b: dist(me, xy(b)))
                d = dist(me, xy(n))
                f = (d - CAST_SPOT) / d
                spot = clamp_area((round(me[0] + (n['x'] - me[0]) * f), round(me[1] + (n['y'] - me[1]) * f)))
                if path_clear(me, spot, [xy(t) for t in threats], FIGHT_GAP) and self.mover.go(me, spot, 'to cast'):
                    return False
            if dloose > CLEAR and dbusy >= CAST_CLEAR:  # no spell with any creature within 6, fighting or not
                m = self.cast_target(me, busy, mobs, st)
                spell = self.spell_for(m, st['mana']) if m else None
                if spell and m and (dist(me, xy(m)) > SPELL_RANGE or time.time() - self.too_far.get(m['serial'], 0) < 5):
                    if self.closer(me, m, threats):
                        return False
                if spell and not (self.meditating and st['mana'] < 60 and m and kind(m) not in CASTERS):
                    if not self.cast_ready(me):
                        time.sleep(0.15)  # bridge 7: let the ride finish first, no casting on the move
                        return False
                    self.cast_at(m, spell)
                    return False
                nearly_dead = any(share(b) is not None and share(b) < 0.25 for b in busy)
                # never with one after him close by (19:02:23: a dire wolf coming at him, 9 -> 5 tiles, counted as busy
                # with a timber wolf, and he sat down to meditate); a pair still marked as after him but fighting each
                # other where they are is fine (the orc and the hart, 18:50: the user wants him meditating then)
                busy_ids = {b['serial'] for b in busy}
                after_him = any(self.coming(t) and dist(me, xy(t)) <= CLEAR
                                and (t['serial'] not in busy_ids or self.approaching(t['serial'])) for t in threats)
                if (not self.meditating and not nearly_dead and not after_him
                        and st['mana'] < st.get('manaMax', 100) - 10 and self.skill_ready()):
                    self.last_skill = time.time()
                    a = call('POST', '/skill', id=MEDITATE)
                    self.meditating = said(a, 'meditative trance', 'at peace')
                    say(f'meditate (mana {st["mana"]}): {texts(a)!r}')
                    return False
            time.sleep(0.15)
            return False

        # nothing coming and nothing fighting
        if self.fought and not self.homeward:
            # the survivors of the fight first (the user, 2026-11-07: "You waited for the orc to be gone before
            # engaging the hart at all"; it was left at 1/25 next to the orc's corpse while he looted): spells from
            # 6-10 tiles, mana to spare only
            left = [m for m in free if m['serial'] in self.fought_with]
            if left:
                self.quiet_since = None
                m = min(left, key=lambda m: dist(me, xy(m)))
                d = dist(me, xy(m))
                spell = self.spell_for(m, st['mana'])
                if spell:
                    if d < CAST_CLEAR:
                        self.flee(me, [xy(t) for t in threats], radii=(8, 6))
                        return False
                    if d > SPELL_RANGE or time.time() - self.too_far.get(m['serial'], 0) < 5:
                        if self.closer(me, m, threats):
                            return False
                    if self.cast_ready(me):
                        self.cast_at(m, spell)
                        return False
                    time.sleep(0.15)
                    return False
                # nothing to spare for it: keep off it (below), loot only with it well away
            if self.quiet_since is None:
                self.quiet_since = time.time()
            if time.time() - self.quiet_since >= 2 and self.loot(me, st):
                return False
            # back to full mana before anything else (the user, 2026-11-06 17:11: "You should be meditating to get back
            # your mana, you just used a lot"), only with no creature within CLEAR; every tick still looks, and one
            # that turns on him or comes near ends it (the branches above, or riding home)
            quiet_for = time.time() - self.quiet_since
            if (quiet_for >= 2 and quiet_for < MEDITATE_FOR and st['mana'] < st.get('manaMax', 100) - 5
                    and min(dfree, dany_creature) > CLEAR and not self.front):
                if not self.meditating and self.skill_ready() and self.still(me):
                    self.mover.clear()
                    self.last_skill = time.time()
                    a = call('POST', '/skill', id=MEDITATE)
                    self.meditating = said(a, 'meditative trance', 'at peace')
                    say(f'meditate after the fight (mana {st["mana"]}): {texts(a)!r}')
                time.sleep(0.3)
                return False
            if quiet_for >= 5:
                self.go_home('nothing is coming after him')
            time.sleep(0.15)
            return False

        if self.homeward:
            return self.step_home(me, threats)

        # something after him that the branches above left be (it went out of their reckoning for a moment): no
        # drawing or looking around now (18:33:12: "riding to 1768,1430 to look around" took him straight back to a
        # gargoyle that was after him; it hit him to 87)
        if any(attackable(m) and self.coming(m) for m in mobs.values()):
            time.sleep(0.15)
            return False

        # drawing one (the user): ride straight to where it'll notice him (5 tiles; casters notice from far, 11) and
        # stand still there until it targets him (turns Criminal); left be if it hasn't by LURE_WAIT (shut in a
        # building, or it doesn't attack). No moving about while waiting.
        lurable = [m for m in free if m['serial'] not in self.ignored and self.visible(m['serial'])
                   and (not self.front or dist(xy(m), HOME) <= FRONT_RANGE)]
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
                f = (d - near_enough) / d if d > near_enough + 1 else 0
                spot = clamp_area((round(me[0] + (target['x'] - me[0]) * f), round(me[1] + (target['y'] - me[1]) * f)))
                # as close as his area lets him (an ettin north of the front line: the spot came back onto his own
                # tile and he "rode" there over and over, 2026-11-06 17:05): then he's there
                if d > near_enough + 1 and dist(spot, me) > 1:
                    if not self.mover.go(me, spot, 'draw ' + target['serial']):
                        say(f'no way toward {target["name"]}; leaving it be')
                        self.ignored.add(target['serial'])
                    time.sleep(0.2)
                    return False
                self.lure_since = time.time()
                say(f'standing {d} tiles from {target["name"]}, waiting for it to come')
            if time.time() - self.lure_since > LURE_WAIT:
                say(f'{target["name"]} never turned on him from {d} tiles; leaving it be (this run)')
                self.ignored.add(target['serial'])
                self.luring = None
                return False
            time.sleep(0.2)
            return False

        return self.search(me)

    def flee(self, me, threats, toward=None, fresh=False, radii=(8, 5), need=None):
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
                    # need: a spot at least that far from every creature comes first (hurt: 10 tiles, the user)
                    far_enough = need is None or min((dist(p, t) for t in threats), default=99) >= need
                    spots.append((far_enough, all(dist(p, t) > dist(me, t) for t in near)
                                  and path_clear(me, p, near, SPACE) and path_in_area(me, p), score(p), p))
        spots.sort(reverse=True)
        for _, _, _, p in spots[:8]:
            if m.go(me, p, 'flee', force=True, urgent=any(dist(me, t) <= ON_HIM for t in threats)):
                return

    def caster_moves(self, me, a, mobs, threats):
        """A caster after him that can't be set on anything right now (the user, 2026-11-06: "for a spellcaster when
        there's no other enemy to provoke it to, you need to get like 15+ tiles away and pull him to someone else
        quickly ... stay far away from it and pull it toward some other animal or monster and provoke it soon to get it
        'off of you'"). With something in sight to set it on: one ride to the far side of that creature from the
        caster (PULL_SPOT tiles from it), then stand and let the caster come; the provoke (checked first every tick)
        goes off once both are in range. Nothing to set it on, or no clear way there: CASTER_CLEAR tiles from it.
        After CASTER_PULL_FOR seconds with nobody to set it on, False: spells at it, as at any other. True when this
        has dealt with the moment."""
        since = self.caster_since.setdefault(a['serial'], time.time())
        if time.time() - since > CASTER_PULL_FOR:
            return False
        d = dist(me, xy(a))
        p = self.partner_for(me, a, mobs, 18)
        if p and (a['serial'], p['serial']) in self.gave_up:
            p = None
        if p and self.coming(p):
            # it's after him too: no riding to it (18:49:34, toward an orc on his heels and away again, over and over);
            # both follow him, so they come together: keep off both and the provoke goes off once both are in range
            p = None
        if d < KEEP_CASTER:
            # too close for anything but getting away (toward the creature to set it on, if any): a pull ride from
            # here went past it (fight_sim)
            self.flee(me, [xy(m) for m in threats], radii=(12, 10, 8), toward=xy(p) if p else None)
            return True
        if p:
            px, py = xy(p)
            ax, ay = xy(a)
            n = max(dist((px, py), (ax, ay)), 1)
            spot = clamp_area((round(px + (px - ax) * PULL_SPOT / n), round(py + (py - ay) * PULL_SPOT / n)))
            why = 'pull to ' + p['serial']
            if dist(me, spot) > 2:
                if self.mover.why == why and self.mover.going(me):
                    time.sleep(0.15)
                    return True
                others = [xy(t) for t in threats if t['serial'] != p['serial']]
                if (path_clear(me, spot, [xy(a)], KEEP_CASTER) and path_clear(me, spot, others, SPACE)
                        and path_clear(me, spot, [xy(p)], 2)
                        and self.mover.go(me, spot, why)):
                    say(f'pulling {a["name"]} ({d} tiles) to {p["name"]} at {px},{py}')
                    return True
                # the caster is in the way (the gargoyle between him and the panther, 18:33): round it, ROUND tiles
                # off, by the waypoint that gets him nearest the spot; one at a time, each kept until he's there
                if self.mover.why == why + ' round' and self.mover.going(me):
                    time.sleep(0.15)
                    return True
                best = None
                for i in range(16):
                    ang = i * math.pi / 8
                    w = clamp_area((round(ax + ROUND * math.cos(ang)), round(ay + ROUND * math.sin(ang))))
                    if dist(w, me) < 3 or dist(w, spot) >= dist(me, spot):
                        continue
                    if (path_clear(me, w, [xy(a)], KEEP_CASTER) and path_clear(me, w, others, SPACE)
                            and path_clear(me, w, [xy(p)], 2)):
                        if best is None or dist(w, spot) < dist(best, spot):
                            best = w
                if best and self.mover.go(me, best, why + ' round'):
                    say(f'round {a["name"]} ({d} tiles) toward {p["name"]} at {px},{py}: via {best[0]},{best[1]}')
                    return True
            else:
                time.sleep(0.15)  # there: let it come into provoke range
                return True
        if d < CASTER_CLEAR - 2:
            # one long ride to well past 15 (getting away only once it's under 13: hops of a tile or two to stay at
            # exactly 15 were a wiggle in fight_sim)
            self.flee(me, [xy(m) for m in threats], radii=(14, 12, 10), need=CASTER_CLEAR + 2,
                      toward=xy(p) if p else None)
            return True
        time.sleep(0.15)
        return True

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

    def loot(self, me, st, front_door=False):
        """After a fight, with nothing coming: the gold in the corpses that fell during it, into his backpack (the
        user, 2026-11-06: "Loot the corpse if you're able to"; 2026-11-08: "You don't have to loot anything except for
        the gold outside of the tower. Only loot the gold"). Only
        corpses that appeared during this fight, within LOOT_RANGE; never a person's ("corpse of ..."). One step per
        look, nothing that waits (the user: "always be ready to move, don't get caught stuck doing something else"):
        a ride to it, then one item a look, and every look checks for creatures first. True while there's looting
        to do."""
        try:
            near = call('GET', '/nearby', range=LOOT_RANGE)['items']
            creatures = [m for m in call('GET', '/nearby', range=18)['mobiles'] if attackable(m)]
        except uo.BridgeError:
            return False
        for c in near:
            name = (c.get('type') or c.get('name') or '').lower()
            if (int(c['graphic'], 16) != 0x2006 or c['serial'] in self.looted or 'corpse of' in name
                    or (c['serial'] in self.corpses_before and not front_door)):
                continue
            if front_door and dist((c['x'], c['y']), HOME) > FRONT_RANGE:
                continue
            # never in to a corpse with a creature near it or him, any creature (the user, 2026-11-06: "you just ran
            # in to loot when the wolf was right next to the corpse"): wait for it to go
            if any(dist(xy(m), (c['x'], c['y'])) < LOOT_CLEAR or dist(xy(m), me) < LOOT_CLEAR
                   for m in creatures if kind(m) not in HARMLESS or m['serial'] in self.fought_with):
                self.looting = None
                continue
            lt = self.looting
            if not lt or lt['serial'] != c['serial']:
                lt = self.looting = {'serial': c['serial'], 'name': name, 'took': [], 'since': time.time(),
                                     'next_to': None}
            if time.time() - lt['since'] > 40:
                say(f'gave up on {name or "a corpse"} after 40 s: ' + (', '.join(lt['took']) or 'nothing taken'))
                self.looted.add(c['serial'])
                self.looting = None
                return True
            if dist(me, (c['x'], c['y'])) > 1:
                if not self.mover.go(me, (c['x'], c['y']), 'loot ' + c['serial']):
                    say(f'could not get to the corpse at {c["x"]},{c["y"]}')
                    self.looted.add(c['serial'])
                    self.looting = None
                return True
            # his client opens a corpse within 2 tiles by itself (auto_open_corpses; the bridge's /open refuses
            # corpses): its contents show up a moment after he gets there
            lt['next_to'] = lt['next_to'] or time.time()
            try:
                items = call('GET', '/contents', serial=c['serial'], depth=1)['items']
            except uo.BridgeError as e:
                say(f'corpse {c["serial"]}: {e}')
                self.looted.add(c['serial'])
                self.looting = None
                return True
            if not items and not lt['took'] and time.time() - lt['next_to'] < 3:
                return True  # not shown yet: look again next time
            items = [i for i in items if int(i['graphic'], 16) == GOLD]  # only the gold (the user, 2026-11-08)
            if not items:
                say(f'looted {name or "a corpse"}: ' + (', '.join(lt['took']) or 'nothing'))
                self.looted.add(c['serial'])
                self.looting = None
                self.quiet_since = time.time()  # looting took a while: look around again before going home
                return True
            i = items[0]
            pack = st['backpack']['serial']
            try:
                # onto a stack of the same kind already in his pack, or the server merges it there itself and the
                # bridge, waiting for the item to show up in the pack, stops (17:10:46: the orc's 41 gold)
                stack = self.stack_in(pack, i)
                if not stack and pack_count(pack) >= PACK_LIMIT - 1:
                    say(f'pack full ({PACK_LIMIT} items): only what stacks gets looted; leaving {i.get("type")}')
                    self.looted.add(c['serial'])
                    self.looting = None
                    return True
                r = call('POST', '/move', serial=i['serial'], to=stack or pack)
                if stack and not r.get('moved'):
                    r = call('POST', '/move', serial=i['serial'], to=pack)  # not one that stacks: back, so in
                if r.get('moved'):
                    lt['took'].append(f'{i.get("amount", 1)} {i.get("type") or i["graphic"]}')
                else:
                    say(f'looting {i.get("type")}: not moved; leaving the rest')
                    self.looted.add(c['serial'])
                    self.looting = None
            except uo.BridgeError as e:
                say(f'looting {i.get("type")}: {e}; leaving the rest')
                self.looted.add(c['serial'])
                self.looting = None
            return True
        return False

    def stack_in(self, pack, item):
        """The serial of a stack in his pack (top level, where the server merges) of the same kind as item: graphic
        and hue, not a container. None if there's none."""
        try:
            mine = call('GET', '/contents', serial=pack, depth=1)['items']
        except uo.BridgeError:
            return None
        same = [i for i in mine if i['graphic'] == item['graphic'] and i.get('hue') == item.get('hue')
                and not i.get('container')]
        return max(same, key=lambda i: i.get('amount', 1))['serial'] if same else None

    def closer(self, me, m, threats):
        """One straight ride to CAST_SPOT tiles from m, to cast at it, clear of everything free. True when he's on his
        way."""
        self.too_far.pop(m['serial'], None)
        d = dist(me, xy(m))
        if d <= CAST_SPOT:
            return False
        f = (d - CAST_SPOT) / d
        spot = clamp_area((round(me[0] + (m['x'] - me[0]) * f), round(me[1] + (m['y'] - me[1]) * f)))
        others = [xy(t) for t in threats if t['serial'] != m['serial']]
        why = 'closer to ' + m['serial']
        if self.mover.why == why and self.mover.going(me):
            time.sleep(0.15)  # on his way already (this said so 30 times a second, 2026-11-06 17:10:32)
            return True
        if path_clear(me, spot, others, SPACE) and self.mover.go(me, spot, why):
            say(f'closer to {m["name"]} to cast ({d} -> {CAST_SPOT} tiles)')
            return True
        return False

    def read_messages(self):
        """The server's word since the last look: the horse tiring, meditation ending, a creature casting (its spell
        may have used his Magic Reflection up: cast again when there's time). Returns the new messages."""
        new = call('GET', '/messages', after=self.seen_message)['messages']
        if new:
            self.seen_message = max(m['id'] for m in new)
        for m in new:
            low = m['text'].lower()
            if m.get('type') == 'Spell' and m.get('serial') and m.get('serial') != self.me_serial and self.reflect_up:
                self.reflect_up = False
                say(f'{m.get("from") or m.get("serial")} cast ({m["text"]!r}): Magic Reflection may be used up')
            if 'stop meditating' in low:
                self.meditating = False  # a step or a spell ends the trance
            own_cast = time.time() - self.last_cast < self.last_gap + 0.5
            if ('frozen and cannot move' in low and not own_cast) or 'you cannot move' in low:
                # his own spell freezes him too: those don't count (20:07:24, a pouch opened 0.6 s after his own
                # bolt's freeze, for nothing)
                self.frozen_at = time.time()
            elif 'you can move' in low:
                self.frozen_at = 0.0
            if 'too fatigued' in low:
                self.tired = 'too'
            elif 'fatigued' in low and self.tired is None:
                self.tired = 'very'
            if 'fatigued' in low:
                say(f'the horse: {m["text"]!r}')
        return new

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

    def door_guard(self):
        """Between the steps through the door: distance comes first (the user, 2026-11-06: "#1 priority is always
        maintain distance between you and the creatures"); a creature within ON_HIM + 1 breaks the way in off."""
        st, mobs = look()
        me = (st['x'], st['y'])
        near = [m for m in mobs.values() if attackable(m) and (not passive(m) or self.coming(m))
                and dist(me, xy(m)) <= ON_HIM + 1]
        if near:
            raise door.Stop('a creature came near: ' + ', '.join(m['name'] or '?' for m in near))

    def step_home(self, me, threats):
        """Short hops to the front door, then in (door.go_in). True once he's inside. A creature within 3 of the door
        (not after him: that's dealt with first) is put off the front steps with the house command "remove thyself" (the
        user, 2026-11-06); he only goes for the door with none there."""
        at_door = [t for t in threats if dist(xy(t), HOME) <= 3]
        if at_door and dist(me, HOME) <= 8:
            t = min(at_door, key=lambda t: dist(xy(t), HOME))
            if time.time() - self.removed_at.get(t['serial'], 0) > 6:
                self.removed_at[t['serial']] = time.time()
                try:
                    a = call('POST', '/say', text='remove thyself')
                    end = time.time() + 1.5  # the house's cursor comes a moment after the words
                    while time.time() < end and not call('GET', '/status').get('targeting'):
                        time.sleep(0.1)
                    r = aim(t['serial']) if call('GET', '/status').get('targeting') else {}
                    say(f'"remove thyself" on {t["name"]} at the door: {texts(r) or texts(a) or "-"}')
                except uo.BridgeError as e:
                    say(f'"remove thyself": {e}')
                    cancel_cursor()
            time.sleep(0.3)
            return False
        if dist(me, HOME) <= 1:
            door.info = info
            door.guard = self.door_guard
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
        if self.front:
            # home from town: nothing (left) in front of the tower is all it takes; no looking further out. The gold
            # first from any corpse lying in front of the door, his earlier kills too (the user, 2026-11-08: "if you
            # can just loot the gold")
            if self.loot(me, call('GET', '/status'), front_door=True):
                return False
            self.go_home('nothing left in front of the tower')
            return False
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


def setup(bridge_info, partner=None):
    """Ready to fight as the character of bridge_info (main, and trips.py coming home from town). Returns /status."""
    global info, ASYNC, PARTNER, BRIDGE
    info = bridge_info
    os.makedirs(WORK, exist_ok=True)
    st = call('GET', '/status')
    if st.get('bridge', 0) < 7:
        raise SystemExit('needs bridge 7 (cuo-agent23)')
    ASYNC = st['bridge'] >= 8  # cast and go on (cuo-agent24)
    BRIDGE = st['bridge']
    PARTNER = partner.lower() if partner else None
    return st


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--minutes', type=float, default=10, help='then home')
    parser.add_argument('--route', choices=sorted(ROUTES), help='where to look (default: one at random)')
    parser.add_argument('--partner', help='set creatures on this kind first (e.g. panther), as the user says')
    parser.add_argument('--front', action='store_true',
                        help='only the creatures in front of the tower, then in (as coming home from town)')
    parser.add_argument('--resume', action='store_true',
                        help='clear a takeover; only when the user has said they hand him back')
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, on_term)
    try:
        st = setup(uo.find_bridge('Clem'), args.partner)
    except SystemExit as e:
        sys.exit(str(e))
    stopped = st.get('takenOver') or st.get('halted')
    if stopped and not args.resume:
        sys.exit(f'the user has him ({stopped}); --resume only once they hand him back')
    if st['y'] < AREA[1]:  # the doorway (y 1414), where door.py out leaves him, counts
        sys.exit('he is not outside (door.py out first)')
    if stopped:
        call('POST', '/resume')
        say(f'resumed, as the user said (was: {stopped})')
    try:
        Fight(args.minutes, args.route, front=args.front).run()
        say('parked inside; the door is locked and closed')
    except Stop as e:
        say(f'STOPPED: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
