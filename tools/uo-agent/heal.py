#!/usr/bin/env python3
"""A character trains Healing with bandages on a ghost (see HEALING.md). Needs bridge 10 (build cuo-agent27).

  python3 -I heal.py run [--char Burgers] [--patient 0x000431CC] [--bandages 0x408DD58F] [--to 100.0]
                          bandage the patient again and again until Healing (base) reaches --to
  python3 -I heal.py stop     the running loop stops after the bandage it is on, and the command waits
  python3 -I heal.py report   start, now, gains and bandages per hour
  python3 -I heal.py rules    put the healing rules into the client (rules/rules-<char>-heal.json)

How this server does it (the user by hand, 2026-11-08 01:17): double-click the clean bandages ("Who will you use
the bandages on?"), aim at the ghost ("You begin applying the bandages."); about 9.9 s later "You are able to
resurrect your patient." (or "unable"). Starting another bandage before that cancels the one under way and nothing is
learned (the user's first six, 6-8 s apart, gave no result at all), so the next one starts the moment a bandage
ends, about every 10 s (the user: "every 10 seconds"); none ever starts sooner.

Stops by itself: Healing reached the target; the patient isn't a ghost any more (the resurrection was accepted), has
gone or is out of reach; the bandages are gone; the user took the character over (handOver: only they hand it back,
then `uo --char NAME resume` and run again). A world save or a lag the server answers after is waited out.

The loop sends nothing between bandages; it only reads (messages, skills). Logs to
~/claude/uo-agent-work/heal/heal.log, state in state.json there.
"""
import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import uo  # noqa: E402

HERE = os.path.dirname(os.path.realpath(__file__))
WORK = os.path.expanduser('~/claude/uo-agent-work/heal')
LOG = os.path.join(WORK, 'heal.log')
STATE = os.path.join(WORK, 'state.json')
PID = os.path.join(WORK, 'heal.pid')
STOP_FILE = os.path.join(WORK, 'stop')

CHAR = 'Burgers'
PATIENT = '0x000431CC'      # Isabel (a ghost on 2026-11-08), a tile south of Burgers
BANDAGES = '0x408DD58F'     # the pile of clean bandages on the tower floor at 1757,1408 (4770 on 2026-11-08)
SKILL = 'Healing'
TARGET = 100.0

BEGUN = 'you begin applying the bandages'
# a bandage that ended (RunUO's wording, which this server uses): the next one may start
ENDED = ('able to resurrect your patient', 'unable to resurrect your patient', 'you finish applying the bandages',
         'barely help', 'that being is not damaged', 'did not stay close enough', 'you have cured', 'failed to cure',
         'you heal what little damage', 'too far away', 'cannot be seen', 'bandages can not be used',
         'bandages cannot be used', 'you cannot heal', 'you cannot use', 'cannot be resurrected')
SLIPS = 'your fingers slip'
BANDAGE_TIMEOUT = 20        # seconds from "begin" with no end message: carry on anyway
LAG_RESUMES = []            # when the loop resumed after the server went quiet (at most 5 an hour)


class Stop(Exception):
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


def install_rules(char):
    shutil.copyfile(os.path.join(HERE, 'rules', f'rules-{char}-heal.json'),
                    os.path.join(uo.AGENT_DIR, f'rules-{char}.json'))


def restore_rules(char):
    """The character's usual rules back (Burgers': mining; mine.py writes them at its start anyway)."""
    usual = os.path.join(HERE, 'rules', f'rules-{char}.json')
    if os.path.exists(usual):
        shutil.copyfile(usual, os.path.join(uo.AGENT_DIR, f'rules-{char}.json'))


def skill(info):
    s = uo.call(info, 'GET', '/skills', name=SKILL)['skills'][0]
    return s['base'], s['value'], s['cap'], s['lock']


def patient(info, serial):
    for m in uo.call(info, 'GET', '/nearby', range=4).get('mobiles', []):
        if m['serial'].lower() == serial.lower():
            return m
    return None


def server_back(info, why):
    """The bridge stopped because the server didn't answer: a world save (waited out), or a lag. Wait up to 5
    minutes for any new message, then resume (at most 5 times an hour); True when resumed."""
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


