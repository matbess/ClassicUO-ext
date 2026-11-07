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
