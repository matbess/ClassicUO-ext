"""The user's entrance reagent chest topped up to 250 of each reagent (the user, 2026-11-22: "I want my secure
entrance-chest to have 250 of each reagent ... look at the chest and see how many are missing and then go to my
unsecure personal reagent chest by the forge and pull out that many reagents and take them over to top it up").

  python3 tools/uo-agent/reagents_topup.py [--then-shovels]

From: the user's personal chest by the forge (2327, 2nd, 0x4059020A), its piles split where they lie (the part
taken keeps the serial; the rest stays on the same spot), wherever in the chest (in a bag too).
To: their secure chest by the window (938 2nd, 0x406F2466), each onto its pile there; a reagent with no pile there
goes on a free spot. Then counted again. --then-shovels puts away the shovels in his pack first (tools_room.py; he's
behind the tables anyway). He comes in first if he's outside (castle.go_in), and finish.py ends it: the table locked
down as he leaves, parked in the great hall.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import tools_room  # noqa: E402
import uo  # noqa: E402
import castle_site  # noqa: E402
import look  # noqa: E402

TARGET = 250
FROM, TO = '0x4059020A', '0x406F2466'
REAGENTS = {'0x0F7A': 'black pearl', '0x0F7B': 'blood moss', '0x0F84': 'garlic', '0x0F85': 'ginseng',
            '0x0F86': 'mandrake root', '0x0F88': 'nightshade', '0x0F8C': 'sulfurous ash', '0x0F8D': "spider's silk"}
# free spots in the entrance chest for a reagent with no pile there yet (its other piles: 18-118 x, 105-150 y)
NEW_SPOTS = [(135, 145), (135, 125), (140, 160), (110, 160)]
say = tools_room.say


def counts(items):
    have = {g: 0 for g in REAGENTS}
    for i in items:
        if i['graphic'] in REAGENTS:
            have[i['graphic']] += i.get('amount', 1)
    return have


BAGS = {'0x0E75', '0x0E76'}  # looked in: backpacks and bags only, never pouches (the user's trapped ones) or boxes


def piles(serial, depth=0):
    """Every reagent pile in a container, and in the backpacks and bags in it. One that never answers an open (a
    wooden box in the user's keys bag did, 2026-11-22 00:17) is skipped."""
    out = []
    try:
        items = look.open_once(tools_room.info, serial)
    except uo.BridgeError as e:
        if e.code == 423 and 'no answer' in e.message and depth:
            uo.call(tools_room.info, 'POST', '/resume')
            say(f'{serial} never answered an open: skipped')
            return out
        raise
    for i in items:
        if i['graphic'] in REAGENTS:
            out.append(i)
        elif i['graphic'] in BAGS and depth < 2 and i['serial'] not in tools_room.OFF_LIMITS:
            out += piles(i['serial'], depth + 1)
    return out


def main():
    tools_room.setup(uo.find_bridge('Clem'))
    info = tools_room.info
    tools_room.OFF_LIMITS = set(uo.call(info, 'GET', '/rules').get('offLimits', []))
    if '--then-shovels' in sys.argv:
        tools_room.put(['shovels'], leave=False)
    else:
        tools_room.stand()  # in, and behind the tables
    mover = castle_site.install(uo, info, say)
    pack = uo.call(info, 'GET', '/status')['backpack']['serial']

    st = uo.call(info, 'GET', '/status')
    if tools_room.in_room((st['x'], st['y'])):  # the tools room isn't on the castle's routes: a plain walk out
        tools_room.walk_to(tools_room.SPARE_STAND, 'to the entrance chest')
    mover.walk_near(info, TO)
    have = counts(look.open_once(info, TO))
    need = {g: max(0, TARGET - n) for g, n in have.items()}
    say('the entrance chest: ' + ', '.join(f'{REAGENTS[g]} {have[g]}' for g in REAGENTS)
        + ' | short: ' + (', '.join(f'{REAGENTS[g]} {n}' for g, n in need.items() if n) or 'nothing'))
    if not any(need.values()):
        return finish()

    mover.walk_near(info, FROM)
    source = piles(FROM)
    got, carried = {}, []
    for g, n in need.items():
        for p in [p for p in source if p['graphic'] == g]:
            if n <= 0:
                break
            take = min(n, p.get('amount', 1))
            spot = (40 + 14 * len(carried), 80)
            uo.call(info, 'POST', '/move', serial=p['serial'], to=pack, x=spot[0], y=spot[1],
                    **({'amount': take} if take < p.get('amount', 1) else {}))
            carried.append((p['serial'], g, take))
            got[g] = got.get(g, 0) + take
            n -= take
    short = {g: need[g] - got.get(g, 0) for g in need if need[g] - got.get(g, 0) > 0}
    say('taken from the forge chest: ' + ', '.join(f'{REAGENTS[g]} {n}' for g, n in got.items())
        + (' | NOT ENOUGH THERE: ' + ', '.join(f'{REAGENTS[g]} {n}' for g, n in short.items()) if short else ''))

    mover.walk_near(info, TO)
    there = {i['graphic']: i for i in look.open_once(info, TO) if i['graphic'] in REAGENTS}
    spots = iter(NEW_SPOTS)
    for serial, g, n in carried:
        if g in there:
            uo.call(info, 'POST', '/move', serial=serial, to=there[g]['serial'])  # onto its pile
        else:
            x, y = next(spots)
            uo.call(info, 'POST', '/move', serial=serial, to=TO, x=x, y=y)
            there[g] = {'serial': serial}
            say(f'{REAGENTS[g]}: a new pile at {x},{y}')
    after = counts(look.open_once(info, TO))
    say('the entrance chest now: ' + ', '.join(f'{REAGENTS[g]} {after[g]}' for g in REAGENTS))
    finish()


def finish():
    r = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'finish.py'), '--side', 'east', '--floor'],
                       env=dict(os.environ, UO_CHAR='Clem'))
    if r.returncode:
        raise SystemExit('finish.py stopped (the table may still be aside: castle.py table close)')


if __name__ == '__main__':
    main()
