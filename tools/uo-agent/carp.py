#!/usr/bin/env python3
"""Icepick trains Carpentry to 100 in the chest room (see CARPENTRY.md).

  python3 -I carp.py run [--item NAME]   the loop: craft, throw the item in the trash barrel, repeat until Carpentry
                                         is 100 (the item comes from the user's table by Carpentry's value, the
                                         displayed one; --item makes one kind regardless)
  python3 -I carp.py stop                the running loop stops after the craft it is on, and the command waits
  python3 -I carp.py report              totals, skill gained, saws
  python3 -I carp.py rules               put Icepick's carpentry rules into the client

Icepick stands at 1759,1410 (z 26) in the chest room. Within reach: two piles of boards on the floor (1760,1409 and
1760,1410), the cloth pile (1759,1408), the small crate of saw bags (1760,1408) and the trash barrel (1758,1410).
He keeps a saw and up to 500 boards (half a stone each) in his pack, and cloth while he makes fishing poles. Full
speed (the user, 2026-11-05: no pacing anywhere).

How this server does it (2026-11-14): double-click the saw: "What type of item do you want to craft?" (Other,
Furniture, Containers, Misc. Add-Ons, and more as the skill rises), then "What do you want to make?" ("medium crate:
15 Boards or Logs"); each menu lists only what he can make now. About 6-9 s later "You create the item." (a crate
also gets "Your tinker skill was sufficient to make the item lockable." and a key inside) or a failure. No Make Last
Item, so every craft goes through both menus. Razor's "Auto search new containers" double-clicked the first crate and
the bridge took it for the user taking over; the user turned it off for Icepick (2026-11-14).

Waits (sends nothing, looks every minute) when the saws, boards or cloth run out, and logs it, so the user can add
more. Logs to ~/claude/uo-agent-work/carp/carp.log; state in state.json there.
"""
import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import uo  # noqa: E402

CHAR = 'Icepick'
HERE = os.path.dirname(os.path.realpath(__file__))
WORK = os.path.expanduser('~/claude/uo-agent-work/carp')
LOG = os.path.join(WORK, 'carp.log')
STATE = os.path.join(WORK, 'state.json')
PID = os.path.join(WORK, 'carp.pid')
STOP_FILE = os.path.join(WORK, 'stop')

BARREL = '0x4068E2BB'       # trash barrel at 1758,1410: deletes after 3 minutes, or at once on the 50th item
SAW_GRAPHICS = ('0x1034', '0x1035', '0x1028', '0x1029')   # saws and dovetail saws
BOARD_GRAPHICS = ('0x1BD7', '0x1BD8', '0x1BD9', '0x1BDA', '0x1BDB', '0x1BDC')
CLOTH_GRAPHICS = ('0x1766', '0x1767')
FLOOR_BOX = (1758, 1408, 1761, 1410)    # the rules area: piles of boards and cloth are looked for here only
SKILL = 'Carpentry'
CAP = 100.0
PACK_BOARDS = 500           # the user: he can hold 500 boards at a time
BOARDS_LOW = 40
PACK_CLOTH = 300
CLOTH_LOW = 10
BOARD_WEIGHT = 0.5
CLOTH_WEIGHT = 0.1
WEIGHT_MARGIN = 20
SUPPLIES_EVERY = 100        # crafts between supply counts in the log
WAIT_LOOK = 60              # seconds between looks while waiting for supplies

# the user's table (2026-11-14), by Carpentry's displayed value: (below, item); fishing poles need Tailoring 40
ITEMS = [
    (37.0, 'small crate'),
    (47.0, 'medium crate'),
    # "ballot box: 5 Boards or Logs" under Misc. Add-Ons: not on the menu at 47.0, there at 48.1 (2026-11-14)
    (55.0, 'ballot box'),
    (68.4, 'wooden shield'),
    (74.0, 'fishing pole'),
    (80.0, 'quarter staff'),
    (1000.0, 'gnarled staff'),
]
NEEDS_CLOTH = ('fishing pole',)
# the names crafted items carry in his pack (a medium crate is "crate"), for clearing leftovers after a stop
LEFTOVER_NAMES = {'crate', 'small crate', 'medium crate', 'ballot box', 'ballot box deed', 'wooden shield',
                  'fishing pole', 'quarter staff', 'quarterstaff', 'gnarled staff'}
