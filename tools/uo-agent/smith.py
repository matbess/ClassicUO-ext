#!/usr/bin/env python3
"""Icepick trains Blacksmithing in the tower (see SMITHING.md).

  python3 -I smith.py run [--item NAME]   the loop: craft, smelt back, repeat until Blacksmithy is 99 (the item for
                                          the skill comes from the user's table; --item makes one kind regardless)
  python3 -I smith.py stop                the running loop stops after the craft it is on, and the command waits
  python3 -I smith.py report              totals, skill gained, crafts per hour, hammers
  python3 -I smith.py ore                 smelt the ore in the grey bag into ingots (the user: first, whenever there is)
                                          and any metal gear left loose in it (the user, 2026-11-06)
  python3 -I smith.py rules               put Icepick's smithing rules into the client (mine.py puts the mining ones back)

Icepick stands on the tower's ground floor next to the forge, the anvil and the bottom wooden chest. The chest holds
the grey bag with the ingots, ore now and then, and a pouch of hammers. He keeps one hammer and a working stack of
ingots in his pack. Smithing runs as fast as the server allows (the user, 2026-11-05).

How this server does it (recorded from the user, 2026-11-05): double-click the hammer: the "Blacksmithy Options"
picture menu (Repair, Smelt, Shields, Armor, Weapons, and Make Last Item once something has been made). Weapons asks
"What materials would you like to work with?" with a target cursor (the ingots), then the kind (Bladed, Axes,
Polearms, Bashing), then the item ("cutlass: 8 Ingots"). About 4.5 s later "You create the item." or "You failed to
create the item, and some of your materials are lost." Make Last Item crafts straight away. Smelt asks "Target an
item to recycle." and answers "You melt the item down into ingots." (a cutlass gave all 8 back).

His own leftovers in the pack (small coloured ore piles, a coloured ingot, three shovels) are left alone.
Logs to ~/claude/uo-agent-work/smith/smith.log; state in state.json there.
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
WORK = os.path.expanduser('~/claude/uo-agent-work/smith')
LOG = os.path.join(WORK, 'smith.log')
STATE = os.path.join(WORK, 'state.json')
PID = os.path.join(WORK, 'smith.pid')
STOP_FILE = os.path.join(WORK, 'stop')

CHEST = '0x4074A4C1'    # the bottom wooden chest at 1757,1407 (holds any weight)
BAG = '0x40BF2C73'      # the grey backpack in it: the ingots, ore to smelt, the hammer pouch
# the hammers are in a pouch or bag inside the grey bag; found by what's in it (the user swaps containers: the
# first pouch 0x40421216 was replaced by 0x408558AD on 2026-11-05)
FORGE = '0x408A3611'    # 1755,1410
ORE = ('0x19B7', '0x19B8', '0x19B9', '0x19BA')
ORE_WEIGHT = 12         # stones per ore
SMELT_AT_ONCE = 25      # ore per trip to the forge (300 stones)
HAMMER_GRAPHICS = ('0x13E3', '0x13E4', '0x0FB4', '0x0FB5')  # smith's hammers, sledge hammers
SKILL = 'Blacksmithy'
STOP_AT = 99.0          # then the spear / plate gloves trial (SMITHING.md)

# the user's table (2026-11-05): below each level, the item to make, and where it is in the menus
ITEMS = [
    (65.0, 'cutlass', ('Weapons', 'Bladed')),
    (78.0, 'kryss', ('Weapons', 'Bladed')),
    (88.0, 'short spear', ('Weapons', 'Polearms')),
    (100.0, 'spear', ('Weapons', 'Polearms')),
]
OTHER_PLACES = {'plate gloves': ('Armor', None)}  # for the trial at 99; the second menu is found by looking

PACK_INGOTS = 150       # the working stack in his pack, topped up from the bag
PACK_LOW = 40
BAG_LOW = 300           # tell the user when the bag gets down to this
HAMMERS_LOW = 3         # tell the user when the pouch holds fewer spare hammers than this
ORE_CHECK_EVERY = 50    # crafts between looks for ore in the bag

info = None


class Stop(Exception):
    pass


class Interrupted(Stop):
    """A menu or target cursor went away before the loop answered it: someone clicked in Icepick's client
    (2026-11-05 20:45: a ground click took the Smelt cursor). The step is tried again."""


def say(text):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + text
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def call(method, endpoint, **params):
    try:
        return uo.call(info, method, endpoint, **params)
    except uo.BridgeError as e:
        if e.code in (404, 409) and ('no target cursor' in e.message or 'no such menu' in e.message):
            raise Interrupted(f'{method} {endpoint}: {e.message}')
        raise Stop(f'{method} {endpoint} {params}: {e}')


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
    shutil.copyfile(os.path.join(HERE, 'rules', 'rules-Icepick-smith.json'),
                    os.path.join(uo.AGENT_DIR, 'rules-Icepick.json'))


def skill():
    for s in call('GET', '/skills', name=SKILL)['skills']:
        if s['name'] == SKILL:
            return s['value']
    raise Stop(f'no {SKILL} skill in /skills')


def is_ingots(item):
    return 'ingot' in (item.get('type') or '') and item.get('hue') == 0


def ingot_stack(items):
    """The plain iron ingot stack among these items (the biggest, if there are several)."""
    stacks = [i for i in items if is_ingots(i)]
    return max(stacks, key=lambda i: i.get('amount') or 1) if stacks else None


# ---- ore ----

def use_on_forge(serial):
    """Uses ore on the forge; gets off the horse if the server won't have it while riding. Returns the answer."""
    answer = '?'
    for _ in range(3):
        r = call('POST', '/use', serial=serial, target=FORGE)
        texts = [m['text'] for m in r.get('messages', []) if 'select the forge' not in m['text'].lower()]
        answer = texts[-1] if texts else '?'
        if 'riding' in answer.lower():
            call('POST', '/dismount')
            continue
        return answer
    return answer


