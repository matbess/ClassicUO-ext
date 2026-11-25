#!/usr/bin/env python3
"""Clem buys shovels from the tinkers every hour, for the castle tools room (SHOVELS.md; the user, 2026-11-24).

The user's job, in their words: "When you go buy shovels you'll do the following each hour: go to the bank (ocllo
bank rune), get gold (however much you think this shovel run will take based on how many shovels you think the
vendors currently have, each hour some of them still start to sell more shovels, like 9 more I think). Go to all of
the vendors in the tinkers runebook & buy all of their shovels, as many as you can, until you're weight is filled up.
Then take them back and put them in the tool room. It will take many trips to the vendors and back to the castle. if
gold gets low you go to the bank to get more. You dont' stop until you have bought all the shovels, and then you go to
the castle tool room and wait for the next hour mark ... Keep doing it until I tell you to stop or you encounter a
blocker (like you ran out of gold) ... When i say stop then put the rune & the tinerks runebook back in my chest."

  python3 -I shovels.py run [--once] [--now]   the loop: each tinker has his own clock (due 61 minutes after his buy
                                               list was first opened in his last cycle; due at once until he's bought
                                               out); trips go to whoever is due, earliest first, home, wait in the
                                               tools room for the next one due. --once: until nothing is due, then
                                               cleanup. --now: forget the skips (blocked spots, players).
  python3 -I shovels.py stop                   ask the loop to stop: it finishes the tinker it's at, comes home,
                                               puts the shovels away, puts the rune and the runebook back in the
                                               user's chest, and waits in the tools room
  python3 -I shovels.py cleanup                only that last part (the rune and the book into the user's chest)
  python3 -I shovels.py fetch                  the rune and the book from the user's chest into his pack
  python3 -I shovels.py status                 the state: tinkers, stock, prices, clocks
  python3 -I shovels.py blocked                which rune spots were blocked, how often (blocked.jsonl)

The pieces:
- Out: Recall from inside the castle (the tools room). The "Ocllo Bank" rune for gold; the Tinkers runebook's
  Recall flags (gems.recall_to) for the tinkers.
- Home: the "skara" rune (0x406EAA74, in his reagent bag, known by its serial) lands him in the north yard (935,2328),
  with no creatures about (the user: "The reason you'll use the skara rune is to avoid having to fight"); in through
  the north door into the north corridor, locked behind him (the key's "You lock it.", then the door shut); then the
  tools room (tools_room.put), the user's table locked again from behind it, and he waits at the stand there.
- The rune and the book live in the user's own secure chest (938 top, 0x406E70A6, "runes and bags") when not buying.
- A tinker is anyone within TINKER_RANGE of the landing whose paperdoll says "the tinker"; "<name> buy", every shovel
  in his list that fits (weight, 125 items) and the gold covers. A player in town: home, and that tinker not for 15
  minutes (the town rule of the map and gem trips). A spot that's blocked: again after 15, 30, 60 and 120 s, then on,
  and that tinker not for 5 minutes.
- Blockers stop the loop with him home, safe in the tools room: no gold left in the bank, a rune or the book missing,
  a Recall that lands somewhere unexpected, reagents short, anything the castle tools refuse.

Only the user hands Clem back: a takeover stops it at once and nothing more is sent.
"""
import argparse
import json
import os
import signal
import sys
import time
import traceback

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import uo  # noqa: E402
import carto  # noqa: E402
import castle  # noqa: E402
import castle_site  # noqa: E402
import door  # noqa: E402
import gems  # noqa: E402
import restock  # noqa: E402
import tools_room  # noqa: E402
import trips  # noqa: E402

CHAR = 'Clem'
WORK = os.path.expanduser('~/claude/uo-agent-work/shovels')
LOG = os.path.join(WORK, 'shovels.log')
STATE = os.path.join(WORK, 'state.json')
VENDORS = os.path.join(WORK, 'vendors.json')
VISITS = os.path.join(WORK, 'visits.jsonl')
STOP_FILE = os.path.join(WORK, 'stop')
# the user, 2026-11-24: "is there a pause ability? I'd like to pause it so I can fix the runes and use clem for a while.
# The pause ability should understand how to adjust the schedule when I pause/unpause". `pause` writes this file: the
# loop finishes the step it's on (in town: that tinker, home, the shovels away), keeps the rune and the book, and
# exits. `resume` takes him back (the user asking is the handback), re-reads the runebook (re-marked runes: new spots,
# his rules' areas follow), forgets the blocked-spot skips, and goes on from wherever he is. The clocks are the
# vendors' own and kept running through the pause: whoever came due meanwhile is due at once, earliest first.
PAUSE_FILE = os.path.join(WORK, 'paused')
# every Recall spot found blocked (the user, 2026-11-24: "try to remember which locations are blocked frequently so I
# can improve the rune locations for those"): one line per blocked try; `shovels.py blocked` sums them up
BLOCKED_LOG = os.path.join(WORK, 'blocked.jsonl')

SHOVELS = {0x0F39, 0x0F3A}
SHOVEL_STONES = 5             # a shovel weighs 5 stones (tools_room.WEIGHT; checked on the first purchase)
WEIGHT_MARGIN = 10            # stones kept free under his max
MIN_ROOM = 3                  # fewer shovels than this fit: home with the load
COINS_PER_STONE = 50          # gold's weight (GEMS.md: 15,517 gold weighed about 310 stones)
TINKER_RANGE = trips.SIGHT    # every tinker in sight of where a rune lands (Serpent's Hold: Andre the tinker was in sight
                              # but past 12 tiles, 16:31:56, and was missed)
GUESS_STOCK, GUESS_PRICE = 20, 15  # for the gold before a tinker's stock and price are known
GROWTH = 10                   # each hour a bought-out tinker stocks about 9 more (the user)
GOLD_LOADS = 2                # gold for at most this many full loads at a time (it weighs: 50 coins a stone)
ONWARD_MANA = 11 + 11 + 5     # on to the next place in town: that Recall, and the Recall home from there
# "That location is blocked." (someone on the rune's spot): again after 15, 30, 60, then 120 s; still blocked, that
# tinker waits for the next round (the user, 2026-11-24: "Do an exponential backoff up to 2 minutes. If it doesn't
# unblock, then move on, we'll try it again on the next round. We don't want to wait too long or the vendors won't be
# refreshed after 1 hour. it will get out of sync")
BLOCKED_WAITS = [15, 30, 60, 120]
PLAYER_WAIT = trips.PLAYER_WAIT  # 15 minutes inside after a player in town (the map and gem trips' rule)
# the courtyard rune, known by its serial: the user marked it in the courtyard (2026-11-24 15:53:55), named it "skara",
# then marked it again (15:54:50), which wiped the name ("a recall rune for an unknown location"). The rune that IS
# named "a recall rune for Skara" is 0x408E20F9, the user's recall-home rune to the castle FRONT (935,2356, among the
# creatures): the first trip home matched it by name and landed outside (16:12:21). Never pick the rune by name.
SKARA_RUNE = '0x406EAA74'
USER_CHEST = '0x406E70A6'     # 938 top, "yours: runes and bags": the user's personal secure chest by the window
COURTYARD_BOX = (930, 2341, 941, 2346)
# the north yard (grass, z 0, walled off from the great hall), where the courtyard ("skara") rune lands him at 935,2328.
# The user, 2026-11-24: "you don't go to the gret hall for shovel runs. we skip it. You go inside the side door that he's
# next to right now": the north doors (east half 0x40913575 shut at 935,2325; west half 0x40913573 at 934,2325) into the
# north corridor (y 2323), the key ring 0x408CB8EB hanging at 935,2326 on the yard side. Locked and closed behind him.
NORTH_YARD = (930, 2326, 941, 2331)
NORTH_DOOR, NORTH_KEY = '0x40913575', '0x408CB8EB'
NORTH_SHUT, NORTH_OUT, NORTH_IN = (935, 2325), (935, 2327), (935, 2324)
OCLLO_BANK = (3686, 2506)     # where the bank rune lands (mine.py; Clem was at 3686,2515 by the bank, 2026-11-24)
BANK_SLACK = 20
RUNEBOOK_GRAPHICS = {0x0EFA, 0x22C5}

