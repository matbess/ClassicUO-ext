#!/usr/bin/env python3
"""Icepick cooks raw fish steaks on the tower forge, ONE AT A TIME, to raise his Intelligence (COOKING.md).

  python3 -I cook.py run [--int 100]   cook until Int reaches --int (or a stop below)
  python3 -I cook.py stop              the loop stops after the steak it is on, and the command waits
  python3 -I cook.py report            cooks, Int and Cooking now, steaks per Int point, the estimate
  python3 -I cook.py rules             put the cooking rules into the client (rules/rules-Icepick-cook.json)

How this server does it (2026-11-17, tested by hand): double-click raw fish steaks in the pack (a target cursor),
aim at the forge from a tile away ("That is too far away." from two). About 5 s later either "Looks delicious." (said
by him) and "You put the cooked food into your backpack.", or "You burn the food to a crisp! It's ruined.". **One
double-click cooks the whole stack** with a single skill check (9 steaks went for one check in the test), so he
takes exactly 1 steak out of the chest each time, and this script refuses to double-click a raw stack bigger than 1.
A Cooking gain can bring a stat gain; the client prints "Your intelligence has changed by 1.  It is now 23".
On this server his max mana is his Int and his max stamina his Dex.

The user, 2026-11-17: Int to 100, then stop (Dex should be 25 by then). Cooking is set up; Herding (47.6) is set down
to make room, then Swordsmanship, Tactics and Wrestling. Hiding stays locked until those are all 0: then stop and
tell the user (the bridge can't set skill locks). The 5000 steaks are in the bottom wooden chest by the forge; the big
raw pile on the floor (1758,1408) is NEVER cooked: it's outside the rules' area and raw steaks are in "neverTouch".

Stops by itself (and says why): Int reached; the down skills all 0; Cooking at 100; the chest out of raw steaks; a raw
stack bigger than 1 in his pack; an answer it doesn't know; too heavy; the user took him over (only they hand him
back). Waits out world saves and the nightly reboot (about 04:15). Log ~/claude/uo-agent-work/cook/cook.log, state
in state.json there.
"""
import argparse
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import uo  # noqa: E402

HERE = os.path.dirname(os.path.realpath(__file__))
WORK = os.path.expanduser('~/claude/uo-agent-work/cook')
LOG = os.path.join(WORK, 'cook.log')
STATE = os.path.join(WORK, 'state.json')
PID = os.path.join(WORK, 'cook.pid')
STOP_FILE = os.path.join(WORK, 'stop')

CHAR = 'Icepick'
CHEST = '0x4074A4C1'    # the bottom wooden chest at 1757,1407,6 (locked down) with the raw fish steaks
FORGE = '0x408A3611'    # 1755,1410
SPOT = (1756, 1409)     # a tile from the forge, two from the chest
RAW = '0x097A'          # raw fish steak
COOKED_STEAK = '0x097B'
PILE = '0x407D3384'     # the cooked steaks on the forge (58290 on 2026-11-17; a pile holds at most 60000)
FLOOR_SPOT = (1757, 1408)  # where the second cooked pile starts, next to the raw pile at 1758,1408 (inside the area)
PILE_MAX = 60000
UNLOAD_EVERY = 100      # cooks between trips to the pile (the user: "put them over there once in a while")
DOWN = ['Herding', 'Swordsmanship', 'Tactics', 'Wrestling']   # set down, in the user's order; Hiding after them
TARGET_INT = 100

COOKED = 'put the cooked food into your backpack'
BURNT = 'burn the food to a crisp'
STAT = re.compile(r'your (strength|dexterity|intelligence) has changed by (-?\d+)\.\s+it is now (\d+)', re.I)
NO_GAIN_LIMIT = 300     # steaks in a row with no Cooking gain: stop and tell (SKILLGAIN.md: an action that can't
                        # fail any more gives no gains, and no gains means no Int)
# SKILLGAIN.md: relative cost of a skill point by band (90-93 = 1), measured on this server across five skills
MULTIPLIERS = [(60, 0.25), (70, 0.4), (80, 0.6), (85, 0.75), (90, 0.9), (93, 1.0), (95, 1.5), (97, 2.2), (100.1, 2.5)]
RESULT_WAIT = 12        # seconds from aiming at the forge to the result (about 5)
LAG_RESUMES = []


class Stop(Exception):
    pass


class Done(Exception):
    pass


