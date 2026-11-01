#!/usr/bin/env python3
"""Talk to the ClassicUO agent bridge.

  uo status                    where the character is, what it holds
  uo nearby [range] [--containers]
  uo item SERIAL               an item and the containers it is inside
  uo contents SERIAL [--depth N]
  uo open SERIAL               open a container (containers only)
  uo name SERIAL[,SERIAL...]   single-click items and show what the server calls them
  uo messages [--after ID]
  uo label SERIAL TEXT         remember what a container is for (kept in labels.json here)
  uo labels                    list the remembered labels
  uo close SERIAL              close a container's window on screen
  uo walk X Y | --to SERIAL [--distance N]
  uo move SERIAL TO [--at X Y] [--amount N]
                               move an item into a container, or onto a stack of the same kind;
                               with --amount, only that many from a stack (the rest stays as a new item)
  uo equip SERIAL              put an item on (into the hands for a wand)
  uo use SERIAL TARGET         use an item held in the hands (a wand) on a target
  uo cancel                    cancel a target cursor
  uo rules                     show Agent/rules.json as the bridge sees it
  uo resume                    carry on after the bridge stopped because the server went quiet
  uo actions                   what the bridge sent and when, next to the server's "You must wait"
  uo clear                     is anyone else in the agent's area? (exit code 0 when clear)
  uo waitclear [--every SECS]  check every minute until the area is clear

Wherever a SERIAL is expected, a label (or a unique part of one) also works.

Options: --char NAME picks the character when several have the bridge on; --json prints raw JSON.
"""
import argparse
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

LABELS = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'labels.json')
# names the server gave items (identified names survive client restarts here; serials never change)
NAMES = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'names.json')
AGENT_DIR = os.path.expanduser(
    '~/Applications/Sikarugir/ClassicUO-Wine10.app/Contents/SharedSupport/prefix/drive_c/ClassicUO/Agent')


class BridgeError(Exception):
    """The bridge refused (code is the HTTP status) or couldn't be reached (code 0)."""

    def __init__(self, code, message):
        super().__init__(f'{code}: {message}' if code else message)
        self.code = code
        self.message = message


def find_bridge(character):
    infos = []
    for path in sorted(glob.glob(os.path.join(AGENT_DIR, '*.json'))):
        try:
            with open(path, encoding='utf-8-sig') as fh:
                infos.append(json.load(fh))
        except (OSError, ValueError):
            pass
    if character:
        infos = [i for i in infos if character.lower() in i.get('character', '').lower()]
    if len(infos) > 1:
        # a client that crashed or was killed leaves its file behind
        infos = [i for i in infos if is_alive(i)] or infos
    if not infos:
        sys.exit('No agent bridge is running' + (f' for "{character}"' if character else '') +
                 '. Tick the option in Options > Experimental on that character.')
    if len(infos) > 1:
        names = ', '.join(i['character'] for i in infos)
        sys.exit(f'Several bridges are running ({names}); pick one with --char.')
    return infos[0]


def resolve(text):
    """A serial, or a container label from labels.json."""
    if text.lower().startswith('0x') or text.isdigit():
        return text
    labels = load_labels()
    exact = [s for s, l in labels.items() if l.lower() == text.lower()]
    found = exact or [s for s, l in labels.items() if text.lower() in l.lower()]
    if len(found) == 1:
        return found[0]
    sys.exit(f'No single label matches "{text}"' + (': ' + ', '.join(labels[s] for s in found) if found else ''))


def others_in_area(info):
    """Names of other people (or ghosts) in the area, the same check the bridge makes before acting."""
    rules = call(info, 'GET', '/rules')
    near = call(info, 'GET', '/nearby', range=24)
    x1, y1, x2, y2 = rules['area']
    zmin, zmax = rules['z']
    ignore = {n.lower() for n in rules['ignorePeople']}
    return [m['name'] or 'someone' for m in near['mobiles']
            if (m['human'] or m['dead']) and (m['name'] or '').lower() not in ignore
            and x1 <= m['x'] <= x2 and y1 <= m['y'] <= y2 and zmin <= m['z'] <= zmax]


def on_floor(info, serial):
    """The item itself, or the outermost container holding it, if that is on the floor; None if carried."""
    found = call(info, 'GET', '/item', serial=serial)
    ground = [i for i in [found['item']] + found['insideOf'] if 'distance' in i]
    return ground[-1] if ground else None


def walk_near(info, serial, reach=1):
    """Walk next to the item (or the container on the floor holding it) when it's out of reach.
    The server ignores a double-click or a lift from more than 2 tiles away without saying anything."""
    spot = on_floor(info, serial)
    if not spot or spot['distance'] <= reach:
        return
    call(info, 'POST', '/walk', to=spot['serial'], distance=reach)
    spot = on_floor(info, serial)
    if spot['distance'] > 2:
        raise BridgeError(0, f"Couldn't get within reach of {spot['serial']} ({spot['distance']} tiles away)")


