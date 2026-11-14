#!/usr/bin/env python3
"""The lumberjacking loop (see LUMBERJACKING.md): Icepick rides the tour of 8x8 wood blocks in west Britain, chops one
tree in each until "not enough wood", saws the logs into boards when they get heavy, and when he's full of boards
rides to Burgers by the building in the middle of the area and hands them over; Burgers banks them in Ocllo.

  python3 lumber.py [--laps N] [--from BLOCK] [--to BLOCK]
                                   --laps 0: lap after lap until something runs out (axes, or Burgers' reagents)
  python3 lumber.py --unload       only saw, hand the boards to Burgers and send him to the bank, then stop
  python3 lumber.py --bank         only a bank trip for Burgers
  python3 lumber.py --park         ask the running loop to park both (mounted and hidden) and end
  python3 lumber.py --stop         end the running loop at once (an emergency: nobody is parked)
  python3 lumber.py --incidents | --reviewed

It's mine.py's Miner with the mining parts swapped out: everything about safety is mining's, unchanged (the guard,
getting away and hiding from people, "Guards!" and stepping away from creatures, poison and cure potions, town
guards, McGee, the tired horse, rides planned on the map and learned buildings, lag, world saves, park and stop).
What's different: the area and rules (rules-Icepick-lumber.json, rules-Burgers-lumber.json), the tour
(lumbering.py), chopping mounted with an axe in his hands, the saw, the meeting spot and the boards at the bank.
Its own work folder: ~/claude/uo-agent-work/lumber (lumber.log, state.json, incidents.jsonl).

Mining and lumberjacking both use Icepick: never run both. This refuses to start while mine.py runs.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import uo  # noqa: E402
import mining  # noqa: E402
import lumbering  # noqa: E402
import mine  # noqa: E402

MINE_PID = mine.PID_FILE   # the mining loop's, to refuse to run alongside it
MINE_STATE = mine.STATE    # the town guards found while mining

# ---- mine.py's module settings, pointed at lumberjacking (its functions read them when they run) ----
WORK = os.path.expanduser('~/claude/uo-agent-work/lumber')
mine.WORK = WORK
mine.LOG = os.path.join(WORK, 'lumber.log')
mine.INCIDENTS = os.path.join(WORK, 'incidents.jsonl')
mine.STATE = os.path.join(WORK, 'state.json')
mine.PID_FILE = os.path.join(WORK, 'lumber.pid')
mine.PARK_FILE = os.path.join(WORK, 'park')
mine.BURGERS_WAIT = lumbering.MEET_BURGERS
mine.ICE_MEET = lumbering.MEET_ICEPICK
# his runes, checked by name before each use: the bank, Mining Start (where he gets away to) and the meeting spot
mine.RUNE_NAMES = {'bank': 'ocllo bank', 'start': 'mining start', 'meet': 'lumber meet'}
# only the recall reagents matter here (no gates)
mine.REAGENTS = {g: n for g, n in mine.REAGENTS.items() if g in mine.RECALL_REAGENTS}
mine.REAGENTS_LOW = {g: n for g, n in mine.REAGENTS_LOW.items() if g in mine.RECALL_REAGENTS}
# Icepick's areas everywhere mine.py asks for them (getting away, rides, hops): the lumberjacking ones
_load_rules = mining.load_rules
mining.load_rules = lambda name='Icepick-lumber': _load_rules(name)
log = mine.log
cheb = mine.cheb
Stop, Alarm, Again, Parked, NoWay = mine.Stop, mine.Alarm, mine.Again, mine.Parked, mine.NoWay


def install_rules(src, dest):
    with open(os.path.join(mining.HERE, 'rules', src), encoding='utf-8') as fh:
        text = mine.paced(fh.read())  # the town pacing flag (pacing.py; off since 2026-11-13)
    return text, os.path.join(mine.AGENT_DIR, dest)


def icepick_rules():
    """Icepick's lumberjacking rules in the client (mine.py puts the mining ones back when it starts)."""
    text, dest = install_rules('rules-Icepick-lumber.json', 'rules-Icepick.json')
    with open(dest, 'w', encoding='utf-8') as fh:
        fh.write(mine.with_guards(text))


def burgers_rules(bank):
    """Burgers' lumberjacking rules, with quick pacing at the bank (as in mining)."""
    text, dest = install_rules('rules-Burgers-lumber.json', 'rules-Burgers.json')
    if bank:
        text = re.sub(r'"pacing": \{[^}]*\}', mine.BANK_PACING, text)
    with open(dest, 'w', encoding='utf-8') as fh:
        fh.write(mine.with_guards(text))


mine.icepick_rules = icepick_rules
mine.burgers_rules = burgers_rules

LIMIT = mine.LIMIT          # never over this (393 of his 390: over it every step tires him; MINING.md)
CHOP = 20                   # a good chop: 10 logs of 2 stones (2026-11-12)
FULL_AT = 320               # after sawing, still above this: he's full of boards; to Burgers (340 made 530 boards,
                            # more than Burgers could carry with his spare axes, 2026-11-12 22:58)
BURGERS_MARGIN = 8          # Burgers is kept this many stones under his most, so he can still recall
AXE_BAG = '0x40766101'      # the blue bag in his pack: "whatever axes I put in the blue bag" (the user, 2026-11-12)
ICEPICK_AXES = 4            # spare axes in his blue bag, topped up by Burgers at every handoff (the user, 2026-11-12:
                            # "just like mining"); the first hatchet broke after about 80 chops
ICEPICK_SAWS = 3            # saws Icepick carries, topped up by Burgers at the handoff like the axes (a saw lasts about
                            # 70 sawings, 6-7 a load: 2026-11-13)
BURGERS_SAWS = 1            # Burgers' spare saw, from the bank's saws on every bank trip
BURGERS_AXES = 2            # Burgers' spares, topped up from an axe bag in his bank on every bank trip (the user,
                            # 2026-11-12: 8 was too many, about 8 stones each; Icepick carries the spares, Burgers only
                            # covers a break between bank trips); more than this go back into the bank
KEEP_REAGENTS = 3           # the user, 2026-11-14: when the loop stops, Burgers still has at least this many of each
                            # recall reagent (to recall to the bank and so on later). A bank trip takes 2 recalls, so
                            # he doesn't set off on one with fewer than KEEP_REAGENTS + 2 of any
AVOID_RANGE = 18            # tiles: blocks this near where a person kept standing are skipped (Hollis by the animal pen
AVOID_FOR = 20 * 60         # at 1288,1770, 2026-11-13: back in sight at every return, the waits doubling to 4 minutes)
# hatchet, double axe, large battle axe first (what the blue bag held), then the other axes; not a war axe (a mace)
AXES = ('0x0F43', '0x0F44', '0x0F4B', '0x0F4C', '0x13FA', '0x13FB', '0x0F49', '0x0F4A', '0x0F47', '0x0F48',
        '0x1442', '0x1443', '0x0F45', '0x0F46')
