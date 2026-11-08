#!/usr/bin/env python3
"""Icepick smelts the junk metal gear in the vault's smelting crates (see SMITHING.md, "Smelting in the vault").

  python3 -I vault.py smelt [--max N]   at his spot in the vault (1759,1409): every piece in the six smelting crates
                                        into his pack, smelted at the vault's forge and anvil with his hammer, and
                                        the new ingots into the bottom crate, smelting 6 (the user, 2026-11-07)
  python3 -I vault.py stop              the running smelt stops after the piece it is on
  python3 -I vault.py report            what's been smelted so far

The crates' copper keys stay where they are. A piece the server won't smelt goes back into its crate and is left
alone after that (listed in the state as not_smeltable). The ingots he already carries (his own, 856 on 2026-11-07)
stay in his pack: only what the gear gives goes to the bottom crate. Getting into the vault and out (the door always
ends locked and closed) is in SMITHING.md. Logs to ~/claude/uo-agent-work/vault/vault.log, state in state.json there.
"""
import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import uo  # noqa: E402
import smith  # noqa: E402  (the menus, the hammer, the smelt, the lag handling)

CHAR = 'Icepick'
HERE = os.path.dirname(os.path.realpath(__file__))
WORK = os.path.expanduser('~/claude/uo-agent-work/vault')
STATE = os.path.join(WORK, 'state.json')
PID = os.path.join(WORK, 'vault.pid')
STOP_FILE = os.path.join(WORK, 'stop')

SPOTS = ((1759, 1409), (1759, 1410))  # where the forge, the anvil and the crates are all in reach
FORGE = '0x4083A084'          # the vault's forge, 1758,1409
ANVIL = '0x408D4FB3'          # the anvil the user placed by it, 1758,1408 (2026-11-07: the hammer's menu needs both)
INGOT_CRATE = '0x408AD7D5'    # smelting 6, the bottom crate: the ingots go here (the user, 2026-11-07; the small
                              # crate by the forge they first named is gone)
CRATES = [                    # stacked at 1758,1411 (bottom to top: 6, 5, 1, 2, 3, 4)
    ('smelting 1', '0x4053812E'),
    ('smelting 2', '0x4053DA72'),
    ('smelting 3', '0x4053C008'),
    ('smelting 4', '0x4053CE6E'),
    ('smelting 5', '0x40538F75'),
    ('smelting 6', '0x408AD7D5'),
]
DEPOSIT_AT = 300              # ingots from the gear carried before they go to the bottom crate
NAMES = uo.load_names()       # the full names Johnny's sorting saw ("a durable bascinet of guarding")


def say(text):
    smith.say(text)


def load_state():
    try:
        with open(STATE, encoding='utf-8') as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def save_state(state):
    uo.write_json(STATE, state, 1)


def install_rules():
    shutil.copyfile(os.path.join(HERE, 'rules', 'rules-Icepick-vault.json'),
                    os.path.join(uo.AGENT_DIR, 'rules-Icepick.json'))


def is_ingot(item):
    return 'ingot' in (item.get('type') or '').lower() or 'ingot' in (item.get('name') or '').lower()


def iron(items):
    return sum(i.get('amount') or 1 for i in items if smith.is_ingots(i))


def hammer():
    for i in smith.pack():
        if i.get('graphic') in smith.HAMMER_GRAPHICS:
            return i['serial']
    raise smith.Stop('no hammer in his pack (the spares are in the grey bag downstairs)')


def to_smelt(serial, state):
    skip = set(state.get('not_smeltable', []))
    return [i for i in smith.contents(serial)
            if not i.get('container') and 'key' not in (i.get('type') or i.get('name') or '').lower()
            and not is_ingot(i) and i['serial'] not in skip]


def deposit(state, everything=False):
    """The ingots the gear gave (everything over his own stack, and any coloured ones) onto the bottom crate's pile."""
    own = state['own_ingots']
    items = smith.pack()
    extra = iron(items) - own
    if extra < (1 if everything else DEPOSIT_AT):
        return 0
    moved = 0
    pile = smith.ingot_stack(smith.contents(INGOT_CRATE))
    mine = smith.ingot_stack(items)
    if mine and extra > 0:
        smith.call('POST', '/move', serial=mine['serial'], to=pile['serial'] if pile else INGOT_CRATE,
                   amount=min(extra, mine.get('amount') or 1))
        moved += extra
    # coloured ingots from the gear (none of his own)
    for i in smith.pack():
        if is_ingot(i) and not smith.is_ingots(i) and i['serial'] not in state.get('own_other', []):
            smith.call('POST', '/move', serial=i['serial'], to=INGOT_CRATE)
            moved += i.get('amount') or 1
    t = state.setdefault('totals', {})
    t['ingots_to_crate'] = t.get('ingots_to_crate', 0) + moved
    in_crate = sum(i.get('amount') or 1 for i in smith.contents(INGOT_CRATE) if is_ingot(i))
    say(f"put {moved} ingots in the bottom smelting crate ({in_crate} there now)")
    save_state(state)
    return moved


