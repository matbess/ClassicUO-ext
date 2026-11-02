#!/usr/bin/env python3
# Decodes ClassicUO effect recorder logs (Logs/Effects/*.log) into readable lines.
import struct
import sys


def u8(b, o): return b[o]
def u16(b, o): return struct.unpack_from(">H", b, o)[0]
def u32(b, o): return struct.unpack_from(">I", b, o)[0]
def s8(b, o): return struct.unpack_from(">b", b, o)[0]


def ascii_z(b): return b.split(b"\0", 1)[0].decode("latin-1")


def decode(pid, b, text):
    if pid in (0xA1, 0xA2, 0xA3):
        name = {0xA1: "hits", 0xA2: "mana", 0xA3: "stam"}[pid]
        return f"{name} {u16(b, 7)}/{u16(b, 5)}"
    if pid == 0x11:
        out = f"status hits {u16(b, 37)}/{u16(b, 39)}"
        if len(b) > 43 and b[42] >= 1:
            out += (f" str {u16(b, 44)} dex {u16(b, 46)} int {u16(b, 48)}"
                    f" stam {u16(b, 50)}/{u16(b, 52)} mana {u16(b, 54)}/{u16(b, 56)}"
                    f" armor {u16(b, 62)} weight {u16(b, 64)}")
        return out
    if pid == 0x2D:
        return f"attrs hits {u16(b, 7)}/{u16(b, 5)} mana {u16(b, 11)}/{u16(b, 9)} stam {u16(b, 15)}/{u16(b, 13)}"
    if pid == 0x54:
        return f"sound 0x{u16(b, 2):04X} at {u16(b, 6)},{u16(b, 8)}"
    if pid in (0x70, 0xC0, 0xC7):
        kind = {0: "moving", 1: "lightning", 2: "at location", 3: "on mobile"}.get(b[1], b[1])
        out = f"effect {kind} gfx 0x{u16(b, 10):04X} src 0x{u32(b, 2):08X} tgt 0x{u32(b, 6):08X} at {u16(b, 12)},{u16(b, 14)}"
        if pid in (0xC0, 0xC7) and len(b) >= 36:
            out += f" speed {b[24]} dur {b[25]} hue {u32(b, 28)} render {u32(b, 32)}"
        if pid == 0xC7 and len(b) >= 49:
            out += f" particle {u16(b, 36)} explode {u16(b, 38)} layer {b[48]}"
        return out
    if pid in (0x1C, 0xAE):
        return f"speech type {b[9]} from 0x{u32(b, 3):08X} {ascii_z(b[14:44])!r}: {text!r}"
    if pid in (0xC1, 0xCC):
        return f"cliloc {u32(b, 14)} type {b[9]} from 0x{u32(b, 3):08X}"
    if pid in (0x20,):
        return f"update player flags 0x{b[10]:02X} hue {u16(b, 8)} body 0x{u16(b, 5):04X}"
    if pid == 0x77:
        return f"update mobile flags 0x{b[15]:02X} noto {b[16]}"
    if pid == 0x78:
        return f"mobile incoming flags 0x{b[17]:02X}"
    if pid == 0x4E:
        return f"personal light {b[5]}"
    if pid == 0x4F:
        return f"global light {b[1]}"
    if pid in (0x6E, 0xE2):
        return f"animation 0x{u16(b, 5):04X}"
    if pid in (0x16, 0x17):
        return f"healthbar status {b[1:].hex()}"
    if pid == 0xDF:
        return f"BUFF icon {u16(b, 7)} action {u16(b, 9)}"
    return b.hex()


for path in sys.argv[1:]:
    for line in open(path, encoding="utf-8-sig"):
        line = line.rstrip("\n")
        if line.startswith("#") or not line:
            print(line)
            continue
        parts = line.split(" ", 3)
        t, pid, hexdata = parts[0], int(parts[1], 16), parts[2]
        text = parts[3].strip().strip('"') if len(parts) > 3 else None
        b = bytes.fromhex(hexdata)
        try:
            print(f"{t}  {decode(pid, b, text)}")
        except Exception as e:  # keep going on odd packets
            print(f"{t}  {pid:02X} undecoded ({e}) {hexdata}")
