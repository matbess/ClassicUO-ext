#!/bin/bash
# Start a build in the throwaway test copy ($BUILDS/cuo-smoke) for 45 seconds and report errors.
# Usage: smoke.sh NAME.  Refuses while any game client (or wineserver) is running: it ends with wineserver -k,
# which would close the user's clients.
set -e
. "$(dirname "$0")/env.sh"
NAME="${1:?usage: smoke.sh NAME}"
if game_running; then echo "game running - not starting the smoke test"; exit 1; fi
T="$BUILDS/cuo-smoke"; L="$BUILDS/cuo-smoke-$NAME.log"
[ -d "$T" ] || { echo "no $T: run make-smoke-folder.sh first"; exit 1; }
cp "$BUILDS/$NAME/cuo.dll" "$BUILDS/$NAME/cuo.pdb" "$T/"
rm -rf "$T/Logs" "$T/Agent"
export WINEPREFIX="$PREFIX" WINEDEBUG=err+all,fixme-all
cd "$T"
("$BUILDTOOLS/w10-wine" "Z:$(echo "$T/ClassicUO.exe" | tr / '\\')" > "$L" 2>&1 &)
perl -e 'sleep 45'
pgrep -fl "ClassicUO.exe" | cut -c1-60 || echo "the test client is not running (it may have crashed)"
grep -a -i -E 'error|exception|fatal|crash|unhandled' "$L" | grep -a -v -E 'err:listview|fixme' | cut -c1-160 | head -5
grep -a -E 'Done!' "$L" | head -1
"$BUILDTOOLS/w10-wineserver" -k
perl -e 'sleep 3'
pgrep -fl -i 'ClassicUO.exe|wineserver' || echo "test client closed"