def say(text):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + text
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def load_state():
    try:
        with open(STATE, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(state):
    with open(STATE + '.tmp', 'w', encoding='utf-8') as fh:
        json.dump(state, fh, indent=1)
    os.replace(STATE + '.tmp', STATE)


def install_rules():
    shutil.copyfile(os.path.join(HERE, 'rules', 'rules-Icepick-cook.json'),
                    os.path.join(uo.AGENT_DIR, 'rules-Icepick.json'))


def skills(info):
    return {s['name']: s for s in uo.call(info, 'GET', '/skills')['skills']}


def raw_items(info, container):
    return [i for i in uo.call(info, 'GET', '/contents', serial=container)['items']
            if (i.get('graphic') or '').upper() == RAW.upper()]


def act(info, method, endpoint, **params):
    """One action; a world save or a lag the server answers after is waited out (at most 5 resumes an hour)."""
    for _ in range(3):
        try:
            return uo.call(info, method, endpoint, **params)
        except uo.TakenOver as e:
            raise Stop(f'the user took Icepick over ({e.message}); only they hand him back')
        except uo.BridgeError as e:
            if e.code == 0:
                raise
            if e.code == 423 and uo.wait_out_world_save(info, e):
                say('a world save: waited it out')
                continue
            if e.code == 423 and server_back(info, e.message):
                continue
            raise Stop(f'{endpoint}: {e}')
    raise Stop(f'{endpoint} failed three times')


def server_back(info, why):
    now = time.time()
    LAG_RESUMES[:] = [t for t in LAG_RESUMES if now - t < 3600]
    if len(LAG_RESUMES) >= 5:
        return False
    say(f'the bridge stopped ({why}); waiting for the server')
    first = uo.call(info, 'GET', '/status').get('lastMessageId')
    for _ in range(60):
        time.sleep(5)
        msgs = uo.call(info, 'GET', '/messages', after=first)['messages']
        texts = [m['text'].lower() for m in msgs]
        if any('world will save' in t for t in texts) and not any('save complete' in t for t in texts):
            continue
        if msgs:
            uo.call(info, 'POST', '/resume')
            LAG_RESUMES.append(time.time())
            say(f'the server answered again: resumed ({len(LAG_RESUMES)} this hour)')
            return True
    return False


def wait_for_bridge(why):
    """The nightly reboot (about 04:15): wait up to 30 minutes for Icepick to log back in, rules back in, go on."""
    say(f'lost the bridge ({why}); waiting for Icepick to log back in (the nightly reboot is about 04:15)')
    end = time.time() + 30 * 60
    while time.time() < end:
        time.sleep(10)
        try:
            info = uo.find_bridge(CHAR)
            st = uo.call(info, 'GET', '/status')
        except (SystemExit, uo.BridgeError):
            continue
        if st.get('takenOver'):
            if not uo.login_routine(info, st['takenOver']):
                raise Stop(f'the user took Icepick over ({st["takenOver"]}); only they hand him back')
            time.sleep(10)
            uo.call(info, 'POST', '/resume')
            say('the login routine counted as a takeover: resumed')
        elif st.get('halted'):
            uo.call(info, 'POST', '/resume')
        install_rules()
        # after a login his client knows nothing inside the chest until it's opened again
        act(info, 'POST', '/open', serial=CHEST)
        say('Icepick is back; carrying on')
        return info
    raise Stop('Icepick did not come back within 30 minutes')


def multiplier(level):
    for top, m in MULTIPLIERS:
        if level < top:
            return m
    return MULTIPLIERS[-1][1]


def estimate(state):
    """Int comes with Cooking gains, and Cooking gains get dearer as Cooking rises (SKILLGAIN.md). Int points per
    Cooking point so far gives the Cooking level where Int reaches the target; the steaks per Cooking point measured
    now, scaled by SKILLGAIN.md's band multipliers, gives the steaks to get there. Returns (Int per Cooking point,
    Cooking needed, steaks per Cooking point now, steaks still needed) or None."""
    gained = state['int'] - state['startInt']
    cooking_gained = state.get('cooking', 0) - state.get('startCooking', 0)
    if gained <= 0 or cooking_gained <= 0:
        return None
    per_point = gained / cooking_gained
    now = state.get('cooking', 0)
    need_cooking = now + max(0, state['target'] - state['int']) / per_point
    bands = state.get('bands', {})
    band = bands.get(str(int(now // 10)), {})
    if band.get('points', 0) < 1.0:     # too little in this band yet: the band below
        band = bands.get(str(int(now // 10) - 1), {})
    if not band.get('points'):
        return per_point, need_cooking, None, None
    steaks_per_point = band['steaks'] / band['points']
    base = steaks_per_point / multiplier(now)
    need, level = 0.0, now
    while level < min(need_cooking, 100.0):
        step = min(0.1, need_cooking - level)
        need += base * multiplier(level) * step
        level += 0.1
    return per_point, need_cooking, steaks_per_point, round(need)


def describe_estimate(state):
    e = estimate(state)
    if not e:
        return ''
    per_point, need_cooking, steaks_per_point, need = e
    text = f'{per_point:.2f} Int per Cooking point, so Int {state["target"]} at about Cooking {need_cooking:.0f}'
    if need is not None:
        text += f'; {steaks_per_point:.1f} steaks per Cooking point now, so about {need} more steaks'
    if need_cooking > 100:
        text += ' (Cooking stops at 100 before Int gets there)'
    return text


def check_done(info, state):
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)
        raise Stop('asked to stop')
    if state['int'] >= state['target']:
        state['done'] = time.strftime('%Y-%m-%d %H:%M:%S')
        save_state(state)
        say(f'DONE: Int {state["int"]}, Dex {state["dex"]} after {state["cooks"]} steaks')
        raise Done()
    sk = skills(info)
    if sk['Cooking']['base'] >= sk['Cooking']['cap']:
        raise Stop(f'Cooking is at its cap ({sk["Cooking"]["base"]}): no more gains, so no more Int')
    if all(sk[n]['base'] <= 0 for n in DOWN) and sk['Cooking']['lock'] == 'up':
        total = uo.call(info, 'GET', '/skills').get('total')
        if total is not None and total >= 699.9:
            raise Stop(f'Herding, Swordsmanship, Tactics and Wrestling are all 0 and the skill total is {total}: '
                       f'Int {state["int"]}. Time to set Hiding down (the bridge cannot set skill locks)')
    return sk


def pile_amount(info, serial):
    try:
        return uo.call(info, 'GET', '/item', serial=serial).get('item', {}).get('amount') or 1
    except uo.BridgeError as e:
        if e.code == 404:
            return None
        raise


def unload(info, pack, state):
    """The cooked steaks in his pack onto the pile on the forge (the user, 2026-11-17); once it can't take them (a
    pile holds at most 60000), onto a second cooked pile on the floor next to the raw pile (the user, 2026-11-17:
    "make a cooked pile on the floor next to the uncooked pile"), started from FLOOR_SPOT. Returns how many."""
    moved = 0
    for i in uo.call(info, 'GET', '/contents', serial=pack)['items']:
        if (i.get('graphic') or '').upper() != COOKED_STEAK.upper():
            continue
        n = i.get('amount') or 1
        forge = pile_amount(info, PILE)
        floor = pile_amount(info, state['floorPile']) if state.get('floorPile') else None
        if forge is not None and forge + n <= PILE_MAX:
            to, where = PILE, 'the pile on the forge'
        elif floor is not None and floor + n <= PILE_MAX:
            to, where = state['floorPile'], 'the cooked pile on the floor'
        else:
            start_floor_pile(info, i['serial'], n, state)
            moved += n
            continue
        r = act(info, 'POST', '/move', serial=i['serial'], to=to)
        if not r.get('moved'):
            raise Stop(f'{where} did not take {n} cooked steaks: {[m["text"] for m in r.get("messages", [])]}')
        moved += n
        say(f'{n} cooked steaks onto {where} (now {pile_amount(info, to)})')
    return moved


def start_floor_pile(info, serial, n, state):
    """A new cooked pile: step to FLOOR_SPOT, put the steaks down at his feet, step back to the cooking spot."""
    r = act(info, 'POST', '/walk', x=FLOOR_SPOT[0], y=FLOOR_SPOT[1])
    st = uo.call(info, 'GET', '/status')
    if (st['x'], st['y']) != FLOOR_SPOT:
        raise Stop(f'could not step to {FLOOR_SPOT} to start the cooked pile on the floor (at {st["x"]},{st["y"]})')
    act(info, 'POST', '/move', serial=serial, ground=1)
    item = uo.call(info, 'GET', '/item', serial=serial).get('item', {})
    act(info, 'POST', '/walk', x=SPOT[0], y=SPOT[1])
    st = uo.call(info, 'GET', '/status')
    if (st['x'], st['y']) != SPOT:
        raise Stop(f'could not step back to the cooking spot {SPOT} (at {st["x"]},{st["y"]})')
    if item.get('container') or (item.get('x'), item.get('y')) != FLOOR_SPOT:
        raise Stop(f'the cooked steaks did not land at {FLOOR_SPOT}: {item}')
    state['floorPile'] = serial
    save_state(state)
    say(f'started a cooked pile on the floor at {FLOOR_SPOT[0]},{FLOOR_SPOT[1]} with {n} steaks ({serial})')


def take_one(info, pack):
    """Exactly one raw steak in the pack, from the chest. Returns its serial."""
    mine = raw_items(info, pack)
    if len(mine) > 1 or any((i.get('amount') or 1) > 1 for i in mine):
        raise Stop(f'raw steaks in his pack are not a single steak ({[(i["serial"], i.get("amount")) for i in mine]}); '
                   'a double-click would cook the whole stack')
    if mine:
        return mine[0]['serial']
    stacks = raw_items(info, CHEST)
    if not stacks:
        raise Stop('the chest has no raw fish steaks left')
    stack = max(stacks, key=lambda i: i.get('amount') or 1)
    act(info, 'POST', '/move', serial=stack['serial'], to=pack, amount=1)
    mine = raw_items(info, pack)
    if len(mine) != 1 or (mine[0].get('amount') or 1) != 1:
        raise Stop(f'after taking one steak, his pack holds {[(i["serial"], i.get("amount")) for i in mine]}')
    return mine[0]['serial']


def cook_one(info, state, pack):
    steak = take_one(info, pack)
    r = act(info, 'POST', '/use', serial=steak)
    if not r.get('targeting'):
        raise Stop(f'no target cursor after double-clicking the steak: {[m["text"] for m in r.get("messages", [])]}')
    r = act(info, 'POST', '/target', serial=FORGE)
    after = min([m['id'] for m in r.get('messages', [])] or [uo.call(info, 'GET', '/status')['lastMessageId']]) - 1
    seen, result, start = [], None, time.time()
    while time.time() - start < RESULT_WAIT:
        for m in uo.call(info, 'GET', '/messages', after=after)['messages']:
            after = max(after, m['id'])
            seen.append(m['text'])
        low = ' | '.join(seen).lower()
        if COOKED in low or BURNT in low:
            time.sleep(0.4)  # the stat lines come right behind the result
            for m in uo.call(info, 'GET', '/messages', after=after)['messages']:
                after = max(after, m['id'])
                seen.append(m['text'])
            result = 'cooked' if COOKED in low else 'burnt'
            break
        time.sleep(0.3)
    if result is None:
        raise Stop(f'no cooking result in {RESULT_WAIT} s; the server said: {seen[-6:]}')
    state['cooks'] += 1
    state[result] += 1
    band = state.setdefault('bands', {}).setdefault(str(int(state.get('cooking', 0) // 10)),
                                                   {'steaks': 0, 'points': 0.0, 'int': 0})
    band['steaks'] += 1
    band['cooked'] = band.get('cooked', 0) + (result == 'cooked')
    for t in seen:
        m = STAT.search(t)
        if m:
            stat, by, now = m.group(1).lower(), int(m.group(2)), int(m.group(3))
            key = {'strength': 'str', 'dexterity': 'dex', 'intelligence': 'int'}[stat]
            state[key] = now
            say(f'{stat} {by:+d} -> {now} (steak #{state["cooks"]})')
            if key == 'int':
                band['int'] += by
                state['intGains'].append([time.strftime('%Y-%m-%d %H:%M:%S'), state['cooks'], now])
    return result


def run(target):
    info = uo.find_bridge(CHAR)
    st = uo.call(info, 'GET', '/status')
    if st.get('takenOver'):
        if not uo.login_routine(info, st['takenOver']):
            raise Stop(f'the user took Icepick over ({st["takenOver"]}); only they hand him back')
        uo.call(info, 'POST', '/resume')
    if (st['x'], st['y']) != SPOT:
        raise Stop(f'Icepick is at {st["x"]},{st["y"]}, not at the cooking spot {SPOT[0]},{SPOT[1]}')
    install_rules()
    pack = st['backpack']['serial']
    state = load_state()
    if not state or state.get('done'):
        state = {'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'startInt': st['manaMax'], 'int': st['manaMax'],
                 'dex': st['staminaMax'], 'str': None, 'cooks': 0, 'cooked': 0, 'burnt': 0, 'intGains': []}
    state['target'] = target
    sk = skills(info)
    state.setdefault('startCooking', sk['Cooking']['base'])
    state['cooking'] = sk['Cooking']['base']
    save_state(state)
    say(f'cooking one steak at a time until Int {target}: Int {state["int"]}, Dex {state["dex"]}, Cooking '
        f'{sk["Cooking"]["base"]} ({sk["Cooking"]["lock"]}), ' +
        ', '.join(f'{n} {sk[n]["base"]} ({sk[n]["lock"]})' for n in DOWN) +
        f'; {sum(i.get("amount") or 1 for i in raw_items(info, CHEST))} raw steaks in the chest')
    last_cooking = sk['Cooking']['base']
    unload(info, pack, state)
    while True:
        try:
            sk = check_done(info, state)
            if st['weight'] > st['weightMax'] - 40 or (state['cooks'] and state['cooks'] % UNLOAD_EVERY == 0):
                unload(info, pack, state)
                st = uo.call(info, 'GET', '/status')
            if st['weight'] > st['weightMax'] - 15:
                raise Stop(f'too heavy to carry more cooked steaks ({st["weight"]}/{st["weightMax"]})')
            result = cook_one(info, state, pack)
            sk = skills(info)
            gain = round(sk['Cooking']['base'] - last_cooking, 1)
            if gain > 0:
                b = state['bands'][str(int(last_cooking // 10))]
                b['points'] = round(b['points'] + gain, 1)
                state['lastGainAt'] = state['cooks']
            elif state['cooks'] - state.setdefault('lastGainAt', state['cooks']) >= NO_GAIN_LIMIT:
                raise Stop(f'{NO_GAIN_LIMIT} steaks in a row with no Cooking gain at {sk["Cooking"]["base"]} '
                           f'(Int {state["int"]}): fish steaks may be too easy for him now')
            last_cooking = state['cooking'] = sk['Cooking']['base']
            save_state(state)
            if state['cooks'] % 25 == 0 or gain:
                say(f'#{state["cooks"]} {result}; Cooking {sk["Cooking"]["base"]}' + (f' (+{gain})' if gain else '') +
                    f'; Int {state["int"]}, Dex {state["dex"]}; Herding {sk["Herding"]["base"]}; ' +
                    describe_estimate(state))
            st = uo.call(info, 'GET', '/status')
        except uo.BridgeError as e:
            if e.code != 0:
                raise Stop(str(e))
            info = wait_for_bridge(e.message)
            st = uo.call(info, 'GET', '/status')
            state['int'], state['dex'] = st['manaMax'], st['staminaMax']
        except Done:
            return


def report():
    s = load_state()
    if not s:
        print('nothing yet')
        return
    print(f"since {s['started']}: {s['cooks']} steaks ({s['cooked']} cooked, {s['burnt']} burnt); "
          f"Int {s['startInt']} -> {s['int']}, Dex {s['dex']}; Cooking {s.get('startCooking')} -> {s.get('cooking')}")
    print(describe_estimate(s) or 'no estimate yet')
    print('by Cooking band: steaks, Cooking points gained, Int gained, steaks per Cooking point, steaks per Int, '
          'burnt %')
    for k in sorted(s.get('bands', {}), key=int):
        b = s['bands'][k]
        print(f"  {int(k) * 10:3d}-{int(k) * 10 + 10:<3d} {b['steaks']:6d} {b['points']:6.1f} {b['int']:4d}"
              f"  {b['steaks'] / b['points'] if b['points'] else 0:7.1f}  {b['steaks'] / b['int'] if b['int'] else 0:7.1f}"
              + (f"  {100 - 100 * b['cooked'] / b['steaks']:5.0f}%" if 'cooked' in b else ''))
    print('last Int gains (time, steak #, Int):', s['intGains'][-5:])


def stop():
    with open(STOP_FILE, 'w') as fh:
        fh.write('stop')
    try:
        with open(PID) as fh:
            pid = int(fh.read().strip())
    except (OSError, ValueError):
        print('no loop running')
        return
    for _ in range(40):
        try:
            os.kill(pid, 0)
        except OSError:
            print('stopped')
            return
        time.sleep(1)
    print('still running after 40 s')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('run').add_argument('--int', type=int, default=TARGET_INT)
    sub.add_parser('stop')
    sub.add_parser('report')
    sub.add_parser('rules')
    args = p.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if args.cmd == 'stop':
        return stop()
    if args.cmd == 'report':
        return report()
    if args.cmd == 'rules':
        return install_rules()
    if os.path.exists(PID):
        try:
            with open(PID) as fh:
                os.kill(int(fh.read().strip()), 0)
            sys.exit('a loop is already running')
        except (OSError, ValueError):
            pass
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)
    with open(PID, 'w') as fh:
        fh.write(str(os.getpid()))
    try:
        run(args.int)
    except Stop as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
    finally:
        os.remove(PID)


if __name__ == '__main__':
    main()