def smelt_ore():
    """Smelts every ore pile in the grey bag, a load at a time, and puts the ingots back on the bag's stack."""
    smelted = 0
    while True:
        piles = [i for i in contents(BAG) if i.get('graphic') in ORE]
        if not piles:
            break
        pile = piles[0]
        s = status()
        room = (s['weightMax'] - s['weight'] - 5) // ORE_WEIGHT
        take = min(pile.get('amount') or 1, SMELT_AT_ONCE, room)
        if take < 1:
            raise Stop(f"Icepick is too heavy to carry ore ({s['weight']}/{s['weightMax']})")
        before = {i['serial'] for i in pack()}
        call('POST', '/move', serial=pile['serial'], to=s['backpack']['serial'], amount=take)
        load = next((i for i in pack() if i['serial'] == pile['serial'] or
                     i['serial'] not in before and i.get('graphic') in ORE), None)
        if not load:
            raise Stop("the ore didn't turn up in Icepick's pack")
        answer = '?'
        for _ in range(5):
            answer = use_on_forge(load['serial'])
            say(f"smelt ore {load['serial']} ({load.get('amount', 1)}): {answer}")
            # a failed smelt burns away some ore; smelt what's left again
            if 'burn away' not in answer.lower():
                break
            load = next((i for i in pack() if i['serial'] == load['serial']), None)
            if not load:
                break
        if load and any(i['serial'] == load['serial'] for i in pack()):
            raise Stop(f"ore {load['serial']} is still in Icepick's pack after smelting: {answer}")
        # the new ingots go back onto the bag's stack
        stack = ingot_stack(contents(BAG))
        for i in pack():
            if i['serial'] not in before and is_ingots(i):
                call('POST', '/move', serial=i['serial'], to=stack['serial'] if stack else BAG)
        smelted += take
    if smelted:
        stack = ingot_stack(contents(BAG))
        say(f"ore smelted: {smelted}; ingots in the bag: {stack.get('amount') if stack else 0}")
    return smelted


# ---- gear to smelt ----