info = None
stopping = {'flag': False}


class Stop(Exception):
    """A blocker: he's left where he is (home if possible); the user is told."""


class UserHas(Stop):
    """The user took him over: nothing more is sent."""


class OutOfGold(Stop):
    pass


class NeedGold(Exception):
    """In town, the gold has run low with shovels still to buy: to the bank and back."""


class Full(Exception):
    """In town, his pack is full: home with the load."""


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
    uo.write_json(STATE, state, 1)


def call(method, endpoint, **params):
    try:
        return trips.call(method, endpoint, **params)
    except trips.Stop as e:
        st = uo.call(info, 'GET', '/status')
        if st.get('takenOver'):
            raise UserHas(f'the user took over ({st["takenOver"]})')
        raise Stop(str(e))


def status():
    return call('GET', '/status')


def texts(answer):
    return ' | '.join(m['text'] for m in answer.get('messages', []))


def taken():
    st = uo.call(info, 'GET', '/status')
    return st.get('takenOver')


def check_stop_file():
    if os.path.exists(STOP_FILE) and not stopping['flag']:
        stopping['flag'] = True
        say('asked to stop: finishing this step, then home, the shovels away, the rune and book into the chest')
    if os.path.exists(PAUSE_FILE) and not stopping['flag']:
        stopping['flag'] = stopping['pause'] = True
        say('asked to pause: finishing this step, then home and the shovels away; the rune and book stay with him')
    return stopping['flag']


# ---- what he carries ----

def pack_items():
    return trips.pack_list()


def gold_carried():
    return trips.gold_carried()


def shovels_carried():
    _, items = pack_items()
    return sum(1 for i in trips.walk_items(items) if int(i['graphic'], 16) in SHOVELS)


def shovel_room():
    """How many more shovels fit: by weight (his max less WEIGHT_MARGIN) and by the pack's 125 items."""
    st = status()
    by_weight = (st['weightMax'] - WEIGHT_MARGIN - st['weight']) // SHOVEL_STONES
    _, items = pack_items()
    by_items = carto.PACK_LIMIT - trips.count_items(items) - 1
    return max(0, min(by_weight, by_items))


def find_kit(state):
    """The skara rune and the Tinkers runebook in his pack (serials into the state); None for one not there."""
    try:
        call('POST', '/open', serial=restock.BAG)  # the client knows nothing inside bags after a login
    except uo.BridgeError:
        pass
    _, items = pack_items()
    every = list(trips.walk_items(items))
    runes = [i['serial'] for i in every if int(i['graphic'], 16) in castle.RUNES]
    books = [i['serial'] for i in every if int(i['graphic'], 16) in RUNEBOOK_GRAPHICS]
    kit = {'rune': None, 'book': None, 'bank': None}
    for a in call('POST', '/name', serial=','.join(runes + books)) if runes or books else []:
        line = ' '.join(a.get('lines', [])).lower()
        if a['serial'] == SKARA_RUNE:
            kit['rune'] = a['serial']
        elif a['serial'] in runes and 'ocllo bank' in line:
            kit['bank'] = a['serial']
        elif a['serial'] in books and 'tinker' in line:
            kit['book'] = a['serial']
    state['kit'] = kit
    state['runebook'] = kit['book']  # gems.open_book reads it from here
    return kit


# ---- the castle ----

def in_courtyard(st):
    x1, y1, x2, y2 = COURTYARD_BOX
    return x1 <= st['x'] <= x2 and y1 <= st['y'] <= y2


def castle_call(fn, *args):
    """A castle.py / tools_room.py step: their stops become ours (a takeover a UserHas)."""
    try:
        return fn(*args)
    except (castle.UserHas,) as e:
        raise UserHas(str(e))
    except (castle.Stop, tools_room.td.Stop, restock.Stop, trips.Stop, gems.Stop) as e:
        if taken():
            raise UserHas(f'the user took over ({taken()})')
        raise Stop(str(e))


def in_north_yard(st):
    x1, y1, x2, y2 = NORTH_YARD
    return x1 <= st['x'] <= x2 and y1 <= st['y'] <= y2 and st['z'] < 4


def go_in_north():
    """From the north yard: unlock the north door, open it, in, lock it ("You lock it."), close it; then it must
    stand shut."""
    castle_call(castle.through, NORTH_DOOR, NORTH_KEY, NORTH_SHUT, NORTH_OUT, NORTH_IN, 'north door')
    st = status()
    if castle.spot(NORTH_DOOR) != NORTH_SHUT:
        raise Stop(f'the north door is not shut after coming in (it stands at {castle.spot(NORTH_DOOR)})')
    if in_north_yard(st):
        raise Stop(f"still in the north yard after the north door ({st['x']},{st['y']},{st['z']})")
    say(f"in: the north door locked (\"You lock it.\") and shut; he's at {st['x']},{st['y']},{st['z']}")


def go_in():
    """From the courtyard (or anywhere castle.go_in knows): in through the central door, locked and closed behind him."""
    castle_call(castle.go_in)
    st = status()
    shut = castle.spot(castle.CENTRAL_DOOR) == castle.CENTRAL_SHUT
    if not shut:
        raise Stop(f'the central door is not shut after coming in (it stands at {castle.spot(castle.CENTRAL_DOOR)})')
    say(f"in: the central door locked (\"You lock it.\") and shut; he's at {st['x']},{st['y']}")


