#!/usr/bin/env python3
"""Test-only: sampling profiler over Azahar's GDB stub.

Stops the emulated process at intervals and records every thread's PC/LR.
usage: gdb_sample.py PORT SAMPLES OUT.txt
"""
import socket
import sys
import time

port, samples, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]


class Gdb:
    def __init__(self, port):
        for _ in range(300):
            try:
                self.s = socket.create_connection(('127.0.0.1', port), timeout=30)
                break
            except OSError:
                time.sleep(1)
        else:
            raise SystemExit('no gdb stub')
        self.buf = b''

    def _byte(self):
        while not self.buf:
            d = self.s.recv(65536)
            if not d:
                raise EOFError
            self.buf += d
        b, self.buf = self.buf[:1], self.buf[1:]
        return b

    def send(self, pkt):
        data = pkt.encode()
        self.s.sendall(b'$' + data + b'#%02x' % (sum(data) & 0xff))

    def recv(self):
        while True:
            c = self._byte()
            if c == b'$':
                break
        body = b''
        while True:
            c = self._byte()
            if c == b'#':
                break
            body += c
        self._byte()
        self._byte()
        self.s.sendall(b'+')
        return body.decode(errors='replace')

    def cmd(self, pkt):
        self.send(pkt)
        return self.recv()


def le32(h):
    return int.from_bytes(bytes.fromhex(h), 'little')


g = Gdb(port)
print('stop:', g.cmd('?'), flush=True)
tids = []
r = g.cmd('qfThreadInfo')
while r.startswith('m'):
    tids += [int(t, 16) for t in r[1:].split(',') if t]
    r = g.cmd('qsThreadInfo')
print('threads:', tids, flush=True)

with open(out, 'w') as f:
    for i in range(samples):
        g.send('c')
        time.sleep(0.02)
        g.s.sendall(b'\x03')
        g.recv()
        time.sleep(0.02)
        for t in tids:
            if g.cmd('Hg%x' % t) != 'OK':
                continue
            regs = g.cmd('g')
            if len(regs) < 16 * 8:
                continue
            pc = le32(regs[15 * 8:16 * 8])
            lr = le32(regs[14 * 8:15 * 8])
            f.write('%d %d %08x %08x\n' % (i, t, pc, lr))
        if i % 100 == 0:
            print('sample', i, flush=True)
            f.flush()
g.send('D')
print('done', flush=True)