def gear_in_bag(state):
    """What the user leaves loose in the grey bag to be smelted (2026-11-06: a katana; old metal gear later): any
    item there but the ingots, ore, hammers and containers, and things that wouldn't smelt before."""
    skip = set(state.get('not_smeltable', []))
    return [i for i in contents(BAG)
            if not i.get('container') and 'ingot' not in (i.get('type') or '')
            and i.get('graphic') not in ORE + HAMMER_GRAPHICS and i['serial'] not in skip]


def smelt_gear(state):
    """Smelts the gear in the grey bag one piece at a time in his pack; its ingots go onto the pile (the supplies
    count them as added). Something that won't smelt goes back in the bag and is left alone after that."""
    gear = gear_in_bag(state)
    if not gear:
        return 0
    t = state.setdefault('totals', {})
    done = 0
    for g in gear:
        name = g.get('type') or g.get('graphic')
        h = hammer(state)
        before = pack_ingots()
        call('POST', '/move', serial=g['serial'], to=pack_serial())
        if not any(i['serial'] == g['serial'] for i in pack()):
            say(f"couldn't take {name} {g['serial']} out of the bag; left it")
            state.setdefault('not_smeltable', []).append(g['serial'])
            continue
        answer = smelt_item(h, g['serial'])
        got = pack_ingots() - before
        if 'melt' in answer.lower() or answer.startswith('gone'):
            done += 1
            t['gear_smelted'] = t.get('gear_smelted', 0) + 1
            t['gear_ingots'] = t.get('gear_ingots', 0) + got
            say(f"smelted {name} {g['serial']} from the bag: {got} ingots ({answer})")
        else:
            if any(i['serial'] == g['serial'] for i in pack()):
                call('POST', '/move', serial=g['serial'], to=BAG)
            state.setdefault('not_smeltable', []).append(g['serial'])
            say(f"couldn't smelt {name} {g['serial']}: {answer}; put it back in the bag and left it")
    # the gear's ingots back onto the bag's stack, leaving his usual working stack
    extra = pack_ingots() - PACK_INGOTS
    mine, stack = ingot_stack(pack()), ingot_stack(contents(BAG))
    if extra > 0 and mine and stack:
        call('POST', '/move', serial=mine['serial'], to=stack['serial'], amount=min(extra, mine.get('amount', 1)))
    save_state(state)
    return done


# ---- supplies ----

def open_supplies():
    """After a login the client knows nothing inside containers until they're opened."""
    for serial in (pack_serial(), CHEST, BAG):
        call('POST', '/open', serial=serial)
    spare_hammers()


def spare_hammers():
    """The hammers in the grey bag: loose, or in any pouch or bag in it (opened when the client doesn't know
    what's inside)."""
    found = []
    for i in contents(BAG):
        if i.get('graphic') in HAMMER_GRAPHICS:
            found.append(i)
        elif i.get('container'):
            inner = contents(i['serial'])
            if not inner and not i.get('knownItems'):
                call('POST', '/open', serial=i['serial'])
                inner = contents(i['serial'])
            found += [h for h in inner if h.get('graphic') in HAMMER_GRAPHICS]
    return found


def hammer(state):
    """The hammer in his pack; takes the next one from the pouch when there's none."""
    for i in pack():
        if i.get('graphic') in HAMMER_GRAPHICS:
            return i['serial']
    spares = spare_hammers()
    if not spares:
        # the user may have just swapped the bag: look again from the chest down
        open_supplies()
        spares = spare_hammers()
    if not spares:
        raise Stop('no hammers left in the grey bag: the user needs to add more')
    call('POST', '/move', serial=spares[0]['serial'], to=pack_serial())
    left = len(spares) - 1
    say(f"took hammer {spares[0]['serial']} ({spares[0].get('type')}) from the pouch; {left} left there")
    if left < HAMMERS_LOW:
        say(f'hammers low: {left} spare in the pouch')
    state.setdefault('hammers', {})[spares[0]['serial']] = 0
    state.setdefault('hammer_taken', {})[spares[0]['serial']] = time.time()
    return spares[0]['serial']


def pack_ingots():
    return sum(i.get('amount') or 1 for i in pack() if is_ingots(i))