TAILORING_NEEDED = 40.0
# how far above the table's level an item may still be missing from the menus before the loop stops (the ballot
# box turned up between 47.0 and 48.1)
UNLOCK_GRACE = 2.0


class Stop(Exception):
    pass


class Interrupted(Stop):
    """A menu went away before the loop answered it (a click in Icepick's client, a lag); the step is tried again."""


def say(text):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + text
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


LAG_RESUMES = []


def call(method, endpoint, **params):
    try:
        return uo.call(info, method, endpoint, **params)
    except uo.TakenOver as e:
        # the user took him over: send nothing more (AGENTS.md, "The user taking over")
        raise Stop(f'the user took Icepick over ({e.message}); waiting for them to hand him back')
    except uo.BridgeError as e:
        if e.code in (404, 409) and ('no target cursor' in e.message or 'no such menu' in e.message):
            raise Interrupted(f'{method} {endpoint}: {e.message}')
        if e.code == 423 and uo.wait_out_world_save(info, e):
            raise Interrupted(f'{method} {endpoint}: a world save; resumed')
        if e.code == 423 and 'went quiet' in e.message and lag_over(e.message):
            raise Interrupted(f'{method} {endpoint}: the server lagged; resumed')
        raise Stop(f'{method} {endpoint} {params}: {e}')


def lag_over(why):
    """smith.py's: wait up to 5 minutes for the server to show it's answering, resume, cancel late menus.
    At most 5 an hour."""
    now = time.time()
    LAG_RESUMES[:] = [t for t in LAG_RESUMES if now - t < 3600]
    if len(LAG_RESUMES) >= 5:
        return False
    say(f'the server lagged ({why}); waiting for it')
    first = uo.call(info, 'GET', '/status').get('lastMessageId')
    for _ in range(60):
        s = uo.call(info, 'GET', '/status')
        if s.get('takenOver'):
            return False
        dialogs = [d for d in uo.call(info, 'GET', '/gumps').get('dialogs', []) if d['kind'] != 'gump']
        if dialogs or s.get('targeting') or s.get('lastMessageId') != first:
            uo.call(info, 'POST', '/resume')
            LAG_RESUMES.append(time.time())
            if s.get('targeting'):
                uo.call(info, 'POST', '/target', cancel=1)
            for d in dialogs:
                uo.call(info, 'POST', '/menu', serial=d['serial'], id=d['id'], index=0)
            say(f'the server answered again: resumed (lag {len(LAG_RESUMES)} this hour)')
            return True
        time.sleep(5)
    return False


def status():
    return call('GET', '/status')


def contents(serial):
    return call('GET', '/contents', serial=serial, depth=1)['items']


def pack_serial():
    return status()['backpack']['serial']


def pack():
    return contents(pack_serial())


def load_state():
    try:
        with open(STATE, encoding='utf-8') as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def save_state(state):
    uo.write_json(STATE, state, 1)


def install_rules():
    shutil.copyfile(os.path.join(HERE, 'rules', 'rules-Icepick-carp.json'),
                    os.path.join(uo.AGENT_DIR, 'rules-Icepick.json'))


def skill(name=SKILL):
    for s in call('GET', '/skills', name=name)['skills']:
        if s['name'] == name:
            return s['value']
    raise Stop(f'no {name} skill in /skills')


def amount(item):
    return item.get('amount') or 1


def of_kind(items, graphics):
    return [i for i in items if i.get('graphic') in graphics]


# ---- supplies ----

def floor_piles(graphics):
    """Piles of that kind lying in his corner (the rules area), biggest last so the small one is used up first."""
    found = []
    for i in call('GET', '/nearby', range=3).get('items', []):
        if i.get('graphic') not in graphics or i.get('container'):
            continue
        x, y = i.get('x'), i.get('y')
        if FLOOR_BOX[0] <= x <= FLOOR_BOX[2] and FLOOR_BOX[1] <= y <= FLOOR_BOX[3] and 26 <= i.get('z', 0) <= 30:
            found.append(i)
    return sorted(found, key=amount)


