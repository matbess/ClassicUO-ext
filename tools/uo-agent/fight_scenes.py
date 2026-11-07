#!/usr/bin/env python3
"""Checks fight.py's decisions offline: made-up scenes (where Clem and the creatures are, their health, what the
server just said) go through one tick of Fight each, with the bridge faked, and what he'd do is printed. Nothing is
sent to the game. Run it after changing fight.py:

  python3 -I fight_scenes.py
"""
import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import fight  # noqa: E402

def mob(serial, name, x, y, war=False, hits=25):
    # war: it has targeted him, which shows as notoriety Criminal (war mode never comes on)
    return {'serial': serial, 'name': name, 'x': x, 'y': y, 'notoriety': 'Criminal' if war else 'Gray', 'warMode': False, 'hits': hits,
            'hitsMax': 25, 'body': '0x1', 'human': False, 'yourPet': False, 'dead': False, 'hidden': False}

acts = []
scene = {}
def fake_call(method, ep, **kw):
    if ep == '/status':
        return dict(scene['me'], serial='0x1', hitsMax=100, backpack={'serial': '0x2'}, lastMessageId=0, mounted=scene['me'].get('mounted', True))
    if ep == '/nearby':
        return {'mobiles': list(scene['mobs'].values()), 'items': []}
    if ep == '/contents':  # a full reagent bag
        return {'items': [{'graphic': hex(g), 'amount': 50} for g in (0x0F7A, 0x0F7B, 0x0F84, 0x0F85, 0x0F86, 0x0F88,
                                                                      0x0F8D, 0x0F8C)]}
    if ep == '/messages':
        return {'messages': scene.get('messages', [])}
    if ep == '/rules':
        return {'mounts': ['0x0000HORS']}
    acts.append((ep, kw))
    if ep == '/skill': return {'targeting': True, 'messages': [{'text': 'Whom do you wish to incite?'}]}
    if ep == '/target': return {'targeting': True, 'messages': [{'text': 'Your music succeeds, as you start a fight.'}]}
    if ep == '/cast': return {'aimed': True, 'mana': 80, 'messages': []}
    return {'walking': True}
fight.call = fake_call
fight.time.sleep = lambda s: None
fight.say = lambda t: None
fight.row = lambda **k: None

def run(name, me, mobs, setup=None):
    global acts
    scene['me'] = me; scene['mobs'] = {m['serial']: m for m in mobs}
    fight._last_walk.update(p=None, t=0.0)  # each scene starts fresh (no walk from the one before)
    f = fight.Fight(10)
    f.positions = [(me['x'], me['y'])] * 3  # he has been standing here (casting needs that)
    if setup: setup(f)
    acts = []
    f.tick()
    out = []
    for ep, kw in acts[:4]:
        if ep == '/walk':
            p = (kw['x'], kw['y'])
            ds = ', '.join('%s %d->%d' % (m['name'], fight.dist((me['x'], me['y']), fight.xy(m)), fight.dist(p, fight.xy(m))) for m in mobs)
            out.append(f'walk to {p[0]},{p[1]} (door {fight.dist((me["x"], me["y"]), fight.HOME)}->{fight.dist(p, fight.HOME)}; {ds})')
        else:
            out.append(f'{ep} {kw}')
    print(f'--- {name}:', ' | '.join(out) or 'holds and watches')

me = {'x': 1790, 'y': 1430, 'z': 0, 'hits': 100, 'mana': 100, 'stamina': 25}
cooldown = lambda f: setattr(f, 'last_skill', time.time())
run('dire wolf following (6), ogre 12 off', me, [mob('0xA', 'a dire wolf', 1784, 1430, True), mob('0xB', 'an ogre', 1802, 1430)])
run('dire wolf 5, ogre 7', me, [mob('0xA', 'a dire wolf', 1785, 1430, True), mob('0xB', 'an ogre', 1797, 1430)])
run('ogre on him (2)', me, [mob('0xB', 'an ogre', 1792, 1430, True)])
run('wolf coming from the tower side, provoke not ready', me, [mob('0xA', 'a dire wolf', 1784, 1430, True)], setup=cooldown)
run('wolf coming from the far side, provoke not ready', me, [mob('0xA', 'a dire wolf', 1796, 1430, True)], setup=cooldown)
run('ogre 12 off, idle', me, [mob('0xB', 'an ogre', 1802, 1430)])
run('ogre 20 off: lure', me, [mob('0xB', 'an ogre', 1810, 1430)])
both_busy = lambda f: (f.pairs.update({'0xA': '0xB'}), f.provoked_at.update({'0xA': time.time()}))
run('wolf and ogre fighting 11 off', me, [mob('0xA', 'a dire wolf', 1801, 1430, True, hits=20), mob('0xB', 'an ogre', 1802, 1431, True, hits=24)], setup=both_busy)
run('uneven: wolf nearly dead, ogre well', me, [mob('0xA', 'a dire wolf', 1801, 1430, True, hits=3), mob('0xB', 'an ogre', 1802, 1431, True, hits=22)], setup=both_busy)
run('ogre at 3/25 (12%) fighting: Lightning', me, [mob('0xA', 'a dire wolf', 1801, 1430, True, hits=20), mob('0xB', 'an ogre', 1802, 1431, True, hits=3)], setup=both_busy)
run('ogre at 1/25 (4%) fighting: Fireball', me, [mob('0xA', 'a dire wolf', 1801, 1430, True, hits=20), mob('0xB', 'an ogre', 1802, 1431, True, hits=1)], setup=both_busy)

