#!/usr/bin/env python3
"""Offline checks for shovels.py (and the tools_room.py parts it uses). Nothing is sent to the game: every bridge call
is replaced by a fake. Run before restarting the loop after any change:

  python3 -I shovels_test.py

Each check is here because of something that went wrong on 2026-11-24:
- names: a function lost in a rewrite (wait_until) crashed the loop the first time it waited (16:53);
- the full-bag check indexed a set (tools_room fill, TRUST_CACHE) and crashed the first put-away (16:43);
- the per-tinker clocks: Serpent's Hold and Trinsic/Vesper came due at the wrong times after the first round;
- blocked Recall spots: backoff 15/30/60/120 s, then the tinker again in 10 minutes, logged for the user;
- Recall reagents: never so few that he can't get home.
"""
import ast
import builtins
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import shovels as S  # noqa: E402
import tools_room  # noqa: E402

failures = []


def check(name, ok, detail=''):
    print(('ok    ' if ok else 'FAIL  ') + name + (f'  ({detail})' if detail and not ok else ''))
    if not ok:
        failures.append(name)


def undefined_names(path):
    """Names loaded somewhere in the module that nothing defines: a lost function, a typo."""
    t = ast.parse(open(path, encoding='utf-8').read())
    defined = {n.name for n in ast.walk(t) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    defined |= {a.asname or a.name.split('.')[0] for n in ast.walk(t) if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in n.names}
    defined |= {n.id for n in ast.walk(t) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    defined |= {a.arg for n in ast.walk(t) if isinstance(n, (ast.FunctionDef, ast.Lambda))
                for a in n.args.args + n.args.kwonlyargs + ([n.args.vararg] if n.args.vararg else [])
                + ([n.args.kwarg] if n.args.kwarg else [])}
    defined |= {n.name for n in ast.walk(t) if isinstance(n, ast.ExceptHandler) and n.name}
    defined |= {n.name for n in ast.walk(t) if isinstance(n, ast.Global) for n in []}
    used = {n.id for n in ast.walk(t) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return sorted(used - defined - set(dir(builtins)) - {'__file__'})


def test_names():
    for f in ('shovels.py', 'tools_room.py'):
        missing = undefined_names(os.path.join(HERE, f))
        check(f'{f}: every name it uses is defined', not missing, missing)


def test_full_bag_check():
    graphics = tools_room.KINDS['shovels']['graphics']
    one = next(iter(graphics))
    full = {'items': {one: tools_room.PER_BAG}}
    room = {'items': {one: 10}}
    try:
        check('a full shovel bag is skipped, one with room is not',
              not tools_room.fits(full, one) and tools_room.fits(room, one))
    except Exception as e:
        check('the full-bag check runs on the kind\'s graphics (a set)', False, repr(e))


def test_clocks():
    now = time.time()
    state = {'tinkers': {
        '0': {'bought_out': True, 'due': now + 600},           # bought out, clock ahead
        '1': {'bought_out': False, 'due': now + 600},          # part bought: due now
        '2': {},                                                # never seen: due now
        '3': {'bought_out': True, 'due': now - 5},              # his hour is up
        '4': {'bought_out': True, 'due': now - 5, 'skip_until': now + 300},  # due, but blocked: in 5 min
    }}
    d = {k: S.due_at(state, k) for k in state['tinkers']}
    check('bought out: due at his clock', abs(d['0'] - (now + 600)) < 2)
    check('not bought out: due now', d['1'] <= time.time())
    check('never seen: due now', d['2'] <= time.time())
    check('hour up: due', d['3'] <= time.time())
    check('blocked: not before the skip ends', abs(d['4'] - (now + 300)) < 2)


def test_migrate():
    state = {'round': {'first_open': {'0': {'time': '16:11', 'stock': 19}, '6': {'time': '16:32', 'stock': 0}},
                       'bought': 95, 'gold': 1330, 'trips': 3}}
    saved = S.save_state
    S.save_state = lambda s: None
    try:
        S.migrate(state)
    finally:
        S.save_state = saved
    t0, t6 = state['tinkers']['0'], state['tinkers']['6']
    lt = time.localtime()
    opened = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 16, 11, 0, 0, 0, -1))
    check('first round: a tinker with shovels gets his clock from his first open',
          t0.get('due') == opened + S.RESTOCK and t0.get('bought_out') is True)
    check('first round: none seen (only the guildmaster) means due now', t6.get('bought_out') is False
          and S.due_at(state, '6') <= time.time())
    check('first round: totals carried over', state['totals']['bought'] == 95 and 'round' not in state)


def test_visit_cycle():
    """A tinker's clock starts on the first open after he was bought out (or ever), not on a revisit mid-cycle."""
    calls = []
    saved = (S.find_tinkers, S.buy_from, S.gold_carried, S.shovel_room, S.save_state, S.gems.check_town, S.VISITS)
    S.find_tinkers = lambda v, me: [{'serial': '0x1', 'distance': 2}]
    S.gold_carried = lambda: 1000
    S.shovel_room = lambda: 50
    S.save_state = lambda s: None
    S.gems.check_town = lambda v, me: None
    S.VISITS = os.path.join(tempfile.mkdtemp(), 'visits.jsonl')
    v = {'npcs': {'0x1': 'Merele the tinker'}}
    entry = {'loc': 'Britain', 'name': 'Britain'}
    try:
        S.buy_from = lambda v, st, e, tk: (19, 19, 14, 0)
        state = {'tinkers': {'Britain': {'bought_out': True, 'due': time.time() - 10}}}
        before = time.time()
        done = S.visit(v, state, entry, '0xme')
        t = state['tinkers']['Britain']
        check('a due tinker bought out: done, clock restarted an hour on',
              done and t['bought_out'] is True and t['due'] >= before + S.RESTOCK - 1)
        # a pack too small: he buys 10 of 19, goes home full; the clock must not restart on the way back
        S.buy_from = lambda v, st, e, tk: (10, 19, 14, 9)
        state = {'tinkers': {'Britain': {'bought_out': True, 'due': time.time() - 10}}}
        S.shovel_room = lambda: 0
        try:
            S.visit(v, state, entry, '0xme')
            check('full part way: raises Full', False, 'no exception')
        except S.Full:
            pass
        first_due = state['tinkers']['Britain']['due']
        S.shovel_room = lambda: 50
        S.buy_from = lambda v, st, e, tk: (9, 9, 14, 0)
        time.sleep(0.01)
        S.visit(v, state, entry, '0xme')
        t = state['tinkers']['Britain']
        check('the revisit for the rest keeps the clock of the first open', t['due'] == first_due and t['bought_out'])
        # Serpent's Hold after the first round: bought_out False, no clock yet -> the visit starts one
        S.buy_from = lambda v, st, e, tk: (19, 19, 14, 0)
        state = {'tinkers': {"Serpent's": {'bought_out': False}}}
        S.visit(v, state, {'loc': "Serpent's", 'name': "Serpent's"}, '0xme')
        check('no clock yet: the visit starts one', state['tinkers']["Serpent's"].get('due'))
        # gold short with room left: to the bank
        S.buy_from = lambda v, st, e, tk: (5, 19, 14, 14)
        S.gold_carried = lambda: 3
        state = {'tinkers': {}}
        try:
            S.visit(v, state, entry, '0xme')
            check('gold short, room left: NeedGold', False, 'no exception')
        except S.NeedGold:
            check('gold short, room left: NeedGold', True)
    finally:
        (S.find_tinkers, S.buy_from, S.gold_carried, S.shovel_room, S.save_state, S.gems.check_town,
         S.VISITS) = saved


def test_blocked_backoff():
    waits, sleeps = [], []
    saved = (S.recall_once, S.recall_reagents, S.time.sleep, S.say, S.BLOCKED_LOG, S.check_stop_file, S.taken,
             S.gems.check_town)
    log = os.path.join(tempfile.mkdtemp(), 'blocked.jsonl')
    S.BLOCKED_LOG = log
    S.recall_reagents = lambda: {'black pearl': 40, 'blood moss': 40, 'mandrake root': 40}
    S.say = lambda text: waits.append(text)
    S.check_stop_file = lambda: False
    S.taken = lambda: None
    S.gems.check_town = lambda v, me: None
    clock = [time.time()]
    real_time = S.time.time

    def fake_sleep(s):
        sleeps.append(s)
        clock[0] += s
    S.time.sleep = fake_sleep
    S.time.time = lambda: clock[0]
    rune = {'slot': 5, 'name': 'Magencia Tinker', 'spot': [3714, 2122], 'loc': 'Magencia'}
    entry = {'loc': 'Magencia', 'name': 'Magencia', 'runes': [rune]}
    try:
        S.recall_once = lambda state, e: None  # blocked every time
        try:
            S.recall_to({}, {}, entry, '0xme', True)
            check('always blocked: Blocked after the backoff', False, 'no exception')
        except S.Blocked:
            said = [w for w in waits if 'again in' in w]
            check('backoff 15, 30, 60, 120 s', [int(w.split('again in ')[1].split(' ')[0]) for w in said]
                  == [15, 30, 60, 120], said)
        rows = [json.loads(line) for line in open(log)]
        check('every blocked try logged', len(rows) == 5 and all(r['blocked'] for r in rows), rows)
        # clears on the third try
        tries = iter([None, None, {'x': 3714, 'y': 2122}])
        S.recall_once = lambda state, e: next(tries)
        st = S.recall_to({}, {}, entry, '0xme', True)
        rows = [json.loads(line) for line in open(log)]
        check('cleared on a later try: logged as cleared', st and rows[-1]['blocked'] is False and rows[-1]['try'] == 3)
        check('a blocked tinker is tried again in 10 minutes', S.SKIP_BLOCKED == 600)
        # reagents: too few to try again leaves town
        S.recall_once = lambda state, e: None
        S.recall_reagents = lambda: {'black pearl': 4, 'blood moss': 40, 'mandrake root': 40}
        try:
            S.recall_to({}, {}, entry, '0xme', True)
            check('too few reagents to try again: home', False, 'no exception')
        except S.gems.LeaveTown:
            check('too few reagents to try again: home', True)
    finally:
        (S.recall_once, S.recall_reagents, S.time.sleep, S.say, S.BLOCKED_LOG, S.check_stop_file, S.taken,
         S.gems.check_town) = saved
        S.time.time = real_time


def test_two_runes():
    """2026-11-24 17:00, the user: "I fixed it by creating 2 runes for each location. From now on we should alternate
    betweek rune 1 and 2 for each location"."""
    book = [{'slot': i, 'name': n, 'spot': [0, 0]} for i, n in enumerate([
        'Britain 1', 'Britain 2', 'Jhelom 1', 'Jhelom 2', 'Minoc 1', 'Minoc 2', 'Vesper 1', 'Vesper 2',
        "Serpent's 1", "Serpent's 2", 'Magencia 1', 'Magencia 2', 'Trinsic 1', 'Trinsic 2'])]
    locs = S.locations(book)
    check('14 runes, 7 towns, rune 1 then 2', list(locs) == ['Britain', 'Jhelom', 'Minoc', 'Vesper', "Serpent's",
                                                             'Magencia', 'Trinsic']
          and all([r['name'][-1] for r in l['runes']] == ['1', '2'] for l in locs.values()))
    # the old state (by slot, one rune a town) carried over by town
    saved = S.say
    S.say = lambda text: None
    state = {'tinkers': {'0': {'name': 'Britain Tinker', 'due': 1}, '6': {'name': 'Serpents Tinker', 'due': 2},
                         '5': {'name': 'Magencia Tinker', 'due': 3}}}
    S.rekey(state, locs)
    S.say = saved
    check('the old clocks carried over by town', state['tinkers'].get('Britain', {}).get('due') == 1
          and state['tinkers'].get("Serpent's", {}).get('due') == 2 and state['tinkers'].get('Magencia', {}).get('due') == 3
          and not any(k.isdigit() for k in state['tinkers']))
    # alternating, and the other rune at once when one is blocked
    used = []
    saved = (S.recall_once, S.recall_reagents, S.say, S.BLOCKED_LOG, S.check_stop_file, S.time.sleep)
    S.recall_reagents = lambda: {'black pearl': 40, 'blood moss': 40, 'mandrake root': 40}
    S.say = lambda text: None
    S.BLOCKED_LOG = os.path.join(tempfile.mkdtemp(), 'blocked.jsonl')
    S.check_stop_file = lambda: False
    S.time.sleep = lambda s: None
    try:
        blocked = set()
        S.recall_once = lambda st, rune: used.append(rune['name']) or (None if rune['name'] in blocked else {'x': 1})
        state = {}
        mag = locs['Magencia']
        for _ in range(3):
            S.recall_to({}, state, mag, '0xme', True)
        check('alternates rune 1, 2, 1', used == ['Magencia 1', 'Magencia 2', 'Magencia 1'], used)
        used.clear()
        blocked = {'Magencia 2'}
        S.recall_to({}, state, mag, '0xme', True)
        check('rune 2 blocked: rune 1 at once, no wait', used == ['Magencia 2', 'Magencia 1'], used)
        used.clear()
        S.recall_to({}, state, mag, '0xme', True)
        check('and next time rune 2 again (after the one that took him)', used[0] == 'Magencia 2', used)
    finally:
        S.recall_once, S.recall_reagents, S.say, S.BLOCKED_LOG, S.check_stop_file, S.time.sleep = saved


def test_reagent_reserve():
    check('3 of each kept for the way home (3 tries)', S.HOME_RESERVE == 3)
    check('on to a tinker needs 2 casts more', S.ONWARD_NEED == S.HOME_RESERVE + 2)
    check('to the bank and back needs 4 casts more', S.BANK_NEED == S.HOME_RESERVE + 4)
    saved = S.recall_reagents
    try:
        S.recall_reagents = lambda: {'black pearl': 5, 'blood moss': 5, 'mandrake root': 5}
        S.recall_reagents_ok(S.ONWARD_NEED, 'test')
        check('5 of each: on to the next tinker', True)
        try:
            S.recall_reagents_ok(S.BANK_NEED, 'test')
            check('5 of each: not to the bank and back', False, 'no exception')
        except S.gems.LeaveTown:
            check('5 of each: not to the bank and back', True)
    finally:
        S.recall_reagents = saved


def test_gold():
    saved = (S.status, S.est_price)
    S.status = lambda: {'weight': 90, 'weightMax': 390}
    S.est_price = lambda state: 14
    try:
        state = {'tinkers': {str(i): {'stock': 19, 'price': 14, 'bought_out': True} for i in range(7)}}
        need = S.round_need(state, list(range(7)))
        check('the need counts the hourly growth', need == 7 * (19 + S.GROWTH) * 14, need)
        carry = S.gold_to_carry(state, list(range(7)))
        load = (390 - S.WEIGHT_MARGIN - 90) // S.SHOVEL_STONES
        check('gold carried capped at 2 full loads (it weighs)', carry == int(S.GOLD_LOADS * load * 14), carry)
    finally:
        S.status, S.est_price = saved


def strip_comments(text):
    """The rules file is JSON with // comments (the bridge reads it so): the comments out, strings left alone."""
    out, i, in_str = [], 0, False
    while i < len(text):
        c = text[i]
        if in_str:
            out.append(c)
            if c == '\\':
                out.append(text[i + 1])
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith('//', i):
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        else:
            out.append(c)
        i += 1
    return ''.join(out)


def test_sync_areas():
    """A re-marked rune moves its tinker area in Clem's rules; the rest of the rules file is untouched."""
    import shutil
    d = tempfile.mkdtemp()
    path = os.path.join(d, 'rules-Clem.json')
    shutil.copy(os.path.join(HERE, 'rules', 'rules-Clem.json'), path)
    before = open(path, encoding='utf-8').read()
    saved = S.say
    S.say = lambda text: None
    try:
        entries = [{'slot': i, 'name': n, 'spot': p} for i, (n, p) in enumerate([
            ('Britain Tinker', [1424, 1661]), ('Jhelom Tinker', [1395, 3808]), ('Minoc Tinker', [2464, 453]),
            ('Trinsic Tinker', [1841, 2675]), ('Vesper Tinker', [2901, 786]), ('Magencia Tinker', [3720, 2130]),
            ('Serpents Tinker', [2942, 3510])])]
        changed = S.sync_areas(entries, path, agent_dir=False)
        after = open(path, encoding='utf-8').read()
        check('a moved rune: the rules change', changed)
        check('Magincia\'s area follows the new spot', '"box": [3695, 2105, 3745, 2155]' in after)
        strip = lambda t: [line for line in t.splitlines() if '"tinker: ' not in line]
        check('nothing else in the rules changes', strip(before) == strip(after))
        check('seven tinker areas, still', after.count('"name": "tinker: ') == 7)
        check('the same book again: no change', not S.sync_areas(entries, path, agent_dir=False))
        json.loads(strip_comments(after))
        check('the rules still parse', True)
    except ValueError as e:
        check('the rules still parse', False, repr(e))
    finally:
        S.say = saved


def test_pause_flag():
    saved = (S.PAUSE_FILE, S.STOP_FILE, S.say, dict(S.stopping))
    d = tempfile.mkdtemp()
    S.PAUSE_FILE, S.STOP_FILE = os.path.join(d, 'paused'), os.path.join(d, 'stop')
    S.say = lambda text: None
    S.stopping.clear()
    S.stopping['flag'] = False
    try:
        check('not paused: carries on', not S.check_stop_file())
        open(S.PAUSE_FILE, 'w').close()
        check('paused: the loop winds down as a pause, not a stop',
              S.check_stop_file() and S.stopping.get('pause') is True)
    finally:
        S.PAUSE_FILE, S.STOP_FILE, S.say = saved[:3]
        S.stopping.clear()
        S.stopping.update(saved[3])


def main():
    for t in (test_names, test_full_bag_check, test_clocks, test_migrate, test_visit_cycle, test_blocked_backoff,
              test_reagent_reserve, test_gold, test_sync_areas, test_pause_flag, test_two_runes):
        try:
            t()
        except Exception as e:
            import traceback
            check(t.__name__, False, f'{e!r}\n{traceback.format_exc()}')
    print(f'\n{len(failures)} failed' if failures else '\nall passed')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
