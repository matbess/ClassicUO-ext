# Paths shared by the build scripts. Override any of them in the environment.
BUILDTOOLS="${BUILDTOOLS:-$HOME/claude/buildtools}"     # zig, xwin output, lld-link wrapper, wine helpers
BUILDS="${BUILDS:-$HOME/claude/builds}"                 # one folder per build, plus cuo-smoke (a test copy of the client)
SRC="${SRC:-$HOME/claude/ClassicUO}"                    # this repository
PREFIX="${PREFIX:-$HOME/Applications/Sikarugir/ClassicUO-Wine10.app/Contents/SharedSupport/prefix}"
GAME="${GAME:-$PREFIX/drive_c/ClassicUO}"               # the installed client the user plays with
BACKUPS="${BACKUPS:-$HOME/Games/backups}"
DOTNET="${DOTNET:-$HOME/.dotnet/dotnet}"

game_running() {
    pgrep -f -i 'ClassicUO.exe|wineserver' >/dev/null
}
