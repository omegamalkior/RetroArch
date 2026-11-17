#!/usr/bin/env python3
"""Test-only: turn gdb_sample.py output into a per-thread function profile.
usage: profile_report.py NM_FILE SAMPLES RETROARCH_LOG"""
import bisect
import collections
import re
import sys

nm_file, samples_file, ra_log = sys.argv[1:4]
syms = []
for line in open(nm_file, errors='replace'):
    parts = line.split(None, 2)
    if len(parts) == 3 and parts[1].lower() in 'tw':
        syms.append((int(parts[0], 16), parts[2].strip()))
syms.sort()
addrs = [a for a, _ in syms]

tc = None
for line in open(ra_log, errors='replace'):
    m = re.search(r'0x[0-9a-f]+/0x[0-9a-f]+/0x[0-9a-f]+/0x[0-9a-f]+/0x([0-9a-f]+)', line)
    if m:
        tc = int(m.group(1), 16)


def name(pc):
    if tc is not None and tc <= pc < tc + (1 << 24):
        return '[dynarec code]'
    i = bisect.bisect_right(addrs, pc) - 1
    if i < 0 or pc - addrs[i] > 0x10000:
        return '?%08x' % pc
    return syms[i][1]


per = collections.defaultdict(collections.Counter)
callers = collections.defaultdict(collections.Counter)
for line in open(samples_file):
    i, t, pc, lr = line.split()
    pc, lr = int(pc, 16), int(lr, 16)
    n = name(pc)
    per[t][n] += 1
    callers[t][(n, name(lr))] += 1

for t, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values())):
    tot = sum(c.values())
    print('thread %s: %d samples' % (t, tot))
    for n, k in c.most_common(25):
        print('  %5.1f%%  %s' % (100.0 * k / tot, n))
    print('  top pc<-lr pairs:')
    for (n, l), k in callers[t].most_common(12):
        print('  %5.1f%%  %s <- %s' % (100.0 * k / tot, n, l))
    print()