SAWS = ('0x1034', '0x1035')
LOGS = ('0x1BDD', '0x1BDE', '0x1BDF', '0x1BE0', '0x1BE1', '0x1BE2')
BOARDS = ('0x1BD7', '0x1BD8', '0x1BD9', '0x1BDA')
# what the server says to a chop (2026-11-12); anything else (a skill gain, the weather, a name) is ignored
CHOP_ANSWERS = ('put some logs', 'fail to produce', 'not enough wood', "can't use an axe", 'cannot be seen',
                'too far', 'equipped', 'worn out', 'broke your axe', 'you cannot', "can't reach")


class NeedAxes(Exception):
    """No axe in his hands and none in the bag: to Burgers for more."""


def is_kind(item, graphics, word):
    return item.get('graphic') in graphics or word in (item.get('type') or '').lower()


class Lumberjack(mine.Miner):
    def __init__(self, args):
        # Miner plans the mining route's ore blocks on start; not needed here
        plan, mining.plan = mining.plan, lambda *a, **k: []
        try:
            super().__init__(args)
        finally:
            mining.plan = plan
        self.tour = lumbering.load_tour()
        self.stats = {'chops': 0, 'logs': 0, 'misses': 0, 'blocks': 0, 'empty': 0, 'saws': 0, 'boards': 0,
                      'axes broken': 0, 'handoffs': 0, 'bank trips': 0, 'incidents': 0, 'fights': 0}
        self.runes = {'bank': mining.RUNES['bank'], 'start': mining.RUNES['start'], 'meet': lumbering.RUNE_MEET}
        self.axe_type = {}
        # for the update after every bank trip (the user, 2026-11-12: everything mining told them, and more)
        self.at_update = dict(self.stats)   # the counts at the last update, for "since then"
        self.broken_since = []              # axes broken since the last update: (kind, chops)
        self.update_since = time.strftime('%Y-%m-%d %H:%M:%S')
        self.last_handed = 0
        self.avoid = {}                     # serial -> (spot, until, name): someone who stays put by a block
        self.block_spot = None              # the block being chopped (its trees' centre)

    def load_state(self):
        try:
            with open(mine.STATE, encoding='utf-8') as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {'next': 0, 'emptied': {}, 'bags': {}}

    # ---- moving: always mounted, rides planned on the map (no recorded mining rides, no gates) ----

    def travel(self, spot):
        self.mount()
        area_list = mining.load_rules()['areas']
        for attempt in range(3):
            self.learn_obstacles()
            s = self.ice.status()
            here = (s['x'], s['y'])
            if cheb(here, spot) <= 1:
                self.check_mount_fatigue()
                return
            path = mining.plan_path(here, spot, area_list)
            if not path:
                log(f'the map shows no way from {here} to {spot}')
                break
            r = self.ice.call('POST', '/travel', path=';'.join(f'{x},{y}' for x, y in path[:200]))
            self.check_mount_fatigue()
            if r['arrived']:
                return
            log(f"ride to {spot} stopped at {r['x']},{r['y']} ({r.get('stopped')}); planning again")
            if r.get('stopped') == 'left the area':
                self.back_into_area(area_list)
        self.hop_to(spot)

    def go_to(self, spot):
        s = self.ice.status()
        if (s['x'], s['y']) == spot and s['mounted']:
            return
        self.check_mount_fatigue()
        self.mount()
        if cheb((s['x'], s['y']), spot) > 3:
            self.travel(spot)
        self.walk_to(spot)

    def burgers_back(self):
        while self.bur.status()['mana'] < 11:
            time.sleep(15)
        self.recall('meet')
        self.burgers_to_wait()

    # ---- the axe and the saw ----

    def axes_in_bag(self):
        try:
            items = self.ice.call('GET', '/contents', serial=AXE_BAG)['items']
        except uo.BridgeError:
            items = []
        loose = [i for i in self.ice.pack() if i.get('graphic') in AXES]
        found = [i for i in items + loose if i.get('graphic') in AXES]
        return sorted(found, key=lambda i: AXES.index(i['graphic']))

    def axe(self):
        """The axe in his hands; one from the blue bag put in his hands if there's none (the server insists on it:
        "The axe must be equipped for any serious wood chopping.")."""
        for h in self.ice.status()['hands']:
            if h.get('graphic') in AXES:
                self.axe_type[h['serial']] = h.get('type') or 'axe'
                return h['serial']
        spare = self.axes_in_bag()
        if not spare:
            raise NeedAxes()
        self.ice.call('POST', '/equip', serial=spare[0]['serial'])
        for h in self.ice.status()['hands']:
            if h.get('graphic') in AXES:
                self.axe_type[h['serial']] = h.get('type') or 'axe'
                log(f"Icepick takes a {h.get('type') or 'axe'} ({h['serial']}) in hand; {len(spare) - 1} more in the bag")
                return h['serial']
        raise Stop(f"Icepick couldn't take the axe {spare[0]['serial']} in hand")

    def piles(self, graphics, word):
        return [i for i in self.ice.pack() if is_kind(i, graphics, word)]

    def saw(self):
        """Saw all his logs into boards (saw -> Other -> board: one use does the whole pile, 2026-11-12). Returns how
        much lighter he got."""
        logs = self.piles(LOGS, 'logs')
        if not logs:
            return 0
        saws = [i for i in self.ice.pack() if i.get('graphic') in SAWS]
        if not saws:
            if not self.state.get('no_saw_warned'):
                log('Icepick has no saw: the logs stay logs (add saws to his pack)')
                self.state['no_saw_warned'] = True
                self.save_state()
            return 0
        self.state['no_saw_warned'] = False
        before = self.ice.status()['weight']
        n = sum(i.get('amount', 1) for i in logs)
        texts = []
        for attempt in range(2):
            a = self.ice.call('POST', '/use', serial=saws[0]['serial'])
            d = self.menu(a, 'what type of item')
            a = self.ice.call('POST', '/menu', serial=d['serial'], id=d['id'], index=self.menu_index(d, 'other'))
            d = self.menu(a, 'what do you want to make')
            a = self.ice.call('POST', '/menu', serial=d['serial'], id=d['id'], index=self.menu_index(d, 'board'))
            texts = self.craft_result(a)
            if any('worn out' in t.lower() for t in texts):
                # "You have worn out your tool!" (2026-11-13 01:47: the first saw, after about 75 sawings)
                left = len([i for i in self.ice.pack() if i.get('graphic') in SAWS])
                log(f'a saw wore out; Icepick has {left} left')
            if not self.piles(LOGS, 'logs'):
                break
        time.sleep(0.5)
        after = self.ice.status()['weight']
        left = sum(i.get('amount', 1) for i in self.piles(LOGS, 'logs'))
        made = n - left
        self.stats['saws'] += 1
        self.stats['boards'] += made
        log(f'sawed {made} logs into boards ({texts[-1] if texts else "?"}); weight {before} -> {after}'
            + (f'; {left} logs left' if left else ''))
        return before - after

    def menu(self, answer, title):
        ds = [d for d in answer.get('dialogs', []) if d['kind'] != 'gump' and title in (d.get('title') or '').lower()]
        for _ in range(30):  # a world save can hold a menu back (SMITHING.md)
            if ds:
                return ds[-1]
            time.sleep(1)
            ds = [d for d in self.ice.call('GET', '/gumps').get('dialogs', [])
                  if d['kind'] != 'gump' and title in (d.get('title') or '').lower()]
        raise Stop(f'the saw\'s menu "{title}" never came')

    @staticmethod
    def menu_index(d, name):
        for i in d['items']:
            if i['name'].split(':')[0].strip().lower() == name:
                return i['index']
        raise Stop(f'no "{name}" in the saw\'s menu {d["items"]}')

    def craft_result(self, answer):
        texts = [m['text'] for m in answer.get('messages', []) if m.get('type') != 'Label']
        last = max([m['id'] for m in answer.get('messages', [])] or [self.ice.status()['lastMessageId']])
        end = time.time() + 30
        while not any('create' in t.lower() or 'fail' in t.lower() for t in texts) and time.time() < end:
            time.sleep(0.5)
            for m in self.ice.call('GET', '/messages', after=last)['messages']:
                last = max(last, m['id'])
                if m.get('type') != 'Label':
                    texts.append(m['text'])
        return texts

    # ---- weight ----

    def room(self):
        """Make room for the next chop: saw when another one could take him past LIMIT; returns False when he's
        full of boards (time to see Burgers)."""
        weight = self.ice.status()['weight']
        if weight + CHOP <= LIMIT:
            return True
        self.saw()
        weight = self.ice.status()['weight']
        return weight <= FULL_AT and weight + CHOP <= LIMIT

    # ---- chopping ----

    def wait_until_gone(self, threat, gone_after=mine.GONE_AFTER):
        """As mine.py's, but a person back in sight again by the same block (mining's doubled wait was for the one
        place it has) has the blocks around them skipped for a while instead, and the wait stays short."""
        serial = (threat or {}).get('serial')
        if serial and self.repeats.get(serial, 0) >= 2:
            spot = (threat['x'], threat['y']) if threat.get('x') else self.block_spot
            if spot:
                name = threat.get('name') or serial
                self.avoid[serial] = (spot, time.time() + AVOID_FOR, name)
                log(f'{name} keeps standing by {spot[0]},{spot[1]}: the blocks within {AVOID_RANGE} tiles of there are '
                    f'skipped for {AVOID_FOR // 60} minutes')
                gone_after = mine.GONE_AFTER
        return super().wait_until_gone(threat, gone_after)

    def avoided(self, n):
        here = lumbering.centre(self.tour[n])
        now = time.time()
        for serial, (spot, until, name) in list(self.avoid.items()):
            if until < now:
                self.avoid.pop(serial)
            elif cheb(here, spot) <= AVOID_RANGE:
                return name, spot
        return None

    def chop_block(self, n):
        t = self.tour[n]
        self.block_spot = lumbering.centre(t)
        skip = self.avoided(n)
        if skip:
            log(f'block {n} skipped: {skip[0]} keeps standing by {skip[1][0]},{skip[1][1]}')
            return
        if not self.room():
            self.unload('a full pack')
        tree, stand, others = lumbering.choose(t)
        tried = 0
        for tree in [tree] + others:
            stands = [s for tr, s in t['pairs'] if tr == tree]
            if not stands:
                continue
            here = self.ice.status()
            stand = stand if stand in stands else min(stands, key=lambda s: cheb(s, (here['x'], here['y'])))
            try:
                self.go_to(stand)
            except NoWay:
                stand = None
                for st in sorted(stands, key=lambda s: cheb(s, (here['x'], here['y'])))[:3]:
                    try:
                        self.go_to(st)
                        stand = st
                        break
                    except NoWay:
                        continue
                if stand is None:
                    continue
            try:
                why = self.chop_tree(tree)
            except NeedAxes:
                self.unload('no axes left')
                return self.chop_block(n)
            tried += 1
            key = f"{t['block'][0]},{t['block'][1]}"
            if why in ('empty', 'already empty'):
                if why == 'empty':
                    self.state.setdefault('emptied', {})[key] = time.strftime('%Y-%m-%d %H:%M')
                else:
                    self.stats['empty'] += 1
                    log(f"block {key} was already empty (last emptied {self.state.get('emptied', {}).get(key, 'never by the loop')})")
                self.save_state()
                return
            if why == 'full':
                self.unload('a full pack')
                return self.chop_block(n)
            if tried >= 3:
                break
            stand = None
        log(f"block {t['block']}: no tree the server would let him chop; moving on")

    def chop_tree(self, tree):
        x, y, z, g = tree
        first, quiet, closer = True, 0, False
        before = self.ice.status()['weight']
        while True:
            self.check_guard()
            if os.path.exists(mine.PARK_FILE):
                self.park()
            if not self.room():
                return 'full'
            before = self.ice.status()['weight']
            axe = self.axe()
            try:
                r = self.ice.call('POST', '/use', serial=axe, x=x, y=y, z=z, graphic=g, reach=2)
            except uo.BridgeError as e:
                if e.code == 404:
                    continue  # the axe wore out as the answer came: the next one
                if e.code == 409 and 'too far' in (e.message or '') and not closer:
                    # a ride that stalled short of the spot (by the castle, 2026-11-13 03:40 and 03:48: 3 tiles off):
                    # once, let the client's path finder take him within reach of the tree itself
                    closer = True
                    try:
                        self.ice.walk(x, y, 2)
                    except uo.BridgeError as e2:
                        if e2.code not in (403, 409):
                            raise
                    continue
                if e.code in (403, 409):
                    log(f'chop {x},{y}: {e.message}')
                    return 'refused'
                raise
            texts = [m['text'] for m in r['messages'] if m.get('type') != 'Label']
            answers = [t for t in texts if any(k in t.lower() for k in CHOP_ANSWERS)]
            uses = self.state.setdefault('axe_uses', {})
            if answers:
                uses[axe] = uses.get(axe, 0) + 1
            if any('broke your axe' in t.lower() or 'worn out' in t.lower() for t in texts):
                # "You broke your axe." (2026-11-12 22:05: the first hatchet, after about 80 chops); axe() takes the
                # next one from the blue bag. How long each lasted, for the user (they'll get more axes)
                self.stats['axes broken'] += 1
                n = uses.pop(axe, 0)
                kind = self.axe_type.get(axe, 'axe')
                self.state.setdefault('axe_life', []).append({'time': time.strftime('%Y-%m-%d %H:%M'), 'axe': axe,
                                                              'type': kind, 'chops': n})
                self.broken_since.append((kind, n))
                log(f'the {kind} {axe} broke after {n} chops; {len(self.axes_in_bag())} left in the bag')
            self.save_state()
            if not answers:
                quiet += 1
                if quiet > 3:
                    log(f'chop {x},{y}: no answer ({texts[-1:]}); moving on')
                    return 'refused'
                continue
            quiet = 0
            low = answers[0].lower()
            self.stats['chops'] += 1
            if 'put some logs' in low:
                self.stats['logs'] += 10
            elif 'fail to produce' in low:
                self.stats['misses'] += 1
            elif 'not enough wood' in low:
                return 'already empty' if first else 'empty'
            elif 'equipped' in low:
                continue  # axe() puts one in his hands
            elif 'worn out' not in low and 'broke your axe' not in low:
                log(f'chop {x},{y}: {answers[0]}')
                return 'refused'
            first = False
            weight = r['weight']
            if 'put some logs' in low and weight <= before:
                # the weight comes a moment after the answer (as with ore: MINING.md, "Never over the weight limit")
                for _ in range(10):
                    time.sleep(0.2)
                    weight = self.ice.status()['weight']
                    if weight > before:
                        break
            if weight > LIMIT:
                log(f'over the weight limit: {weight}/{LIMIT}')
            before = weight

    # ---- Burgers ----

    def unload(self, why):
        """Saw what's left, ride to Burgers, hand him the boards (and any logs), and he banks them."""
        self.stats['handoffs'] += 1
        self.saw()
        log(f'to Burgers ({why})')
        self.handoff()
        if self.burgers_should_bank():
            self.hide(self.ice)  # he waits hidden by the meeting spot while Burgers is at the bank
            self.bank_trip()
            if len(self.axes_in_bag()) < ICEPICK_AXES and self.burgers_axes():
                self.handoff()  # the axes fetched on that trip
        if not self.axes_in_bag() and not any(h.get('graphic') in AXES for h in self.ice.status()['hands']):
            how = self.leave_safe()
            raise Stop('Icepick has no axes left and Burgers has none to give'
                       + (' (none in his bank either)' if self.bank_out_of_axes() else '') + f'. Parked: {how}')
        self.reagents_stop(KEEP_REAGENTS + 2)  # one the bank had none of, too few for another trip: stop now

    def burgers_saws(self):
        """Burgers' spare saws, loose in his pack or in a bag in it."""
        pack = self.bur.status()['backpack']['serial']
        found = []
        for item in self.bur.call('GET', '/contents', serial=pack, depth=2)['items']:
            if item.get('graphic') in SAWS:
                found.append(item['serial'])
            if 'spellbook' not in (item.get('type') or ''):
                found += [i['serial'] for i in item.get('items', []) if i.get('graphic') in SAWS]
        return found

    def bank_places(self, bags, bank, first=None):
        """Every bag in the bank box, then the box itself: tools are counted and taken from all of them, not only the
        bag the loop remembers (2026-11-13: 2 double axes in a second bag went uncounted all night). `first` (a
        remembered bag) is used up first. The bank trip opens them all, so the client knows what's inside."""
        in_bank = self.bur.call('GET', '/contents', serial=bank)['items']
        places = [i['serial'] for i in in_bank if i.get('container')]
        if first in places:
            places.remove(first)
            places.insert(0, first)
        return places + [bank]

    def bank_tools(self, graphics, bags, bank, first=None):
        found = []
        for w in self.bank_places(bags, bank, first):
            found += [i['serial'] for i in self.bur.call('GET', '/contents', serial=w)['items'] if i.get('graphic') in graphics]
        return found

    def bank_saw_list(self, bags, bank):
        """The saws in the bank, in any of its bags or loose in the box (the saw bag first)."""
        return self.bank_tools(SAWS, bags, bank, bags.get('saws'))

    def burgers_axes(self):
        """Burgers' spare axes, loose in his pack or in a bag in it."""
        pack = self.bur.status()['backpack']['serial']
        found = []
        for item in self.bur.call('GET', '/contents', serial=pack, depth=2)['items']:
            if item.get('graphic') in AXES:
                found.append(item['serial'])
            if 'spellbook' not in (item.get('type') or ''):
                found += [i['serial'] for i in item.get('items', []) if i.get('graphic') in AXES]
        return found

    def bank_out_of_axes(self):
        t = self.state.get('bank_out_of_axes')
        return bool(t) and time.time() - t < 1800

    def burgers_should_bank(self, end_of_pass=False, where=None):
        """He banks the boards after every handoff (a load of boards is most of what he can carry), or when his
        recall reagents run low; not with too little mana for there and back."""
        b = self.bur.status()
        if b['mana'] < 22:
            # rare: a load takes far longer than his mana takes to come back (about 3 minutes for 22)
            log(f"Burgers has {b['mana']} mana; Icepick waits hidden until he has 22 for the bank trip")
            self.hide(self.ice)
            while self.bur.status()['mana'] < 22:
                self.check_guard()
                time.sleep(15)
        held = sum(i.get('amount', 1) for i in self.bur.pack() if is_kind(i, BOARDS + LOGS, 'board') or is_kind(i, LOGS, 'logs'))
        reagents, _ = self.burgers_reagents()
        short = self.state.get('bank_short') or []
        low = any(reagents[g][0] < low for g, low in mine.REAGENTS_LOW.items() if g not in short)
        axes = len(self.axes_in_bag()) < ICEPICK_AXES and not self.burgers_axes() and not self.bank_out_of_axes()
        return held > 0 or low or axes

    def handoff(self, extra=()):
        boards = self.piles(BOARDS, 'board') + self.piles(LOGS, 'logs')
        cures = self.cure_potions(self.bur)[:max(0, mine.CURES_WANTED - len(self.cure_potions(self.ice)))]
        axes = self.burgers_axes()[:max(0, ICEPICK_AXES - len(self.axes_in_bag()))]
        saws = self.burgers_saws()[:max(0, ICEPICK_SAWS - self.saws_of(self.ice))]
        if not boards and not cures and not axes and not saws:
            return
        self.to_burgers()
        b = self.bur.status()
        if b['hidden']:
            ice = self.ice.status()
            if self.step_aside(self.bur, [(ice['x'], ice['y'])]) is None:
                raise Stop(f"Burgers found no free tile next to him to step out to for the trade (at {b['x']},{b['y']})")
        bur_serial = self.bur.status()['serial']
        for _ in range(10):
            seen = [m for m in self.ice.call('GET', '/nearby', range=3)['mobiles'] if m['serial'] == bur_serial]
            if seen and seen[0].get('name'):
                break
            time.sleep(0.5)
        # only what Burgers can carry and still recall (2026-11-12 22:58: 530 boards and his 8 spare axes took him to
        # 404/390, "Thou art too encumbered to move." and no Recall); Icepick keeps the rest for the next handoff
        b = self.bur.status()
        room = b['weightMax'] - BURGERS_MARGIN - b['weight']
        given = []
        for pile in boards:
            each = 0.5 if is_kind(pile, BOARDS, 'board') else 2
            amount = min(pile.get('amount', 1), int(max(0, room) / each))
            if amount <= 0:
                continue
            self.ice.call('POST', '/give', serial=pile['serial'], to=bur_serial,
                          amount=amount if amount < pile.get('amount', 1) else None)
            room -= amount * each
            given.append((pile, amount))
        kept = sum(p.get('amount', 1) for p in boards) - sum(a for _, a in given)
        if kept:
            log(f'Burgers can only carry part of the load ({b["weight"]}/{b["weightMax"]}): Icepick keeps {kept} for the next handoff')
        for item in axes + saws + cures:
            self.bur.call('POST', '/give', serial=item, to=self.ice.status()['serial'])
        self.ice.call('POST', '/trade', accept=1)
        self.bur.call('POST', '/trade', accept=1)
        time.sleep(1)
        if self.ice.status().get('trade') or self.bur.status().get('trade'):
            raise Stop('the trade between Icepick and Burgers did not finish')
        n = sum(a for p, a in given if is_kind(p, BOARDS, 'board'))
        self.last_handed = n
        logs = sum(a for p, a in given if is_kind(p, LOGS, 'logs'))
        totals = self.state.setdefault('totals', {'boards': 0, 'logs': 0})
        totals['boards'] += n
        totals['logs'] = totals.get('logs', 0) + logs
        self.save_state()
        for item in axes:  # into the blue bag ("whatever axes I put in the blue bag")
            try:
                self.ice.call('POST', '/move', serial=item, to=AXE_BAG)
            except uo.BridgeError as e:
                log(f"couldn't put the axe {item} in the blue bag ({e}); it stays loose in his pack")
        need = self.attention()
        log(('NEEDS YOU: ' + '; '.join(need) + ' || ' if need else '') + f'handed Burgers {n} boards' + (f' and {logs} logs' if logs else '')
            + (f'; gave Icepick ' + ' and '.join(f'{n} {w}{"" if n == 1 else "s"}' for n, w in
                                                 ((len(axes), 'axe'), (len(saws), 'saw')) if n)
               if axes or saws else '')
            + (f'; gave Icepick {len(cures)} cure potions' if cures else '')
            + f". Total: {totals['boards']} boards. Boards in the bank: {self.bank_boards()}."
            + f" Run and hide: {len(self.state.get('unreviewed', []))} to review. Fights: {len(self.state.get('fights', []))}"
            + f" to review. Reagents: {self.reagent_counts()}. Axes: Icepick {len(self.axes_in_bag())} in the bag,"
            + f" Burgers {len(self.burgers_axes())}, {self.bank_axes()}."
            + f" Saws: {len([i for i in self.ice.pack() if i.get('graphic') in SAWS])}."
            + f" Cure potions: Icepick {len(self.cure_potions(self.ice))}, Burgers {len(self.cure_potions(self.bur))}."
            + f" Lumberjacking {self.skill('Lumberjacking')}")
        ice = self.ice.status()
        if (ice['x'], ice['y']) != mine.BURGERS_WAIT:
            self.bur.walk(*mine.BURGERS_WAIT, 0)
        self.hide(self.bur)

    def skill(self, name):
        try:
            for s in self.ice.call('GET', '/skills', name=name).get('skills', []):
                return s.get('value')
        except uo.BridgeError:
            pass
        return '?'

    def bank_axes(self):
        bank = self.state.get('bank_axes')
        return f"bank {bank['count']} (counted {bank['time']})" if bank else 'bank not counted yet'

    def bank_boards(self):
        bank = self.state.get('bank_boards')
        return f"{bank['count']} (counted {bank['time']})" if bank else 'not counted yet'

    def bank_bags(self, bank):
        """The bank's bag for boards (one with boards in it) and the reagent bag, found by what's in them; a bag the
        user has taken out is looked for again (they swap whole bags: MINING.md)."""
        bags = self.state.setdefault('bags', {})
        in_bank = self.bur.call('GET', '/contents', serial=bank)['items']
        here = {i['serial'] for i in in_bank}
        for kind in [k for k, s in bags.items() if s not in here]:
            bags.pop(kind)
        if bags.get('boards') and bags.get('reagents') and bags.get('axes'):
            return bags
        for item in in_bank:
            if not item.get('container') or item['serial'] in bags.values():
                continue
            self.bur.call('POST', '/open', serial=item['serial'])
            inside = self.bur.call('GET', '/contents', serial=item['serial'])['items']
            if any(is_kind(i, BOARDS, 'board') for i in inside):
                bags['boards'] = item['serial']
            elif any(i.get('graphic') in AXES for i in inside):
                bags['axes'] = item['serial']
            elif any(i.get('graphic') in SAWS for i in inside):
                bags['saws'] = item['serial']  # (the user keeps spare saws in the bank too, 2026-11-12)
            elif any(i.get('graphic') in mine.REAGENTS for i in inside):
                bags['reagents'] = item['serial']
        if bags.get('boards'):
            uo.save_label(bags['boards'], "bag: boards (Burgers' bank)")
        if bags.get('axes'):
            uo.save_label(bags['axes'], "bag: axes (Burgers' bank)")
        self.save_state()
        return bags

    def lighten_burgers(self):
        """Too heavy to recall ("Thou art too encumbered to move.", 2026-11-12 22:58 at 404/390): Burgers hands enough
        boards back to Icepick first. Both must be in sight of each other for the trade: a step shows each."""
        b = self.bur.status()
        over = b['weight'] - (b['weightMax'] - BURGERS_MARGIN)
        if over <= 0:
            return
        boards = [i for i in self.bur.pack() if is_kind(i, BOARDS, 'board')]
        if not boards:
            raise Stop(f"Burgers is too heavy to recall ({b['weight']}/{b['weightMax']}) and has no boards to hand back")
        pile = max(boards, key=lambda i: i.get('amount', 1))
        n = min(pile.get('amount', 1), int(over / 0.5) + 10)
        log(f"Burgers is too heavy to recall ({b['weight']}/{b['weightMax']}); he hands {n} boards back to Icepick")
        s = self.ice.status()
        if cheb((s['x'], s['y']), (b['x'], b['y'])) > 1:
            self.to_burgers()
        elif s['hidden']:
            self.step_aside(self.ice, [(b['x'], b['y'])])
        if self.bur.status()['hidden']:
            s = self.ice.status()
            self.step_aside(self.bur, [(s['x'], s['y'])])
        ice_serial = self.ice.status()['serial']
        for _ in range(10):
            seen = [m for m in self.bur.call('GET', '/nearby', range=3)['mobiles'] if m['serial'] == ice_serial]
            if seen and seen[0].get('name'):
                break
            time.sleep(0.5)
        self.bur.call('POST', '/give', serial=pile['serial'], to=ice_serial,
                      amount=n if n < pile.get('amount', 1) else None)
        self.bur.call('POST', '/trade', accept=1)
        self.ice.call('POST', '/trade', accept=1)
        time.sleep(1)
        if self.ice.status().get('trade') or self.bur.status().get('trade'):
            raise Stop('the trade handing boards back to Icepick did not finish')
        totals = self.state.setdefault('totals', {'boards': 0, 'logs': 0})
        totals['boards'] -= n
        self.save_state()
        b = self.bur.status()
        log(f"Burgers is now {b['weight']}/{b['weightMax']}")

    def bank_axe_list(self, bags, bank):
        """The axes in the bank, in any of its bags or loose in the box (the axe bag first)."""
        return self.bank_tools(AXES, bags, bank, bags.get('axes'))

    def bank_trip(self):
        """Burgers to the Ocllo bank with the boards, and back to his spot. The bank is relaxed: guard off there."""
        self.stats['bank trips'] += 1
        b = self.bur.status()
        if cheb((b['x'], b['y']), mine.OCLLO_BANK) > 10:  # (already at the bank, he restocks before recalling back)
            self.reagents_stop(KEEP_REAGENTS + 2, only_if_bank_short=False)
        log('Burgers takes the boards to the bank')
        self.bur.call('POST', '/guard', on=0)
        try:
            burgers_rules(bank=True)
            self.bur.call('GET', '/rules')
            b = self.bur.status()
            if cheb((b['x'], b['y']), mine.OCLLO_BANK) > 10:
                self.lighten_burgers()
                r = self.recall('bank')
                if not r['moved']:
                    raise Stop(f"Burgers' Recall to the bank didn't work: {[m['text'] for m in r['messages']][-2:]}")
            bank = self.bur.call('POST', '/say', text='bank').get('bank', {}).get('serial')
            if not bank:
                raise Stop('Burgers said "bank" but no bank box opened')
            bags = self.bank_bags(bank)
            to = bags.get('boards') or bank
            if not bags.get('boards'):
                log("no bag with boards in Burgers' bank yet: the boards go into the bank box itself")
            # every bag in the bank is opened before anything's counted: after a login or a trip away the client knows
            # nothing inside a bag until it's shown (2026-11-12 23:00: the axe bag unopened read as empty), and spare
            # axes or saws can be in any bag (2026-11-13: 2 axes in a second bag were missed)
            for bag in [i['serial'] for i in self.bur.call('GET', '/contents', serial=bank)['items'] if i.get('container')]:
                self.bur.call('POST', '/open', serial=bag)
            for kind, graphics, word in (('boards', BOARDS, 'board'), ('logs', LOGS, 'logs')):
                there = self.bur.call('GET', '/contents', serial=to)['items']
                for pile in [i for i in self.bur.pack() if is_kind(i, graphics, word)]:
                    same = next((i for i in there if is_kind(i, graphics, word) and i.get('hue') == pile.get('hue')), None)
                    self.bur.call('POST', '/move', serial=pile['serial'], to=same['serial'] if same else to)
            try:
                count = sum(i.get('amount', 1) for i in self.bur.call('GET', '/contents', serial=to)['items']
                            if is_kind(i, BOARDS, 'board'))
                self.state['bank_boards'] = {'count': count, 'time': time.strftime('%H:%M')}
                stuck = sum(i.get('amount', 1) for i in self.bur.pack() if is_kind(i, BOARDS, 'board'))
                log(f'Burgers put the boards in the bank: {count} there now'
                    + (f'; {stuck} still in his pack' if stuck else ''))
            except Exception as e:  # a count gone wrong mustn't leave him standing at the bank
                log(f"couldn't count the boards in the bank: {e!r}")
            want = BURGERS_AXES - len(self.burgers_axes())
            if want < 0:
                # more than he should carry (8 before the user cut it to 2): the rest back into the bank's axe bag
                back = self.burgers_axes()[:-want]
                for item in back:
                    self.bur.call('POST', '/move', serial=item, to=bags.get('axes') or bank)
                log(f'Burgers put {len(back)} axes back in the bank (he carries {BURGERS_AXES})')
            if want > 0:
                spare = self.bank_axe_list(bags, bank)
                if not spare and bags.get('axes'):
                    self.state['bags'].pop('axes', None)  # that bag is empty: look for another with axes in it
                    bags = self.bank_bags(bank)
                    spare = self.bank_axe_list(bags, bank)
                for item in spare[:want]:
                    self.bur.call('POST', '/move', serial=item, to=self.bur.status()['backpack']['serial'])
                left = len(self.bank_axe_list(bags, bank))
                log(f'Burgers took {min(want, len(spare))} axes from the bank; ' +
                    (f'{left} left there' if spare else 'the bank has none (the user needs to put more in)'))
                self.state['bank_out_of_axes'] = None if spare else time.time()
            try:  # a spare saw for Icepick (2026-11-13: the user keeps 20 in the bank)
                want = BURGERS_SAWS - len(self.burgers_saws())
                if want > 0:
                    spare = self.bank_saw_list(bags, bank)[:want]
                    for item in spare:
                        self.bur.call('POST', '/move', serial=item, to=self.bur.status()['backpack']['serial'])
                    if spare:
                        log(f'Burgers took {len(spare)} saw{"" if len(spare) == 1 else "s"} from the bank')
            except Exception as e:
                log(f"couldn't take a saw from the bank: {e!r}")
            try:  # counts for the update (one going wrong mustn't leave him standing at the bank)
                self.state['bank_axes'] = {'count': len(self.bank_axe_list(bags, bank)), 'time': time.strftime('%H:%M')}
                self.state['bank_saws'] = {'count': self.bank_saw_count(bags, bank), 'time': time.strftime('%H:%M')}
            except Exception as e:
                log(f"couldn't count the axes and saws in the bank: {e!r}")
            self.save_state()
            if bags.get('reagents'):
                self.restock_reagents(bags['reagents'])
                try:
                    stock = self.bur.call('GET', '/contents', serial=bags['reagents'])['items']
                    self.state['bank_reagents'] = {name: sum(i.get('amount', 1) for i in stock if i.get('graphic') == g)
                                                   for g, name in mine.REAGENTS.items()}
                    self.save_state()
                except Exception as e:
                    log(f"couldn't count the reagents in the bank: {e!r}")
            burgers_rules(bank=False)
            self.bur.call('GET', '/rules')
            r = self.recall('meet')
            if not r['moved']:
                raise Stop(f"Burgers' Recall back to the meeting spot didn't work: {[m['text'] for m in r['messages']][-2:]}")
            self.bur.walk(*mine.BURGERS_WAIT, 0)
        finally:
            burgers_rules(bank=False)
            self.bur.call('POST', '/guard', on=1)
        time.sleep(2)
        missing = [w['serial'] for w in self.bur.status()['guard'].get('watching', []) if not w['seen']]
        if missing:
            raise Stop(f"a rune is missing from Burgers' pack after the bank trip: {missing}")
        self.hide(self.bur)
        self.update()

    def bank_saw_count(self, bags, bank):
        """Saws in the bank: in any of its bags or loose in the box."""
        return len(self.bank_saw_list(bags, bank))

    def saws_of(self, c):
        pack = c.status()['backpack']['serial']
        n = 0
        for item in c.call('GET', '/contents', serial=pack, depth=2)['items']:
            if item.get('graphic') in SAWS:
                n += 1
            if 'spellbook' not in (item.get('type') or ''):
                n += sum(1 for i in item.get('items', []) if i.get('graphic') in SAWS)
        return n

    def attention(self):
        """What will end the loop unless the user restocks it, repeated at every handoff and update until it's fixed
        (the user, 2026-11-12: "if something needs my attention right away keep repeating it at each hand-off so I
        see it. Not run & hides or fights.. stuff that will end the loop (out of something)")."""
        need = []
        try:
            si = self.ice.status()
            ax_ice = len(self.axes_in_bag()) + sum(1 for h in si['hands'] if h.get('graphic') in AXES)
            ax_bur = len(self.burgers_axes())
            ax_bank = (self.state.get('bank_axes') or {}).get('count')
            if ax_bank == 0:
                need.append(f"no spare axes in Burgers' bank (Icepick has {ax_ice}, Burgers {ax_bur}; out of axes "
                            'ends the loop)')
            elif ax_ice + ax_bur <= 2:
                need.append(f'axes running out: Icepick has {ax_ice}, Burgers {ax_bur}')
            # cure potions are relaxed (the user, 2026-11-12: he's never been poisoned; 3 on Icepick is all that's
            # needed): only when Icepick is down to one (after any top-up from Burgers at the handoff)
            cures_b, cures_i = len(self.cure_potions(self.bur)), len(self.cure_potions(self.ice))
            if cures_i <= 1:
                need.append(f'Icepick is down to {cures_i} cure potion{"" if cures_i == 1 else "s"} (Burgers has {cures_b}; '
                            'poisoned with none ends the loop)')
            have, _ = self.burgers_reagents()
            bank_r = self.state.get('bank_reagents') or {}
            for g, name in mine.REAGENTS.items():
                in_bank = bank_r.get(name)
                if in_bank is not None and in_bank < mine.REAGENTS_WANTED:
                    need.append(f'{name}: only {in_bank} left in the bank bag (Burgers has {have[g][0]})')
                elif have[g][0] < mine.REAGENTS_WARN:
                    need.append(f'{name}: Burgers is down to {have[g][0]}')
            saws = self.saws_of(self.ice)
            saws_b = len(self.burgers_saws())
            saws_bank = (self.state.get('bank_saws') or {}).get('count')
            if saws <= 1 and saws_b == 0:
                need.append(f'Icepick has {saws} saw{"" if saws == 1 else "s"} left and Burgers none (without one the logs '
                            'stay logs and he fills up four times faster)')
            elif saws_bank == 0:
                need.append(f'no spare saws in the bank (Icepick has {saws}, Burgers {saws_b})')
        except Exception as e:
            need.append(f"(couldn't check what's running out: {e!r})")
        return need

    def update(self):
        """After every bank trip, one line with everything (the user, 2026-11-12): boards, axes, saws, reagents (Burgers'
        and the bank bag's), cure potions, run and hides, fights (a creature hit him and the guards were called),
        broken axes, and the chopping since the last update."""
        try:
            si = self.ice.status()
            in_hand = any(h.get('graphic') in AXES for h in si['hands'])
            have, _ = self.burgers_reagents()
            bank_r = self.state.get('bank_reagents') or {}
            since = {k: self.stats.get(k, 0) - self.at_update.get(k, 0) for k in ('blocks', 'chops', 'misses', 'logs')}
            totals = self.state.get('totals') or {}
            ax_bank = (self.state.get('bank_axes') or {}).get('count', '?')
            saw_bank = (self.state.get('bank_saws') or {}).get('count', '?')

            def news(kind):
                new = [i for i in self.state.get(kind, []) if i['time'] > self.update_since]
                text = f'{len(new)} new' + (' (' + '; '.join(f"{i['time'][11:16]} {i['who']}: {(i.get('what') or '')[:70]}"
                                                              for i in new) + ')' if new else '')
                return text + f", {len(self.state.get(kind, []))} to review"
            parts = [
                f"boards: {self.last_handed} handed this time, {(self.state.get('bank_boards') or {}).get('count', '?')} in "
                f"the bank, {totals.get('boards', 0)} in all",
                f"axes: Icepick {'1 in hand + ' if in_hand else ''}{len(self.axes_in_bag())} in the bag, Burgers "
                f"{len(self.burgers_axes())}, bank {ax_bank}; broken since the last update: "
                + (', '.join(f'{k} after {n} chops' for k, n in self.broken_since) or 'none'),
                f'saws: Icepick {self.saws_of(self.ice)}, Burgers {self.saws_of(self.bur)}, bank {saw_bank}',
                'reagents: Burgers ' + ', '.join(f'{name} {have[g][0]}' for g, name in mine.REAGENTS.items())
                + '; bank bag ' + ', '.join(f"{name} {bank_r.get(name, '?')}" for name in mine.REAGENTS.values()),
                f'cure potions: Icepick {len(self.cure_potions(self.ice))}, Burgers {len(self.cure_potions(self.bur))}',
                'run and hides: ' + news('unreviewed'),
                'fights (a creature hit him, guards called): ' + news('fights'),
                f"since the last update: {since['blocks']} blocks, {since['chops']} chops, {since['logs'] // 10} good, "
                f"{since['misses']} misses; Lumberjacking {self.skill('Lumberjacking')}",
            ]
            need = self.attention()
            if need:
                parts.insert(0, 'NEEDS YOU: ' + '; '.join(need))
            log('UPDATE: ' + ' | '.join(parts))
        except Exception as e:  # the update is for the user; it mustn't stop the loop
            log(f"couldn't put the update together: {e!r}")
        self.at_update = dict(self.stats)
        self.broken_since = []
        self.update_since = time.strftime('%Y-%m-%d %H:%M:%S')

    # ---- the lap ----

    def preflight(self):
        # the town guards found while mining are town guards here too
        try:
            with open(MINE_STATE, encoding='utf-8') as fh:
                found = json.load(fh).get('town_guards') or {}
        except (OSError, ValueError):
            found = {}
        guards = self.state.setdefault('town_guards', {})
        if any(s not in guards for s in found):
            guards.update(found)
            self.save_state()
        burgers_rules(bank=False)
        icepick_rules()
        for c in (self.ice, self.bur):
            pack = c.status()['backpack']
            if not pack.get('knownItems'):
                c.call('POST', '/open', serial=pack['serial'])
        for c in (self.ice, self.bur):
            for item in c.pack():
                if item.get('container') and not item.get('knownItems') and 'spellbook' not in (item.get('type') or ''):
                    c.call('POST', '/open', serial=item['serial'])  # Burgers' reagent pouch, Icepick's axe bag
        si, sb = self.ice.status(), self.bur.status()
        saws = len([i for i in self.ice.pack() if i.get('graphic') in SAWS])
        log(f"Icepick at {si['x']},{si['y']} weight {si['weight']}/{si['weightMax']}, {len(self.axes_in_bag())} axes in "
            f"the bag, {saws} saws, {len(self.cure_potions(self.ice))} cure potions; Burgers at {sb['x']},{sb['y']} "
            f"mana {sb['mana']}/{sb['manaMax']}")
        if not saws:
            log('Icepick has no saw: logs will stay logs')
        at_bank = cheb((sb['x'], sb['y']), mine.OCLLO_BANK) <= 10
        for c in (self.ice, self.bur):
            if not (c is self.bur and at_bank):
                c.call('POST', '/guard', on=1)
        time.sleep(2)
        missing = [w['serial'] for w in self.bur.status()['guard'].get('watching', []) if not w['seen']]
        if missing and not at_bank:
            raise Stop(f"Burgers' pack doesn't show these runes: {missing} (open his backpack once?)")
        if not self.mcgee() and not si['mounted']:
            raise Stop('McGee is not near Icepick')
        self.mount()
        for key in mine.RUNE_NAMES:
            self.rune(key)
        log('runes checked: ' + ', '.join(f'{k} {v}' for k, v in self.runes.items()))
        self.warn_reagents()
        if at_bank:
            log('Burgers is at the bank (a run stopped during a bank trip); he finishes the trip')
            self.bank_trip()
        elif cheb((sb['x'], sb['y']), mine.BURGERS_WAIT) > 15:
            log(f"Burgers is at {sb['x']},{sb['y']}, not at the meeting spot; recalling him there")
            self.burgers_back()
        self.burgers_to_wait()
        log(f"axes: Icepick {len(self.axes_in_bag())} in the bag, Burgers {len(self.burgers_axes())}; "
            f"Lumberjacking {self.skill('Lumberjacking')}")
        try:
            self.axe()
        except NeedAxes:
            self.unload('no axes')

    def run(self):
        os.makedirs(WORK, exist_ok=True)
        start = time.time()
        self.preflight()
        first = self.args.start if self.args.start is not None else self.state.get('next', 0)
        last = self.args.end if self.args.end is not None else len(self.tour) - 1
        lap = 0
        while not self.args.laps or lap < self.args.laps:  # --laps 0: until something runs out (the user, 2026-11-14)
            lap += 1
            log(f'lap {lap}: blocks {first} to {last} of {len(self.tour)}'
                + ('' if self.args.laps else ' (lap after lap until something runs out)'))
            for n in range(first, last + 1):
                self.state['next'] = n
                self.save_state()
                self.safely(self.chop_block, n)
                self.stats['blocks'] += 1
                self.safely(self.check_mount_fatigue)
                if os.path.exists(mine.PARK_FILE):
                    self.state['next'] = n + 1
                    self.save_state()
                    self.safely(self.park)
            self.state['next'] = (last + 1) % len(self.tour)
            self.save_state()
            first, last = 0, len(self.tour) - 1
        # the laps (or a test stretch) done: both mounted and hidden, as for --park
        self.report(start)
        self.safely(self.park)


