#!/usr/bin/env python3
"""Record a character's path while the user walks it (read only: nothing is sent to the server).

  python3 record_route.py --char Icepick OUT.jsonl [--minutes 60]

Every half second it asks the bridge where the character is and writes each new spot as a line of JSON
({"t", "x", "y", "z"}), plus every message the server sends (with where the character was standing), so the
guards' "you have left the protection" line shows exactly where the guarded zone ends. Stops after --minutes,
when the character logs out, or when a file named STOP appears next to OUT.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import uo  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--char', required=True)
    parser.add_argument('out')
    parser.add_argument('--minutes', type=float, default=60)
    args = parser.parse_args()

    info = uo.find_bridge(args.char)
    stop_file = os.path.join(os.path.dirname(os.path.abspath(args.out)), 'STOP')
    end = time.time() + args.minutes * 60
    last_spot, steps = None, 0
    last_message = uo.call(info, 'GET', '/status')['lastMessageId']

    with open(args.out, 'a', encoding='utf-8') as fh:
        while time.time() < end and not os.path.exists(stop_file):
            try:
                s = uo.call(info, 'GET', '/status')
                messages = uo.call(info, 'GET', '/messages', after=last_message)['messages']
            except uo.BridgeError as e:
                print(f'bridge gone ({e}); stopping', flush=True)
                break
            stamp = time.strftime('%H:%M:%S')
            spot = (s['x'], s['y'], s['z'])
            if spot != last_spot:
                fh.write(json.dumps({'t': stamp, 'x': spot[0], 'y': spot[1], 'z': spot[2]}) + '\n')
                last_spot, steps = spot, steps + 1
            for m in messages:
                last_message = max(last_message, m['id'])
                if m['type'] in ('Label',):
                    continue
                fh.write(json.dumps({'t': stamp, 'x': spot[0], 'y': spot[1], 'z': spot[2], 'message': m['text'],
                                     'from': m.get('name') or '', 'type': m['type']}) + '\n')
                print(f"{stamp} at {spot[0]},{spot[1]}: {m.get('name') or ''}: {m['text']}", flush=True)
            fh.flush()
            time.sleep(0.5)
    print(f'recorded {steps} spots in {args.out}')


if __name__ == '__main__':
    main()