scene['messages'] = [{'id': 5, 'text': 'Your mount is very fatigued.'}]
run('horse very fatigued, wolf 6 off: get away first', me, [mob('0xA', 'a dire wolf', 1784, 1430, True)])
run('horse very fatigued, nothing near: the trick', me, [mob('0xA', 'a dire wolf', 1770, 1430)])
scene['messages'] = [{'id': 6, 'text': 'Your mount is too fatigued to move.'}]
run('horse too fatigued, wolf 6 off: the trick at once', me, [mob('0xA', 'a dire wolf', 1784, 1430, True)])
scene['messages'] = []
run('two panthers 14 off: left be (search instead)', me, [mob('0xP', 'a panther', 1776, 1430), mob('0xQ', 'a panther', 1804, 1430)])
run('timber wolf 8 off, not attacking: left be', me, [mob('0xT', 'a timber wolf', 1782, 1430)])
run('panther attacking him (war mode, 5 off): a threat after all', me, [mob('0xP', 'a panther', 1785, 1430, True)])
run('dire wolf 15 off: drawn', me, [mob('0xD', 'a dire wolf', 1805, 1430)])

# a dire wolf beating a mongbat (provoked): bolt the dire wolf, the one winning, never the mongbat
run('dire wolf winning against a mongbat', me, [mob('0xA', 'a dire wolf', 1781, 1430, True, hits=22), mob('0xM', 'a mongbat', 1782, 1431, True, hits=10)], setup=lambda f: (f.pairs.update({'0xM': '0xA'}), f.provoked_at.update({'0xM': time.time()})))
# an even fight: let them wear each other down (no spell)
run('dire wolf and ogre evenly matched', me, [mob('0xA', 'a dire wolf', 1781, 1430, True, hits=18), mob('0xB', 'an ogre', 1782, 1431, True, hits=17)], setup=lambda f: (f.pairs.update({'0xA': '0xB'}), f.provoked_at.update({'0xA': time.time()})))
# a harmless-looking timber wolf at his feet: get away from it
run('timber wolf at his feet', me, [mob('0xT', 'a timber wolf', 1791, 1430)])

# after the fight (2026-11-06 17:11, the user: "You should be meditating to get back your mana, you just used a lot"):
# nothing near, mana down: meditate; a creature within 10: no standing about, home
after = lambda f: (setattr(f, 'fought', True), setattr(f, 'quiet_since', time.time() - 6), setattr(f, 'looted', set()))
low = dict(me, mana=40)
run('after the fight, mana 40, nothing near: meditate', low, [], setup=after)
run('after the fight, mana 40, a timber wolf 8 off: home, no meditating', low, [mob('0xT', 'a timber wolf', 1782, 1430)], setup=after)
run('after the fight, mana full: home', me, [], setup=after)
# killing one with spells (nothing to set it on): an ogre 5 off: a getaway first, no spell
run('killing an ogre, it is 5 off: away first', me, [mob('0xB', 'an ogre', 1795, 1430, True)],
    setup=lambda f: setattr(f, 'killing', '0xB'))

# looting onto a stack of the same kind in his pack (17:10:46: the orc's gold merged into his gold, the bridge stopped)
pack_items = [{'serial': '0xG', 'graphic': '0x0EED', 'hue': 0, 'amount': 158},
              {'serial': '0xR', 'graphic': '0x0E76', 'hue': 34, 'container': True},
              {'serial': '0xW', 'graphic': '0x1439', 'hue': 0}]
