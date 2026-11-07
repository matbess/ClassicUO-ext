#!/usr/bin/env python3
"""Runs fight.py's decisions over time in a made-up world, to catch wiggling: Clem rides toward whatever spot he was
last sent to (2 tiles a moment), creatures move toward him once they've turned on him (Criminal), and every walk he's
sent and every reversal of direction is counted. Nothing is sent to the game.

  python3 -I fight_sim.py
"""
import math
import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import fight  # noqa: E402

world = {}
log = []


def mob(serial, name, x, y, sees=12, speed=1, stays=False):
    return {'serial': serial, 'name': name, 'x': x, 'y': y, 'notoriety': 'Gray', 'warMode': False, 'hits': 25,
            'hitsMax': 25, 'body': '0x1', 'human': False, 'yourPet': False, 'dead': False, 'hidden': False,
            '_sees': sees, '_speed': speed, '_stays': stays}


def fake_call(method, ep, **kw):
    me = world['me']
    if ep == '/status':
        return dict(me, serial='0x1', hitsMax=100, backpack={'serial': '0x2'}, lastMessageId=0, mounted=True,
                    targeting=False)
    if ep == '/nearby':
        return {'mobiles': [{k: v for k, v in m.items() if not k.startswith('_')} for m in world['mobs']]}
    if ep == '/contents':  # a full reagent bag
        return {'items': [{'graphic': hex(g), 'amount': 50} for g in (0x0F7A, 0x0F7B, 0x0F84, 0x0F85, 0x0F86, 0x0F88,
                                                                      0x0F8D, 0x0F8C)]}
    if ep == '/messages':
        return {'messages': []}
    if ep == '/rules':
        return {'mounts': ['0xH']}
    if ep == '/walk':
        world['goal'] = (kw['x'], kw['y'])
        log.append(('walk', world['t'], (kw['x'], kw['y'])))
        return {'walking': True}
    log.append((ep, world['t'], kw))
    if ep == '/skill':
        return {'targeting': True, 'messages': [{'text': 'Whom do you wish to incite?'}]}
    if ep == '/target':
        world.setdefault('aims', []).append(kw.get('serial'))
        if world.get('pair_check'):
            a, b = world['provoking']
            if fight.dist(fight.xy(a), fight.xy(b)) > 7:
                return {'targeting': False, 'messages': [{'text': 'The creatures you are trying to provoke are too far away from each other for your music to have an effect.'}]}
        aims = world['aims']
        if len(aims) >= 2:
            world.setdefault('provoked', {})[aims[-2]] = aims[-1]  # the first now goes for the second
        return {'targeting': True, 'messages': [{'text': 'Your music succeeds, as you start a fight.'}]}
    if ep == '/cast':
        return {'aimed': True, 'mana': 80, 'messages': []}
    return {}


def step_world():
    me = world['me']
    g = world.get('goal')
    if g:
        for _ in range(2):
            dx, dy = (g[0] > me['x']) - (g[0] < me['x']), (g[1] > me['y']) - (g[1] < me['y'])
            me['x'] += dx
            me['y'] += dy
    for m in world['mobs']:
        d = fight.dist((me['x'], me['y']), fight.xy(m))
        if m['notoriety'] == 'Gray' and d <= m['_sees'] and not m['_stays']:
            m['notoriety'] = 'Criminal'
        goal = (me['x'], me['y'])
        other = world.get('provoked', {}).get(m['serial'])
        if other:
            o = next(x for x in world['mobs'] if x['serial'] == other)
            goal = fight.xy(o)
            d = fight.dist(fight.xy(m), goal)
        if m['notoriety'] == 'Criminal' and d > 1 and world['t'] % m['_speed'] == 0:
            m['x'] += (goal[0] > m['x']) - (goal[0] < m['x'])
            m['y'] += (goal[1] > m['y']) - (goal[1] < m['y'])


def run(name, me, mobs, ticks=40):
    fight.call = fake_call
    fight.time.sleep = lambda s: None
    fight.time.time = lambda: 1000000.0 + world['t'] * 0.3  # the made-up world's clock: a moment is 0.3 s
    fight.say = lambda t: log.append(('say', world['t'], t))
    fight.row = lambda **k: None
    fight._last_walk.update(p=None, t=0.0)
    world.update(me=dict(me), mobs=mobs, goal=None, t=0, aims=[], provoked={})
    del log[:]
    f = fight.Fight(10)
    path = [(world['me']['x'], world['me']['y'])]
    closest = 99
    for t in range(ticks):
        world['t'] = t
        f.tick()
        step_world()
        path.append((world['me']['x'], world['me']['y']))
        closest = min([closest] + [fight.dist(path[-1], fight.xy(m)) for m in world['mobs']])
    walks = [e for e in log if e[0] == 'walk']
    moves = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]) if a != b]
    reversals = sum(1 for u, v in zip(moves, moves[1:]) if u[0] * v[0] + u[1] * v[1] < 0)
    print(f'--- {name}: {len(walks)} walks, {reversals} reversals, closest to a creature {closest}')
    for e in log:
        if e[0] != 'walk' or True:
            print('   ', e[1], e[0], e[2] if e[0] != 'walk' else f'to {e[2][0]},{e[2][1]}')


me = {'x': 1756, 'y': 1430, 'z': 0, 'hits': 100, 'mana': 100, 'stamina': 25}
run('a dire wolf 15 off, an ogre 12 beyond it', me,
    [mob('0xD', 'a dire wolf', 1756, 1445, sees=5), mob('0xO', 'an ogre', 1768, 1452, stays=True)])
run('a gargoyle (caster) 18 off, a dire wolf off to the side', me,
    [mob('0xG', 'a gargoyle', 1756, 1448, sees=14), mob('0xD', 'a dire wolf', 1745, 1440, stays=True)])

run('an orc 15 off, a panther 15 off to the side (the two far apart)', me,
    [mob('0xR', 'Ulmragha', 1756, 1445, sees=5), mob('0xP', 'a panther', 1745, 1440, stays=True)], ticks=45)

run('a lone skeleton coming (nothing to set it on)', me, [mob('0xS', 'a skeleton', 1756, 1442, sees=8)], ticks=40)

# a dire wolf already fighting a grizzly bear, 10 tiles off: he should bolt it straight away, not wait for it
wolf = mob('0xW', 'a dire wolf', 1766, 1430, stays=True)
bear = mob('0xB', 'a grizzly bear', 1767, 1430, stays=True)
run('a dire wolf already fighting a bear 10 off', me, [wolf, bear], ticks=20)
