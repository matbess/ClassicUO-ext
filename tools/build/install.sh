#!/bin/bash
# Install a build into the user's client, after backing up what's installed.
# Usage: install.sh NAME BACKUP_NAME   (backup goes to $BACKUPS/classicuo-1.1.0.347-BACKUP_NAME)
# Only with the user's OK, and never while a client is running.
set -e
. "$(dirname "$0")/env.sh"
NAME="${1:?usage: install.sh NAME BACKUP_NAME}"; KEEP="${2:?usage: install.sh NAME BACKUP_NAME}"
if game_running; then echo "game running - not installing"; exit 1; fi
K="$BACKUPS/classicuo-1.1.0.347-$KEEP"
mkdir -p "$K"
cp -p "$GAME/cuo.dll" "$GAME/cuo.pdb" "$K/"
cp "$BUILDS/$NAME/cuo.dll" "$BUILDS/$NAME/cuo.pdb" "$GAME/"
shasum -a 256 "$K/cuo.dll" "$GAME/cuo.dll" | cut -c1-16
echo "installed $NAME; the previous cuo.dll/pdb are in $K"