fight.call = lambda method, ep, **kw: {'items': pack_items, 'lastMessageId': 0}
f = fight.Fight(10)
for item in ({'serial': '0x9', 'graphic': '0x0EED', 'hue': 0, 'amount': 41}, {'serial': '0x8', 'graphic': '0x0E76', 'hue': 34},
             {'serial': '0x7', 'graphic': '0x0F3F', 'hue': 0}):
    print(f'--- loot {item["graphic"]}: onto', f.stack_in('0x2', item) or 'the pack')

# the bridge stopped after a drop: resumed only when it landed and nobody took over
def recovery(name, status, item):
    sent = []
    def fake(info, method, ep, **kw):
        if ep == '/status': return status
        if ep == '/item':
            if item is None: raise fight.uo.BridgeError(404, 'unknown item')
            return item
        sent.append(ep)
        return {}
    real, fight.uo.call = fight.uo.call, fake
    try:
        print(f'--- {name}:', 'resumed' if fight.recover_drop() and sent == ['/resume'] else 'stays stopped')
    finally:
        fight.uo.call = real
pack = {'serial': '0x2'}
drop = 'no answer after dropping 0x406D57D9'
recovery('drop merged (item gone)', {'halted': drop, 'backpack': pack}, None)
recovery('drop landed in his pack', {'halted': drop, 'backpack': pack}, {'insideOf': [{'serial': '0x2'}]})
recovery('drop went elsewhere', {'halted': drop, 'backpack': pack}, {'insideOf': [{'serial': '0x5'}]})
recovery('the user took over', {'halted': drop, 'takenOver': 'a step', 'backpack': pack}, None)
recovery('another stop', {'halted': 'stopped because the server went quiet (no answer to a skill)', 'backpack': pack}, None)

# a gargoyle (caster) after him (the user, 2026-11-06): Magic Reflection whenever it isn't up; nothing to set it on:
# 15+ tiles away; something to set it on: pull it there; provoke as soon as both are in range (before reflection)
fight.call = fake_call
fight.ASYNC = True
up = lambda f: setattr(f, 'reflect_up', True)
run('gargoyle coming 12 off, reflection not up: Magic Reflection', me, [mob('0xG', 'a gargoyle', 1802, 1430, True)])
run('gargoyle coming 9 off, reflection up, nothing else: 15+ away', me, [mob('0xG', 'a gargoyle', 1799, 1430, True)], setup=up)
run('gargoyle coming 16 off, reflection up, nothing else: holds', me, [mob('0xG', 'a gargoyle', 1806, 1430, True)], setup=up)
run('gargoyle coming 12 off, an ogre 8 the other way: pull it to the ogre', me,
    [mob('0xG', 'a gargoyle', 1802, 1430, True), mob('0xB', 'an ogre', 1782, 1432)], setup=up)
run('gargoyle 7 off and an ogre 5 off near it, provoke ready: provoke first (no reflection)', me,
    [mob('0xG', 'a gargoyle', 1797, 1430, True), mob('0xB', 'an ogre', 1794, 1433)])
run('gargoyle after him 70 s with nobody to set it on: spells', me, [mob('0xG', 'a gargoyle', 1799, 1430, True)],
    setup=lambda f: (up(f), f.caster_since.update({'0xG': time.time() - 70})))
run('bridge 8: a spell on its way: no second spell, no provoke', me, [mob('0xG', 'a gargoyle', 1806, 1430, True)],
    setup=lambda f: setattr(f, 'spell', {'spell': 42, 'target': '0xG', 'name': 'a gargoyle', 'kind': 'attack',
                                         'at': time.time(), 'before': 0}))
fight.ASYNC = False
run('bridge 7: gargoyle 12 off, reflection not up: no reflection (it would hold the bridge 6 s)', me,
    [mob('0xG', 'a gargoyle', 1802, 1430, True)])

# a spell's outcome, settled from what follows it
def settle(name, kind, messages, hits_after=None, age=0.5):
    f = fight.Fight(10)
    f.spell = {'spell': 42 if kind == 'attack' else 36, 'target': '0xG', 'name': 'a gargoyle', 'kind': kind,
               'at': time.time() - age, 'before': 10, 'hits': 20}
    said = []
    fight.say = said.append
    g = mob('0xG', 'a gargoyle', 1802, 1430, True, hits=hits_after if hits_after is not None else 20)
    f.settle_spell({'0xG': g}, [{'id': 11 + i, 'text': t} for i, t in enumerate(messages)])
    fight.say = lambda t: None
    print(f'--- settle: {name}:', said[0] if said else 'still on its way',
          '| too far noted' if '0xG' in f.too_far else '', '| reflection up' if f.reflect_up else '')