def smelt_piece(state, crate_name, crate, piece):
    t = state.setdefault('totals', {})
    name = NAMES.get(piece['serial']) or piece.get('name') or piece.get('type') or piece.get('graphic')
    before = iron(smith.pack())
    smith.call('POST', '/move', serial=piece['serial'], to=smith.pack_serial())
    if not any(i['serial'] == piece['serial'] for i in smith.pack()):
        say(f"couldn't take {name} {piece['serial']} out of {crate_name}; left it")
        state.setdefault('not_smeltable', []).append(piece['serial'])
        return
    answer = smith.smelt_item(hammer(), piece['serial'])
    still = any(i['serial'] == piece['serial'] for i in smith.pack())
    got = iron(smith.pack()) - before
    if still:
        smith.call('POST', '/move', serial=piece['serial'], to=crate)
        state.setdefault('not_smeltable', []).append(piece['serial'])
        state.setdefault('not_smelted', []).append({'serial': piece['serial'], 'name': name, 'crate': crate_name,
                                                    'answer': answer})
        say(f"couldn't smelt {name} {piece['serial']} ({answer}); back in {crate_name}")
        return
    t['pieces'] = t.get('pieces', 0) + 1
    t['ingots'] = t.get('ingots', 0) + got
    c = state.setdefault('crates', {}).setdefault(crate_name, {'pieces': 0, 'ingots': 0})
    c['pieces'] += 1
    c['ingots'] += got
    say(f"smelted {name} {piece['serial']} from {crate_name}: {got} ingots ({answer}); "
        f"{t['pieces']} pieces, {t['ingots']} ingots so far")


def smelt(limit=None):
    state = load_state()
    s = smith.status()
    if (s['x'], s['y']) not in SPOTS:
        raise smith.Stop(f"Icepick is at {s['x']},{s['y']}, not at his spot in the vault {SPOTS}")
    smith.cancel_open_menus()
    items = smith.pack()
    if 'own_ingots' not in state:
        state['own_ingots'] = iron(items)
        state['own_other'] = [i['serial'] for i in items if is_ingot(i) and not smith.is_ingots(i)]
        state['started'] = time.strftime('%Y-%m-%d %H:%M:%S')
    hammer()
    smith.call('POST', '/open', serial=INGOT_CRATE)
    say(f"start: his own ingots {state['own_ingots']} stay in his pack; hammer {hammer()}")
    save_state(state)
    done = 0
    for crate_name, crate in CRATES:
        smith.call('POST', '/open', serial=crate)
        pieces = to_smelt(crate, state)
        say(f"{crate_name}: {len(pieces)} pieces to smelt")
        while pieces:
            if os.path.exists(STOP_FILE):
                deposit(state, everything=True)
                say('stopped (stop file)')
                return
            if limit is not None and done >= limit:
                deposit(state, everything=True)
                say(f'stopped after {done} pieces (--max)')
                return
            try:
                smelt_piece(state, crate_name, crate, pieces[0])
            except smith.Interrupted as e:
                say(f'interrupted ({e}); looking again')
            done += 1
            save_state(state)
            deposit(state)
            pieces = to_smelt(crate, state)
        deposit(state, everything=True)
    t = state.get('totals', {})
    in_crate = sum(i.get('amount') or 1 for i in smith.contents(INGOT_CRATE) if is_ingot(i))
    left = {n: len(to_smelt(c, state)) for n, c in CRATES}
    state['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    save_state(state)
    say(f"done: {t.get('pieces', 0)} pieces smelted into {t.get('ingots', 0)} ingots; {in_crate} ingots in the "
        f"bottom crate; not smelted: {len(state.get('not_smelted', []))}; left in the crates: {left}")


def stop():
    with open(STOP_FILE, 'w') as fh:
        fh.write(time.strftime('%Y-%m-%d %H:%M:%S'))
    print('asked to stop after the piece it is on')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('smelt')
    r.add_argument('--max', type=int)
    sub.add_parser('stop')
    sub.add_parser('report')
    args = p.parse_args()
    os.makedirs(WORK, exist_ok=True)
    smith.LOG = os.path.join(WORK, 'vault.log')
    if args.cmd == 'stop':
        return stop()
    if args.cmd == 'report':
        print(json.dumps(load_state(), indent=1))
        return
    smith.info = uo.find_bridge(CHAR)
    install_rules()
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)
    try:
        with open(PID, 'w') as fh:
            fh.write(str(os.getpid()))
        smelt(args.max)
    except smith.Stop as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
    finally:
        if os.path.exists(PID):
            os.remove(PID)


if __name__ == '__main__':
    main()
