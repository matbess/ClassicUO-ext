#!/usr/bin/env python3
"""Step 3 of a sorting batch: decide where every identified item goes, from the keep rules in
skills/uo-sort/SKILL.md, and write the spec for sortbatch.py.

  plan.py BATCHDIR [--no-open]

Reads BATCHDIR/inv.json and loot.json (from look.py) and the names idall.py recorded in names.json. To apply the
"at most 2 of each piece type" limits it reads what the metal armour bags already hold; it opens those bags first
(about a dozen paced actions) unless --no-open is given, in which case it uses only what the client already knows.
Writes BATCHDIR/spec.json and prints every decision. Anything the rules don't settle goes to the needs-your-decision
chest, and is listed so the user can be told.

Keep the rules here in step with the skill's "What to keep" table.
"""
import collections
import importlib.util
import json
import os
import re
import sys

here = os.path.dirname(os.path.realpath(__file__))
for module in ('uo', 'look'):
    spec = importlib.util.spec_from_file_location(module, os.path.join(here, module + '.py'))
    globals()[module] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(globals()[module])

DAMAGE = ['ruin', 'might', 'force', 'power', 'vanquishing']
PROTECTION = ['defense', 'guarding', 'hardening', 'fortification', 'invulnerability']
ACCURACY = ['accurate', 'surpassingly accurate', 'eminently accurate', 'exceedingly accurate', 'supremely accurate']
DURABILITY = ['durable', 'substantial', 'massive', 'fortified', 'indestructible']
GOOD_CHARGES = ["daemon's breath", "dragon's breath", 'thunder', "ghoul's touch"]
GOOD_WANDS = ['greater healing', 'fireball', 'lightning']
GOOD_WEAR = ['invisibility', 'spell reflection', 'magic reflection', 'teleport']
CURSES = ['clumsiness', 'clumsy', 'night eyes', 'feeblemind', 'weakness']  # always rejected

WEAPONS = {  # weapon chest -> item types (the client's tiledata names)
    'swords': ['broadsword', 'longsword', 'katana', 'viking sword', 'scimitar', 'cutlass'],
    'knives': ['butcher knife', 'skinning knife', 'cleaver'],
    'axes': ['axe', 'battle axe', 'double axe', "executioner's axe", 'large battle axe', 'two handed axe', 'war axe',
             'hatchet', 'pickaxe'],
    'maces & staves': ['club', 'mace', 'maul', 'war mace', 'war hammer', 'hammer pick', 'quarter staff', 'black staff',
                       'gnarled staff', "shepherd's crook"],
    'fencing': ['dagger', 'kryss', 'short spear', 'spear', 'war fork', 'pitchfork'],
    'polearms': ['bardiche', 'halberd'],
    'archery': ['bow', 'crossbow', 'heavy crossbow'],
}
WEAPON_BAG = {'swords': ('swords', 'swords'), 'knives': ('knives', 'swords'), 'axes': ('axes', 'axes'),
              'maces & staves': ('maces & staves', 'maces & staves'), 'fencing': ('fencing', 'fencing'),
              'polearms': ('polearms', 'polearms'), 'archery': ('crossbows', 'archery')}
WOOD = {'club', 'quarter staff', 'black staff', 'gnarled staff', "shepherd's crook", 'bow', 'crossbow', 'heavy crossbow',
        'wooden shield'}
NO_FORCE = {'dagger', 'skinning knife', 'butcher knife', 'cleaver', "shepherd's crook"}  # force/power isn't enough
JEWELLERY = {'bracelet', 'earrings', 'necklace', 'bead necklace', 'ring'}
SHIELDS = {'buckler', 'kite shield', 'metal shield', 'wooden shield', 'heater shield', 'metal kite shield',
           'bronze shield', 'tear kite shield', 'chaos shield', 'order shield'}
