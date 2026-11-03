# Building the client on macOS

The user plays through ClassicUO under Wine (the Sikarugir wrapper `ClassicUO-Wine10.app`). The client is
`cuo.dll`, a NativeAOT Windows DLL, so it's cross-built on the Mac: .NET compiles it, and zig's `lld-link` links it
against the MSVC and Windows SDK libraries that `xwin` downloads.

## Paths

`env.sh` holds them; every one can be overridden from the environment.

| Name | Default | What |
|---|---|---|
| `SRC` | `~/claude/ClassicUO` | this repository (branch `extensions`) |
| `BUILDTOOLS` | `~/claude/buildtools` | zig, xwin output, `lld-link-wrapper.py` |
| `BUILDS` | `~/claude/builds` | one folder per build, and `cuo-smoke`, a test copy of the client |
| `GAME` | `…/ClassicUO-Wine10.app/Contents/SharedSupport/prefix/drive_c/ClassicUO` | the client the user plays with |
| `BACKUPS` | `~/Games/backups` | the previous `cuo.dll`/`cuo.pdb` before each install |
| `DOTNET` | `~/.dotnet/dotnet` | .NET 10 SDK |

## One-time setup of the toolchain (already done on the user's Mac)

1. .NET 10 SDK in the home folder:
   `curl -sSL https://dot.net/v1/dotnet-install.sh | bash -s -- --channel 10.0 --install-dir ~/.dotnet`
2. Source: this repository at `~/claude/ClassicUO` (branch `extensions`), with submodules
   (`git submodule update --init --recursive`; the upstream base is ClassicUO commit `ee79d7e`).
3. In `$BUILDTOOLS`:
   - `dl/zig/zig-x86_64-macos-0.17.0/` (zig 0.17.0 for macOS x86_64, from ziglang.org)
   - `xwin-out/` (the MSVC CRT and Windows SDK libraries), made by running xwin 0.10.0 for Windows under Wine:
     ```
     B=~/claude/buildtools; mkdir -p "$B/xwin-out" "$B/xwin-cache"
     export WINEPREFIX="$B/xwin-prefix" WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml="
     "$B/w10-wine" wineboot -i
     "$B/w10-wine" "$B/dl/xwin/xwin-0.10.0-x86_64-pc-windows-msvc/xwin.exe" --accept-license --arch x86_64 \
         --cache-dir "Z:$(echo "$B/xwin-cache" | tr / '\\')" splat --output "Z:$(echo "$B/xwin-out" | tr / '\\')"
     ```
   - copies of `lld-link`, `lld-link-wrapper.py`, `w10-wine` and `w10-wineserver` from this folder.
4. A test copy of the client: `./make-smoke-folder.sh`. It gets its own `settings.json` with no account. Never copy
   the user's `settings.json`, which holds their password.

## Each change

```
./build.sh cuo-agent8            # safe while the game runs: writes only into $BUILDS/cuo-agent8
./smoke.sh cuo-agent8            # 45 s in the test copy; refuses while any client or wineserver runs
./install.sh cuo-agent8 agent7   # refuses while the game runs; backs up the installed DLL as …-agent7 first
```

Rules from the user:
- Before the clients close for an install while mining runs, both characters are left mounted and hidden (the
  user, 2026-11-02; how, in `tools/uo-agent/MINING.md`).
- Never smoke test, install, or run `wineserver -k` while their clients are running ("don't mess up my game"). Ask
  them to close the clients first, and ask before installing.
- Back up the installed `cuo.dll` and `cuo.pdb` before every install (install.sh does).
- Don't use ClassicUO's `-packetlog`: it logs the password.
- Leave the original UOSA install (`UOSecondAge.app`) untouched.

## What the fork adds

All on branch `extensions` of github.com/matbess/ClassicUO-ext, one commit per feature (see the root `AGENTS.md`).