def move_onto(serial, to, n, graphics):
    """Moves n from a pile onto his stack (or into his pack). A drop that merges into a stack can get no answer from
    the server, and the bridge then stops as if the server went quiet (2026-11-14 15:58); when his pack's count of
    that kind went up, that's what happened: resume."""
    before = sum(amount(i) for i in of_kind(pack(), graphics))
    try:
        return uo.call(info, 'POST', '/move', serial=serial, to=to, amount=n)
    except uo.TakenOver as e:
        raise Stop(f'the user took Icepick over ({e.message}); waiting for them to hand him back')
    except uo.BridgeError as e:
        if e.code == 423 and 'went quiet' in e.message:
            after = sum(amount(i) for i in of_kind(pack(), graphics))
            if after > before:
                uo.call(info, 'POST', '/resume')
                return {'moved': True}
        raise Stop(f'moving {serial} to {to}: {e}')


def room_for(weight_each):
    s = status()
    room = s.get('weightMax', 390) - WEIGHT_MARGIN - s.get('weight', 0)
    return max(0, int(room / weight_each))


def top_up(graphics, want, low, weight_each, what):
    """Keeps about want of that kind in his pack, from the floor piles. Returns what he has, waiting for the user
    when he has too few and the floor has none."""
    while True:
        mine = of_kind(pack(), graphics)
        have = sum(amount(i) for i in mine)
        if have >= low:
            return have
        piles = floor_piles(graphics)
        if not piles:
            wait_for(f'{what}: {have} in his pack and no pile left on the floor', lambda: floor_piles(graphics))
            continue
        target = mine[0]['serial'] if mine else pack_serial()
        need = min(want - have, room_for(weight_each))
        for p in piles:
            if need <= 0:
                break
            n = min(need, amount(p))
            move_onto(p['serial'], target, n, graphics)
            need -= n
            if not mine:
                mine = of_kind(pack(), graphics)
                target = mine[0]['serial'] if mine else target
        floor = sum(amount(p) for p in floor_piles(graphics))
        say(f'{what}: topped up to {sum(amount(i) for i in of_kind(pack(), graphics))} in his pack; {floor} left on the floor')


def wait_for(why, ready):
    """Sends nothing; looks every minute until ready() says the user added what's missing."""
    say(f'WAITING: {why}; the user needs to add more')
    while not ready():
        if os.path.exists(STOP_FILE):
            raise Stop('asked to stop while waiting')
        time.sleep(WAIT_LOOK)
    say(f'supplies back ({why.split(":")[0]}); carrying on')


def saw_containers():
    """Every container lying in his corner (the user's saw crate, wherever in the corner it is now; it was moved
    away on 2026-11-14 16:30 and the loop stopped on the missing serial)."""
    found = []
    for i in call('GET', '/nearby', range=3).get('items', []):
        if not i.get('container') or i.get('x') is None:
            continue
        if FLOOR_BOX[0] <= i['x'] <= FLOOR_BOX[2] and FLOOR_BOX[1] <= i['y'] <= FLOOR_BOX[3] \
                and 26 <= i.get('z', 0) <= 30 and i['serial'] != BARREL:
            found.append(i)
    return found


OPENED = set()     # containers opened this run


def saw_bags(open_unknown=True):
    """The saws in the containers in his corner, loose or in bags (opened when the client knows nothing inside)."""
    found = []
    for box in saw_containers():
        # an empty crate always shows 0 known items, so open each container once a run only (2026-11-14: the user
        # asked why he kept opening the two empty crates)
        if open_unknown and not box.get('knownItems') and box['serial'] not in OPENED:
            call('POST', '/open', serial=box['serial'])
            OPENED.add(box['serial'])
        for i in contents(box['serial']):
            if i.get('graphic') in SAW_GRAPHICS:
                found.append(i)
            elif i.get('container'):
                inner = contents(i['serial'])
                if open_unknown and not inner and not i.get('knownItems') and i['serial'] not in OPENED:
                    call('POST', '/open', serial=i['serial'])
                    OPENED.add(i['serial'])
                    inner = contents(i['serial'])
                found += of_kind(inner, SAW_GRAPHICS)
    return found


def saw(state):
    """The saw in his pack; the next from the crate's bags when there's none."""
    mine = of_kind(pack(), SAW_GRAPHICS)
    if mine:
        return mine[0]['serial']
    while True:
        spares = saw_bags()
        if spares:
            break
        wait_for('saws: none in his pack and none in a container in his corner (1758-1761,1408-1410)', lambda: bool(saw_bags()))
    call('POST', '/move', serial=spares[0]['serial'], to=pack_serial())
    left = len(spares) - 1
    say(f"took saw {spares[0]['serial']} from the crate; {left} left there")
    if left < 3:
        say(f'saws low: {left} spare in the crate')
    state.setdefault('saws', {})[spares[0]['serial']] = 0
    return spares[0]['serial']


