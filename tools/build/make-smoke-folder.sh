#!/bin/bash
# Make $BUILDS/cuo-smoke: a throwaway copy of the installed client for smoke tests. It gets its own settings.json
# with no account, so it only reaches the login screen. Never copy the user's settings.json (it holds the password).
set -e
. "$(dirname "$0")/env.sh"
T="$BUILDS/cuo-smoke"
rm -rf "$T"; mkdir -p "$T/Data"
for f in "$GAME"/*; do
    b=$(basename "$f")
    case "$b" in Data|Logs|Agent|settings.json|Play.bat) ;; *) cp -p "$f" "$T/" ;; esac
done
cp -R "$GAME/Data/Client" "$T/Data/" 2>/dev/null || true
/usr/bin/python3 -I - "$T/settings.json" "$HOME" <<'PY'
import json, sys
home = sys.argv[2]
s = {"username": "", "password": "", "ip": "login.uosecondage.com", "port": 2593,
     "ultimaonlinedirectory": "Z:" + (home + "/Games/UOSA-data").replace("/", "\\"), "profilespath": "",
     "clientversion": "5.0.8.3", "lang": "ENU", "lastservernum": 1, "last_server_name": "SecondAge", "fps": 60,
     "saveaccount": False, "autologin": False, "reconnect": False, "reconnect_time": 1, "login_music": False,
     "login_music_volume": 0, "shard_type": 0, "fixed_time_step": True, "run_mouse_in_separate_thread": True,
     "force_driver": 0, "use_verdata": False, "encryption": 0, "plugins": []}
open(sys.argv[1], "w").write(json.dumps(s, indent=2))
PY
echo "made $T"