def supplies(state):
    """What's left (the user, 2026-11-05: keep track of hammers broken and the hammers and ingots left): the iron
    ingots in the grey bag and in his pack, the spare hammers, the hammers broken so far. Kept in the state."""
    bag = sum(i.get('amount') or 1 for i in contents(BAG) if is_ingots(i))
    loose = sum(i.get('amount') or 1 for i in contents(CHEST) if is_ingots(i))
    mine = sum(i.get('amount') or 1 for i in pack() if is_ingots(i))
    spare = len(spare_hammers())
    broken = len(state.get('broken', []))
    t = state.get('totals', {})
    # the user's measure (2026-11-05): used = what we started with (3,309, plus every addition since) minus what's
    # left in the bag and his pack. An addition is any rise in bag + pack beyond what the pack count says he used.
    measured = t.get('ingots_used', 0) + t.get('ingots_used_before_counting', 0)
    ing = state.setdefault('ingots', {'start': 3309, 'added': 0, 'last_total': 2867, 'last_used': 442})
    left = bag + mine
    ing['added'] += left - ing['last_total'] + (measured - ing['last_used'])
    ing['last_total'], ing['last_used'] = left, measured
    started = ing['start'] + ing['added']
    used = started - left
    state['supplies'] = {'ingots_started_with': started, 'ingots_left': left, 'ingots_used': used, 'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'ingots_in_bag': bag, 'ingots_loose_in_chest': loose,
                         'ingots_in_pack': mine, 'spare_hammers': spare, 'hammers_broken': broken}
    # how long the hammers last (the user, 2026-11-05): smith's hammers only (the first, a sledge hammer, lasted 198)
    smith = [b['uses'] for b in state.get('broken', [])[1:]]
    per_use = t.get('timed_seconds', 0) / t['timed_crafts'] if t.get('timed_crafts') else 10.7
    hammers = ''
    if smith:
        uses = sum(smith) / len(smith)
        hours = spare * uses * per_use / 3600
        hammers = f" (about {uses:.0f} uses each at {per_use:.1f} s a use: {hours:.1f} hours of smithing)"
        state['supplies_hammer_hours'] = round(hours, 1)
    pieces = t.get('gear_smelted', 0)
    gear = (f", {t['gear_ingots']} of them from {pieces} piece{'' if pieces == 1 else 's'} of gear smelted"
            if t.get('gear_ingots') else '')
    return (f"supplies: ingots: started with {started} ({ing['start']} + {ing['added']} added{gear}), {left} left "
            f"({bag} in the bag, {mine} in his pack), {used} used; {spare} spare hammers{hammers}, "
            f"{broken} broken so far")


def top_up_ingots(state, force=False):
    """Keeps about PACK_INGOTS in his pack from the bag's stack. Returns the pack's stack."""
    items = pack()
    mine = ingot_stack(items)
    have = mine.get('amount', 1) if mine else 0
    if have >= PACK_LOW and not force:
        return mine
    # from the grey bag, or a stack the user left loose in the chest (2026-11-05: moving all the ingots there)
    bag = ingot_stack(contents(BAG))
    if not bag or bag.get('amount', 1) < PACK_INGOTS:
        bag = ingot_stack(contents(CHEST)) or bag
    available = bag.get('amount', 1) if bag else 0
    want = min(PACK_INGOTS - have, available)
    if want > 0:
        call('POST', '/move', serial=bag['serial'], to=mine['serial'] if mine else pack_serial(), amount=want)
        available -= want
        warned = state.get('bag_warned', 10 ** 9)
        if available < BAG_LOW and available < warned - 50:
            say(f'ingots low: {available} left in the bag')
            state['bag_warned'] = available
        elif available >= BAG_LOW:
            state.pop('bag_warned', None)
    mine = ingot_stack(pack())
    if not mine or mine.get('amount', 1) < 20:
        raise Stop('out of ingots: the bag is empty')
    return mine


# ---- menus ----