def running(pid_file, name):
    try:
        with open(pid_file, encoding='utf-8') as fh:
            pid = int(fh.read().strip())
    except (OSError, ValueError):
        return None
    if pid == os.getpid():
        return pid
    ps = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True)
    return pid if name in ps.stdout and '--park' not in ps.stdout and '--stop' not in ps.stdout else None


def park_or_stop(park):
    import signal
    pid = running(mine.PID_FILE, 'lumber.py')
    if not pid:
        print('no lumberjacking loop is running')
        return
    with open(mine.LOG, encoding='utf-8') as fh:
        seen = len(fh.readlines())
    if park:
        open(mine.PARK_FILE, 'w').close()
        print(f'asked the loop (pid {pid}) to park; waiting')
        deadline = time.time() + 20 * 60
        while running(mine.PID_FILE, 'lumber.py') and time.time() < deadline:
            time.sleep(2)
        if running(mine.PID_FILE, 'lumber.py'):
            print('the loop is still running after 20 minutes (stuck?)')
            sys.exit(1)
    else:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            if not running(mine.PID_FILE, 'lumber.py'):
                break
            time.sleep(0.5)
        else:
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)
        print(f'stopped the loop (pid {pid}); ' + ('it is gone' if not running(mine.PID_FILE, 'lumber.py') else 'IT IS STILL RUNNING'))
        print('nobody was parked: check where Icepick and Burgers are, and hide them')
    with open(mine.LOG, encoding='utf-8') as fh:
        for line in fh.readlines()[seen:][-6:]:
            print(line.rstrip())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--laps', type=int, default=1, help='laps of the tour; 0: lap after lap until something runs out')
    p.add_argument('--from', dest='start', type=int, help='first block of the tour (default: where the last run stopped)')
    p.add_argument('--to', dest='end', type=int, help='last block (a test stretch: both parked at the end)')
    p.add_argument('--unload', action='store_true', help='only saw, hand the boards to Burgers and bank them, then stop')
    p.add_argument('--bank', action='store_true', help='only a bank trip for Burgers, then stop')
    p.add_argument('--incidents', action='store_true')
    p.add_argument('--reviewed', action='store_true')
    p.add_argument('--park', action='store_true')
    p.add_argument('--stop', action='store_true')
    args = p.parse_args()
    if args.park or args.stop:
        return park_or_stop(args.park)
    if args.incidents or args.reviewed:
        try:
            with open(mine.STATE, encoding='utf-8') as fh:
                state = json.load(fh)
        except (OSError, ValueError):
            state = {}
        items, fights = state.get('unreviewed', []), state.get('fights', [])
        if args.incidents:
            for what, its in (('run-and-hide incidents', items), ('fights', fights)):
                print(f'{len(its)} {what} to review' + (':' if its else ''))
                for i in its:
                    print(f"  {i['time']}  {i['who']}  {i['where']}  ({i['what']})")
        else:
            state['unreviewed'], state['fights'] = [], []
            state.setdefault('reviewed', []).append({'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'count': len(items),
                                                     'fights': len(fights)})
            with open(mine.STATE, 'w', encoding='utf-8') as fh:
                json.dump(state, fh, indent=1)
            print(f'marked {len(items)} run and hides and {len(fights)} fights reviewed')
        return
    if running(MINE_PID, 'mine.py'):
        sys.exit('the mining loop is running (it uses Icepick too); park it first: python3 -I mine.py --park')
    if running(mine.PID_FILE, 'lumber.py'):
        sys.exit('a lumberjacking loop is already running; --park or --stop it first')
    os.makedirs(WORK, exist_ok=True)
    with open(mine.PID_FILE, 'w', encoding='utf-8') as fh:
        fh.write(str(os.getpid()))
    try:
        os.remove(mine.PARK_FILE)
    except OSError:
        pass
    jack = None
    try:
        jack = Lumberjack(args)
        if args.bank or args.unload:
            start = time.time()
            jack.preflight()
            if args.bank:
                jack.safely(jack.bank_trip)
            else:
                jack.safely(jack.unload, 'asked to unload')
            jack.safely(jack.park)
            jack.report(start)
            return
        jack.run()
    except Parked as e:
        log(f'PARKED: {e}')
        jack.report(time.time())
    except Stop as e:
        log(f'STOPPED: {e}')
        if jack:
            jack.report(time.time())
        sys.exit(2)
    except uo.BridgeError as e:
        log(f'STOPPED on an unexpected answer from the bridge: {e}')
        sys.exit(3)
    finally:
        if running(mine.PID_FILE, 'lumber.py') == os.getpid():
            os.remove(mine.PID_FILE)


if __name__ == '__main__':
    main()