def supplies_line(state):
    boards = sum(amount(i) for i in of_kind(pack(), BOARD_GRAPHICS))
    floor_boards = sum(amount(p) for p in floor_piles(BOARD_GRAPHICS))
    cloth = sum(amount(i) for i in of_kind(pack(), CLOTH_GRAPHICS))
    floor_cloth = sum(amount(p) for p in floor_piles(CLOTH_GRAPHICS))
    try:
        # counted from what the client already knows: nothing is opened just to count (the user, 2026-11-14:
        # "why does he keep opening empty crates?")
        spare = len(saw_bags(open_unknown=False))
    except Stop:
        spare = '?'
    broken = state.get('broken', [])
    uses = f", about {sum(broken) // len(broken)} crafts a saw" if broken else ''
    return (f'supplies: boards {boards} in his pack + {floor_boards} on the floor; cloth {cloth} + {floor_cloth}; '
            f'{spare} spare saws, {len(broken)} worn out{uses}')


# ---- menus ----

def norm(text):
    return (text or '').split(':')[0].strip().lower()


def same_item(name, other):
    """"quarter staff" matches "quarterstaff", "ballot box" matches "ballot box deed"."""
    other = norm(other)
    name = name.lower()
    return (other == name or other.replace(' ', '') == name.replace(' ', '')
            or all(w in other for w in name.split()))


def menu_item(dialog, name):
    items = dialog.get('items', [])
    for i in items:
        if norm(i['name']) == name.lower():
            return i['index']
    for i in items:
        if same_item(name, i['name']):
            return i['index']
    return None


def menus():
    return [d for d in call('GET', '/gumps').get('dialogs', []) if d['kind'] != 'gump']


def last_menu(answer):
    found = [d for d in answer.get('dialogs', []) if d['kind'] != 'gump']
    return found[-1] if found else None


def wait_menu(answer):
    """The menu a choice or double-click brought, waiting up to 30 s when a world save held it back."""
    d = last_menu(answer)
    for _ in range(30):
        if d:
            return d
        time.sleep(1)
        found = menus()
        d = found[-1] if found else None
    return None


def cancel_open_menus():
    for d in menus():
        call('POST', '/menu', serial=d['serial'], id=d['id'], index=0)
        say(f"cancelled a menu left open ({d.get('title')})")


def top_menu(saw_serial):
    for _ in range(3):
        answer = call('POST', '/use', serial=saw_serial)
        d = wait_menu(answer)
        if d:
            return d
        say(f"no menu 30 s after the saw ({[m['text'] for m in answer.get('messages', [])]}); again")
    raise Stop("the saw didn't show its menu three times")


def choose(dialog, index):
    return call('POST', '/menu', serial=dialog['serial'], id=dialog['id'], index=index)


def find_item(state, saw_serial, item):
    """Where the item is (its category), looking through every category once and remembering it. None when no
    category has it (the skill isn't high enough yet, or another name)."""
    places = state.setdefault('places', {})
    known = places.get(item)
    top = top_menu(saw_serial)
    cats = [i['name'] for i in top['items']]
    order = ([known] if known in cats else []) + [c for c in cats if c != known]
    for n, cat in enumerate(order):
        if n:
            top = top_menu(saw_serial)
        sub = wait_menu(choose(top, menu_item(top, cat)))
        if not sub:
            raise Stop(f'no menu after choosing {cat}')
        index = menu_item(sub, item)
        if index:
            if places.get(item) != cat:
                places[item] = cat
                say(f'{item} is under {cat}: {next(i["name"] for i in sub["items"] if i["index"] == index)}')
            return sub, index
        choose(sub, 0)
    return None, None


# messages that aren't answers: world saves and the weather (smith.py)
NOISE = ('world will save', 'world is saving', 'world save', 'save complete', 'rain', 'snow', 'storm', 'weather')