def menu_item(dialog, name):
    """The index of the item called name ("cutlass" matches "cutlass: 8 Ingots"), or None."""
    for item in dialog.get('items', []):
        if item['name'].split(':')[0].strip().lower() == name.lower():
            return item['index']
    return None


def last_menu(answer, title=None):
    menus = [d for d in answer.get('dialogs', []) if d['kind'] != 'gump' and (not title or title.lower() in (d.get('title') or '').lower())]
    return menus[-1] if menus else None


def choose(dialog, index):
    return call('POST', '/menu', serial=dialog['serial'], id=dialog['id'], index=index)


def options_menu(hammer_serial):
    answer = call('POST', '/use', serial=hammer_serial)
    d = last_menu(answer, 'Blacksmithy')
    if not d:
        texts = [m['text'] for m in answer.get('messages', [])]
        raise Stop(f"the hammer didn't show the Blacksmithy menu: {texts}")
    return d


# messages that aren't answers: world saves (one came in place of a craft result, 21:33) and the weather ("It begins
# to rain." came after a smelt's answer and stopped the loop, 2026-11-06 01:10)
NOISE = ('world will save', 'world is saving', 'world save', 'save complete', 'begins to rain', 'stops raining',
         'begins to snow', 'stops snowing', 'rain', 'snow', 'storm', 'weather')


def result_text(answer):
    """The server's answer, leaving out the world-save notices (one came in place of a craft result, 21:33)."""
    texts = [m['text'] for m in answer.get('messages', []) if not m.get('serial')
             and not any(n in m['text'].lower() for n in NOISE)]
    return texts[-1] if texts else '?'


def craft_result(answer):
    """The craft's result: from the answer, or (when a world save held it up) the next one the server sends."""
    text = result_text(answer)
    if 'create' in text.lower() or 'failed' in text.lower() or 'must wait' in text.lower():
        return text
    last = max([m['id'] for m in answer.get('messages', [])] or [0])
    end = time.time() + 60
    while time.time() < end:
        for m in call('GET', '/messages', after=last)['messages']:
            last = m['id']
            low = m['text'].lower()
            if not m.get('serial') and ('you create' in low or 'failed to create' in low):
                return m['text']
        time.sleep(0.5)
    return text


def craft_full(hammer_serial, item, place, ingots):
    """The whole way through the menus. Returns the server's answer, or None when the item isn't on that menu."""
    top, kind = place
    d = options_menu(hammer_serial)
    answer = choose(d, menu_item(d, top))
    if answer.get('targeting'):
        answer = call('POST', '/target', serial=ingots['serial'])
    kinds = last_menu(answer)
    if not kinds:
        raise Stop(f"no menu after choosing {top}: {result_text(answer)}")
    order = [kind] if kind else []
    order += [i['name'] for i in kinds['items'] if i['name'] not in order]
    # the kind we expect first; if the item isn't there, look in the others (the menus come round again each time)
    for n, k in enumerate(order):
        if n:
            d = options_menu(hammer_serial)
            answer = choose(d, menu_item(d, top))
            if answer.get('targeting'):
                answer = call('POST', '/target', serial=ingots['serial'])
            kinds = last_menu(answer)
        answer = choose(kinds, menu_item(kinds, k))
        items = last_menu(answer)
        index = menu_item(items, item) if items else None
        if index:
            return choose(items, index)
        if items:
            choose(items, 0)
        say(f'{item} is not under {top} / {k}')
    return None


def make(state, hammer_serial, item, ingots):
    """One attempt at the item: Make Last Item when that's what it will make, else through the menus.
    Returns (answer text, the new items in the pack)."""
    before = {i['serial'] for i in pack()}
    answer = None
    if state.get('last_item') == item:
        d = options_menu(hammer_serial)
        last = menu_item(d, 'Make Last Item')
        if last:
            answer = choose(d, last)
        else:
            choose(d, 0)
    if answer is None:
        place = next((p for _, n, p in ITEMS if n == item), None) or OTHER_PLACES.get(item)
        answer = craft_full(hammer_serial, item, place, ingots)
        if answer is None:
            raise Stop(f'{item} is not on any {place[0]} menu (skill too low, or a different name?)')
        state['last_item'] = item
    text = craft_result(answer)
    after = pack()
    # anything new, and any crafted item left lying in the pack
    made = [i for i in after if i['serial'] not in before and not is_ingots(i)]
    made += [i for i in made_items(after) if i not in made]
    return text, made


