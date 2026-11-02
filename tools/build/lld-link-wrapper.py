# Runs zig's lld-link for NativeAOT cross-linking on macOS.
# lld-link treats any argument starting with "/" as an option, so absolute
# Unix input paths are rewritten relative to the current directory.
import os, shlex, subprocess, sys

B = os.path.dirname(os.path.abspath(__file__))
ZIG = os.path.join(B, "dl/zig/zig-x86_64-macos-0.17.0/zig")
XW = os.path.join(B, "xwin-out")
LIBPATHS = ["crt/lib/x86_64", "sdk/lib/um/x86_64", "sdk/lib/ucrt/x86_64"]

def expand(args):
    out = []
    for a in args:
        if a.startswith("@"):
            with open(a[1:], encoding="utf-8-sig") as f:
                out += shlex.split(f.read().replace("\\", "\\\\"), posix=True)
        else:
            out.append(a)
    return out

args = []
for a in expand(sys.argv[1:]):
    if a.startswith("/") and os.path.exists(a):
        a = os.path.relpath(a)
    args.append(a)
args += ["/LIBPATH:" + os.path.join(XW, p) for p in LIBPATHS]
with open(os.path.join(B, "last-link-args.txt"), "w") as f:
    f.write("\n".join(args))
sys.exit(subprocess.call([ZIG, "lld-link"] + args))
