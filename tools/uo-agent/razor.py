"""Razor's AutoSearch: it double-clicks every bag that lands in the character's pack (and the bags inside it), and
the bridge takes that for the user taking over. install() wraps a uo module's call so that such a takeover, checked
to be Razor's (castle_move.razor_opened: the click within a second of the bag's drop, nothing else sent), is handed
back and the request sent again; a real takeover goes on up as before."""
import castle_move


def install(uo, info, say=print):
    if getattr(uo.call, 'past_razor', False):
        return
    castle_move.info, castle_move.say = info, say
    plain = uo.call

    def call(i, method, endpoint, **params):
        for _ in range(4):
            try:
                return plain(i, method, endpoint, **params)
            except uo.TakenOver:
                if not castle_move.razor_opened(params.get('serial')):
                    raise
        return plain(i, method, endpoint, **params)

    call.past_razor = True
    uo.call = call