settle('too far away', 'attack', ['That is too far away.'])
settle('concentration disturbed', 'attack', ['Your concentration is disturbed, thus ruining thy spell.'])
settle('its health fell 1.5 s after', 'attack', [], hits_after=12, age=1.5)
settle('its health fell 0.5 s after (someone else)', 'attack', [], hits_after=12)
settle('nothing yet', 'attack', [])
settle('nothing against it after 3 s', 'attack', [], age=3.5)
settle('reflection: already in effect', 'reflect', ['This spell is already in effect.'])
settle('reflection: nothing against it', 'reflect', [], age=3.5)

# mana kept for healing (the user, 2026-11-06: "don't use all your mana! save mana for healing")
fight.ASYNC = True
fight.call = fake_call
both = lambda f: (f.pairs.update({'0xA': '0xB'}), f.provoked_at.update({'0xA': time.time()}))
pair = [mob('0xA', 'a dire wolf', 1801, 1430, True, hits=20), mob('0xB', 'an ogre', 1802, 1431, True, hits=24)]
run('wolf and ogre fighting 11 off, mana 100: a spell', dict(me, x=1793), pair, setup=both)
run('the same, mana 40 (about even): let them fight, meditate', dict(me, x=1793, mana=40), pair, setup=both)
run('the same, mana 35: no spell (keeps 30), meditate', dict(me, x=1793, mana=35), pair, setup=both)

# looting, one step per look
def loot_scene(name, me_at, corpse_items, creatures=()):
    state = {'items': list(corpse_items), 'moves': []}
    corpse = {'serial': '0xC', 'graphic': '0x2006', 'type': 'corpse', 'name': 'an orcish corpse', 'x': 1790, 'y': 1432}
    def call(method, ep, **kw):
        if ep == '/nearby':
            return {'items': [corpse], 'mobiles': list(creatures)}
        if ep == '/contents':
            return {'items': state['items'] if kw['serial'] == '0xC' else [], 'lastMessageId': 0}
        if ep == '/status':
            return {'lastMessageId': 0, 'serial': '0x1'}
        if ep == '/rules':
            return {'mounts': []}
        if ep == '/move':
            state['moves'].append(kw['serial'])
            state['items'] = [i for i in state['items'] if i['serial'] != kw['serial']]
            return {'moved': True}
        if ep == '/walk':
            state['moves'].append(f'walk {kw["x"]},{kw["y"]}')
            return {'walking': True}
        return {}
    fight.call = call
    f = fight.Fight(10)
    f.corpses_before = set()  # it fell during the fight
    steps = []
    for _ in range(4):
        state['moves'] = []
        more = f.loot(me_at, {'backpack': {'serial': '0x2'}})
        steps.append(('/'.join(state['moves']) or '-') if more else 'done')
    print(f'--- loot: {name}:', ' | '.join(steps))
    fight.call = fake_call
gold = {'serial': '0xI1', 'graphic': '0x0EED', 'hue': 0, 'amount': 41, 'type': 'gold coin'}
hammer = {'serial': '0xI2', 'graphic': '0x1439', 'hue': 0, 'type': 'war hammer'}
loot_scene('corpse 2 off: ride, then one item a look', (1790, 1430), [gold, hammer])
loot_scene('a wolf 4 from the corpse: nothing', (1790, 1431), [gold], [mob('0xW', 'a dire wolf', 1793, 1434)])
loot_scene('next to the corpse: one item a look, then done', (1790, 1431), [gold, hammer])

# the gargoyle between him and the panther (18:33): round it toward the panther, not straight through or away
fight.ASYNC = True
fight.call = fake_call
run('gargoyle 10 off, the panther beyond it: round the gargoyle toward the panther', me,
    [mob('0xG', 'a gargoyle', 1782, 1430, True), mob('0xP', 'a panther', 1774, 1430)], setup=up)
fight.PARTNER = 'panther'
run('--partner panther: the panther before an orc nearer the gargoyle', me,
    [mob('0xG', 'a gargoyle', 1799, 1430, True), mob('0xR', 'Nehrakgu', 1800, 1437), mob('0xP', 'a panther', 1781, 1433)],
    setup=up)
fight.PARTNER = None

# 2026-11-07, the user's list: hit both of an even pair when health and mana are full; finish the survivor (a great
# hart left at 1/25) before looting; keep 4 from one on his heels
fight.ASYNC = True
fight.call = fake_call
even = [mob('0xR', 'Nehrakgu', 1799, 1430, True, hits=13), mob('0xH', 'a great hart', 1800, 1431, False, hits=15)]
pair_up = lambda f: (f.pairs.update({'0xR': '0xH'}), f.provoked_at.update({'0xR': time.time()}),
                     f.fought_with.update({'0xR', '0xH'}))
