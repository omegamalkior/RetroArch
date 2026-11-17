#!/usr/bin/env python3
"""Test-only: make the 3DS gpSP dynarec usable under Azahar.

Azahar implements neither svcControlProcessMemory nor the kernel backdoors
the 3DS build uses to get RWX memory and flush caches. It does not enforce
execute permissions though, and it does implement Luma's
svcInvalidateInstructionCacheRange (0x93), which invalidates its JIT.
So keep the translation caches in regular heap memory and sync through 0x93.
The dynarec itself is untouched. Applied to both test variants.
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


edit('cpu.h',
     '#elif defined(_3DS)\n#define rom_translation_cache ((u8*)0x02000000 - ROM_TRANSLATION_CACHE_SIZE)',
     '#elif defined(_3DS) && defined(AZAHAR_TEST)\nextern u8* rom_translation_cache;\nextern u8* ram_translation_cache;\n'
     '#elif defined(_3DS)\n#define rom_translation_cache ((u8*)0x02000000 - ROM_TRANSLATION_CACHE_SIZE)')

edit('cpu_threaded.c',
     '#elif defined(_3DS) \nu8* rom_translation_cache_ptr;',
     '#elif defined(_3DS) && defined(AZAHAR_TEST)\nu8* rom_translation_cache;\nu8* ram_translation_cache;\n'
     'u8 *rom_translation_ptr;\nu8 *ram_translation_ptr;\n'
     '#elif defined(_3DS) \nu8* rom_translation_cache_ptr;')

edit('cpu_threaded.c',
     '''#elif defined(_3DS)
  #include "3ds/3ds_utils.h"
  void platform_cache_sync(void *baseaddr, void *endptr) {
    ctr_flush_invalidate_cache();
  }''',
     '''#elif defined(_3DS) && defined(AZAHAR_TEST)
  void platform_cache_sync(void *baseaddr, void *endptr) {
    register u32 r0 __asm__("r0") = (u32)baseaddr;
    register u32 r1 __asm__("r1") = (u32)((u8*)endptr - (u8*)baseaddr);
    __asm__ volatile("svc 0x93" : "+r"(r0), "+r"(r1) : : "r2", "r3", "memory");
  }
#elif defined(_3DS)
  #include "3ds/3ds_utils.h"
  void platform_cache_sync(void *baseaddr, void *endptr) {
    ctr_flush_invalidate_cache();
  }''')

edit('libretro/libretro.c',
     '''  #elif defined(_3DS)
   if (__ctr_svchax && !translation_caches_inited)''',
     '''  #elif defined(_3DS) && defined(AZAHAR_TEST)
   if (!translation_caches_inited)
   {
      rom_translation_cache = memalign(0x1000, ROM_TRANSLATION_CACHE_SIZE);
      ram_translation_cache = memalign(0x1000, RAM_TRANSLATION_CACHE_SIZE);
      rom_translation_ptr = rom_translation_cache;
      ram_translation_ptr = ram_translation_cache;
      translation_caches_inited = 1;
   }
  #elif defined(_3DS)
   if (__ctr_svchax && !translation_caches_inited)''')

edit('libretro/libretro.c',
     '''#if defined(_3DS) && defined(HAVE_DYNAREC)

   if (__ctr_svchax && translation_caches_inited)''',
     '''#if defined(_3DS) && defined(HAVE_DYNAREC) && !defined(AZAHAR_TEST)

   if (__ctr_svchax && translation_caches_inited)''')

edit('libretro/libretro_core_options.h',
     '#if defined(_3DS) && (HAVE_DYNAREC)\n   if(!__ctr_svchax)',
     '#if defined(_3DS) && (HAVE_DYNAREC) && !defined(AZAHAR_TEST)\n   if(!__ctr_svchax)')

edit('Makefile',
     '\tCFLAGS += -DARM11 -D_3DS\n',
     '\tCFLAGS += -DARM11 -D_3DS -DAZAHAR_TEST\n')

print('Azahar test variant applied')
