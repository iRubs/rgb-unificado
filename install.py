#!/usr/bin/env python3
"""Install/upgrade for the current Linux user. Never runs sudo or downloads code."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

SOURCE = Path(__file__).resolve().parent


def desktop_quote(value):
    # Desktop Entry Exec is not a shell command. Escape its own reserved characters.
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'


def stop_watcher(base):
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            args = (proc / 'cmdline').read_bytes().split(b'\0')
            if str(base / 'rgb-control.py').encode() in args and b'--watch' in args:
                os.kill(int(proc.name), signal.SIGTERM)
        except (OSError, ValueError):
            pass


def main():
    parser = argparse.ArgumentParser(description='Instala RGB unificado para tu usuario, sin privilegios root')
    parser.add_argument('--data-dir', type=Path, default=Path.home() / '.local/share/rgb-unificado')
    parser.add_argument('--no-autostart', action='store_true')
    parser.add_argument('--start', action='store_true', help='Inicia el monitor al terminar (aplica preferencias guardadas)')
    args = parser.parse_args()
    if sys.platform != 'linux' or sys.version_info < (3, 10):
        parser.error('Requiere Linux y Python 3.10 o posterior')
    if os.geteuid() == 0:
        parser.error('Ejecuta este instalador como usuario normal, sin sudo')
    base = args.data_dir.expanduser().resolve()
    if base == SOURCE:
        parser.error('La carpeta de instalación debe ser distinta del repositorio')
    base.mkdir(parents=True, exist_ok=True)
    control_lock = (base / 'control.lock').open('w')
    try:
        fcntl.flock(control_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error('RGB unificado está aplicando ajustes o tiene un diálogo abierto. Ciérralo e intenta de nuevo.')
    backup = base / 'backups' / time.strftime('%Y%m%d-%H%M%S')
    backup.mkdir(parents=True, exist_ok=True)
    for name in ('rgb-control.py', 'rgb_unificado', 'data', 'settings.json', 'profile-template.json'):
        source = base / name
        if source.is_dir():
            shutil.copytree(source, backup / name, dirs_exist_ok=True)
        elif source.exists():
            shutil.copy2(source, backup / name)
    stop_watcher(base)
    for name in ('rgb_unificado', 'data'):
        shutil.copytree(SOURCE / name, base / name, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(SOURCE / 'rgb-control.py', base / 'rgb-control.py')
    shutil.copy2(SOURCE / 'README.md', base / 'README.md')
    # Migration only reads local settings; it never accesses USB/I2C.
    sys.path.insert(0, str(SOURCE))
    from rgb_unificado.core import atomic_json, read_state
    atomic_json(base / 'settings.json', read_state(base))
    appdir = Path.home() / '.local/share/applications'
    autodir = Path.home() / '.config/autostart'
    appdir.mkdir(parents=True, exist_ok=True)
    autodir.mkdir(parents=True, exist_ok=True)
    command = desktop_quote(sys.executable) + ' ' + desktop_quote(base / 'rgb-control.py')
    # A custom data directory must also be passed to the launched app.
    command = 'env ' + desktop_quote('RGB_UNIFICADO_HOME=' + str(base)) + ' ' + command
    icon = base / 'openrgb/usr/share/icons/hicolor/128x128/apps/org.openrgb.OpenRGB.png'
    icon_value = str(icon) if icon.exists() else 'preferences-desktop-color'
    for path in (appdir / 'rgb-unificado.desktop', autodir / 'rgb-unificado.desktop'):
        if path.exists():
            shutil.copy2(path, backup / (path.parent.name + '.desktop'))
    (appdir / 'rgb-unificado.desktop').write_text(
        '[Desktop Entry]\nType=Application\nName=RGB unificado\n'
        'Comment=Detectar RGB compatible, unificar color y conservar apagados\n'
        f'Exec={command}\nIcon={icon_value}\nTerminal=false\nCategories=Settings;HardwareSettings;\n'
        'Actions=Off;\n\n[Desktop Action Off]\nName=Elegir luces que mantener apagadas\n'
        f'Exec={command} --off-menu\n')
    if not args.no_autostart:
        (autodir / 'rgb-unificado.desktop').write_text(
            '[Desktop Entry]\nType=Application\nName=RGB unificado\n'
            f'Exec={command} --watch\nTerminal=false\nX-KDE-autostart-after=panel\n')
    if shutil.which('update-desktop-database'):
        subprocess.run(['update-desktop-database', str(appdir)], check=True)
    fcntl.flock(control_lock, fcntl.LOCK_UN)
    control_lock.close()
    if args.start:
        environment = dict(os.environ, RGB_UNIFICADO_HOME=str(base))
        with (base / 'watch-launch.log').open('a') as log:
            subprocess.Popen([sys.executable, str(base / 'rgb-control.py'), '--watch'],
                             env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    print('Instalado en:', base)
    print('Respaldo previo:', backup)
    print('Abre «RGB unificado» en el menú de aplicaciones.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