def stay_in_tools_room():
    """The table locked from behind it (it ends locked whatever happened), then to the stand in the tools room
    (the user: "go to the castle tool room and wait"). The table can't be seen from the tools room, so it's always
    looked at from beside it (castle-sorting's shovels-stay.py, 2026-11-24)."""
    mover = tools_room.MOVER or castle_site.Mover(uo, info, say)
    st = status()
    if not castle_site.behind((st['x'], st['y'])) and not tools_room.in_room((st['x'], st['y'])):
        mover.go(tools_room.OUT, 'to the tools room')
    tools_room.walk_to(tools_room.OUT, 'out of the tools room to check the table')
    mover.close_up()
    st = status()
    if not castle_site.behind((st['x'], st['y'])):
        raise Stop(f"in front of the table after locking it ({st['x']},{st['y']}): stopped, not going back past it")
    mover.table_opened = False
    mover.go(tools_room.OUT, 'back to the tools room')
    tools_room.walk_to(tools_room.STAND, 'into the tools room')
    tools_room.MOVER = None


def put_away(state):
    n = shovels_carried()
    if not n:
        stay_in_tools_room_safe()
        return 0
    tools_room.MOVER = None
    castle_call(tools_room.put, ['shovels'], (), False)
    left = shovels_carried()
    in_room = room_shovels()
    say(f'put away {n - left} shovels; TOOLS ROOM: {in_room} shovels'
        + (f'; {left} still in his pack' if left else ''))
    state['room_total'] = in_room
    tot = state.setdefault('totals', {})
    tot['put_away'] = tot.get('put_away', 0) + (n - left)
    save_state(state)
    stay_in_tools_room_safe()
    if left:
        raise Stop(f'{left} shovels did not go into the tools room (see the log)')
    return n - left


def meditate(want):
    """In town with too little mana to Recall home: meditate (players are looked for when the vendors are known)."""
    if V.get('v') is not None:
        gems.meditate_in_town(V['v'], status()['serial'], want)
    else:
        castle_call(trips.meditate_to, want)


V = {'v': None}


def room_shovels():
    return sum(e['items'].get('0x0F39', 0) + e['items'].get('0x0F3A', 0) for e in tools_room.load().values())


def count_room(state):
    """The tools room counted in full, once at the start of a run (every bag opened); after that the count is kept
    from the put-aways (tools_room.TRUST_CACHE): nobody takes shovels out during a run (the user, 2026-11-24)."""
    tools_room.TRUST_CACHE = False
    tools_room.MOVER = None
    if shovels_carried():
        put_away(state)  # (put() recounts every bag while TRUST_CACHE is off)
    else:
        castle_call(tools_room.stand)
        cache = tools_room.load()
        castle_call(tools_room.refresh, cache)
        tools_room.to_page(cache)
        state['room_total'] = room_shovels()
        say(f"TOOLS ROOM: {state['room_total']} shovels (counted at the start of the run)")
        stay_in_tools_room_safe()
    tools_room.TRUST_CACHE = True
    save_state(state)


def stay_in_tools_room_safe():
    castle_call(stay_in_tools_room)


def home(state):
    """Recall with the skara rune to the courtyard, in, the shovels away, waiting in the tools room."""
    try:
        call('POST', '/shop', close=1)
    except (uo.BridgeError, Stop):
        pass
    rune = state['kit']['rune']
    if status()['mana'] < 11:
        meditate(15)
    st = castle_call(castle.recall, rune, 'skara (the castle courtyard)')
    if in_north_yard(st):  # where the user marked it (935,2328): in by the north door
        go_in_north()
        put_away(state)
        return
    if not in_courtyard(st):
        where = f"{st['x']},{st['y']},{st['z']}"
        if 929 <= st['x'] <= 941 and 2351 <= st['y'] <= 2362:  # the castle front: never left standing out there
            say(f'the courtyard rune put him at the castle front ({where}): in through the front door (the fight '
                f'logic), then the loop stops')
            go_in()
            put_away(state)
        raise Stop(f"the courtyard rune put him at {where}, not in the castle courtyard")
    go_in()
    put_away(state)


def refill_reagents():
    """Any reagent below 25: topped up from the user's entrance reagent chest (938 2nd), and straight back to the tools
    room. Not castle.reagents_ok(): its restock_inside ends with a walk past the user's table to the great hall, by the
    west stairs (16:33, the user: "why is he going to the great hall?"); the chest's walkway is on the tools room's side
    of the tables, so the table never moves for this."""
    if not restock.low(restock.counts()):
        return
    mover = castle_site.Mover(uo, info, say)
    tower_chest, restock.CHEST = restock.CHEST, restock.CASTLE_CHEST
    try:
        restock.ensure(walk=lambda: mover.walk_near(info, restock.CASTLE_CHEST))
    finally:
        restock.CHEST = tower_chest
    if mover.table_opened:  # (only if he was in front of the tables to start with)
        tools_room.MOVER = mover
        stay_in_tools_room()
    else:
        mover.go(tools_room.OUT, 'back to the tools room')
        tools_room.walk_to(tools_room.STAND, 'into the tools room')


def prepare(state, need_mana):
    """Inside, before a trip out: reagents (any below 25: the user's chest), healed, mana for the trip."""
    castle_call(refill_reagents)
    st = status()
    if st['hits'] < st['hitsMax'] and st['mana'] >= 11:
        a = call('POST', '/cast', spell=trips.HEAL, target=st['serial'])
        say(f'healed before leaving: {texts(a) or "-"}')
    castle_call(trips.meditate_to, min(need_mana, status()['manaMax']))


# ---- the rune and the book: the user's chest ----

def to_user_chest():
    mover = castle_site.Mover(uo, info, say)
    mover.walk_near(info, USER_CHEST)
    call('POST', '/open', serial=USER_CHEST)
    return mover


def cleanup(state):
    """The skara rune and the Tinkers runebook back into the user's chest (938 top), then the tools room."""
    kit = find_kit(state)
    put = [s for s in (kit['rune'], kit['book']) if s]
    if not put:
        say("cleanup: neither the skara rune nor the Tinkers runebook is in his pack (in the user's chest already?)")
        return
    st = status()
    if not castle.inside((st['x'], st['y'])):
        raise Stop(f"cleanup is done from inside the castle; he's at {st['x']},{st['y']}")
    tools_room.MOVER = None
    castle_call(to_user_chest)
    for serial in put:
        r = call('POST', '/move', serial=serial, to=USER_CHEST)
        if not r.get('moved', True):
            raise Stop(f'{serial} did not go into the user\'s chest: {r}')
    call('POST', '/close', serial=USER_CHEST)
    say("the skara rune and the Tinkers runebook are back in the user's chest (938 top)")
    state.pop('kit', None)
    save_state(state)
    stay_in_tools_room_safe()


