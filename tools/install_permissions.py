#!/usr/bin/env python3
"""Optional Linux udev rules for catalogued USB RGB devices. No drivers or services."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description='Instala permisos udev; ejecuta con sudo o pkexec')
    parser.add_argument('--i2c', action='store_true', help='También permite acceso I2C a la sesión activa; no habilita detectores')
    parser.add_argument('--print', action='store_true', dest='print_only', help='Muestra las reglas sin modificar el sistema')
    args = parser.parse_args()
    catalog = json.loads((ROOT / 'data/openrgb-1.1.json').read_text())
    pairs = {tuple(r['ids']) for r in catalog['matches'] if r['kind'] == 'usb'}
    pairs.add(('2e3c', 'c365'))  # Guarded Redragon adapter; checks product and firmware itself.
    lines = ['# RGB unificado: only exact supported USB IDs, access for the active session.']
    for vid, pid in sorted(pairs):
        if not all(re.fullmatch('[0-9a-f]{4}', value) for value in (vid, pid)):
            raise ValueError('VID/PID inválido en el catálogo')
        lines.append(f'SUBSYSTEM=="hidraw", ATTRS{{idVendor}}=="{vid}", ATTRS{{idProduct}}=="{pid}", TAG+="uaccess"')
        lines.append(f'SUBSYSTEM=="usb", ENV{{DEVTYPE}}=="usb_device", ATTR{{idVendor}}=="{vid}", ATTR{{idProduct}}=="{pid}", TAG+="uaccess"')
    if args.i2c:
        lines.append('SUBSYSTEM=="i2c-dev", KERNEL=="i2c-*", TAG+="uaccess"')
    text = '\n'.join(lines) + '\n'
    if args.print_only:
        print(text, end='')
        return
    if os.geteuid() != 0:
        parser.error('Usa sudo python3 tools/install_permissions.py; --print no requiere root')
    dest = Path('/etc/udev/rules.d/60-rgb-unificado.rules')
    backup = Path('/var/lib/rgb-unificado/backup') / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup.mkdir(parents=True, mode=0o700)
    shutil.copytree('/etc/udev/rules.d', backup / 'udev-before', dirs_exist_ok=True)
    # Back up before adding permissions. Existing rules are never edited or removed.
    dest.write_text(text)
    dest.chmod(0o644)
    subprocess.run(['udevadm', 'control', '--reload-rules'], check=True)
    for subsystem in ('usb', 'hidraw', 'i2c-dev'):
        subprocess.run(['udevadm', 'trigger', '--action=change', '--subsystem-match=' + subsystem], check=True)
    subprocess.run(['udevadm', 'settle'], check=True)
    print('Reglas instaladas:', dest)
    print('Respaldo de reglas anteriores:', backup)


if __name__ == '__main__':
    main()