def craft_result(answer):
    texts = [m['text'] for m in answer.get('messages', []) if not m.get('serial')
             and not any(n in m['text'].lower() for n in NOISE)]
    for t in reversed(texts):
        low = t.lower()
        if 'create' in low or 'fail' in low or 'must wait' in low or 'worn out' in low or 'do not have' in low \
                or "don't have" in low or 'not enough' in low or 'lack' in low:
            return t
    last = max([m['id'] for m in answer.get('messages', [])] or [0])
    end = time.time() + 60
    while time.time() < end:
        for m in call('GET', '/messages', after=last)['messages']:
            last = m['id']
            low = m['text'].lower()
            if not m.get('serial') and ('you create' in low or 'fail' in low or 'must wait' in low):
                return m['text']
        time.sleep(0.5)
    return texts[-1] if texts else '?'


def trash(serial, what):
    try:
        uo.call(info, 'POST', '/move', serial=serial, to=BARREL)
    except uo.TakenOver as e:
        raise Stop(f'the user took Icepick over ({e.message}); waiting for them to hand him back')
    except uo.BridgeError as e:
        if uo.resume_after_barrel_emptied(info, e):
            return
        raise Stop(f'throwing {what} {serial} away: {e}')


def supplies_kinds():
    return SAW_GRAPHICS + BOARD_GRAPHICS + CLOTH_GRAPHICS


def item_start(item):
    """The value the table starts the item at."""
    below = 0.0
    for b, name in ITEMS:
        if name == item:
            return below
        below = b
    return below


def previous_item(item):
    names = [n for _, n in ITEMS]
    i = names.index(item) if item in names else 0
    return names[i - 1] if i > 0 else None


def item_for(value):
    for below, name in ITEMS:
        if value < below:
            return name


def report():
    state = load_state()
    print(json.dumps({k: state.get(k) for k in ('totals', 'item', 'places', 'start_skill', 'skill', 'broken')},
                     indent=1))


def stop():
    with open(STOP_FILE, 'w') as fh:
        fh.write(time.strftime('%Y-%m-%d %H:%M:%S'))
    try:
        with open(PID) as fh:
            pid = int(fh.read().strip())
    except (OSError, ValueError):
        print('no loop running (no pid file)')
        return
    for _ in range(120):
        try:
            os.kill(pid, 0)
        except OSError:
            print('stopped')
            return
        time.sleep(1)
    print('still running after 2 minutes')


# ---- the loop ----

