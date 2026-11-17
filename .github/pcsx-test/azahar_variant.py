#!/usr/bin/env python3
"""Test-only: let the 3DS PCSX ReARMed dynarec run under Azahar.

Azahar has no svcControlProcessMemory and no kernel backdoor (svc 0x80),
which the 3DS build uses for RWX memory and cache maintenance. Azahar does
not enforce execute permission, and it implements Luma's
svcInvalidateInstructionCacheRange (0x93), which drops its own JIT code for
that range. So skip the protection calls, sync through 0x93, and keep the
dynarec on. Applied to every Azahar variant alike.
"""
import sys

root = sys.argv[1]


def edit(path, old, new, count=1):
    p = root + '/' + path
    s = open(p, encoding='latin-1').read()
    n = s.count(old)
    if n != count:
        sys.exit('%s: expected %d match(es), found %d for:\n%s' % (path, count, n, old))
    open(p, 'w', encoding='latin-1').write(s.replace(old, new))


# Never touch svchax-only kernel paths; the weak symbol may be absent.
edit('frontend/3ds/3ds_utils.h',
     'extern __attribute__((weak)) int  __ctr_svchax;',
     '#ifdef AZAHAR_TEST\n#define __ctr_svchax 0\n#else\n'
     'extern __attribute__((weak)) int  __ctr_svchax;\n#endif')

# mprotect: nothing to do on Azahar
edit('frontend/3ds/sys/mman.h',
     'static inline int mprotect(void *addr, size_t len, int prot)\n{\n',
     'static inline int mprotect(void *addr, size_t len, int prot)\n{\n'
     '#ifdef AZAHAR_TEST\n   return 0;\n#endif\n')

# cache sync through svc 0x93
edit('libpcsxcore/new_dynarec/new_dynarec.c',
     '''  #elif defined(_3DS)
  // tuned for old3ds' 16k:16k cache (in it's mostly clean state...)''',
     '''  #elif defined(_3DS) && defined(AZAHAR_TEST)
  {
    register u_int r0 __asm__("r0") = (u_int)start;
    register u_int r1 __asm__("r1") = (u_int)len;
    __asm__ volatile("svc 0x93" : "+r"(r0), "+r"(r1) : : "r2", "r3", "memory");
  }
  #elif defined(_3DS)
  // tuned for old3ds' 16k:16k cache (in it's mostly clean state...)''')

# keep the dynarec on without svchax
edit('frontend/libretro.c',
     '''#ifdef _3DS
      if (!__ctr_svchax)
         Config.Cpu = CPU_INTERPRETER;
      else
#endif''',
     '''#if defined(_3DS) && !defined(AZAHAR_TEST)
      if (!__ctr_svchax)
         Config.Cpu = CPU_INTERPRETER;
      else
#endif''')
edit('frontend/libretro.c',
     '''#ifdef _3DS
   /* emu_core_preinit sets the cpu to dynarec */
   if (!__ctr_svchax)''',
     '''#if defined(_3DS) && !defined(AZAHAR_TEST)
   /* emu_core_preinit sets the cpu to dynarec */
   if (!__ctr_svchax)''')

# real 3DS (CIA) maps psx memory with svcControlMemory; do the same here
edit('frontend/libretro.c',
     '   if (__ctr_svchax) do\n',
     '#ifdef AZAHAR_TEST\n   if (1) do\n#else\n   if (__ctr_svchax) do\n#endif\n')
edit('frontend/libretro.c',
     '   if (ptr && __ctr_svchax)\n',
     '#ifdef AZAHAR_TEST\n   if (ptr)\n#else\n   if (ptr && __ctr_svchax)\n#endif\n')

edit('Makefile.libretro',
     '\tCFLAGS += -DARM11 -D_3DS -D__3DS__\n',
     '\tCFLAGS += -DARM11 -D_3DS -D__3DS__ -DAZAHAR_TEST\n')

print('Azahar test variant applied')
