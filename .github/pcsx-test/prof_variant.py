#!/usr/bin/env python3
"""Test-only: per-frame tick accounting of the PCSX ReARMed main thread
(where its time goes: dynarec code, GPU/SPU plugin calls, recompiling,
frame output). Printed to the RetroArch log as PROF lines."""
import sys

root = sys.argv[1]


def edit(path, old, new, count=1):
    p = root + '/' + path
    s = open(p, encoding='latin-1').read()
    n = s.count(old)
    if n != count:
        sys.exit('%s: expected %d match(es), found %d for:\n%s' % (path, count, n, old))
    open(p, 'w', encoding='latin-1').write(s.replace(old, new))


open(root + '/frontend/prof3ds.c', 'w').write(r'''
#include <string.h>
#include <3ds/types.h>
#include <3ds/svc.h>
#include <3ds/thread.h>
#include "../libpcsxcore/plugins.h"

extern void SysPrintf(const char *fmt, ...);
void prof3ds_push(int id);
void prof3ds_pop(void);

#define NCAT 8
static const char *names[NCAT] = { "exec", "gpu_dma", "gpu_io", "gpu_vblank",
   "vout_flip", "spu", "drc_compile", "frontend" };
static u64 acc[NCAT], cnt[NCAT];
static int stk[32], sp, cur = 7;
static u64 t;
static unsigned frames;

static int on_main(void) { return threadGetCurrent() == NULL; }

void prof3ds_push(int id)
{
   u64 n;
   if (!on_main()) return;
   n = svcGetSystemTick();
   acc[cur] += n - t; t = n;
   if (sp < 32) stk[sp++] = cur;
   cur = id; cnt[id]++;
}

void prof3ds_pop(void)
{
   u64 n;
   if (!on_main()) return;
   n = svcGetSystemTick();
   acc[cur] += n - t; t = n;
   if (sp) cur = stk[--sp];
}

void prof3ds_run_begin(void) { t = svcGetSystemTick(); cur = 7; sp = 0; }

void prof3ds_run_end(void)
{
   u64 n = svcGetSystemTick(), tot = 0;
   int i;
   acc[cur] += n - t; t = n;
   frames++;
   if (frames == 600) { memset(acc, 0, sizeof(acc)); memset(cnt, 0, sizeof(cnt)); }
   if (frames != 2400) return;
   for (i = 0; i < NCAT; i++) tot += acc[i];
   SysPrintf("PROF per-frame ticks over 1800 frames: total %llu\n", tot / 1800);
   for (i = 0; i < NCAT; i++)
      SysPrintf("PROF %-12s %9llu  %5.1f%%  calls/frame %llu\n", names[i], acc[i] / 1800,
            tot ? 100.0 * acc[i] / tot : 0.0, cnt[i] / 1800);
}

#define W0(cat, T, R, name, args, call) \
   static T o_##name; \
   static R w_##name args { R r; prof3ds_push(cat); r = o_##name call; prof3ds_pop(); return r; }
#define WV(cat, T, name, args, call) \
   static T o_##name; \
   static void w_##name args { prof3ds_push(cat); o_##name call; prof3ds_pop(); }

WV(1, GPUwriteDataMem, gwdm, (uint32_t *a, int b), (a, b))
WV(1, GPUwriteData, gwd, (uint32_t a), (a))
W0(1, GPUdmaChain, long, gdc, (uint32_t *a, uint32_t b, uint32_t *c, int32_t *d), (a, b, c, d))
W0(2, GPUreadStatus, uint32_t, grs, (void), ())
W0(2, GPUreadData, uint32_t, grd, (void), ())
WV(2, GPUreadDataMem, grdm, (uint32_t *a, int b), (a, b))
WV(2, GPUwriteStatus, gws, (uint32_t a), (a))
WV(3, GPUvBlank, gvb, (int a, int b), (a, b))
WV(5, SPUwriteRegister, swr, (unsigned long a, unsigned short b, unsigned int c), (a, b, c))
W0(5, SPUreadRegister, unsigned short, srr, (unsigned long a, unsigned int b), (a, b))
WV(5, SPUwriteDMAMem, swdm, (unsigned short *a, int b, unsigned int c), (a, b, c))
WV(5, SPUreadDMAMem, srdm, (unsigned short *a, int b, unsigned int c), (a, b, c))
WV(5, SPUasync, sa, (unsigned int a, unsigned int b), (a, b))

#define HOOK(ptr, name) if (ptr != w_##name) { o_##name = ptr; ptr = w_##name; }
void prof3ds_hook(void)
{
   HOOK(GPU_writeDataMem, gwdm) HOOK(GPU_writeData, gwd) HOOK(GPU_dmaChain, gdc)
   HOOK(GPU_readStatus, grs) HOOK(GPU_readData, grd) HOOK(GPU_readDataMem, grdm)
   HOOK(GPU_writeStatus, gws) HOOK(GPU_vBlank, gvb)
   HOOK(SPU_writeRegister, swr) HOOK(SPU_readRegister, srr) HOOK(SPU_writeDMAMem, swdm)
   HOOK(SPU_readDMAMem, srdm) HOOK(SPU_async, sa)
}
''')