HELMS = {'plate helm', 'close helmet', 'close helm', 'helmet', 'nose helm', 'norse helm', 'bascinet', 'orc helm'}
TUNICS = {'platemail', 'plate armor', 'female plate', 'chainmail tunic', 'ringmail tunic', 'leather armor',
          'leather tunic', 'leather bustier', 'studded armor', 'studded tunic', 'studded bustier', 'bone armor'}
SET_PIECES = {'ringmail gloves', 'ringmail sleeves', 'chainmail leggings', 'chainmail tunic', 'platemail gorget',
              'plate helm', 'close helmet', 'close helm', 'helmet', 'nose helm'}
FOOTWEAR = {'boots', 'thigh boots', 'shoes', 'sandals'}
MISC = {'crystal ball'}  # things the user keeps that have no other home: the miscellaneous chest
MISC_GRAPHICS = {'0x097C', '0x097D', '0x097E'}  # cheese: wedges and wheels (tiledata names carry plural codes)

# armour bags for keepers and gear the user doesn't mind losing: (material, slot) -> bag kind, chest
TYPE_BAG = {('plate', 'gloves'): ('plate gloves', 'plate'), ('plate', 'helm'): ('helms', 'helms'),
            ('plate', 'tunic'): ('plate tunics', 'plate'), ('plate', 'gorget'): ('plate gorgets', 'plate'),
            ('plate', 'arms'): ('plate arms', 'plate'), ('plate', 'legs'): ('plate legs', 'plate'),
            ('chain', 'tunic'): ('chain tunics', 'chain & ring'), ('chain', 'helm'): ('coifs', 'chain & ring'),
            ('chain', 'legs'): ('chain leggings', 'chain & ring')}
MATERIAL_BAG = {'ring': ('ringmail', 'chain & ring'), 'chain': ('chain armour', 'chain & ring'),
                'plate': ('plate armour', 'plate'), 'leather': ('leather armour', 'leather + caps'),
                'studded': ('studded armour', 'studded'), 'shield': ('shields', 'spare + invulnerability shields'),
                'bone': ('bone armour', 'bone armour')}
PLAIN_BAG = {'plate': ('plate (defense)', 'plain gear'), 'chain': ('chain & ring (defense)', 'plain gear'),
             'ring': ('chain & ring (defense)', 'plain gear')}
GM_CHEST = {'plate': 'plate', 'chain': 'chain & ring', 'ring': 'chain & ring', 'leather': 'leather + caps',
            'studded': 'studded', 'shield': 'spare + invulnerability shields'}


def base(t):
    return ' '.join(t.split()).lower()


def level(name, words):
    found = [w for w in words if re.search(rf'\b(of|and) {re.escape(w)}\b', name)]
    return max((words.index(w) for w in found), default=-1)


def value(name):
    """For ordering, best first: damage, protection, accuracy, durability."""
    n = name.lower()
    return (level(n, DAMAGE), level(n, PROTECTION), sum(a in n for a in ACCURACY), sum(d in n for d in DURABILITY))


def weapon_chest(t):
    return next((k for k, ts in WEAPONS.items() if t in ts), None)


def material(t):
    """plate (with metal helms), chain, ring, leather, studded, bone, shield; None for anything else."""
    if t in SHIELDS:
        return 'shield'
    if t in HELMS or t.startswith('plate') or t == 'female plate':
        return 'plate'
    for m in ('chain', 'ring', 'leather', 'studded', 'bone', 'daemon bone'):
        if t.startswith(m):
            return 'bone' if 'bone' in m else m
    return None


def slot(t):
    if t in TUNICS:
        return 'tunic'
    if t.endswith('legs') or t.endswith('leggings') or t in ('leather skirt', 'leather shorts'):
        return 'legs'
    if t.endswith('arms') or t.endswith('sleeves'):
        return 'arms'
    if t.endswith('gloves'):
        return 'gloves'
    if t.endswith('gorget'):
        return 'gorget'
    if t in HELMS or t in ('chainmail coif', 'chainmail  coif', 'leather cap') or 'helm' in t:
        return 'helm'
    return t