def fetch(state):
    kit = find_kit(state)
    if kit['rune'] and kit['book']:
        return kit
    st = status()
    if not castle.inside((st['x'], st['y'])):
        raise Stop(f"the rune or the book isn't in his pack, and he's not inside the castle ({st['x']},{st['y']})")
    castle_call(to_user_chest)
    items = call('GET', '/contents', serial=USER_CHEST, depth=1)['items']
    want = [i['serial'] for i in items if int(i['graphic'], 16) in set(castle.RUNES) | RUNEBOOK_GRAPHICS]
    for a in call('POST', '/name', serial=','.join(want)) if want else []:
        line = ' '.join(a.get('lines', [])).lower()
        courtyard = a['serial'] == SKARA_RUNE
        if (courtyard and not kit['rune']) or ('tinker' in line and not kit['book']):
            to = restock.BAG if courtyard else status()['backpack']['serial']
            call('POST', '/move', serial=a['serial'], to=to)
            say(f"from the user's chest: {line}")
    call('POST', '/close', serial=USER_CHEST)
    kit = find_kit(state)
    stay_in_tools_room_safe()
    if not (kit['rune'] and kit['book']):
        raise Stop(f"the skara rune or the Tinkers runebook is neither in his pack nor in the user's chest: {kit}")
    return kit


# ---- gold ----

def est_price(state):
    prices = [t['price'] for t in state.get('tinkers', {}).values() if t.get('price')]
    return max(prices) if prices else GUESS_PRICE


def round_need(state, todo):
    """Gold this round's tinkers still want: each one's last stock plus the hour's growth, at his last price."""
    need = 0
    for slot in todo:
        t = state.get('tinkers', {}).get(str(slot), {})
        stock = (t.get('stock') if t.get('stock') is not None else GUESS_STOCK) + (GROWTH if t.get('bought_out') else 0)
        if t.get('bought_out') is False and t.get('left') is not None:
            stock = t['left']  # part way through his cycle: what he has left
        need += stock * (t.get('price') or est_price(state))
    return need


