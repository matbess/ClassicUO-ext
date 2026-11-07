#!/usr/bin/env python3
"""The black box: follows every running client's bridge event log into
~/claude/uo-agent-work/blackbox/<Character>-<date>.jsonl, one JSON event per line.

The bridge keeps its event log in memory: what the client sent the server (after Razor: double-clicks, pick-ups,
drops, targets, skills, spells), and what the server and Razor said. A client restart wipes it, and some problems
can only be fixed by restarting (2026-11-06: Razor's drag queue jammed on a heavy crossbow until the user restarted
Clem's client). This keeps a copy on disk so it can be read afterwards.

Read-only: it only asks each bridge for /events, never sends anything to the game. It carries on across client
restarts (it rereads Agent/<Character>.json) and writes a "client started" line when a new client appears.

  blackbox.py            run until stopped
  blackbox.py --show N   print the last N events of each character's newest file
"""
import argparse
import datetime
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uo import AGENT_DIR, describe_event  # noqa: E402

OUT = os.path.expanduser('~/claude/uo-agent-work/blackbox')
EVERY = 1.0


def bridges():
    infos = []
    for path in glob.glob(os.path.join(AGENT_DIR, '*.json')):
        try:
            with open(path, encoding='utf-8-sig') as fh:
                info = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(info, dict) and 'port' in info and 'token' in info and 'character' in info:
            infos.append(info)
    return infos


def get_events(info, after):
    query = urllib.parse.urlencode({'after': after})
    request = urllib.request.Request(f"http://127.0.0.1:{info['port']}/events?{query}",
                                     headers={'Authorization': f"Bearer {info['token']}"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def write(character, record):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{character}-{datetime.date.today().isoformat()}.jsonl")
    with open(path, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(record) + '\n')


def run():
    # character -> [the client's start time, last event id read, whether it answered last time]
    seen = {}
    print(f'black box: recording into {OUT}', flush=True)
    while True:
        for info in bridges():
            name = info['character']
            state = seen.get(name)
            if state is None or state[0] != info.get('started'):
                # a client we haven't read yet: everything it still has
                state = seen[name] = [info.get('started'), 0, True]
                write(name, {'blackbox': 'client started', 'started': info.get('started'),
                             'at': datetime.datetime.now().isoformat(timespec='milliseconds')})
            try:
                result = get_events(info, state[1])
            except (urllib.error.URLError, OSError, ValueError):
                if state[2]:
                    write(name, {'blackbox': 'client not answering',
                                 'at': datetime.datetime.now().isoformat(timespec='milliseconds')})
                    state[2] = False
                continue
            state[2] = True
            for e in result.get('events', []):
                state[1] = max(state[1], e.get('id', 0))
                write(name, e)
        time.sleep(EVERY)


def show(n):
    for character in sorted({os.path.basename(p).split('-')[0] for p in glob.glob(os.path.join(OUT, '*.jsonl'))}):
        newest = sorted(glob.glob(os.path.join(OUT, f'{character}-*.jsonl')))[-1]
        with open(newest, encoding='utf-8') as fh:
            lines = fh.readlines()[-n:]
        print(f'== {character} ({newest})')
        for line in lines:
            e = json.loads(line)
            print(f"   {e['blackbox']} {e.get('started') or ''} at {e['at']}" if 'blackbox' in e else describe_event(e))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--show', type=int, metavar='N')
    args = parser.parse_args()
    if args.show:
        show(args.show)
    else:
        try:
            run()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