def decide(item, name):
    """(action, detail). Actions: keep (detail says where), limit (metal armour under the 2-per-type rule), set,
    spares, trash, smelt, cut, decide (ask the user)."""
    t = base(item['type'])
    n = name.lower()
    if not name:
        return 'decide', 'no name'
    if re.match(r'^(an? )?magic ', n):
        return 'decide', 'still unidentified'
    m = material(t)
    if 'exceptional' in n:  # GM crafted: always kept (the user's exception)
        if t in SET_PIECES:
            return 'set', ''
        if weapon_chest(t):
            return 'keep', ('gm weapon', weapon_chest(t))
        if m in GM_CHEST:
            return 'keep', ('gm armour', m)
        return 'decide', 'GM item of a kind with no home yet'
    charged_tool = t == 'wand' or (re.search(r'\(\d+ charges?\)', n) and t in ('gnarled staff', 'black staff',
                                                                              'quarter staff'))
    if charged_tool:
        what = re.sub(r'\s*\(\d+ charges?\)', '', n.split(' of ', 1)[1]) if ' of ' in n else ''
        if what == 'identification':
            return 'spares', ''
        return ('keep', ('wand', 'healing wands' if what == 'greater healing' else 'attack wands')) \
            if what in GOOD_WANDS else ('trash', 'wand')
    if t in JEWELLERY:
        if t == 'ring' and ' of ' in n and not any(c in n for c in CURSES):
            return 'keep', ('jewellery', 'rings')  # all magic rings (they're teleport or invisibility), curses aside
        if any(w in n for w in GOOD_WEAR):
            return 'keep', ('jewellery', t.split()[-1] + 's' if not t.endswith('s') else t)
        return 'trash', 'jewellery'
    wc = weapon_chest(t)
    if wc:
        good = 'vanquishing' in n or any(c in n for c in GOOD_CHARGES)
        if t in ('crossbow', 'heavy crossbow'):
            good = good or 'of power' in n  # the user's exception: crossbows only if really good
        elif t not in NO_FORCE:
            good = good or level(n, DAMAGE) >= DAMAGE.index('force')
        if good:
            return 'keep', ('weapon', 'bows' if t == 'bow' else WEAPON_BAG[wc][0], WEAPON_BAG[wc][1])
        return ('trash' if t in WOOD else 'smelt'), 'weapon'
    if m:
        p = level(n, PROTECTION)
        if m == 'bone':  # only really good bone: like plate's keepers (the user, 2026-11-01); can't be smelted or cut
            if 'daemon' in t or p >= PROTECTION.index('hardening'):
                return 'keep', ('armour', m)
            return 'trash', 'bone below hardening'
        if p < 0:
            if ' of ' in n:
                return 'decide', 'armour with a property the rules do not cover'
            return ('trash' if t in WOOD else 'cut' if m in ('leather', 'studded') else 'smelt'), 'plain armour'
        if m in ('shield', 'leather', 'studded'):  # Emetah's rule: invulnerability only
            if p == PROTECTION.index('invulnerability'):
                return 'keep', ('armour', m)
            return ('trash' if t in WOOD else 'cut' if m in ('leather', 'studded') else 'smelt'), 'below invulnerability'
        if (m == 'chain' and p >= PROTECTION.index('fortification')) or \
                (m in ('plate', 'ring') and p >= PROTECTION.index('hardening')):
            return 'keep', ('armour', m)
        return 'limit', 'defense' if p == 0 else 'guarding'  # gear the user doesn't mind losing
    if t in ('torch', 'torches'):
        return 'trash', 'torch'  # the user, 2026-11-04
    if t in MISC or item['graphic'] in MISC_GRAPHICS:
        return 'keep', ('misc',)  # kept, loose in the miscellaneous chest (the user, 2026-11-04)
    # cloth clothes, hats and footwear
    if any(w in n for w in GOOD_WEAR):
        return 'keep', ('clothing', 'footwear' if t in FOOTWEAR else 'hats' if 'hat' in t or t in
                        ('cap', 'bandana', 'skullcap', 'bonnet') else 'tunics & shirts')
    if re.search(r'\b(hat|cap|bandana|skullcap|bonnet|shirt|tunic|doublet|skirt|kilt|pants|robe|cloak|dress|sash|'
                 r'apron|surcoat|boots|shoes|sandals)\b', t):
        return 'cut', 'clothing'
    return 'decide', 'not covered by the keep rules'


