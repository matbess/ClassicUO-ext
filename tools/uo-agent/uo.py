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
  uo use SERIAL                use a tool the rules allow (a smith's hammer) and show the menu, gump or cursor
                               the server answers with (bridge 6)
  uo use SERIAL --at X Y Z [--graphic G] [--reach N]
                               use a tool on a spot on the map: a pickaxe on rock (graphic 0 = the ground),
                               ore on a forge (the forge's graphic)
  uo tiles [range]             the ground and statics around the character (what rock there is to mine)
  uo give SERIAL TO [--amount N]
                               drop a carried item on a partner character: opens the trade window
  uo trade accept|unaccept|cancel
  uo cast SPELL TARGET         cast an allowed spell (32 = Recall) on a carried item (a rune)
  uo say TEXT                  say one of the allowed words ("bank")
  uo guard on|off              the guard: stops work if anyone talks, loiters, attacks or steals (on also
                               clears an alarm once the person has gone)
  uo skill ID                  use an allowed skill (21 = Hiding)
  uo dismount | uo mount SERIAL
                               get off the horse / on one of the mounts named in the rules
  uo alarm                     the last guard alarm (Agent/alarm.json) and the alarm log
  uo logout                    log the character out now
  uo animations                the animations the server sent for characters nearby (to tell NPCs by their idle
                               fidgets), and the NPCs learned that way (Agent/npcs-learned.json)
  uo cancel                    cancel a target cursor
  uo rules                     show the rules as the bridge sees them (Agent/rules-NAME.json or rules.json)
  uo resume                    carry on after the bridge stopped because the server went quiet
  uo actions                   what the bridge sent and when, next to the server's "You must wait"
  uo clear                     is anyone else in the agent's area? (exit code 0 when clear)
  uo waitclear [--every SECS]  check every minute until the area is clear

Bridge 6 (build cuo-agent19 on): menus, gumps, target cursors, skills and the event log
  uo skills [NAME]             skills: value, base, cap, lock, and the total
  uo gumps                     the menus and gumps open now, with their items, buttons and text
  uo menu SERIAL ID INDEX      choose an item in a menu (from 1; 0 cancels)
  uo gump SERIAL ID BUTTON [--switches 1,2]
                               press a button in a gump (0 closes it)
  uo target SERIAL | --cancel  answer the server's target cursor with an item in reach
  uo events [--after ID]       what happened: messages, menus and gumps shown, cursors, skill changes, and what
                               the client sent (double-clicks, menu choices, buttons, targets), the user's too
  uo record FILE               follow the event log into FILE (JSON lines) until Ctrl-C: record a task done by
                               hand

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
    """The bridge of the named character; with no name, $UO_CHAR's (UO_CHAR=Johnny for sorting while Icepick and
    Burgers are logged in too), or the only one running."""
    character = character or os.environ.get('UO_CHAR')
    infos = []
    for path in sorted(glob.glob(os.path.join(AGENT_DIR, '*.json'))):
        try:
            with open(path, encoding='utf-8-sig') as fh:
                infos.append(json.load(fh))
        except (OSError, ValueError):
            pass
    # rules files and the guard's alarm.json sit in the same folder
    infos = [i for i in infos if isinstance(i, dict) and 'port' in i and 'token' in i]
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
    ignore = {n.lower() for n in rules['ignorePeople'] + rules.get('partners', [])}

    def inside(m):
        return any(a['box'][0] <= m['x'] <= a['box'][2] and a['box'][1] <= m['y'] <= a['box'][3]
                   and a['z'][0] <= m['z'] <= a['z'][1] for a in rules['areas'])

    return [m['name'] or 'someone' for m in near['mobiles']
            if (m['human'] or m['dead']) and (m['name'] or '').lower() not in ignore and inside(m)]


def read_alarm():
    """The guard's last alarm (Agent/alarm.json), or None."""
    try:
        with open(os.path.join(AGENT_DIR, 'alarm.json'), encoding='utf-8-sig') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


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
    # the server only tells us about a drop into a container we've opened since logging in; without that the
    # bridge hears nothing back and stops, so open one the client knows nothing about
    # first (before standing where both ends are in reach)
    dest = call(info, 'GET', '/item', serial=to)['item']
    if dest.get('container') and not dest.get('open') and not dest.get('knownItems'):
        walk_near(info, to)
        call(info, 'POST', '/open', serial=to)
        call(info, 'POST', '/close', serial=to)
    source, target = on_floor(info, serial), on_floor(info, to)
    if source and target and max(abs(source['x'] - target['x']), abs(source['y'] - target['y'])) <= 4 \
            and (source['distance'] > 2 or target['distance'] > 2):
        # close enough together: try to stand where both are within reach
        try:
            call(info, 'POST', '/walk', x=(source['x'] + target['x']) // 2, y=(source['y'] + target['y']) // 2, distance=0)
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


def resume_after_fizzle(info, error):
    """A spell that fizzles is said by the caster ("The spell fizzles."), not as a system message, so the bridge
    (before cuo-agent14) takes it for silence and stops. If that's what happened, resume and return True."""
    if error.code != 423:
        return False
    said = [m['text'].lower() for m in call(info, 'GET', '/messages')['messages'][-4:]]
    if not any('fizzles' in t for t in said):
        return False
    call(info, 'POST', '/resume')
    return True


def resume_after_barrel_emptied(info, error):
    """The 50th item in the trash barrel makes it empty itself, deleting the item just dropped. The barrel says so
    itself ("The trash is full! Emptying!"), not as a system message, so the bridge takes it for silence and stops.
    If that's what happened, resume and return True: the item is gone, as it was meant to be."""
    if error.code != 423:
        return False
    said = [m['text'].lower() for m in call(info, 'GET', '/messages')['messages'][-3:]]
    if not any('trash is full' in t for t in said):
        return False
    call(info, 'POST', '/resume')
    return True


def is_alive(info):
    request = urllib.request.Request(f"http://127.0.0.1:{info['port']}/status",
                                     headers={'Authorization': f"Bearer {info['token']}"})
    try:
        with urllib.request.urlopen(request, timeout=2):
            return True
    except (urllib.error.URLError, OSError):
        return False


def _keep_both(pairs):
    """Bridge 6's /events gave sent menu choices and gump buttons an "id" field (the menu's or gump's) beside the
    event's own "id"; keep the event's, and the other as "menu" (renamed in the bridge from build cuo-agent20)."""
    d = {}
    for k, v in pairs:
        if k in d:
            k = 'menu' if k == 'id' else k + '2'
        d[k] = v
    return d


def call(info, method, endpoint, **params):
    # (the endpoint isn't called "path": /travel takes a query parameter of that name)
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"http://127.0.0.1:{info['port']}{endpoint}" + (f'?{query}' if query else '')
    request = urllib.request.Request(url, method=method, headers={'Authorization': f"Bearer {info['token']}"})
    try:
        # paced actions are slow (a dozen names take half a minute), so allow plenty of time
        with urllib.request.urlopen(request, timeout=600) as response:
            result = json.load(response, object_pairs_hook=_keep_both)
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
            write_json(NAMES, names, 1)


def write_json(path, data, indent):
    """Write a shared file in one step: sorting and mining run side by side, and a reader must never see a
    half-written names.json or labels.json (it would load as empty and the next write would wipe it)."""
    tmp = f'{path}.{os.getpid()}.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=indent, sort_keys=True)
    os.replace(tmp, path)


def load_labels():
    try:
        with open(LABELS, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_label(serial, text):
    labels = load_labels()
    labels['0x' + serial[2:].upper().zfill(8)] = text
    write_json(LABELS, labels, 2)


def forget_labels(serials):
    """Drop the labels of containers that are gone (a bag the user took out of the bank)."""
    labels = load_labels()
    gone = [s for s in serials if labels.pop('0x' + s[2:].upper().zfill(8), None) is not None]
    if gone:
        write_json(LABELS, labels, 2)
    return gone


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


def print_trade(trade):
    if not trade:
        print('trade: none open')
        return
    print(f"trade with {trade['partnerName']} {trade['partner']}: "
          f"me {'ACCEPTING' if trade['imAccepting'] else 'not accepting'}, "
          f"them {'ACCEPTING' if trade['heIsAccepting'] else 'not accepting'}")
    for side in ('mine', 'his'):
        for item in trade[side]:
            print(f"  {side}: {describe(item)}")


def print_dialog(d, indent=''):
    """A menu or gump from the bridge (bridge 6)."""
    head = f"{indent}{d['kind']} {d['serial']} id {d['id']}"
    if d['kind'] != 'gump':
        print(f"{head}: {d.get('title')!r}")
        for item in d['items']:
            print(f"{indent}  {item['index']:3}  {item['name']}" + (f"  ({item['graphic']})" if item.get('graphic') else ''))
        return
    print(head)
    for b in d['buttons']:
        print(f"{indent}  button {b['button']:<6} {b.get('label') or ''}  @{b['x']},{b['y']}")
    for s in d['switches']:
        print(f"{indent}  switch {s['switch']:<6} {'on ' if s['on'] else 'off'} {s.get('label') or ''}")
    for t in d['texts']:
        print(f"{indent}  text  p{t['page']} @{t['x']},{t['y']}  {t['text']}")


def describe_event(e):
    """One line for an event from /events (bridge 6)."""
    skip = ('id', 'time', 'kind', 'dialog')
    fields = '  '.join(f'{k} {v}' for k, v in e.items() if k not in skip)
    line = f"#{e['id']} {e['time']} {e['kind']}  {fields}"
    d = e.get('dialog')
    if d:
        if d['kind'] == 'gump':
            labels = ', '.join(f"{b['button']}={b.get('label') or '?'}" for b in d['buttons'])
            line += f"{d['serial']} id {d['id']}  buttons: {labels}"
        else:
            line += f"{d['serial']} id {d['id']} {d.get('title')!r}: " + ', '.join(
                f"{i['index']}={i['name']}" for i in d['items'])
    return line


def record(info, path, every=0.5):
    """Follows the bridge's event log into a file of JSON lines (and prints each event) until Ctrl-C: for recording
    a task the user does by hand, such as crafting one item, so a script can repeat the same steps."""
    last = call(info, 'GET', '/events')['lastEventId']
    print(f'recording into {path} from event #{last}; Ctrl-C to stop', flush=True)
    try:
        with open(path, 'a', encoding='utf-8') as fh:
            while True:
                for e in call(info, 'GET', '/events', after=last)['events']:
                    last = e['id']
                    fh.write(json.dumps(e) + '\n')
                    fh.flush()
                    print(describe_event(e), flush=True)
                time.sleep(every)
    except KeyboardInterrupt:
        print(f'stopped at event #{last}')


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
    p.add_argument('target', nargs='?')
    p.add_argument('--at', nargs=3, type=int, metavar=('X', 'Y', 'Z'))
    p.add_argument('--graphic', default='0')
    p.add_argument('--reach', type=int)
    sub.add_parser('tiles').add_argument('range', nargs='?', type=int)
    p = sub.add_parser('give')
    p.add_argument('serial')
    p.add_argument('to')
    p.add_argument('--amount', type=int)
    sub.add_parser('trade').add_argument('what', choices=['accept', 'unaccept', 'cancel'])
    p = sub.add_parser('cast')
    p.add_argument('spell', type=int)
    p.add_argument('target')
    sub.add_parser('say').add_argument('text', nargs='+')
    sub.add_parser('guard').add_argument('on', choices=['on', 'off'])
    sub.add_parser('skill').add_argument('id', type=int)
    sub.add_parser('dismount')
    sub.add_parser('mount').add_argument('serial')
    sub.add_parser('alarm')
    sub.add_parser('logout')
    sub.add_parser('animations')
    sub.add_parser('cancel')
    sub.add_parser('rules')
    sub.add_parser('clear')
    sub.add_parser('resume')
    sub.add_parser('actions')
    sub.add_parser('waitclear').add_argument('--every', type=int, default=60)
    sub.add_parser('skills').add_argument('name', nargs='?')
    sub.add_parser('gumps')
    p = sub.add_parser('menu')
    p.add_argument('serial')
    p.add_argument('id')
    p.add_argument('index', type=int)
    p = sub.add_parser('gump')
    p.add_argument('serial')
    p.add_argument('id')
    p.add_argument('button', type=int)
    p.add_argument('--switches', default='')
    p = sub.add_parser('target')
    p.add_argument('serial', nargs='?')
    p.add_argument('--cancel', action='store_true')
    sub.add_parser('events').add_argument('--after', type=int, default=0)
    sub.add_parser('record').add_argument('file')
    args = parser.parse_args()

    if args.command in ('label', 'labels'):
        if args.command == 'label':
            save_label(args.serial if args.serial.lower().startswith('0x') else f'0x{int(args.serial):08X}',
                       ' '.join(args.text))
        labels = load_labels()
        for serial, text in sorted(labels.items(), key=lambda kv: kv[1]):
            print(f'{serial}  {text}')
        return

    if args.command == 'alarm':
        print(json.dumps(read_alarm()))
        try:
            with open(os.path.join(AGENT_DIR, 'alarms.log'), encoding='utf-8') as fh:
                print(''.join(fh.readlines()[-10:]), end='')
        except OSError:
            pass
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
        if args.at:
            x, y, z = args.at
            result = call(info, 'POST', '/use', serial=args.serial, x=x, y=y, z=z,
                          graphic=int(args.graphic, 0), reach=args.reach)
        elif args.target:
            result = call(info, 'POST', '/use', serial=args.serial, target=args.target)
        else:
            result = call(info, 'POST', '/use', serial=args.serial)
            c = 'answer'
    elif c == 'tiles':
        result = call(info, 'GET', '/tiles', range=args.range)
    elif c == 'give':
        result = call(info, 'POST', '/give', serial=args.serial, to=args.to, amount=args.amount)
    elif c == 'trade':
        result = call(info, 'POST', '/trade', **({'cancel': 1} if args.what == 'cancel' else
                                                 {'accept': 1 if args.what == 'accept' else 0}))
    elif c == 'cast':
        result = call(info, 'POST', '/cast', spell=args.spell, target=args.target)
    elif c == 'say':
        result = call(info, 'POST', '/say', text=' '.join(args.text))
    elif c == 'guard':
        result = call(info, 'POST', '/guard', on=1 if args.on == 'on' else 0)
    elif c == 'logout':
        result = call(info, 'POST', '/logout')
    elif c == 'animations':
        result = call(info, 'GET', '/animations')
    elif c == 'skill':
        result = call(info, 'POST', '/skill', id=args.id)
    elif c == 'dismount':
        result = call(info, 'POST', '/dismount')
    elif c == 'mount':
        result = call(info, 'POST', '/mount', serial=args.serial)
    elif c == 'cancel':
        result = call(info, 'POST', '/cancel')
    elif c == 'rules':
        result = call(info, 'GET', '/rules')
    elif c == 'resume':
        result = call(info, 'POST', '/resume')
    elif c == 'skills':
        result = call(info, 'GET', '/skills', name=args.name)
    elif c == 'gumps':
        result = call(info, 'GET', '/gumps')
    elif c == 'menu':
        result = call(info, 'POST', '/menu', serial=args.serial, id=args.id, index=args.index)
        c = 'answer'
    elif c == 'gump':
        result = call(info, 'POST', '/gump', serial=args.serial, id=args.id, button=args.button,
                      switches=args.switches or None)
        c = 'answer'
    elif c == 'target':
        if not args.cancel and not args.serial:
            sys.exit('target needs a SERIAL or --cancel')
        result = call(info, 'POST', '/target', **({'cancel': 1} if args.cancel else {'serial': args.serial}))
        c = 'answer'
    elif c == 'events':
        result = call(info, 'GET', '/events', after=args.after)
    elif c == 'record':
        record(info, args.file)
        return
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
        flags = [f for f in ('mounted', 'warMode', 'hidden', 'dead', 'targeting') if r.get(f)]
        if flags or r.get('holding'):
            print('state:', ', '.join(flags + ([f"holding {r['holding']}"] if r.get('holding') else [])))
        if r.get('backpack'):
            print('backpack:', describe(r['backpack']))
        for item in r['hands']:
            print('in hand:', describe(item))
        if r.get('bank'):
            print('bank box:', r['bank'])
        print_trade(r.get('trade'))
        g = r.get('guard')
        if g:
            seen = ', '.join(f"{w['serial']}{'' if w['seen'] else ' (not seen yet)'}" for w in g.get('watching', []))
            print(f"guard: {'ON' if g['on'] else 'off'}" + (f"  watching {seen}" if seen else ''))
            a = g.get('alarm')
            if a:
                t = a.get('threat')
                print(f"  ALARM {a['reason']} ({a['seconds']} s ago{', getting away' if a['evading'] else ''})" +
                      (f"; {t['name'] or '?'} {t['serial']} last at {t['x']},{t['y']}"
                       f" {'in sight' if t['visible'] else str(t['secondsSinceSeen']) + ' s ago'}" if t else ''))
            for m in g.get('near', []):
                print(f"  near: {m['name'] or '?'} {m['serial']} for {m['seconds']} s")
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
    elif c == 'tiles':
        for t in result['tiles']:
            statics = ', '.join(f"{s['graphic']} {s['name']} z{s['z']}" for s in t['statics'])
            print(f"{t['x']},{t['y']}  {t.get('land')} {t.get('landName')} z{t.get('landZ')}" +
                  (f"  | {statics}" if statics else ''))
    elif c in ('give', 'trade'):
        print_trade(result.get('trade'))
        print_messages(result.get('messages', []))
    elif c == 'cast':
        print(('moved' if result['moved'] else 'did not move') + f" to {result['x']},{result['y']},{result['z']}"
              f"  mana {result['mana']}")
        print_messages(result['messages'])
    elif c in ('say', 'guard', 'logout'):
        print(json.dumps(result))
    elif c == 'animations':
        for a in result['animations']:
            print(f"{a['time']} {a['serial']} {a['name'] or '?'} action {a['action']} at {a['x']},{a['y']}")
        print('learned NPCs:', ', '.join(result['npcsLearned']) or 'none')
    elif c in ('skill', 'dismount', 'mount'):
        print(', '.join(f'{k} {v}' for k, v in result.items() if k != 'messages'))
        print_messages(result['messages'])
    elif c == 'name':
        for r in result:
            print(f"{r['serial']}  " + (' / '.join(r['lines']) if r['answered'] else '(no answer)'))
    elif c == 'skills':
        for s in result['skills']:
            print(f"{s['id']:3}  {s['name']:<22} {s['value']:6.1f}  base {s['base']:5.1f}  cap {s['cap']:5.1f}  {s['lock']}")
        print(f"total (base) {result['total']}")
    elif c in ('gumps', 'answer'):
        if c == 'answer':
            print_messages(result['messages'])
            if result.get('targeting'):
                print('a target cursor is up')
        for d in result['dialogs']:
            print_dialog(d)
    elif c == 'events':
        for e in result['events']:
            print(describe_event(e))
        print(f"last event #{result['lastEventId']}")
    else:
        print_messages(result['messages'])
        print(f"last message #{result['lastMessageId']}")


if __name__ == '__main__':
    try:
        main()
    except BridgeError as e:
        sys.exit(str(e))