def smelt_item(hammer_serial, serial):
    for attempt in range(3):
        try:
            d = options_menu(hammer_serial)
            answer = choose(d, menu_item(d, 'Smelt'))
            if not answer.get('targeting'):
                raise Stop(f'no target cursor after Smelt: {result_text(answer)}')
            answer = call('POST', '/target', serial=serial)
            texts = [m['text'] for m in answer.get('messages', [])]
            melted = next((x for x in texts if 'melt' in x.lower()), None)
            if melted:
                return melted
            # no "melt" among the answers: gone from the pack means it melted all the same
            if not any(i['serial'] == serial for i in pack()):
                return f"gone from the pack ({result_text(answer)})"
            return result_text(answer)
        except Interrupted as e:
            say(f'smelting {serial} interrupted ({e}); again')
            if not any(i['serial'] == serial for i in pack()):
                return 'gone (melted?)'
    raise Stop(f'smelting {serial} was interrupted three times')


def made_items(items):
    """Crafted things in his pack (any item from the table, or plate gloves), e.g. one left after a stop."""
    names = [n for _, n, _ in ITEMS] + list(OTHER_PLACES)
    return [i for i in items if (i.get('type') or '').lower() in names]


# ---- the loop ----

def item_for(value):
    for below, name, _ in ITEMS:
        if value < below:
            return name
    return ITEMS[-1][1]