def move(info, serial, to, x=None, y=None, amount=None):
    """Move an item, carrying it in the backpack when the item and its destination are too far apart to reach both."""
    source, target = on_floor(info, serial), on_floor(info, to)
    if source and target and max(abs(source['x'] - target['x']), abs(source['y'] - target['y'])) <= 4 \
            and (source['distance'] > 2 or target['distance'] > 2):
        # close enough together: try to stand where both are within reach
        try:
            call(info, 'POST', '/walk', x=(source['x'] + target['x']) // 2, y=(source['y'] + target['y']) // 2, distance=1)
        except BridgeError as e:
            if e.code != 409 or 'paused' in e.message:
                raise
        source, target = on_floor(info, serial), on_floor(info, to)
    if source and target and source['distance'] <= 2 and target['distance'] <= 2:
        pass
    elif source:
        walk_near(info, serial)
        target = on_floor(info, to)
        if target and target['distance'] > 2:
            backpack = call(info, 'GET', '/status')['backpack']['serial']
            carried = call(info, 'POST', '/move', serial=serial, to=backpack, amount=amount)
            if not carried['moved']:
                return carried
            amount = None  # the part carried is now an item of its own
            walk_near(info, to)
    elif target:
        walk_near(info, to)
    # the server only tells us about a drop into a container we've opened since logging in; without that the
    # bridge hears nothing back and stops, so open one the client knows nothing about first
    dest = call(info, 'GET', '/item', serial=to)['item']
    if dest.get('container') and not dest.get('open') and not dest.get('knownItems'):
        walk_near(info, to)
        call(info, 'POST', '/open', serial=to)
        call(info, 'POST', '/close', serial=to)
    return call(info, 'POST', '/move', serial=serial, to=to, x=x, y=y, amount=amount)


def wait_out_world_save(info, error):
    """If the bridge stopped because a world save froze the server, wait for the save to finish, resume and return
    True. Any other stop returns False and stays stopped for the user to look at."""
    if error.code != 423:
        return False
    texts = [m['text'].lower() for m in call(info, 'GET', '/messages')['messages'][-15:]]
    if not any('world will save' in t or 'world save' in t for t in texts):
        return False
    for _ in range(60):  # saves take seconds; give up after five minutes
        texts = [m['text'].lower() for m in call(info, 'GET', '/messages')['messages'][-15:]]
        if any('world save complete' in t for t in texts):
            call(info, 'POST', '/resume')
            return True
        time.sleep(5)
    return False


def is_alive(info):
    request = urllib.request.Request(f"http://127.0.0.1:{info['port']}/status",
                                     headers={'Authorization': f"Bearer {info['token']}"})
    try:
        with urllib.request.urlopen(request, timeout=2):
            return True
    except (urllib.error.URLError, OSError):
        return False


def call(info, method, path, **params):
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"http://127.0.0.1:{info['port']}{path}" + (f'?{query}' if query else '')
    request = urllib.request.Request(url, method=method, headers={'Authorization': f"Bearer {info['token']}"})
    try:
        # paced actions are slow (a dozen names take half a minute), so allow plenty of time
        with urllib.request.urlopen(request, timeout=600) as response:
            result = json.load(response)
            remember_names(result)
            return result
    except urllib.error.HTTPError as e:
        try:
            message = json.load(e).get('error', e.reason)
        except ValueError:
            message = e.reason
        raise BridgeError(e.code, message)
    except (TimeoutError, OSError) as e:
        if isinstance(e, urllib.error.URLError):
            raise BridgeError(0, f"Can't reach the bridge for {info['character']} ({e.reason}). Is that client still logged in?")
        raise BridgeError(0, f'No answer from the bridge ({e}); it may still be busy with the request')
    except urllib.error.URLError as e:
        raise BridgeError(0, f"Can't reach the bridge for {info['character']} ({e.reason}). Is that client still logged in?")


def load_names():
    try:
        with open(NAMES, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def remember_names(result):
    """Keep every item name seen in a bridge answer."""
    found = {}

    def walk(o):
        if isinstance(o, dict):
            if 'serial' in o and 'graphic' in o and o.get('name'):
                found[o['serial']] = o['name']
            if 'serial' in o and o.get('answered') and o.get('lines'):
                found[o['serial']] = ' / '.join(o['lines'])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(result)
    if found:
        names = load_names()
        if any(names.get(k) != v for k, v in found.items()):
            names.update(found)
            with open(NAMES, 'w', encoding='utf-8') as fh:
                json.dump(names, fh, indent=1, sort_keys=True)


def load_labels():
    try:
        with open(LABELS, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_label(serial, text):
    labels = load_labels()
    labels['0x' + serial[2:].upper().zfill(8)] = text
    with open(LABELS, 'w', encoding='utf-8') as fh:
        json.dump(labels, fh, indent=2, sort_keys=True)


def describe(item, indent=''):
    if not item.get('name') and load_names().get(item['serial']):
        item = dict(item, name=load_names()[item['serial']])
    text = f"{indent}{item['serial']}  {item.get('name') or item['type']}"
    label = load_labels().get(item['serial'])
    if label:
        text = f"{indent}{item['serial']}  <{label}>  {item.get('name') or item['type']}"
    if item.get('name') and item['type'] and item['type'].lower() not in item['name'].lower():
        text += f"  ({item['type']})"
    if item.get('amount'):
        text += f"  x{item['amount']}"
    if item.get('hue'):
        text += f"  hue {item['hue']}"
    if item.get('container'):
        text += f"  [container, {item['knownItems']} known items{', open' if item.get('open') else ''}]"
    if 'distance' in item:
        text += f"  at {item['x']},{item['y']},{item['z']} ({item['dx']:+},{item['dy']:+}, {item['distance']} tiles)"
    else:
        text += f"  @{item['x']},{item['y']}"
    if item.get('layer'):
        text += f"  worn on {item['layer']}"
    return text


def print_items(items, indent=''):
    for item in items:
        print(describe(item, indent))
        if 'items' in item:
            print_items(item['items'], indent + '    ')


def print_messages(messages):
    for m in messages:
        who = f"{m['name']}: " if m.get('name') else ''
        about = f" [{m['serial']}]" if m.get('serial') else ''
        print(f"#{m['id']} {m['time']} {m['type']}{about} {who}{m['text']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--char')
    parser.add_argument('--json', action='store_true')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    p = sub.add_parser('nearby')
    p.add_argument('range', nargs='?', type=int)
    p.add_argument('--containers', action='store_true')
    sub.add_parser('item').add_argument('serial')
    p = sub.add_parser('contents')
    p.add_argument('serial')
    p.add_argument('--depth', type=int)
    sub.add_parser('open').add_argument('serial')
    sub.add_parser('name').add_argument('serial')
    sub.add_parser('messages').add_argument('--after', type=int)
    p = sub.add_parser('label')
    p.add_argument('serial')
    p.add_argument('text', nargs='+')
    sub.add_parser('labels')
    sub.add_parser('close').add_argument('serial')
    p = sub.add_parser('walk')
    p.add_argument('x', nargs='?', type=int)
    p.add_argument('y', nargs='?', type=int)
    p.add_argument('--to')
    p.add_argument('--distance', type=int)
    p = sub.add_parser('move')
    p.add_argument('serial')
    p.add_argument('to')
    p.add_argument('--at', nargs=2, type=int, metavar=('X', 'Y'))
    p.add_argument('--amount', type=int)
    sub.add_parser('equip').add_argument('serial')
    p = sub.add_parser('use')
    p.add_argument('serial')
    p.add_argument('target')
    sub.add_parser('cancel')
    sub.add_parser('rules')
    sub.add_parser('clear')
    sub.add_parser('resume')
    sub.add_parser('actions')
    sub.add_parser('waitclear').add_argument('--every', type=int, default=60)
    args = parser.parse_args()

    if args.command in ('label', 'labels'):
        if args.command == 'label':
            save_label(args.serial if args.serial.lower().startswith('0x') else f'0x{int(args.serial):08X}',
                       ' '.join(args.text))
        labels = load_labels()
        for serial, text in sorted(labels.items(), key=lambda kv: kv[1]):
            print(f'{serial}  {text}')
        return

    info = find_bridge(args.char)
    c = args.command
    if c in ('clear', 'waitclear'):
        while True:
            others = others_in_area(info)
            stamp = time.strftime('%H:%M:%S')
            if not others:
                print(f'{stamp} clear')
                return
            print(f"{stamp} occupied: {', '.join(others)}", flush=True)
            if c == 'clear':
                sys.exit(1)
            time.sleep(args.every)

    for name in ('serial', 'to', 'target'):
        if getattr(args, name, None):
            setattr(args, name, resolve(getattr(args, name)))

    if c == 'status':
        result = call(info, 'GET', '/status')
    elif c == 'nearby':
        result = call(info, 'GET', '/nearby', range=args.range, containers=1 if args.containers else None)
    elif c == 'item':
        result = call(info, 'GET', '/item', serial=args.serial)
    elif c == 'contents':
        result = call(info, 'GET', '/contents', serial=args.serial, depth=args.depth)
    elif c == 'open':
        walk_near(info, args.serial)
        result = call(info, 'POST', '/open', serial=args.serial)
    elif c == 'name':
        result = call(info, 'POST', '/name', serial=args.serial)
    elif c == 'close':
        result = call(info, 'POST', '/close', serial=args.serial)
    elif c == 'walk':
        if args.to is None and (args.x is None or args.y is None):
            sys.exit('walk needs X Y or --to SERIAL')
        result = call(info, 'POST', '/walk', x=args.x, y=args.y, to=args.to, distance=args.distance)
    elif c == 'move':
        x, y = args.at if args.at else (None, None)
        result = move(info, args.serial, args.to, x, y, args.amount)
    elif c == 'equip':
        result = call(info, 'POST', '/equip', serial=args.serial)
    elif c == 'use':
        result = call(info, 'POST', '/use', serial=args.serial, target=args.target)
    elif c == 'cancel':
        result = call(info, 'POST', '/cancel')
    elif c == 'rules':
        result = call(info, 'GET', '/rules')
    elif c == 'resume':
        result = call(info, 'POST', '/resume')
    elif c == 'actions':
        sent = call(info, 'GET', '/actions')
        waits = [m for m in call(info, 'GET', '/messages')['messages'] if 'must wait' in m['text'].lower()]
        events = [(a['time'], f"sent {a['what']} {a['serial']}") for a in sent] + [(m['time'], '  SERVER: ' + m['text']) for m in waits]
        for t, text in sorted(events):
            print(t, text)
        return
    else:
        result = call(info, 'GET', '/messages', after=args.after)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    if c == 'status':
        r = result
        if r.get('halted'):
            print(f"STOPPED: the server went quiet ({r['halted']}). Check the game, then 'uo resume'.")
        print(f"{r['character']} {r['serial']} at {r['x']},{r['y']},{r['z']} map {r['map']}")
        print(f"hits {r['hits']}/{r['hitsMax']}  stamina {r['stamina']}/{r['staminaMax']}  mana {r['mana']}/{r['manaMax']}"
              f"  weight {r['weight']}/{r['weightMax']}")
        flags = [f for f in ('warMode', 'hidden', 'dead', 'targeting') if r.get(f)]
        if flags or r.get('holding'):
            print('state:', ', '.join(flags + ([f"holding {r['holding']}"] if r.get('holding') else [])))
        if r.get('backpack'):
            print('backpack:', describe(r['backpack']))
        for item in r['hands']:
            print('in hand:', describe(item))
        print(f"last message #{r['lastMessageId']}")
    elif c == 'nearby':
        print(f"you are at {result['you']['x']},{result['you']['y']},{result['you']['z']}")
        print_items(result['items'])
        for m in result['mobiles']:
            tags = [t for t in ('human', 'yourPet', 'dead', 'hidden') if m.get(t)]
            print(f"{m['serial']}  {m['name'] or '?'}  body {m['body']}  {m['notoriety']}"
                  f"  at {m['x']},{m['y']},{m['z']} ({m['dx']:+},{m['dy']:+}, {m['distance']} tiles)"
                  + (f"  [{', '.join(tags)}]" if tags else ''))
    elif c == 'item':
        print(describe(result['item']))
        for parent in result['insideOf']:
            if parent.get('mobile') is not None:
                print(f"  carried by {parent['mobile']} {parent['serial']}")
            elif parent.get('unknown'):
                print(f"  inside {parent['serial']} (not known to the client)")
            else:
                print('  inside', describe(parent))
    elif c in ('contents', 'open'):
        if c == 'open':
            print_messages(result['messages'])
            if not result['opened']:
                print('not opened')
                return
            result = result['contents']
        print(describe(result['container']))
        print_items(result['items'], '    ')
    elif c in ('close', 'cancel', 'rules', 'resume'):
        print(json.dumps(result))
    elif c == 'walk':
        print(('arrived' if result['arrived'] else f"stopped {result['tilesLeft']} tiles short") +
              f" at {result['x']},{result['y']},{result['z']}")
    elif c in ('move', 'equip', 'use'):
        done = result.get('moved', result.get('equipped', result.get('targeted')))
        print({'move': 'moved' if done else 'NOT moved', 'equip': 'equipped' if done else 'NOT equipped',
               'use': 'used' if done else 'NOT used (no target cursor)'}[c] +
              (' (merged into the stack)' if result.get('mergedIntoStack') else ''))
        if result.get('item'):
            print(describe(result['item']))
        if result.get('target'):
            print('target:', describe(result['target']))
        print_messages(result['messages'])
    elif c == 'name':
        for r in result:
            print(f"{r['serial']}  " + (' / '.join(r['lines']) if r['answered'] else '(no answer)'))
    else:
        print_messages(result['messages'])
        print(f"last message #{result['lastMessageId']}")


if __name__ == '__main__':
    try:
        main()
    except BridgeError as e:
        sys.exit(str(e))
