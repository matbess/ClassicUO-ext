#!/usr/bin/env python3
"""Read the game's map files (map0.mul, statics0.mul, tiledata.mul, radarcol.mul) to plan where to mine.

Read only, standard library only. Map 0 (Felucca/Britannia) is 7168 x 4096 tiles in 8x8 blocks.

  import uomap
  m = uomap.Map()
  m.land(1130, 1547)        -> (tile id, z)
  m.statics(1130, 1547)     -> [(tile id, z, hue), ...]
  m.land_name(id), m.static_name(id), m.radar_land(id) -> (r, g, b)

  python3 uomap.py X Y [RANGE]   print the tiles around a spot
"""
import os
import struct
import sys

DATA = os.path.expanduser('~/Games/UOSA-data')
WIDTH, HEIGHT = 7168, 4096
BLOCKS_HIGH = HEIGHT // 8


class Map:
    def __init__(self, data=DATA, diffs=False):
        self.data = data
        self._map = open(os.path.join(data, 'map0.mul'), 'rb')
        self._idx = open(os.path.join(data, 'staidx0.mul'), 'rb')
        self._sta = open(os.path.join(data, 'statics0.mul'), 'rb')
        self._land_blocks, self._static_blocks = {}, {}
        self._read_tiledata()
        with open(os.path.join(data, 'radarcol.mul'), 'rb') as fh:
            raw = fh.read()
        self.radar = struct.unpack(f'<{len(raw) // 2}H', raw)
        self.diff_land, self.diff_statics = {}, {}
        if diffs:
            self._read_diffs()

    # ---- tiledata: the old (pre High Seas) format, 26-byte land and 37-byte static entries ----
    def _read_tiledata(self):
        with open(os.path.join(self.data, 'tiledata.mul'), 'rb') as fh:
            raw = fh.read()
        self.land_flags, self.land_names, pos = [], [], 0
        for _ in range(512):
            pos += 4
            for _ in range(32):
                flags, _tex = struct.unpack_from('<IH', raw, pos)
                self.land_flags.append(flags)
                self.land_names.append(raw[pos + 6:pos + 26].split(b'\0')[0].decode('latin-1'))
                pos += 26
        self.static_flags, self.static_heights, self.static_names = [], [], []
        while pos + 4 + 32 * 37 <= len(raw):
            pos += 4
            for _ in range(32):
                flags = struct.unpack_from('<I', raw, pos)[0]
                self.static_flags.append(flags)
                self.static_heights.append(raw[pos + 16])
                self.static_names.append(raw[pos + 17:pos + 37].split(b'\0')[0].decode('latin-1'))
                pos += 37

    def land_name(self, tile):
        return self.land_names[tile] if tile < len(self.land_names) else '?'

    def static_name(self, tile):
        return self.static_names[tile] if tile < len(self.static_names) else '?'

    def impassable_land(self, tile):
        return bool(self.land_flags[tile] & 0x40) if tile < len(self.land_flags) else True

    def impassable_static(self, tile):
        return bool(self.static_flags[tile] & 0x40) if tile < len(self.static_flags) else False

    def radar_land(self, tile):
        return _rgb(self.radar[tile]) if tile < 0x4000 else (0, 0, 0)

    def radar_static(self, tile):
        i = 0x4000 + tile
        return _rgb(self.radar[i]) if i < len(self.radar) else (0, 0, 0)

    # ---- the map itself ----
    def _block(self, bx, by):
        key = bx * BLOCKS_HIGH + by
        if key in self.diff_land:
            return self.diff_land[key]
        if key not in self._land_blocks:
            self._map.seek(key * 196 + 4)
            raw = self._map.read(192)
            self._land_blocks[key] = [struct.unpack_from('<Hb', raw, i * 3) for i in range(64)]
        return self._land_blocks[key]

    def _static_block(self, bx, by):
        key = bx * BLOCKS_HIGH + by
        if key in self.diff_statics:
            return self.diff_statics[key]
        if key not in self._static_blocks:
            self._idx.seek(key * 12)
            offset, length, _ = struct.unpack('<iii', self._idx.read(12))
            cells = {}
            if offset >= 0 and length > 0:
                self._sta.seek(offset)
                raw = self._sta.read(length)
                for i in range(length // 7):
                    tile, x, y, z, hue = struct.unpack_from('<HBBbH', raw, i * 7)
                    cells.setdefault((x, y), []).append((tile, z, hue))
            self._static_blocks[key] = cells
        return self._static_blocks[key]

    def land(self, x, y):
        return self._block(x >> 3, y >> 3)[(y & 7) * 8 + (x & 7)]

    def statics(self, x, y):
        return self._static_block(x >> 3, y >> 3).get((x & 7, y & 7), [])

    def _read_diffs(self):
        d = self.data
        with open(os.path.join(d, 'mapdifl0.mul'), 'rb') as fh:
            blocks = struct.unpack(f'<{os.path.getsize(fh.name) // 4}i', fh.read())
        with open(os.path.join(d, 'mapdif0.mul'), 'rb') as fh:
            for key in blocks:
                raw = fh.read(196)[4:]
                self.diff_land[key] = [struct.unpack_from('<Hb', raw, i * 3) for i in range(64)]
        with open(os.path.join(d, 'stadifl0.mul'), 'rb') as fh:
            blocks = struct.unpack(f'<{os.path.getsize(fh.name) // 4}i', fh.read())
        with open(os.path.join(d, 'stadifi0.mul'), 'rb') as ih, open(os.path.join(d, 'stadif0.mul'), 'rb') as sh:
            for key in blocks:
                offset, length, _ = struct.unpack('<iii', ih.read(12))
                cells = {}
                if offset >= 0 and length > 0:
                    sh.seek(offset)
                    raw = sh.read(length)
                    for i in range(length // 7):
                        tile, x, y, z, hue = struct.unpack_from('<HBBbH', raw, i * 7)
                        cells.setdefault((x, y), []).append((tile, z, hue))
                self.diff_statics[key] = cells


def _rgb(c):
    return (((c >> 10) & 31) * 255 // 31, ((c >> 5) & 31) * 255 // 31, (c & 31) * 255 // 31)


if __name__ == '__main__':
    m = Map()
    x0, y0 = int(sys.argv[1]), int(sys.argv[2])
    r = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    for y in range(y0 - r, y0 + r + 1):
        for x in range(x0 - r, x0 + r + 1):
            tile, z = m.land(x, y)
            st = ', '.join(f'0x{t:04X} {m.static_name(t)} z{sz}' for t, sz, _ in m.statics(x, y))
            print(f'{x},{y}  0x{tile:04X} {m.land_name(tile)} z{z}' + (f'  | {st}' if st else ''))
