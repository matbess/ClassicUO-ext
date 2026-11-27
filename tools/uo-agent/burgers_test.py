#!/usr/bin/env python3
"""Offline checks for burgers.py. Nothing is sent to the game. Run after any change, before a run:

  python3 -I burgers_test.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import burgers as B  # noqa: E402
import shovels_test as T  # noqa: E402

check, failures = T.check, T.failures


def test_names():
    missing = T.undefined_names(os.path.join(HERE, 'burgers.py'))
    check('burgers.py: every name it uses is defined', not missing, missing)


def test_parse_reagents():
    got = B.parse_reagents('black pearl=200, bloodmoss=150,mandrake=10,sulfrous ash=5')
    check('the mining agent\'s amounts are read, by any of the user\'s spellings',
          got == {'0x0F7A': 200, '0x0F7B': 150, '0x0F86': 10, '0x0F8C': 5}, got)


def test_needed():
    pack = {'0x0F7A': 34, '0x0F7B': 34, '0x0F86': 60, '0x0F8C': 35}
    bank = {'0x0F7A': 100, '0x0F7B': 250, '0x0F86': 0, '0x0F8C': 300}
    got = B.reagents_needed(pack, bank)
    check('his pack to 50 and his bank to 250 of each (none taken away)',
          got == {'0x0F7A': (16, 150), '0x0F7B': (16, 0), '0x0F86': (0, 250), '0x0F8C': (15, 0)}, got)
    got = B.reagents_needed(pack, bank, {'0x0F7A': 10, '0x0F7B': 100})
    check("the asked amounts: the pack's share first, the rest for the bank",
          got == {'0x0F7A': (10, 0), '0x0F7B': (16, 84), '0x0F86': (0, 0), '0x0F8C': (0, 0)}, got)


def test_share():
    left = {'0x0F7A': 300, '0x0F7B': 30, '0x0F86': 0, '0x0F8C': 3}
    got = B.share(left, 3, 100)
    check('an even part over the trips left', got == {'0x0F7A': 100, '0x0F7B': 10, '0x0F8C': 1}, got)
    got = B.share(left, 1, 100)
    check('all of it on the last trip when it fits', got == {'0x0F7A': 300, '0x0F7B': 30, '0x0F8C': 3}, got)
    got = B.share(left, 1, 16.5)
    check('cut to the weight (0.1 a reagent), in proportion', sum(got.values()) <= 165 and got.get('0x0F7A', 0) > 140, got)
    check('nothing when there is no room', B.share(left, 1, 0) == {}, B.share(left, 1, 0))


def test_rules():
    text = open(os.path.join(HERE, 'rules', 'rules-Burgers.json'), encoding='utf-8').read()
    new = B.rules_with_bank(text)
    rules = json.loads(T.strip_comments(new))
    names = [a['name'] for a in rules['areas']]
    check("Burgers' rules: the Ocllo bank added to his areas, the forge kept", names[0].startswith('Ocllo bank') and
          'forge' in names, names)
    box = rules['areas'][0]['box']
    check('the bank area holds both landing spots and the tiles round them',
          all(box[0] < p[0] < box[2] and box[1] < p[1] < box[3] for p in (B.CLEM_LANDS, B.BURGERS_LANDS)), box)
    check('full speed', rules['pacing']['gap'] == [1100, 1100], rules['pacing'])
    check('done twice, added once', B.rules_with_bank(new) == new)


def test_pick_bag():
    def bag(serial, x, z):
        return {'serial': serial, 'x': x, 'y': 2345, 'z': z}
    by_spot = {(944, 2345): [bag('a', 944, 0), bag('b', 944, 5)],
               (945, 2345): [bag('c', 945, 0), bag('d', 945, 5), bag('e', 945, 10)],
               (946, 2345): [bag('f', 946, 0)]}
    full = {'items': {'0x0F39': 30, '0x0F3A': 20}}
    cache = {s: full for s in 'abcdf'}
    cache['e'] = {'items': {'0x0F39': 12}}
    got = B.pick_bag(by_spot, cache)
    check("the top of the highest stack, but not a part-full bag: the next stack's top",
          got and got['serial'] == 'b', got)
    cache['e'] = full
    check('the top of the highest stack', B.pick_bag(by_spot, cache)['serial'] == 'e')
    cache['b'] = {'items': {'0x0F39': 49, '0x0F43': 1}}
    cache['e'] = cache['f'] = {'items': {}}
    check('none when no top bag holds 50 shovels', B.pick_bag(by_spot, cache) is None)


def test_loops():
    ps = '\n'.join(['/usr/bin/python3 -I mine.py --resume', '/bin/bash -c tail -F mine.log',
                    'Python -I shovels.py run --keep-count', 'vim heal.py'])
    bur, clem = B.loops_running(ps)
    check("mine.py running is Burgers' loop (not a tail of its log, not an editor)", bur == ['mine.py'], bur)
    check('the shovel loop is seen', clem == 'shovels.py', clem)
    check('nothing running', B.loops_running('/usr/bin/python3 -I look.py\n') == ([], None))


def test_bank_bags():
    src = open(os.path.join(HERE, 'burgers.py'), encoding='utf-8').read()
    check('the third bag stays in his pack (the user: only 2 go into the bank)',
          B.BANK_BAGS == 2 and 'to_bank=given < bank_bags' in src)
    check("a bag weighs 253 stones and he's checked for room before every trip",
          B.BAG_STONES == 253 and "room < BAG_STONES" in src)


def test_razor_click():
    ev = [{'time': '15:21:40.600', 'kind': 'sent pick up', 'serial': 'b'},
          {'time': '15:21:41.606', 'kind': 'sent drop', 'serial': 'b'},
          {'time': '15:21:41.697', 'kind': 'sent double-click', 'serial': 'b'}]
    check("Razor's AutoSearch: a click on the bag 0.09 s after its drop (15:21:41)", B.razor_click(ev, ev[2:]))
    late = dict(ev[2], time='15:21:43.000')
    check('a click two seconds later is the user', not B.razor_click(ev + [late], [late]))
    other = dict(ev[2], serial='c')
    check('a click on something else is the user', not B.razor_click(ev + [other], [other]))


def test_inside_of():
    got = {'item': {}, 'insideOf': [{'serial': '0x4093E516'}, {'serial': '0x0004344A', 'mobile': 'Clem'}]}
    check("the bridge's insideOf is the chain: the first is the container it's in (15:24:44)",
          B.inside_of(got) == '0x4093E516')
    check('on the ground: none', B.inside_of({'item': {}}) is None)


def test_reagents_separate():
    src = open(os.path.join(HERE, 'burgers.py'), encoding='utf-8').read()
    check('the reagents only on trips without a bag (Clem overloaded, 2026-11-26 15:29)', 'if not bag:' in src
          and "st['weight'] > st['weightMax'] - WEIGHT_MARGIN" in src)


def test_login_routine():
    src = open(os.path.join(HERE, 'burgers.py'), encoding='utf-8').read()
    check("the nightly reboot's login double-click is no takeover, for Clem and Burgers (2026-11-27 11:25)",
          src.count('login_resumed(') == 4 and 'uo.login_routine(i, taken)' in src)


def main():
    for t in (test_names, test_parse_reagents, test_needed, test_share, test_rules, test_pick_bag, test_loops,
              test_bank_bags, test_razor_click, test_inside_of, test_reagents_separate,
              test_login_routine):
        try:
            t()
        except Exception as e:
            import traceback
            check(t.__name__, False, f'{e!r}\n{traceback.format_exc()}')
    print(f'\n{len(failures)} failed' if failures else '\nall passed')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