def bandage(info, bandages, serial):
    """One bandage, start to end. Returns the end message ('' when none came in time)."""
    for attempt in range(3):
        try:
            r = uo.call(info, 'POST', '/use', serial=bandages, target=serial)
            break
        except uo.BridgeError as e:
            if e.code == 423 and 'took over' in e.message:
                raise Stop(f'the user took {info["character"]} over ({e.message}); only they hand him back')
            if e.code == 423 and server_back(info, e.message):
                continue
            raise Stop(f'/use: {e}')
    else:
        raise Stop('/use failed three times')
    texts = [m['text'] for m in r.get('messages', [])]
    if not r.get('targeted'):
        return 'no cursor: ' + ' | '.join(texts)
    if not any(BEGUN in t.lower() for t in texts):
        return ' | '.join(texts) or 'no answer'
    start = time.time()
    after = max([m['id'] for m in r.get('messages', [])] or [0])
    slips = 0
    while time.time() - start < BANDAGE_TIMEOUT:
        time.sleep(0.25)
        for m in uo.call(info, 'GET', '/messages', after=after)['messages']:
            after = max(after, m['id'])
            low = m['text'].lower()
            if SLIPS in low:
                slips += 1
            elif any(e in low for e in ENDED):
                return m['text'] + (f' ({slips} slips)' if slips else '') + f' after {time.time() - start:.1f} s'
    return f'no end message in {BANDAGE_TIMEOUT} s'


def run(char, serial, bandages, target):
    info = uo.find_bridge(char)
    if uo.call(info, 'GET', '/status').get('bridge', 0) < 10:
        raise Stop(f"{char}'s client has bridge {uo.call(info, 'GET', '/status').get('bridge')}: bandages need "
                   'bridge 10 (build cuo-agent27)')
    install_rules(char)
    state = load_state()
    base, value, cap, lock = skill(info)
    if state.get('char') != char or state.get('done'):
        state = {'char': char, 'skill': SKILL, 'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'startBase': base,
                 'bandages': 0, 'results': {}, 'gains': []}
    state.update(target=target, patient=serial, pile=bandages)
    save_state(state)
    say(f'{char}: {SKILL} {base} (shown {value}, cap {cap}, {lock}); bandaging {serial} until {target}')
    if lock != 'up':
        say(f'note: {SKILL} is set to {lock}, not up')
    last = base
    while True:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
            raise Stop('asked to stop')
        if base >= target or base >= cap:
            state['done'] = time.strftime('%Y-%m-%d %H:%M:%S')
            save_state(state)
            say(f'DONE: {SKILL} {base} after {state["bandages"]} bandages')
            return
        m = patient(info, serial)
        if m is None:
            raise Stop(f'the patient {serial} is not in sight')
        if not m.get('dead'):
            raise Stop(f'{m["name"]} is alive now (a resurrection was accepted?): no more bandages on a ghost')
        if m['distance'] > 1:
            raise Stop(f'{m["name"]} is {m["distance"]} tiles away (a bandage reaches 1)')
        try:
            pile = uo.call(info, 'GET', '/item', serial=bandages).get('item')
        except uo.BridgeError as e:
            raise Stop(f'the bandages {bandages} are gone ({e})')
        result = bandage(info, bandages, serial)
        state['bandages'] += 1
        key = result.split(' (')[0].split(' after ')[0]
        state['results'][key] = state['results'].get(key, 0) + 1
        base, value, cap, lock = skill(info)
        gained = round(base - last, 1)
        if gained:
            state['gains'].append([time.strftime('%Y-%m-%d %H:%M:%S'), base])
            last = base
        save_state(state)
        say(f'#{state["bandages"]}: {result}; {SKILL} {base}' + (f' (+{gained})' if gained > 0 else '') +
            f'; {pile.get("amount", "?")} bandages left')


def report():
    s = load_state()
    if not s:
        print('nothing yet')
        return
    print(json.dumps({k: v for k, v in s.items() if k != 'gains'}, indent=1))
    gains = s.get('gains', [])
    print(f'{len(gains)} gains; last: {gains[-5:]}')


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
    r = sub.add_parser('run')
    r.add_argument('--char', default=CHAR)
    r.add_argument('--patient', default=PATIENT)
    r.add_argument('--bandages', default=BANDAGES)
    r.add_argument('--to', type=float, default=TARGET)
    sub.add_parser('stop')
    sub.add_parser('report')
    sub.add_parser('rules').add_argument('--char', default=CHAR)
    args = p.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if args.cmd == 'stop':
        return stop()
    if args.cmd == 'report':
        return report()
    if args.cmd == 'rules':
        return install_rules(args.char)
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
        run(args.char, args.patient, args.bandages, args.to)
    except Stop as e:
        say(f'STOPPED: {e}')
        sys.exit(1)
    finally:
        os.remove(PID)
        restore_rules(args.char)


if __name__ == '__main__':
    main()