def run(forced_item):
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)
    state = load_state()
    t = state.setdefault('totals', {'crafts': 0, 'made': 0, 'failed': 0, 'smelted': 0})
    open_supplies()
    smelt_ore()
    smelt_gear(state)
    value = skill()
    started = {'time': time.time(), 'skill': value, 'crafts': t['crafts']}
    ingots = top_up_ingots(state, force=True)
    leftovers = made_items(pack())
    if leftovers:
        h = hammer(state)
        before = pack_ingots()
        for m in leftovers:
            say(f"smelting {m.get('type')} {m['serial']} left in his pack: {smelt_item(h, m['serial'])}")
        # the craft that made it counted its ingots as used; they're back now
        t['ingots_used'] = t.get('ingots_used', 0) - (pack_ingots() - before)
    say(supplies(state))
    say(f"start: {SKILL} {value}; {ingots.get('amount')} ingots in his pack" +
        (f'; making {forced_item} (--item)' if forced_item else ''))
    since_ore = 0
    interrupted = 0
    last_craft = None
    while True:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
            say('STOPPED: asked to stop')
            break
        if value >= STOP_AT and not forced_item:
            say(f'STOPPED: {SKILL} reached {value}: time for the spear / plate gloves trial (SMITHING.md)')
            break
        item = forced_item or item_for(value)
        if item != state.get('item'):
            say(f'now making {item} ({SKILL} {value})')
            state['item'] = item
        if since_ore >= ORE_CHECK_EVERY:
            since_ore = 0
            if smelt_ore():
                state.pop('last_item', None)
            smelt_gear(state)
        h = hammer(state)
        ingots = top_up_ingots(state)
        # ingots used (the user, 2026-11-05): counted in his pack round each craft and smelt, so the user's
        # additions to the bag don't count; spent on crafting, returned by smelting, and the difference used up
        before_craft = pack_ingots()
        try:
            text, made = make(state, h, item, ingots)
            interrupted = 0
        except Interrupted as e:
            interrupted += 1
            if interrupted >= 5:
                raise Stop(f'interrupted five times in a row ({e}): is someone playing Icepick?')
            say(f'craft interrupted ({e}); again')
            continue
        if 'must wait' in text.lower() and not made:
            # the server didn't take it (just after a world save, 21:33): not a craft; again in a moment
            time.sleep(1)
            continue
        t['crafts'] += 1
        since_ore += 1
        now = time.time()
        if last_craft and now - last_craft < 60:
            t['timed_seconds'] = t.get('timed_seconds', 0) + now - last_craft
            t['timed_crafts'] = t.get('timed_crafts', 0) + 1
        last_craft = now
        state.setdefault('hammers', {})[h] = state.get('hammers', {}).get(h, 0) + 1
        # a hammer that broke is gone from the pack; the next one smelts
        if not any(i['serial'] == h for i in pack()):
            taken = state.get('hammer_taken', {}).get(h)
            minutes = round((time.time() - taken) / 60, 1) if taken else None
            state.setdefault('broken', []).append({'serial': h, 'uses': state['hammers'][h], 'minutes': minutes,
                                                   'time': time.strftime('%Y-%m-%d %H:%M:%S')})
            say(f"hammer {h} broke after {state['hammers'][h]} uses" +
                (f" in {minutes} minutes ({minutes * 60 / state['hammers'][h]:.1f} s a use)" if minutes else '') +
                f": {text}")
            h = hammer(state)
            broke = True
        else:
            broke = False
        low = text.lower()
        if 'you create' in low:
            t['made'] += 1
            t[item] = t.get(item, 0) + 1
        elif 'failed' in low:
            t['failed'] += 1
        else:
            say(f'craft {t["crafts"]} {item}: {text}')
            if 'not enough' in low or 'ingots' in low:
                top_up_ingots(state, force=True)
        after_craft = pack_ingots()
        for m in made:
            if item not in (m.get('type') or '').lower():
                # Make Last Item made something else (the user crafted by hand in between?): the menus next time
                say(f"made {m.get('type')} instead of {item}")
                state.pop('last_item', None)
            answer = smelt_item(h, m['serial'])
            if 'melt' in answer.lower() or answer.startswith('gone'):
                t['smelted'] += 1
            else:
                raise Stop(f"smelting {m['serial']} ({m.get('type')}) answered: {answer}")
        after_smelt = pack_ingots() if made else after_craft
        t['ingots_spent'] = t.get('ingots_spent', 0) + max(0, before_craft - after_craft)
        t['ingots_returned'] = t.get('ingots_returned', 0) + max(0, after_smelt - after_craft)
        t['ingots_used'] = t.get('ingots_used', 0) + before_craft - after_smelt
        if broke:
            # after this craft's ingots are counted, so the totals agree
            say(supplies(state))
        new = skill()
        if new != value:
            hours = (time.time() - started['time']) / 3600
            say(f"{SKILL} {value} -> {new} after {t['crafts']} crafts ({t['made']} made, {t['failed']} failed); "
                f"{(new - started['skill']) / hours:.2f} an hour since the start" if hours > 0.05 else
                f"{SKILL} {value} -> {new} after {t['crafts']} crafts ({t['made']} made, {t['failed']} failed)")
            if int(new) > int(value):
                say(supplies(state))
            value = new
        t['skill'] = value
        save_state(state)


def report():
    state = load_state()
    t = state.get('totals', {})
    broken = state.get('broken', [])
    uses = [b['uses'] for b in broken]
    print(json.dumps({'totals': t, 'item': state.get('item'), 'supplies': state.get('supplies'),
                      'hammers broken': len(broken),
                      'uses per hammer': round(sum(uses) / len(uses)) if uses else None,
                      'hammer in use': {k: v for k, v in state.get('hammers', {}).items()
                                        if k not in {b['serial'] for b in broken}}}, indent=1))


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


def main():
    global info
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--item')
    sub.add_parser('stop')
    sub.add_parser('report')
    sub.add_parser('ore')
    sub.add_parser('rules')
    args = p.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if args.cmd == 'stop':
        return stop()
    if args.cmd == 'report':
        return report()
    info = uo.find_bridge(CHAR)
    install_rules()
    try:
        if args.cmd == 'ore':
            open_supplies()
            smelt_ore()
            smelt_gear(load_state())
        elif args.cmd == 'run':
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
