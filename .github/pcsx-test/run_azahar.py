#!/usr/bin/env python3
"""Test-only: run a RetroArch 3DS test build in Azahar for each PS1 test
program and collect the timing log and frame dumps it writes to the SD card.

usage: run_azahar.py AZAHAR_APPRUN VARIANT 3DSX CONTENT_DIR RESULTS_DIR [TAG]
"""
import os
import shutil
import subprocess
import sys
import time

azahar, variant, app, content_dir, results = sys.argv[1:6]
tag = sys.argv[6] if len(sys.argv) > 6 else ''
frames_timeout = int(os.environ.get('RUN_TIMEOUT', '900'))

QT_CONFIG = r'''[UI]
check_for_update_on_start\default=false
check_for_update_on_start=false
first_start\default=false
first_start=false
confirm_before_closing\default=false
confirm_before_closing=false
pause_when_in_background\default=false
pause_when_in_background=false
mute_when_in_background\default=false
mute_when_in_background=false
[System]
is_new_3ds\default=false
is_new_3ds=true
[Core]
cpu_clock_percentage\default=true
cpu_clock_percentage=100
[Renderer]
graphics_api\default=false
graphics_api=0
use_vsync\default=false
use_vsync=false
[Audio]
output_type\default=false
output_type=1
[Miscellaneous]
log_filter\default=true
log_filter=*:Info
'''

RA_CFG = '''config_save_on_exit = "false"
menu_driver = "rgui"
video_font_enable = "false"
menu_show_load_content_animation = "false"
log_verbosity = "true"
log_to_file = "true"
log_to_file_timestamp = "false"
frontend_log_level = "0"
libretro_log_level = "0"
savefile_directory = "sdmc:/retroarch/e2e/saves"
savestate_directory = "sdmc:/retroarch/e2e/states"
'''

os.makedirs(results, exist_ok=True)
summary = []
for name in sorted(os.listdir(content_dir)):
    if not name.lower().endswith(('.exe', '.cue', '.chd', '.pbp', '.m3u')):
        continue
    stem = os.path.splitext(name)[0]
    only = os.environ.get('ONLY', '').split()
    if only and stem not in only:
        continue
    home = os.path.abspath('az_home_%s%s_%s' % (variant, tag, stem))
    shutil.rmtree(home, ignore_errors=True)
    data = os.path.join(home, 'data', 'azahar-emu')
    conf = os.path.join(home, 'config', 'azahar-emu')
    sdmc = os.path.join(data, 'sdmc')
    e2e = os.path.join(sdmc, 'retroarch', 'e2e')
    os.makedirs(conf)
    os.makedirs(e2e)
    os.makedirs(os.path.join(sdmc, '3ds'))
    fw = bytearray(1024)
    fw[0x100:0x104] = b'DSP1'
    fw[0x105] = 4
    open(os.path.join(sdmc, '3ds', 'dspfirm.cdc'), 'wb').write(fw)
    open(os.path.join(conf, 'qt-config.ini'), 'w').write(QT_CONFIG)
    open(os.path.join(sdmc, 'retroarch', 'retroarch.cfg'), 'w').write(RA_CFG)
    shutil.copy(os.path.join(content_dir, name), os.path.join(e2e, name))
    open(os.path.join(e2e, 'autoload.txt'), 'w').write('sdmc:/retroarch/e2e/' + name)
    log = os.path.join(e2e, 'out_' + variant, 'log.txt')

    env = dict(os.environ)
    env['XDG_DATA_HOME'] = os.path.join(home, 'data')
    env['XDG_CONFIG_HOME'] = os.path.join(home, 'config')
    env['XDG_CACHE_HOME'] = os.path.join(home, 'cache')
    env['QT_QPA_PLATFORM'] = 'xcb'
    print('== %s / %s' % (variant, name), flush=True)
    t0 = time.time()
    profile = int(os.environ.get('PROFILE_SAMPLES', '0'))
    argv = [azahar]
    if profile:
        argv += ['-g', '24689']
    p = subprocess.Popen(argv + [os.path.abspath(app)], env=env,
                         stdout=open(os.path.join(home, 'stdout.txt'), 'w'),
                         stderr=subprocess.STDOUT)
    result = 'did not finish'
    last_line = ''
    while time.time() - t0 < frames_timeout:
        time.sleep(5)
        if os.path.exists(log):
            lines = open(log).read().splitlines()
            if lines:
                last_line = lines[-1]
            done = [l for l in lines if l.startswith('DONE')]
            if profile and any(l.startswith('frame 600 ') for l in lines):
                samples = os.path.join(home, 'samples.txt')
                subprocess.call([sys.executable, os.path.join(os.path.dirname(__file__), 'gdb_sample.py'),
                                 '24689', str(profile), samples], timeout=frames_timeout)
                result = 'profiled'
                break
            if done:
                result = done[0]
                break
        if p.poll() is not None:
            result = 'azahar exited (%s)' % p.returncode
            break
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill()
    secs = int(time.time() - t0)
    if result == 'did not finish' and last_line:
        result += ' (last: %s)' % last_line
    print('   %s [%ds]' % (result, secs), flush=True)
    summary.append('%s%s %s : %s [%ds]' % (variant, tag, stem, result, secs))

    dest = os.path.join(results, variant + tag, stem)
    os.makedirs(dest, exist_ok=True)
    out = os.path.join(e2e, 'out_' + variant)
    if os.path.isdir(out):
        for f in os.listdir(out):
            shutil.copy(os.path.join(out, f), dest)
    for src, dst in ((os.path.join(sdmc, 'retroarch', 'logs', 'retroarch.log'), 'retroarch.log'),
                     (os.path.join(data, 'log', 'azahar_log.txt'), 'azahar_log.txt'),
                     (os.path.join(home, 'stdout.txt'), 'azahar_stdout.txt'),
                     (os.path.join(home, 'samples.txt'), 'samples.txt')):
        if os.path.exists(src):
            shutil.copy(src, os.path.join(dest, dst))

with open(os.path.join(results, 'summary_%s%s.txt' % (variant, tag)), 'w') as f:
    f.write('\n'.join(summary) + '\n')
print('\n'.join(summary))