edit('frontend/libretro.c',
     '''   if (OpenPlugins(0) == -1)
   {
      LogErr("failed to open plugins\\n");
      return false;
   }
''',
     '''   if (OpenPlugins(0) == -1)
   {
      LogErr("failed to open plugins\\n");
      return false;
   }
   { extern void prof3ds_hook(void); prof3ds_hook(); }
''')
edit('frontend/libretro.c',
     'void retro_run(void)\n{\n',
     'void prof3ds_run_begin(void);\nvoid prof3ds_run_end(void);\n'
     'static void retro_run_real(void);\nvoid retro_run(void)\n{\n   prof3ds_run_begin();\n   retro_run_real();\n   prof3ds_run_end();\n}\n'
     'static void retro_run_real(void)\n{\n')
edit('frontend/libretro.c',
     '   psxCpu->Execute(&psxRegs);\n',
     '   prof3ds_push(0);\n   psxCpu->Execute(&psxRegs);\n   prof3ds_pop();\n')
edit('frontend/libretro.c',
     '   .pl_vout_flip     = vout_flip,\n',
     '   .pl_vout_flip     = vout_flip_prof,\n')
edit('frontend/libretro.c',
     'struct rearmed_cbs pl_rearmed_cbs = {\n',
     'void prof3ds_push(int id);\nvoid prof3ds_pop(void);\n'
     'static void vout_flip_prof(const void *vram_, int vram_ofs, int bgr24,\n'
     '      int x, int y, int w, int h, int dims_changed)\n'
     '{\n   prof3ds_push(4);\n   vout_flip(vram_, vram_ofs, bgr24, x, y, w, h, dims_changed);\n   prof3ds_pop();\n}\n\n'
     'struct rearmed_cbs pl_rearmed_cbs = {\n')
edit('libpcsxcore/new_dynarec/new_dynarec.c',
     'static int noinline new_recompile_block(u_int addr)\n{\n',
     'void prof3ds_push(int id);\nvoid prof3ds_pop(void);\n'
     'static int noinline new_recompile_block_real(u_int addr);\n'
     'static int noinline new_recompile_block(u_int addr)\n{\n'
     '  int r;\n  prof3ds_push(6);\n  r = new_recompile_block_real(addr);\n  prof3ds_pop();\n  return r;\n}\n\n'
     'static int noinline new_recompile_block_real(u_int addr)\n{\n')
edit('Makefile.libretro',
     '\tOBJS += frontend/3ds/utils.o\n',
     '\tOBJS += frontend/3ds/utils.o\n\tOBJS += frontend/prof3ds.o\n')
print('profiling variant applied')