def gold_to_carry(state, todo):
    """What he should carry leaving the bank: the round's need, but no more than GOLD_LOADS full loads (gold weighs)."""
    st = status()
    load = max(1, (st['weightMax'] - WEIGHT_MARGIN - st['weight']) // SHOVEL_STONES)
    cap = int(GOLD_LOADS * load * est_price(state))
    return max(est_price(state) * 10, min(round_need(state, todo), cap))


def bank(state, todo):
    """Recall to the Ocllo bank, "bank", gold from the box up to gold_to_carry. Raises OutOfGold (after the gold
    there is taken) when the box has none."""
    rune = state['kit']['bank']
    if not rune:
        raise Stop('no "Ocllo Bank" rune in his pack')
    st = castle_call(castle.recall, rune, 'the Ocllo bank')
    if max(abs(st['x'] - OCLLO_BANK[0]), abs(st['y'] - OCLLO_BANK[1])) > BANK_SLACK:
        raise gems.LeaveTown(f"the bank rune put him at {st['x']},{st['y']}, not at the Ocllo bank")
    r = call('POST', '/say', text='bank')
    box = (r.get('bank') or {}).get('serial')
    if not box:
        raise gems.LeaveTown(f'"bank" opened no bank box: {texts(r)}')
    time.sleep(1)
    items = call('GET', '/contents', serial=box, depth=3)['items']
    piles = sorted((i for i in trips.walk_items(items) if int(i['graphic'], 16) == trips.GOLD),
                   key=lambda i: -(i.get('amount') or 1))
    in_bank = sum(i.get('amount') or 1 for i in piles)
    have = gold_carried()
    want = gold_to_carry(state, todo) - have
    say(f'the bank: {in_bank} gold in the box; he carries {have}, takes {max(0, want)} '
        f'(the round still wants about {round_need(state, todo)} at {est_price(state)} a shovel)')
    state['bank_gold'] = {'gold': in_bank, 'time': time.strftime('%Y-%m-%d %H:%M')}
    if want <= 0:
        return
    if not piles:
        raise OutOfGold(f'no gold left in the bank (he carries {have})')
    _, pack_list = pack_items()
    mine = [i for i in pack_list if int(i['graphic'], 16) == trips.GOLD]
    for p in piles:
        if want <= 0:
            break
        amount = p.get('amount') or 1
        take = min(want, amount)
        onto = mine[0]['serial'] if mine else status()['backpack']['serial']
        call('POST', '/move', serial=p['serial'], to=onto, amount=take if take < amount else None)
        want -= take
        _, pack_list = pack_items()
        mine = [i for i in pack_list if int(i['graphic'], 16) == trips.GOLD]
    say(f'gold: he carries {gold_carried()} now; {in_bank - (gold_carried() - have)} left in the bank')
    state['bank_gold']['gold'] = in_bank - (gold_carried() - have)
    save_state(state)


# ---- at the tinkers ----

def find_tinkers(v, me):
    near = [m for m in call('GET', '/nearby', range=trips.SIGHT)['mobiles']
            if m.get('human') and not m.get('dead') and m['serial'] != me]
    untitled = [m['serial'] for m in near if m.get('distance', 99) <= TINKER_RANGE
                and not trips.NPC_LABEL.search(v['npcs'].get(m['serial'], ''))]
    if untitled:
        for serial, title in gems.titles(v, untitled).items():
            if title and trips.NPC_LABEL.search(title):
                v['npcs'][serial] = title
        trips.save_vendor(v)
    found = [m for m in near if ' the tinker' in v['npcs'].get(m['serial'], '').lower()
             and m.get('distance', 99) <= TINKER_RANGE]
    return sorted(found, key=lambda m: m.get('distance', 99))


def buy_from(v, state, entry, tinker):
    """"<name> buy" and every shovel that fits and the gold covers. Returns (bought, his stock, price, left)."""
    serial = tinker['serial']
    label = v['npcs'].get(serial, serial)
    if not tinker.get('title'):
        gems.titles(v, [serial])  # the client forgets titles once he has left town; the bridge needs it
    r = trips.shop(serial, 'buy')
    rows = [i for i in r.get('items', []) if int(i['graphic'], 16) in SHOVELS]
    stock = sum(i.get('amount') or 0 for i in rows)
    price = max((i.get('price') or 0) for i in rows) if rows else None
    if not rows:
        if r.get('open'):
            call('POST', '/shop', close=1)
        say(f'{label} ({entry["name"]}): no shovels in his list' + (f' ({texts(r)})' if texts(r) else ''))
        return 0, 0, None, 0
    room, gold = shovel_room(), gold_carried()
    want = min(stock, room, gold // max(price, 1))
    if want <= 0:
        call('POST', '/shop', close=1)
        say(f'{label}: {stock} shovels at {price}, but room for {room} and {gold} gold: buys none')
        return 0, stock, price, stock
    deal, left_to_take = [], want
    for i in rows:
        take = min(i['amount'], left_to_take)
        if take > 0:
            deal.append((i['serial'], take))
            left_to_take -= take
    w0 = status()['weight']
    b = trips.at_him(serial, '/buy', items=','.join(f'{s}:{a}' for s, a in deal))
    bought = b.get('bought', 0)
    w1 = status()['weight']
    say(f'{label} ({entry["name"]}): bought {bought} of his {stock} shovels at {price} '
        f'({b.get("goldBefore")} -> {b.get("gold")} gold; room was {room}; weight {w0} -> {w1})'
        + (f': {texts(b)}' if texts(b) else ''))
    if bought and (w1 - w0) > bought * SHOVEL_STONES + 1:
        raise Stop(f'the shovels weigh more than {SHOVEL_STONES} stones each ({w1 - w0} for {bought}): '
                   f'SHOVEL_STONES needs changing')
    return bought, stock, price, stock - bought


def visit(v, state, entry, me):
    """Every tinker near this landing. Returns True when every one of them is bought out."""
    tot = state.setdefault('totals', {})
    tinkers = find_tinkers(v, me)
    t = tinker(state, entry['loc'])
    t['name'] = entry['name']
    t.pop('skip_until', None)
    if t.get('bought_out') is not False or not t.get('due'):  # the first open since he was bought out (or ever):
        # a new cycle, his clock starts
        t['opened'], t['due'], t['bought_out'] = time.time(), time.time() + RESTOCK, False
    if not tinkers:
        say(f'no tinker near where {entry["name"]} lands')
        t['note'] = 'no tinker found'
        t['bought_out'] = True
        return True
    done, slot_stock = True, 0
    for tk in tinkers:
        gems.check_town(v, me)
        bought, stock, price, left = buy_from(v, state, entry, tk)
        slot_stock += stock  # every tinker at this rune together (Britain's guildmaster sells none)
        t.update({'stock': slot_stock, 'price': price or t.get('price'), 'time': time.strftime('%Y-%m-%d %H:%M')})
        if stock:
            t['tinker'] = v['npcs'].get(tk['serial'], tk['serial'])
        tot['bought'] = tot.get('bought', 0) + bought
        tot['gold'] = tot.get('gold', 0) + bought * (price or 0)
        with open(VISITS, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps({'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'rune': entry['name'],
                                 'tinker': tk['serial'], 'title': v['npcs'].get(tk['serial']), 'stock': stock,
                                 'price': price, 'bought': bought, 'left': left, 'gold': gold_carried()}) + '\n')
        save_state(state)
        t['left'] = left
        if left:
            done = False
            t['bought_out'] = False
            if gold_carried() < (price or 1) and shovel_room() >= MIN_ROOM:
                raise NeedGold(f'{left} shovels left at {entry["name"]}, {gold_carried()} gold')
            raise Full(f'{left} shovels left at {entry["name"]}; his pack is full ({shovel_room()} more fit)')
        t['bought_out'] = True
    return done


def recall_once(state, entry):
    """One Recall with the book's flag: his /status once landed by the rune, None when "That location is blocked."
    (each try costs reagents: 2026-11-24 16:25-16:28 gems.recall_to's three quick tries per attempt took 22 of each
    down to 17 at Magincia). A fizzle is cast once more; anything else raises gems.LeaveTown."""
    for _ in range(2):
        st0 = status()
        if st0['mana'] < 11:
            raise gems.LeaveTown(f'no mana to Recall to {entry["name"]} ({st0["mana"]})')
        g = gems.open_book(state)
        before = gems.last_message_id()
        call('POST', '/gump', serial=g['serial'], id=g['id'], button=2 + 6 * entry['slot'] + gems.RECALL)
        end, said = time.time() + 8, ''
        while time.time() < end:
            st = status()
            if abs(st['x'] - st0['x']) + abs(st['y'] - st0['y']) > 10:
                spot = entry.get('spot')
                off = max(abs(st['x'] - spot[0]), abs(st['y'] - spot[1])) if spot else 0
                say(f"Recall to {entry['name']}: at {st['x']},{st['y']},{st['z']}")
                if off > gems.LANDING_SLACK:
                    raise gems.LeaveTown(f"landed at {st['x']},{st['y']}, {off} tiles from {entry['name']}'s spot")
                return st
            said = ' | '.join(m['text'] for m in call('GET', '/messages')['messages'] if m['id'] > before)
            low = said.lower()
            if 'location is blocked' in low:
                return None
            if any(w in low for w in ('fizzle', 'disturbed', 'more reagents', 'insufficient mana',
                                      'not yet recovered', 'already casting', 'cannot')):
                break
            time.sleep(0.15)
        say(f'Recall to {entry["name"]} did not take him: {said or "-"}')
        if min(recall_reagents().values()) < HOME_RESERVE + 1:
            break  # what's left is for the way home
        time.sleep(1.5)
    raise gems.LeaveTown(f'Recall to {entry["name"]} failed: {said or "-"}')


class Blocked(Exception):
    """The rune's spot stayed blocked: the next tinker this trip, this one again next trip."""


def recall_to(v, state, loc, me, away):
    """To a town's tinker by one of its runes. The user, 2026-11-24, after blocked spots: "I fixed it by creating 2
    runes for each location. From now on we should alternate betweek rune 1 and 2 for each location": each visit starts
    with the rune after the one that took him last time. A blocked spot tries the town's other rune at once; both
    blocked: the backoff (the user: "If a location is blocked then try it again in 1 minute" -> "exponential backoff up
    to 2 minutes"), both runes again after each wait. Every blocked try is logged by rune (blocked.jsonl)."""
    t = tinker(state, loc['loc'])
    runes = loc['runes']
    first = t.get('next_rune', 0) % len(runes)
    order = runes[first:] + runes[:first]
    for attempt in range(len(BLOCKED_WAITS) + 1):
        for rune in order:
            if away:
                recall_reagents_ok(ONWARD_NEED, f'to try {rune["name"]}')
            gems.here['entry'] = rune
            st = recall_once(state, rune)
            if attempt or st is None or rune is not order[0]:
                with open(BLOCKED_LOG, 'a', encoding='utf-8') as fh:
                    fh.write(json.dumps({'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'rune': rune['name'],
                                         'spot': rune.get('spot'), 'try': attempt + 1,
                                         'blocked': st is None}) + '\n')
            if st is not None:
                t['next_rune'] = (runes.index(rune) + 1) % len(runes)
                t['last_rune'] = rune['name']
                return st
            if len(order) > 1 and rune is not order[-1]:
                say(f'{rune["name"]}: that location is blocked; trying {order[order.index(rune) + 1]["name"]}')
        if attempt == len(BLOCKED_WAITS) or check_stop_file():
            break
        wait = BLOCKED_WAITS[attempt]
        say(f'{loc["name"]}: ' + ('both runes' if len(runes) > 1 else 'that location') + f' blocked; again in {wait} s')
        end = time.time() + wait
        while time.time() < end:
            if away:
                gems.check_town(v, me)
            elif taken():
                raise UserHas(f'the user took over ({taken()})')
            time.sleep(10)
    raise Blocked(f'{loc["name"]}: every rune stayed blocked (tried again after {sum(BLOCKED_WAITS)} s)')


def location_key(name):
    """ "Britain 1", "Britain 2" -> "Britain"; "Serpents Tinker" (the old book) -> "Serpents" """
    import re
    return re.sub(r'\s+(\d+|tinker)$', '', name.strip(), flags=re.I)


def norm(name):
    import re
    return re.sub('[^a-z]', '', location_key(name).split()[0].lower()) if name.strip() else ''


def locations(entries):
    """The book's runes by town, in the book's order, rune 1 before rune 2."""
    import re
    out = {}
    for e in entries:
        key = location_key(e['name'])
        e['loc'] = key
        out.setdefault(key, {'loc': key, 'name': key, 'runes': []})['runes'].append(e)
    def number(e):
        m = re.search(r'(\d+)$', e['name'])
        return int(m.group(1)) if m else 0
    for loc in out.values():
        loc['runes'].sort(key=number)
    return out


def rekey(state, locs):
    """The tinkers' state by town (it was by runebook slot, one rune a town, before 2026-11-24 17:00)."""
    tinkers = state.setdefault('tinkers', {})
    by_norm = {norm(k): k for k in locs}
    for old in [k for k in tinkers if k.isdigit()]:
        t = tinkers.pop(old)
        new = by_norm.get(norm(t.get('name') or ''))
        if new and new not in tinkers:
            tinkers[new] = t
            say(f'the state of {t.get("name")} (slot {old}) is now {new}\'s')


# ---- the schedule: a clock per tinker ----
# The user, 2026-11-24: "how are we going to space this out so the vendors refresh soon enough? If a run takes 10
# minutes and you have problems with blocked locations and it ends up taking 20 minutes.." -> "yes, do that": each
# tinker has his own clock. A vendor restocks when his buy list is asked for an hour or more after his last restock, so
# a tinker's cycle starts the first time his list is opened after he was bought out, and he's due again RESTOCK after
# that. Trips go to whoever is due, earliest first; a slow trip only delays the ones still in it.

# Recall's reagents (the user, 2026-11-24: "watch the reagent count for the 2 reagents used by the recall spell and top
# up using the reagent chest when it gets low"): black pearl, blood moss, mandrake root. Before every trip
# castle.reagents_ok() tops every reagent up from the user's entrance reagent chest (938 2nd) when any is below 25
# (restock.MINIMUM; to 45/40/45), and a trip needs at most about 12 Recalls (the bank twice, 7 tinkers, home, spares),
# so he never leaves short. In town he checks before every Recall on that he keeps 2 of each (that one and home).
RECALL_REAGENTS = {0x0F7A: 'black pearl', 0x0F7B: 'blood moss', 0x0F86: 'mandrake root'}
# never so few that he can't get home (the user, 2026-11-24): the Recall home is tried up to 3 times (a fizzle uses
# reagents too), so 3 of each are always kept for it; a Recall on in town may take 2 casts (recall_once casts again
# after a fizzle). So: on to a tinker only with 2 + 3 of each; to the bank and back with 2 x 2 + 3.
HOME_RESERVE = 3
ONWARD_NEED = 2 + HOME_RESERVE
BANK_NEED = 4 + HOME_RESERVE
TRIP_RECALLS = 12


def recall_reagents():
    have = restock.counts(refresh=False)
    return {name: have.get(g, 0) for g, name in RECALL_REAGENTS.items()}


def recall_reagents_ok(need, where):
    have = recall_reagents()
    short = {k: n for k, n in have.items() if n < need}
    if short:
        raise gems.LeaveTown(f'Recall reagents low {where} ({", ".join(f"{k} {n}" for k, n in short.items())}): home '
                             f'to top up from the reagent chest')


RESTOCK = 61 * 60   # a tinker is due this long after his list was first opened in his last cycle
SKIP_BLOCKED = 10 * 60  # a spot still blocked after the backoff: tried again every 10 minutes (the user, 2026-11-24:
                        # "re-schedule the ones that were blocked to try them again each 10 minutes"); others go on


def tinker(state, slot):
    return state.setdefault('tinkers', {}).setdefault(str(slot), {})


def due_at(state, slot):
    """When this tinker is next worth a visit: now if he isn't bought out in his current cycle (or never seen), else
    his clock; never before a skip ends."""
    t = tinker(state, slot)
    at = time.time() if t.get('bought_out') is False or not t.get('due') else t['due']
    return max(at, t.get('skip_until') or 0)


def skip(state, slot, seconds, why):
    t = tinker(state, slot)
    t['skip_until'] = time.time() + seconds
    t['skipped'] = f"{time.strftime('%H:%M')}: {why}"
    save_state(state)


def trip(v, state, entries, todo):
    """One trip out: the bank if the gold is low, then the due tinkers in todo in turn until he's full, home. Returns
    why he came home early (None: every one in todo done)."""
    tot = state.setdefault('totals', {})
    need = ONWARD_MANA + 11 * min(3, len(todo))
    prepare(state, need)
    have = recall_reagents()
    if min(have.values()) < TRIP_RECALLS:  # (reagents_ok tops up below 25: this only shows if the chest ran short)
        raise Stop(f"not enough Recall reagents for a trip after the top-up: {have} (the user's reagent chest, 938 2nd, "
                   f"may be running out)")
    price = est_price(state)
    away, why = False, None
    me = status()['serial']
    try:
        if gold_carried() < min(round_need(state, todo), price * shovel_room()):
            away = True  # (a failed Recall to the bank leaves him inside; home() then just comes back in)
            bank(state, todo)
        for slot in list(todo):
            if check_stop_file():
                break
            entry = entries[slot]
            if shovel_room() < MIN_ROOM:
                raise Full('his pack is full')
            if status()['mana'] < ONWARD_MANA:
                if away:
                    gems.meditate_in_town(v, me, ONWARD_MANA + 11)
                if status()['mana'] < ONWARD_MANA:
                    raise gems.LeaveTown(f'not enough mana to go on ({status()["mana"]})')
            while True:
                gems.here['entry'] = entry
                if away:
                    recall_reagents_ok(ONWARD_NEED, 'in town')
                try:
                    recall_to(v, state, entry, me, away)
                except Blocked as e:
                    say(f'{e}: on to the next tinker; this one again in {SKIP_BLOCKED // 60} minutes or later')
                    skip(state, slot, SKIP_BLOCKED, 'the spot stayed blocked')
                    todo.remove(slot)
                    break
                away = True
                try:
                    gems.check_town(v, me)
                    if visit(v, state, entry, me):
                        todo.remove(slot)
                        save_state(state)
                    break
                except NeedGold as e:
                    say(f'{e}: to the bank and back')
                    if status()['mana'] < 11 * 3:
                        gems.meditate_in_town(v, me, 11 * 3 + 5)
                    recall_reagents_ok(BANK_NEED, 'for the bank and back')
                    bank(state, todo)
                    continue
    except NeedGold as e:
        why = str(e)
    except Full as e:
        why = str(e)
    except gems.PlayerInTown as e:
        why = 'player'
        say(f'leaving town: {e}')
        slot = (gems.here.get('entry') or {}).get('loc')
        if slot is not None:
            # the town rule (map and gem trips): home, and 15 minutes before going back there
            skip(state, slot, PLAYER_WAIT, str(e))
            say(f'{entries[slot]["name"]}: not before {PLAYER_WAIT // 60} minutes from now')
    except (gems.LeaveTown, trips.GoHome) as e:
        if not away:
            raise Stop(f'could not leave the castle: {e}')
        why = str(e)
        say(f'leaving town: {e}')
        slot = (gems.here.get('entry') or {}).get('loc')
        if isinstance(e, trips.GoHome) and slot is not None:
            skip(state, slot, SKIP_BLOCKED, str(e))
            say(f'{entries[slot]["name"]}: skipped for {SKIP_BLOCKED // 60} minutes ({e})')
    except UserHas:
        raise
    except OutOfGold:
        if away:
            home(state)
        raise
    except (Stop, gems.Stop, trips.Stop, uo.BridgeError) as e:
        if taken():
            raise UserHas(f'the user took over ({taken()})')
        if not away:
            raise
        st = uo.call(info, 'GET', '/status')
        if st.get('halted'):
            uo.call(info, 'POST', '/resume')
            say(f'in town the bridge stopped ({st.get("halted")}): resumed, going home')
        say(f'in town: {e}; going home')
        home(state)
        raise Stop(f'in town: {e} (he came home; the loop stops)')
    except Exception as e:
        if taken():
            raise UserHas(f'the user took over ({taken()})')
        if not away:
            raise
        say(f'in town, something unexpected: {e!r}; going home\n{traceback.format_exc()}')
        home(state)
        raise Stop(f'in town, something unexpected: {e!r} (he came home; the loop stops)')
    if away:
        home(state)
    tot['trips'] = tot.get('trips', 0) + 1
    save_state(state)
    return why


def wait_until(t):
    """In the tools room until t (the stop file, a takeover or a bridge stop end it early). Sends nothing."""
    while time.time() < t:
        if check_stop_file():
            return
        st = uo.call(info, 'GET', '/status')
        if st.get('takenOver'):
            raise UserHas(f'the user took over ({st["takenOver"]})')
        if st.get('halted'):
            raise Stop(f'the bridge stopped ({st["halted"]})')
        time.sleep(15)


RULES = os.path.join(HERE, 'rules', 'rules-Clem.json')
AREA_HALF = 25


def area_lines(entries):
    return [f'    {{ "name": "tinker: {e["name"]}", "box": [{e["spot"][0] - AREA_HALF}, {e["spot"][1] - AREA_HALF}, '
            f'{e["spot"][0] + AREA_HALF}, {e["spot"][1] + AREA_HALF}], "z": [-30, 80] }},' for e in entries if e.get('spot')]


def sync_areas(entries, rules_path=None, agent_dir=None):
    """Clem's rules' tinker areas from the runebook: a rune the user re-marked (to get off a blocked spot) moves its
    area with it. Returns True when the rules changed (written here and into the client's Agent folder)."""
    import re
    rules_path = rules_path or RULES
    text = open(rules_path, encoding='utf-8').read()
    pat = re.compile(r'(?m)^    \{ "name": "tinker: .*\},\n')
    old = pat.findall(text)
    new = [line + '\n' for line in area_lines(entries)]
    if not old or sorted(old) == sorted(new):
        return False
    first = pat.search(text).start()
    text = pat.sub('', text)
    text = text[:first] + ''.join(new) + text[first:]
    with open(rules_path, 'w', encoding='utf-8') as fh:
        fh.write(text)
    if agent_dir is not False:
        import shutil
        shutil.copy(rules_path, os.path.join(agent_dir or uo.AGENT_DIR, 'rules-Clem.json'))
    say("the runebook's spots changed: Clem's rules' tinker areas updated (" +
        ', '.join(f"{e['name']} {e['spot']}" for e in entries) + ')')
    return True


def migrate(state):
    """The first round (16:11-16:19, one clock for the whole round): each tinker's first open as his clock."""
    rnd = state.get('round') or {}
    for slot, fo in (rnd.get('first_open') or {}).items():
        t = tinker(state, slot)
        if t.get('due'):
            continue
        if not fo.get('stock'):  # no shovels seen (Serpent's Hold: only the guildmaster was in range): due now
            t['bought_out'] = False
            continue
        h, m = map(int, fo['time'].split(':'))
        lt = time.localtime()
        opened = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
        t['opened'], t['due'] = opened, opened + RESTOCK
        t.setdefault('bought_out', True)
    if rnd:
        tot = state.setdefault('totals', {})
        tot.setdefault('bought', rnd.get('bought', 0))
        tot.setdefault('gold', rnd.get('gold', 0))
        tot.setdefault('trips', rnd.get('trips', 0))
        state['first_round'] = rnd
        state.pop('round', None)
    save_state(state)


def schedule_line(state, entries):
    return '; '.join(f"{e['name'].replace(' Tinker', '')} " +
                     ('now' if due_at(state, e['loc']) <= time.time() else
                      time.strftime('%H:%M', time.localtime(due_at(state, e['loc'])))) for e in entries)


def run(once=False, now=False, keep_count=False):
    state = load_state()
    st = status()
    say(f"--- shovels.py run: Clem at {st['x']},{st['y']},{st['z']}, {st['weight']}/{st['weightMax']} stones, "
        f"mana {st['mana']}, {gold_carried()} gold")
    # wherever he is: home first
    if in_north_yard(st):
        go_in_north()
    elif in_courtyard(st):
        go_in()
    elif not castle.inside((st['x'], st['y'])):
        kit = find_kit(state)
        if not kit['rune']:
            raise Stop(f"he's at {st['x']},{st['y']} with no skara rune to come home with")
        home(state)
    kit = fetch(state)
    if not kit['bank']:
        raise Stop('no "Ocllo Bank" rune in his pack (his reagent bag)')
    if keep_count:  # a restart in the middle of a run (new code): the count kept so far stands
        tools_room.TRUST_CACHE = True
        if shovels_carried():
            put_away(state)
        say(f'TOOLS ROOM: {room_shovels()} shovels (the count kept from the run so far)')
    else:
        count_room(state)
    migrate(state)
    v = gems.load_vendors()
    V['v'] = v
    g = gems.open_book(state)
    entries = gems.book_entries(g)
    gems.close_book(g)
    by_slot = locations(entries)  # by town: two runes each since 2026-11-24 17:00
    rekey(state, by_slot)
    for key in by_slot:
        tinker(state, key)['name'] = key
    sync_areas(entries)
    if now:
        for key in by_slot:
            tinker(state, key).pop('skip_until', None)
    entries = list(by_slot.values())  # the schedule lines go by town
    save_state(state)
    say('the runebook: ' + ', '.join(f"{k} ({', '.join(r['name'] for r in loc['runes'])})" for k, loc in by_slot.items()))
    say('the tinkers are due: ' + schedule_line(state, entries))
    idle, last_wait_line = 0, None
    while not check_stop_file():
        due = sorted((s for s in by_slot if due_at(state, s) <= time.time()), key=lambda s: due_at(state, s))
        if not due:
            if once and state.get('totals', {}).get('trips'):
                break
            nxt = min(due_at(state, s) for s in by_slot)
            state['next_due'] = time.strftime('%H:%M', time.localtime(nxt))
            save_state(state)
            st = status()
            if (st['x'], st['y']) != tools_room.STAND:
                stay_in_tools_room_safe()
            line = 'waiting in the tools room: ' + schedule_line(state, entries)
            if line != last_wait_line:
                say(line)
                last_wait_line = line
            wait_until(min(nxt, time.time() + 300))
            continue
        tot = state.setdefault('totals', {})
        before = (tot.get('bought', 0), len(due))
        say(f"--- trip: due {', '.join(by_slot[s]['name'] for s in due)}")
        why = trip(v, state, by_slot, due)
        idle = idle + 1 if (tot.get('bought', 0), len(due)) == before and why != 'player' else 0
        if idle >= 3:
            raise Stop(f'three trips in a row bought nothing and finished no tinker (last: {why}); he is home')
        bank = state.get('bank_gold') or {}
        say(f"STATUS: TOOLS ROOM {state.get('room_total', '?')} shovels; this trip bought "
            f"{tot.get('bought', 0) - before[0]}; this run {tot.get('bought', 0)} shovels for {tot.get('gold', 0)} gold "
            f"spent; the bank {bank.get('gold', '?')} gold (at {bank.get('time', '?')[-5:]}), he carries "
            f"{gold_carried()}; next due: {schedule_line(state, entries)}")
        last_wait_line = None
    if stopping.get('pause'):
        if shovels_carried():
            put_away(state)
        state['paused'] = time.strftime('%Y-%m-%d %H:%M:%S')
        save_state(state)
        st = status()
        say(f"PAUSED: Clem waits in the tools room at {st['x']},{st['y']} with the rune and the book; the tinkers' "
            f"clocks keep running (`shovels.py resume` goes on with whoever is due)")
        return
    if stopping['flag'] or once:
        if shovels_carried():
            put_away(state)
        cleanup(state)
        try:
            os.remove(STOP_FILE)
        except OSError:
            pass
        st = status()
        say(f"stopped: the rune and the runebook are in the user's chest; Clem waits in the tools room at "
            f"{st['x']},{st['y']}")


def blocked_report():
    """Per rune: how often its spot was blocked, how often it cleared on a later try, how often it never did."""
    rows = []
    try:
        with open(BLOCKED_LOG, encoding='utf-8') as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
    except OSError:
        pass
    # the visits each rune got, for the rate
    visits = {}
    try:
        with open(VISITS, encoding='utf-8') as fh:
            for line in fh:
                r = json.loads(line)
                visits.setdefault(r['rune'], set()).add(r['time'][:16])
    except OSError:
        pass
    by = {}
    for r in rows:
        e = by.setdefault(r['rune'], {'spot': r.get('spot'), 'blocked tries': 0, 'cleared': 0, 'days': set()})
        e['days'].add(r['time'][:10])
        if r['blocked']:
            e['blocked tries'] += 1
        else:
            e['cleared'] += 1
    if not by:
        print('no blocked Recall spots recorded yet')
    for rune, e in sorted(by.items(), key=lambda kv: -kv[1]['blocked tries']):
        print(f"{rune} (rune spot {e['spot']}): blocked {e['blocked tries']} tries, cleared on a later try "
              f"{e['cleared']} times; {len(visits.get(rune, ()))} visits recorded")


def show():
    state = load_state()
    print(json.dumps({k: state.get(k) for k in ('next_due', 'room_total', 'bank_gold', 'totals', 'tinkers', 'kit')},
                     indent=1))


def on_term(signum, frame):
    stopping['flag'] = True
    say('asked to stop (signal): finishing this step, then home')


def main():
    global info
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['run', 'stop', 'pause', 'resume', 'cleanup', 'fetch', 'status', 'blocked'])
    parser.add_argument('--once', action='store_true', help='one round, then the cleanup')
    parser.add_argument('--keep-count', action='store_true',
                        help='a restart mid-run: no recount of the tools room, the count kept so far stands')
    parser.add_argument('--now', action='store_true', help='start a round at once, not at the next hour mark')
    args = parser.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if args.command == 'status':
        show()
        return
    if args.command == 'blocked':
        blocked_report()
        return
    if args.command == 'pause':
        open(PAUSE_FILE, 'w').close()
        running = os.popen("pgrep -f 'Python -I shovels.py (run|resume)'").read().split()
        print('asked: the loop finishes this step (in town: that tinker, then home), puts the shovels away and exits; '
              'the rune and book stay with him' if running else 'paused (the loop was not running)')
        return
    if args.command == 'stop':
        open(STOP_FILE, 'w').close()
        print('asked: the loop stops after this step, comes home, puts the shovels away and the rune and book back')
        return
    info = uo.find_bridge(CHAR)
    tools_room.setup(info)  # its uo.call goes past Razor's AutoSearch (bags landing in his pack)
    trips.info = carto.info = door.info = restock.info = castle.info = gems.info = info
    trips.LOG = carto.LOG = gems.LOG = castle.LOG = restock.LOG = LOG
    tools_room.say = say
    tools_room.castle_move.say = say
    trips.approach = gems.approach  # up to a vendor by his shop's way (gems.SHOP_ROOMS), another floor: on to the next
    trips.VENDOR = gems.VENDORS = VENDORS
    st = uo.call(info, 'GET', '/status')
    if args.command == 'resume':
        try:
            os.remove(PAUSE_FILE)
        except OSError:
            pass
        if st.get('takenOver'):  # the user asking to resume is the handback (the uo skill: start means handback)
            uo.call(info, 'POST', '/resume', handback=True)
            say(f"handed back by the user to resume (was: {st['takenOver']})")
            st = uo.call(info, 'GET', '/status')
    elif os.path.exists(PAUSE_FILE) and args.command == 'run':
        sys.exit('paused: `shovels.py resume` to go on')
    if st.get('takenOver'):
        sys.exit(f"the user has him ({st['takenOver']}): `uo --char Clem handback` when they ask for a job with him")
    if st.get('halted'):
        sys.exit(f"the bridge has stopped ({st['halted']}): look first")
    try:
        if args.command in ('run', 'resume'):
            try:
                os.remove(STOP_FILE)
            except OSError:
                pass
            signal.signal(signal.SIGTERM, on_term)
            if args.command == 'resume':
                state = load_state()
                state.pop('paused', None)
                save_state(state)
                run(now=True, keep_count=True)  # skips forgotten (the runes may be fixed), no recount mid-run
            else:
                run(args.once, args.now, args.keep_count)
        elif args.command == 'cleanup':
            cleanup(load_state())
        elif args.command == 'fetch':
            state = load_state()
            fetch(state)
            save_state(state)
    except UserHas as e:
        say(f'STOPPED (the user has him): {e}')
        sys.exit(1)
    except (Stop, trips.Stop, gems.Stop, castle.Stop, restock.Stop, tools_room.td.Stop) as e:
        say(f'STOPPED: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