def armour_bag(t, keeper_or_guarding):
    """(bag kind, chest) for a kept armour piece."""
    m, sl = material(t), slot(t)
    if not keeper_or_guarding:
        return PLAIN_BAG[m]
    return TYPE_BAG.get((m, sl)) or MATERIAL_BAG[m]


def bag_label(labels, kind):
    found = [s for s, t in labels.items() if t.startswith(f'bag: {kind} (')]
    return found[0] if found else None


def existing_counts(info, labels, names, opening):
    """(group, material, slot) -> pieces already kept in the metal armour bags and their markers."""
    layout = json.load(open(os.path.join(here, 'layout.json')))
    marker_of = {b['serial']: b['marker'] for e in layout.values() for b in e['bags']}
    kinds = {k for k, _ in list(TYPE_BAG.values()) + list(PLAIN_BAG.values())} | {'ringmail', 'chain armour',
                                                                                  'plate armour'}
    counts = collections.Counter()
    for kind in sorted(kinds):
        bag = bag_label(labels, kind)
        if not bag:
            continue
        try:
            items = uo.call(info, 'GET', '/contents', serial=bag)['items']
            known = uo.call(info, 'GET', '/item', serial=bag)['item'].get('knownItems', 0)
        except uo.BridgeError:
            items, known = [], 0
        if opening and not known:
            chest = next(c for c, e in layout.items() if any(b['serial'] == bag for b in e['bags']))
            look.open_once(info, chest)
            items = look.open_once(info, bag)
        plain = '(defense)' in labels[bag]
        pieces = [(i['serial'], base(i['type'])) for i in items]
        if marker_of.get(bag):
            pieces.append((marker_of[bag]['serial'], None))
        for s, t in pieces:
            name = names.get(s, '').split(' / ')[0].lower()
            if t is None:  # a marker: its type from its name ("a durable platemail gloves of guarding")
                t = ' '.join(w for w in name.split(' of ')[0].replace(',', '').split()
                             if w not in ('a', 'an') and not any(w in d.split() for d in ACCURACY + DURABILITY))
            m = material(t)
            if m not in ('plate', 'chain', 'ring'):
                continue
            p = level(name, PROTECTION)
            if not plain and ((m == 'chain' and p >= 3) or (m in ('plate', 'ring') and p >= 2)):
                continue  # a keeper, not under the limit
            counts[('defense' if plain else 'guarding', m, slot(t))] += 1
    return counts


