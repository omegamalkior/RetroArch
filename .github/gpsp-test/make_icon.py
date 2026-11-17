#!/usr/bin/env python3
"""Draw the test build's icon (a ringed planet in space) as a PNG.

usage: make_icon.py SIZE OUT.png
Standard library only, so it runs inside the devkitPro container.
"""
import math
import struct
import sys
import zlib


def png(path, w, h, rgba):
    raw = b''.join(b'\x00' + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))

    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)))
        f.write(chunk(b'IDAT', zlib.compress(raw, 9)))
        f.write(chunk(b'IEND', b''))


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))


def sample(u, v):
    """Colour at (u, v) in [-1, 1]^2."""
    r = math.hypot(u, v)
    col = mix((40, 12, 70), (6, 8, 24), min(1.0, r / 1.3))
    # stars
    for sx, sy, s in ((-0.72, -0.62, 0.05), (0.66, -0.78, 0.04), (0.78, 0.55, 0.035),
                      (-0.55, 0.74, 0.03), (0.15, -0.88, 0.025), (-0.86, 0.12, 0.03)):
        d = math.hypot(u - sx, v - sy)
        if d < s:
            col = mix(col, (255, 245, 210), 1 - d / s)
    # ring, tilted ellipse
    a = math.radians(-22)
    ru = u * math.cos(a) - v * math.sin(a)
    rv = u * math.sin(a) + v * math.cos(a)
    e = math.hypot(ru / 0.92, rv / 0.30)
    in_ring = 0.80 < e < 1.0
    planet = r < 0.52
    if in_ring and rv < 0 and not planet:
        col = mix((255, 196, 80), (230, 110, 30), (e - 0.8) / 0.2)
    if planet:
        lu, lv = u + 0.2, v + 0.25
        shade = max(0.0, 1 - math.hypot(lu, lv) / 0.75)
        col = mix((150, 40, 20), (255, 140, 40), shade)
        band = math.sin((v + 0.1 * u) * 18)
        if band > 0.6:
            col = mix(col, (255, 210, 120), 0.35)
    if in_ring and rv >= 0:
        col = mix((255, 196, 80), (230, 110, 30), (e - 0.8) / 0.2)
    return col


def main():
    size = int(sys.argv[1])
    ss = 4
    out = []
    for y in range(size):
        for x in range(size):
            acc = [0.0, 0.0, 0.0]
            for j in range(ss):
                for i in range(ss):
                    u = ((x + (i + 0.5) / ss) / size) * 2 - 1
                    v = ((y + (j + 0.5) / ss) / size) * 2 - 1
                    c = sample(u, v)
                    for k in range(3):
                        acc[k] += c[k]
            out += [int(acc[0] / ss / ss), int(acc[1] / ss / ss), int(acc[2] / ss / ss), 255]
    png(sys.argv[2], size, size, out)


main()
