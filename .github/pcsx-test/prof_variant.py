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

u64 prof3ds_gcmd_ticks[256], prof3ds_spr_ticks[512];
u32 prof3ds_gcmd_cnt[256], prof3ds_spr_cnt[512];

static void report_gpu(void)
{
   u64 tot = 0, best;
   int i, k, bi;
   static u8 used[512];
   for (i = 0; i < 256; i++) tot += prof3ds_gcmd_ticks[i];
   SysPrintf("PROFG gpu thread cmd-list ticks/frame %llu\n", tot / 1800);
   memset(used, 0, sizeof(used));
   for (k = 0; k < 12; k++) {
      best = 0; bi = -1;
      for (i = 0; i < 256; i++)
         if (!used[i] && prof3ds_gcmd_ticks[i] > best) { best = prof3ds_gcmd_ticks[i]; bi = i; }
      if (bi < 0) break;
      used[bi] = 1;
      SysPrintf("PROFG cmd %02x %9llu  %5.1f%%  n/frame %u\n", bi, best / 1800,
            tot ? 100.0 * best / tot : 0.0, prof3ds_gcmd_cnt[bi] / 1800);
   }
   memset(used, 0, sizeof(used));
   for (k = 0; k < 10; k++) {
      best = 0; bi = -1;
      for (i = 0; i < 512; i++)
         if (!used[i] && prof3ds_spr_ticks[i] > best) { best = prof3ds_spr_ticks[i]; bi = i; }
      if (bi < 0) break;
      used[bi] = 1;
      SysPrintf("PROFG sprite drv %03x %9llu  n/frame %u\n", bi, best / 1800, prof3ds_spr_cnt[bi] / 1800);
   }
}

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
   if (frames == 600) {
      memset(acc, 0, sizeof(acc)); memset(cnt, 0, sizeof(cnt));
      memset(prof3ds_gcmd_ticks, 0, sizeof(prof3ds_gcmd_ticks));
      memset(prof3ds_gcmd_cnt, 0, sizeof(prof3ds_gcmd_cnt));
      memset(prof3ds_spr_ticks, 0, sizeof(prof3ds_spr_ticks));
      memset(prof3ds_spr_cnt, 0, sizeof(prof3ds_spr_cnt));
   }
   if (frames != 2400) return;
   report_gpu();
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
edit('plugins/gpu_unai/gpulib_if.cpp',
     'extern const unsigned char cmd_lengths[256];\n',
     'extern const unsigned char cmd_lengths[256];\n'
     '#include <3ds/types.h>\n#include <3ds/svc.h>\n'
     'extern "C" u64 prof3ds_gcmd_ticks[256], prof3ds_spr_ticks[512];\n'
     'extern "C" u32 prof3ds_gcmd_cnt[256], prof3ds_spr_cnt[512];\n')
edit('plugins/gpu_unai/gpulib_if.cpp',
     '    PtrUnion packet = { .ptr = (void*)&gpu_unai.PacketBuffer };\n\n    switch (cmd)\n',
     '    PtrUnion packet = { .ptr = (void*)&gpu_unai.PacketBuffer };\n'
     '    u64 prof_t0 = svcGetSystemTick();\n\n    switch (cmd)\n')
edit('plugins/gpu_unai/gpulib_if.cpp',
     '    }\n  }\n\nbreakloop:',
     '    }\n    prof3ds_gcmd_ticks[cmd] += svcGetSystemTick() - prof_t0;\n    prof3ds_gcmd_cnt[cmd]++;\n  }\n\nbreakloop:')
edit('plugins/gpu_unai/gpulib_if.cpp',
     '  gpuDrawS(packet, driver, &w, &h);\n  gput_sum(cpu_cycles_sum, cpu_cycles, gput_sprite(w, h));\n}',
     '  u64 prof_s0 = svcGetSystemTick();\n  gpuDrawS(packet, driver, &w, &h);\n'
     '  prof3ds_spr_ticks[driver_idx & 511] += svcGetSystemTick() - prof_s0;\n  prof3ds_spr_cnt[driver_idx & 511]++;\n'
     '  gput_sum(cpu_cycles_sum, cpu_cycles, gput_sprite(w, h));\n}')
print('profiling variant applied')