def run(forced_item):
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)
    state = load_state()
    t = state.setdefault('totals', {'crafts': 0, 'made': 0, 'failed': 0, 'trashed': 0})
    if status().get('takenOver'):
        raise Stop(f"the user has Icepick ({status()['takenOver']}); waiting for them to hand him back")
    cancel_open_menus()
    call('POST', '/open', serial=pack_serial())
    value = skill()
    state.setdefault('start_skill', value)
    # anything crafted left in his pack from before a stop goes in the barrel: only items named exactly like what he
    # makes (a magic "gnarled staff of ..." of his own stays); everything else in his pack now is kept
    keep = set()
    for i in pack():
        if norm(i.get('type')) in LEFTOVER_NAMES:
            trash(i['serial'], i.get('type'))
            say(f"threw away {i.get('type')} {i['serial']} left in his pack")
        else:
            keep.add(i['serial'])
    say(supplies_line(state))
    say(f'start: {SKILL} {value}' + (f'; making {forced_item} (--item)' if forced_item else ''))
    since_supplies = 0
    since_gain = state.get('since_gain', {'crafts': 0, 'made': 0, 'failed': 0})
    interrupted = 0
    while True:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
            say('STOPPED: asked to stop')
            break
        if value >= CAP:
            say(f'STOPPED: {SKILL} reached {value}, the cap. Done.')
            break
        item = forced_item or item_for(value)
        if item != state.get('item'):
            say(f'now making {item} ({SKILL} {value})')
            state['item'] = item
        if item in NEEDS_CLOTH:
            tailoring = skill('Tailoring')
            if tailoring < TAILORING_NEEDED:
                raise Stop(f'fishing poles need Tailoring {TAILORING_NEEDED}; his is {tailoring}')
        try:
            s = saw(state)
            top_up(BOARD_GRAPHICS, PACK_BOARDS if item not in NEEDS_CLOTH else PACK_BOARDS - 100, BOARDS_LOW,
                   BOARD_WEIGHT, 'boards')
            if item in NEEDS_CLOTH:
                top_up(CLOTH_GRAPHICS, PACK_CLOTH, CLOTH_LOW, CLOTH_WEIGHT, 'cloth')
            before = {i['serial'] for i in pack()}
            # The ballot box wasn't on the menu at 47.0 but was at 48.1: an item can turn up a little above the
            # table's level, and that isn't an error (the user, 2026-11-14: "Don't stop a level early again and
            # think it's an error"). So the one before it carries on, and the item is looked for again after each
            # gain. Still missing UNLOCK_GRACE above its level: stop and tell the user (the user, 2026-11-14: "if
            # you can't make an item that you're supposed to make", stop; never switch to anything else).
            start = item_start(item)
            waiting = state.get('waiting_for') == item and state.get('waiting_at') == value
            sub, index = (None, None) if waiting else find_item(state, s, item)
            if sub is None:
                before_it = previous_item(item)
                if not before_it or value >= start + UNLOCK_GRACE:
                    raise Stop(f'{item} is on none of the saw\'s menus at {SKILL} {value} (the table starts it at '
                               f'{start})')
                if state.get('waiting_for') != item:
                    say(f'{item} is not on the menus yet at {SKILL} {value}: {before_it} until it turns up '
                        f'(stops if it is still missing at {start + UNLOCK_GRACE:.1f})')
                state['waiting_for'], state['waiting_at'] = item, value
                sub, index = find_item(state, s, before_it)
                if sub is None:
                    raise Stop(f'neither {item} nor {before_it} is on the menus at {SKILL} {value}')
                item = before_it
            elif state.get('waiting_for') == item:
                state.pop('waiting_for', None)
                state.pop('waiting_at', None)
                say(f'{item} is on the menus now ({SKILL} {value})')
            answer = choose(sub, index)
            text = craft_result(answer)
            interrupted = 0
        except Interrupted as e:
            interrupted += 1
            if interrupted >= 5:
                raise Stop(f'interrupted five times in a row ({e}): is someone playing Icepick?')
            say(f'craft interrupted ({e}); again')
            continue
        low = text.lower()
        if 'must wait' in low:
            time.sleep(1)
            continue
        if 'do not have' in low or "don't have" in low or 'not enough' in low or 'lack' in low:
            say(f'the server says: {text}')
            raise Stop(f'not enough materials for {item}: {text}')
        t['crafts'] += 1
        since_gain['crafts'] += 1
        since_supplies += 1
        state['saws'][s] = state.setdefault('saws', {}).get(s, 0) + 1
        if 'you create' in low:
            t['made'] += 1
            since_gain['made'] += 1
        else:
            t['failed'] += 1
            since_gain['failed'] += 1
        after = pack()
        if not any(i['serial'] == s for i in after):
            uses = state['saws'].get(s, 0)
            state.setdefault('broken', []).append(uses)
            say(f'saw {s} wore out after {uses} crafts')
        for i in after:
            if i['serial'] in before or i['serial'] in keep or i.get('graphic') in supplies_kinds():
                continue
            trash(i['serial'], i.get('type') or 'item')
            t['trashed'] += 1
        new = skill()
        if new != value:
            say(f"{SKILL} {value} -> {new} after {since_gain['crafts']} crafts ({since_gain['made']} made, "
                f"{since_gain['failed']} failed) of {item}")
            since_gain = {'crafts': 0, 'made': 0, 'failed': 0}
            value = new
        state['since_gain'] = since_gain
        state['skill'] = value
        save_state(state)
        if since_supplies >= SUPPLIES_EVERY:
            since_supplies = 0
            say(supplies_line(state) + f"; {t['crafts']} crafts so far ({t['made']} made, {t['failed']} failed)")


def main():
    global info
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--item')
    sub.add_parser('stop')
    sub.add_parser('report')
    sub.add_parser('rules')
    args = p.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if args.cmd == 'stop':
        return stop()
    if args.cmd == 'report':
        return report()
    info = uo.find_bridge(CHAR)
    install_rules()
    if args.cmd == 'rules':
        return
    try:
        if os.path.exists(PID):
            try:
                with open(PID) as fh:
                    os.kill(int(fh.read().strip()), 0)
                sys.exit('a loop is already running')
            except (OSError, ValueError):
                pass
        with open(PID, 'w') as fh:
            fh.write(str(os.getpid()))
        try:
            run(args.item)
        finally:
            os.remove(PID)
    except Stop as e:
        say(f'STOPPED: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