def main():
    batch = sys.argv[1]
    opening = '--no-open' not in sys.argv
    inv = json.load(open(os.path.join(batch, 'inv.json')))
    loot = json.load(open(os.path.join(batch, 'loot.json')))
    names, labels = uo.load_names(), uo.load_labels()
    info = uo.find_bridge(None)
    spec = {'loot': loot, 'learn_first': [], 'new_slots': [], 'into': [], 'place_in': [], 'spares': [], 'trash': [],
            'smelt': [], 'cut': [], 'sets': []}
    groups = collections.defaultdict(list)  # (bag kind, chest) -> serials
    limited = collections.defaultdict(list)
    report = collections.defaultdict(list)
    present = set()  # idall.py moves used-up ID wands to the barrel, so look at what's still in the loot
    for bag in loot:
        try:
            present |= {i['serial'] for i in uo.call(info, 'GET', '/contents', serial=bag)['items']}
        except uo.BridgeError:
            pass
    for s, item in inv.items():
        if look.kind(item) != 'gear':
            continue
        if s not in present:
            report['no longer in the loot (skipped)'].append(('', names.get(s, item['type'])))
            continue
        name = names.get(s, '').split(' / ')[0]
        action, detail = decide(item, name)
        t = base(item['type'])
        report[action].append((str(detail), name or item['type']))
        if action == 'keep':
            what = detail[0]
            if what == 'misc':
                spec['place_in'].append([s, 'miscellaneous'])
            elif what == 'wand':
                groups[(detail[1], 'magic wands')].append(s)
            elif what == 'jewellery':
                groups[(detail[1], 'jewellery')].append(s)
            elif what == 'clothing':
                groups[(detail[1], 'magic clothing')].append(s)
            elif what == 'weapon':
                groups[(detail[1], detail[2])].append(s)
            elif what == 'gm weapon':
                groups[(f'exceptional {WEAPON_BAG[detail[1]][1]}', WEAPON_BAG[detail[1]][1])].append(s)
            elif what == 'gm armour':
                chest = GM_CHEST[detail[1]]
                groups[(f'exceptional {detail[1]}', chest)].append(s)
            else:
                groups[armour_bag(t, True)].append(s)
        elif action == 'limit':
            m = 'chain' if t.startswith('chain') else material(t)
            limited[(detail, m, slot(t))].append(s)
        elif action == 'decide':
            spec['place_in'].append([s, 'needs your decision'])
        elif action == 'set':
            spec['sets'].append(s)
        else:
            spec[action].append(s)
    if limited:
        counts = existing_counts(info, labels, names, opening)
        for key, serials in limited.items():
            for s in sorted(serials, key=lambda s: value(names.get(s, '')), reverse=True):
                t = base(inv[s]['type'])
                if counts[key] < 2:
                    counts[key] += 1
                    groups[armour_bag(t, key[0] == 'guarding')].append(s)
                else:
                    spec['cut' if material(t) in ('leather', 'studded') else 'smelt'].append(s)
                    report['over the limit'].append((str(key), names.get(s, '')))
    # existing bags get items best first; a new bag gets the least valuable piece as its marker
    for (kind, chest), serials in groups.items():
        serials.sort(key=lambda s: value(names.get(s, '')), reverse=True)
        bag = bag_label(labels, kind)
        if bag is None:
            spec['new_slots'].append([chest, serials.pop(), kind])
            chest_label = next(t for t in labels.values() if t.startswith('chest: ' + chest))
            bag = f"bag: {kind} ({chest_label[7:].split(' (')[0]} chest)"
        if chest not in spec['learn_first']:
            spec['learn_first'].append(chest)
        spec['into'] += [[s, bag] for s in serials]
    json.dump(spec, open(os.path.join(batch, 'spec.json'), 'w'), indent=1)
    for action in sorted(report):
        print(f'== {action}: {len(report[action])}')
        if action not in ('trash', 'smelt', 'cut'):
            for detail, name in sorted(report[action]):
                print(f'     {detail:40} {name}')
    for chest, marker, kind in spec['new_slots']:
        print(f"NEW BAG '{kind}' in the {chest} chest, marker {names.get(marker)}")
    print({k: len(v) for k, v in spec.items()})
    asking = [s for s, chest in spec['place_in'] if chest == 'needs your decision']
    if asking:
        print('TELL THE USER: these go to the needs-your-decision chest:',
              '; '.join(names.get(s, inv[s]['type']) for s in asking))


if __name__ == '__main__':
    try:
        main()
    except uo.BridgeError as e:
        print(f'STOPPED: {e}')
        sys.exit(1)