run('orc 13 and hart 15 even, health and mana full: a spell at the healthier (the hart)', me, even, setup=pair_up)
run('the same, mana 60: let them fight on', dict(me, mana=60), even, setup=pair_up)
survivor = lambda f: (setattr(f, 'fought', True), setattr(f, 'quiet_since', time.time() - 6),
                      f.fought_with.update({'0xH'}))
run('after the fight, the hart left at 1/25, 8 off: finish it before looting', me,
    [mob('0xH', 'a great hart', 1798, 1430, False, hits=1)], setup=survivor)
run('after the fight, the hart left at 1/25, 2 off: get away from it first', me,
    [mob('0xH', 'a great hart', 1792, 1430, False, hits=1)], setup=survivor)

# 19:01-19:04 run: finish one nearly dead straight away; no meditating with one after him close by
fight.ASYNC = True
fight.call = fake_call
dying = [mob('0xD', 'a dire wolf', 1800, 1430, True, hits=1), mob('0xT', 'a timber wolf', 1801, 1431, False, hits=2)]
pair_dying = lambda f: (f.pairs.update({'0xD': '0xT'}), f.provoked_at.update({'0xD': time.time()}),
                        f.fought_with.update({'0xD', '0xT'}))
run('dire wolf 1/25 and timber wolf 2/25 fighting, mana 60: finish the dire wolf now', dict(me, mana=60), dying,
    setup=pair_dying)
busy_close = [mob('0xD', 'a dire wolf', 1797, 1430, True, hits=10), mob('0xT', 'a timber wolf', 1798, 1430, False, hits=20)]
run('dire wolf 7 off fighting a timber wolf where they are, mana 37: meditate', dict(me, mana=37), busy_close,
    setup=lambda f: (f.pairs.update({'0xD': '0xT'}), f.provoked_at.update({'0xD': time.time()})))

# a caster fighting a dire wolf: both down together, the caster first on a tie
garg_pair = lambda f: (f.pairs.update({'0xG': '0xD'}), f.provoked_at.update({'0xG': time.time()}),
                       f.fought_with.update({'0xG', '0xD'}), setattr(f, 'reflect_up', True))
run('gargoyle 24 and dire wolf 25 fighting, full: the healthier (the dire wolf)', me,
    [mob('0xG', 'a gargoyle', 1800, 1430, True, hits=24), mob('0xD', 'a dire wolf', 1801, 1431, True, hits=25)], setup=garg_pair)
run('gargoyle 14 and dire wolf 22 fighting: the dire wolf (ahead), not the caster', dict(me, mana=60),
    [mob('0xG', 'a gargoyle', 1800, 1430, True, hits=14), mob('0xD', 'a dire wolf', 1801, 1431, True, hits=22)], setup=garg_pair)
run('gargoyle 22 and dire wolf 20 fighting, mana 60: about even, let them fight', dict(me, mana=60),
    [mob('0xG', 'a gargoyle', 1800, 1430, True, hits=22), mob('0xD', 'a dire wolf', 1801, 1431, True, hits=20)], setup=garg_pair)
run('gargoyle 3 and dire wolf 2: finish them', dict(me, mana=60),
    [mob('0xG', 'a gargoyle', 1800, 1430, True, hits=3), mob('0xD', 'a dire wolf', 1801, 1431, True, hits=2)], setup=garg_pair)
run('gargoyle 3 and dire wolf 20: the dire wolf, not finishing the gargoyle', dict(me, mana=60),
    [mob('0xG', 'a gargoyle', 1800, 1430, True, hits=3), mob('0xD', 'a dire wolf', 1801, 1431, True, hits=20)], setup=garg_pair)

# a dire wolf marked busy with a timber wolf but coming at him (19:02:23): no meditating
coming_busy = lambda f: (f.pairs.update({'0xD': '0xT'}), f.provoked_at.update({'0xD': time.time()}),
                         f.history.update({'0xD': [(time.time() - 2, 10), (time.time() - 0.5, 7)]}))
run('dire wolf busy with a timber wolf but coming at him 10 -> 7, mana 37: no meditating', dict(me, mana=37),
    [mob('0xD', 'a dire wolf', 1797, 1430, True, hits=10), mob('0xT', 'a timber wolf', 1798, 1430, False, hits=12)],
    setup=coming_busy)
