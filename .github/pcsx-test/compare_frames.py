#!/usr/bin/env python3
"""Test-only: compare frame dumps and DONE timings of two variants."""
import os
import sys

res, a, b = sys.argv[1:4]
da, db = os.path.join(res, a), os.path.join(res, b)


def done(d):
    try:
        for l in open(os.path.join(d, 'log.txt')):
            if l.startswith('DONE'):
                return int(l.split()[4])
    except OSError:
        pass
    return None


for c in sorted(os.listdir(da)):
    if not os.path.isdir(os.path.join(da, c)) or not os.path.isdir(os.path.join(db, c)):
        continue
    ta, tb = done(os.path.join(da, c)), done(os.path.join(db, c))
    same = diff = 0
    for f in sorted(os.listdir(os.path.join(da, c))):
        if not f.endswith('.raw'):
            continue
        fb = os.path.join(db, c, f)
        if not os.path.exists(fb):
            diff += 1
            continue
        if open(os.path.join(da, c, f), 'rb').read() == open(fb, 'rb').read():
            same += 1
        else:
            diff += 1
    pct = '%+.1f%%' % (100.0 * (tb - ta) / ta) if ta and tb else '?'
    print('%-22s core ticks/frame %s -> %s (%s)  frames identical %d, different %d'
          % (c, ta, tb, pct, same, diff))
