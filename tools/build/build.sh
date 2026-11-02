#!/bin/bash
# Build cuo.dll (NativeAOT, win-x64) from this repository into $BUILDS/NAME.  Usage: build.sh NAME
# Safe while the game runs: it only writes into $BUILDS.
set -e
. "$(dirname "$0")/env.sh"
NAME="${1:?usage: build.sh NAME}"
cd "$SRC"
"$DOTNET" publish src/ClassicUO.Client/ClassicUO.Client.csproj -c Release -r win-x64 -o "$BUILDS/$NAME" \
    -p:IS_DEV_BUILD=true -p:AssemblyVersion=1.1.0.347 -p:FileVersion=1.1.0.347 -p:NativeLib=Shared \
    -p:OutputType=Library -p:DisableUnsupportedError=true -p:IlcUseEnvironmentalTools=true \
    -p:CppLinker="$BUILDTOOLS/lld-link" -p:EnableSourceLink=false 2>&1 | grep -E " error |ClassicUO.Client ->" | sort -u
cp "$SRC/bin/Release/net10.0/win-x64/native/cuo.pdb" "$BUILDS/$NAME/cuo.pdb"
shasum -a 256 "$BUILDS/$NAME/cuo.dll" | cut -c1-16
