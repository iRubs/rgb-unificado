"""Linux CLI and KDE dialog frontend; OpenRGB remains the hardware driver."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from .core import (atomic_json, build_profile, capabilities, color_value, controller_ids,
                   identity, matched_detectors, read_state, sysfs_inventory)
from .keyboard import Keyboard

ROOT = Path(__file__).resolve().parent.parent
BASE = Path(os.environ.get('RGB_UNIFICADO_HOME', Path.home() / '.local/share/rgb-unificado'))
KEYBOARD_KEY = 'redragon-k686rgb-m'


def dialog(*args):
    result = subprocess.run(['kdialog', '--title', 'RGB unificado', *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def executable():
    configured = os.environ.get('OPENRGB_BIN')
    local = BASE / 'openrgb/usr/bin/openrgb'
    result = configured or (str(local) if local.exists() else shutil.which('openrgb'))
    if not result:
        raise RuntimeError('Instala OpenRGB 1.1 o define OPENRGB_BIN con su ruta.')
    return result


def run_openrgb(*args):
    result = subprocess.run([executable(), '--config', str(BASE / 'config'), '--noautoconnect', *args],
                            capture_output=True, text=True, timeout=45)
    with (BASE / 'openrgb.log').open('a') as handle:
        handle.write(result.stdout + result.stderr)
    if result.returncode or re.search(r'(?m)^Error:', result.stdout + result.stderr):
        raise RuntimeError('OpenRGB falló; revisa openrgb.log en la carpeta de datos.')
    return result


def prepare_detection(state):
    catalog = json.loads((ROOT / 'data/openrgb-1.1.json').read_text())
    result = subprocess.run([executable(), '--version'], capture_output=True, text=True, timeout=10)
    version = re.search(r'OpenRGB\s+(\d+(?:\.\d+)+)', result.stdout + result.stderr)
    if result.returncode or not version or version[1] != catalog['openrgb_version']:
        raise RuntimeError('El catálogo fue revisado para OpenRGB ' + catalog['openrgb_version'] +
                           '. Actualiza el catálogo antes de usar otra versión; no se sondeó hardware.')
    inventory = sysfs_inventory()
    allowed = (matched_detectors(catalog, inventory) | set(state.get('enabled_detectors', []))) - set(state.get('disabled_detectors', []))
    unknown = allowed - set(catalog['all_detectors'])
    if unknown:
        raise ValueError('Detector no incluido en el catálogo revisado: ' + ', '.join(sorted(unknown)))
    path = BASE / 'config/OpenRGB.json'
    config = json.loads(path.read_text()) if path.exists() else {}
    config['Detectors'] = {'hid_safe_mode': False, 'detectors': {name: name in allowed for name in catalog['all_detectors']}}
    config['Server'] = {'default_host': '127.0.0.1', 'default_port': 6742, 'all_controllers': False}
    atomic_json(path, config)
    return inventory, allowed


def keyboard_present():
    for path in Path('/sys/bus/usb/devices').glob('*'):
        try:
            if (path / 'idVendor').read_text().strip() == '2e3c' and (path / 'idProduct').read_text().strip() == 'c365' and (path / 'product').read_text().strip() == 'K686RGB-M':
                return True
        except OSError:
            pass
    return False


def scan(state):
    inventory, detectors = prepare_detection(state)
    snapshot_path = BASE / 'config/profiles/Deteccion.json'
    snapshot_path.unlink(missing_ok=True)
    run_openrgb('--save-profile', 'Deteccion')
    snapshot = json.loads(snapshot_path.read_text())
    if not isinstance(snapshot.get('controllers'), list):
        raise ValueError('Respuesta de OpenRGB sin lista de controladores')
    for entry in state['devices'].values():
        entry['present'] = False
    for controller, (key, ambiguous) in zip(snapshot['controllers'], controller_ids(snapshot['controllers'])):
        entry = state['devices'].setdefault(key, {'off': state['new_devices_off']})
        caps = capabilities(controller)
        entry.update(label=controller['name'], present=True, ambiguous=ambiguous,
                     backend='openrgb', color=caps['color'], controllable=caps['off'] and not ambiguous)
    if keyboard_present():
        entry = state['devices'].setdefault(KEYBOARD_KEY, {'off': state['new_devices_off']})
        entry.update(label='Redragon K686RGB-M (firmware verificado)', present=True,
                     ambiguous=False, backend='redragon', color=True, controllable=True)
    atomic_json(BASE / 'settings.json', state)
    atomic_json(BASE / 'inventory.json', {'hardware': inventory, 'enabled_detectors': sorted(detectors),
                                        'devices': state['devices'], 'scanned_at': time.strftime('%Y-%m-%d %H:%M:%S%z')})
    return snapshot


def apply(state, snapshot):
    profile, warnings = build_profile(snapshot, state)
    atomic_json(BASE / 'config/profiles/Unificado.json', profile)
    errors = []
    if profile['controllers']:
        try:
            actual_path = BASE / 'config/profiles/Ultima-aplicacion.json'
            actual_path.unlink(missing_ok=True)
            run_openrgb('--profile', 'Unificado', '--save-profile', 'Ultima-aplicacion')
            actual = json.loads(actual_path.read_text())
            by_id = {identity(c): c for c in actual['controllers']}
            for wanted in profile['controllers']:
                got = by_id.get(identity(wanted))
                if (got is None or got['colors'] != wanted['colors'] or
                        got['modes'][got['active_mode']]['name'] != wanted['modes'][wanted['active_mode']]['name']):
                    errors.append(wanted['name'] + ': aplicación no confirmada')
        except Exception as exc:
            errors.append(str(exc))
    keyboard_entry = state['devices'].get(KEYBOARD_KEY, {})
    if keyboard_entry.get('present'):
        keyboard = None
        try:
            keyboard = Keyboard(BASE)
            keyboard.apply(state['color'], keyboard_entry['off'])
        except Exception as exc:
            errors.append('Redragon: ' + str(exc))
        finally:
            if keyboard:
                keyboard.close()
    atomic_json(BASE / 'last-application.json', {'color': state['color'],
                'off': [key for key, entry in state['devices'].items() if entry['off']],
                'warnings': warnings, 'errors': errors, 'applied_at': time.strftime('%Y-%m-%d %H:%M:%S%z')})
    for warning in warnings:
        print('Aviso:', warning)
    if errors:
        raise RuntimeError('Preferencias guardadas; aplicación incompleta:\n' + '\n'.join(errors))
    print('Color #' + state['color'] + '; apagados guardados: ' + str(sum(e['off'] for e in state['devices'].values())))


def off_menu(state):
    selectable = [(k, e) for k, e in state['devices'].items() if e.get('controllable') or not e.get('present')]
    if not selectable:
        dialog('--msgbox', 'No se detectaron dispositivos RGB controlables. Consulta Inventario y revisa los permisos.')
        return None
    args = ['--separate-output', '--ok-label', 'Guardar y aplicar', '--checklist',
            'Marca las luces que deben permanecer apagadas. Desmarca para recuperar el color.\n'
            'Los ausentes conservan su orden. Los headers agrupan sus ventiladores y tiras.']
    for key, entry in sorted(selectable, key=lambda pair: (pair[1]['label'], pair[0])):
        suffix = '' if entry.get('present') else ' [desconectado]'
        args += [key, entry['label'] + ' [' + key[-6:] + ']' + suffix, 'on' if entry['off'] else 'off']
    answer = dialog(*args)
    if answer is None:
        return None
    selected = set(answer.splitlines())
    if not selected <= {key for key, _ in selectable}:
        raise ValueError('Selección desconocida')
    return {key: key in selected for key, _ in selectable}


def show_inventory(state):
    lines = ['DISPOSITIVOS RGB', '']
    for key, entry in state['devices'].items():
        status = 'presente' if entry.get('present') else 'desconectado'
        if not entry.get('controllable') and entry.get('present'):
            status += '; no controlable o identidad ambigua'
        lines += [entry['label'], '  ' + key + ' — ' + status + (' — APAGADO' if entry['off'] else '')]
    lines += ['', 'USB/PCI ENUMERADOS (su presencia no confirma que tengan RGB)', '']
    for row in json.loads((BASE / 'inventory.json').read_text())['hardware']:
        lines.append(row['kind'] + ' ' + ':'.join(row['ids']) + ' ' + row['name'])
    lines += ['', 'Sin control RGB detectado: puede faltar soporte, permiso o conexión de datos.',
              'No se inventan comandos para hardware desconocido. Consulta README y docs/COMPATIBILIDAD.md.']
    path = BASE / 'inventory-view.txt'
    path.write_text('\n'.join(lines))
    dialog('--textbox', str(path), '900', '650')


def hardware_signature():
    signature = [(item['kind'], tuple(item['ids']), item['port']) for item in sysfs_inventory()]
    for node in Path('/sys/class/hidraw').glob('*'):
        try:
            signature.append(('hid', str(node.resolve()), node.resolve().stat().st_ino,
                              os.access('/dev/' + node.name, os.R_OK | os.W_OK)))
        except OSError:
            pass
    signature += [('i2c', n.name, os.access(n, os.R_OK | os.W_OK)) for n in Path('/dev').glob('i2c-*')]
    return repr(signature)


def watch():
    with (BASE / 'watch.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        previous, offset, remaining, due = None, time.time() - time.monotonic(), 0, 0
        with (BASE / 'watch.log').open('a', buffering=1) as log:
            while True:
                current, new_offset = hardware_signature(), time.time() - time.monotonic()
                if current != previous or abs(new_offset - offset) > 5:
                    remaining, due = 3, time.monotonic() + (0 if previous is None else 2)
                previous, offset = current, new_offset
                if remaining and time.monotonic() >= due:
                    try:
                        result = subprocess.run([sys.executable, str(ROOT / 'rgb-control.py'), '--apply'],
                                                stdout=log, stderr=log, timeout=120)
                        remaining = remaining - 1 if result.returncode else 0
                    except subprocess.TimeoutExpired:
                        print('Tiempo de aplicación agotado', file=log)
                        remaining -= 1
                    due = time.monotonic() + 15
                time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description='RGB unificado: descubrimiento compatible y apagados persistentes')
    parser.add_argument('--color')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--scan', action='store_true', help='Descubre y guarda inventario; no aplica un perfil de color')
    parser.add_argument('--status', action='store_true', help='Preferencias locales; no accede al hardware')
    parser.add_argument('--off-menu', action='store_true')
    parser.add_argument('--off', nargs='*', help='Lista completa de IDs que mantener apagados; vacía reactiva todos')
    parser.add_argument('--new-devices', choices=['off', 'color'], help='Comportamiento de nuevos componentes')
    parser.add_argument('--enable-detector', action='append', default=[], help='Opt-in de un detector OpenRGB revisado, por ejemplo RAM')
    parser.add_argument('--disable-detector', action='append', default=[])
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    BASE.mkdir(parents=True, exist_ok=True)
    if args.watch:
        return watch()
    if args.color:
        args.color = color_value(args.color)
    if args.status:
        print(json.dumps(read_state(BASE), indent=2, ensure_ascii=False))
        return 0
    interactive = args.off_menu or len(sys.argv) == 1
    action = 'off' if args.off_menu else None
    if len(sys.argv) == 1:
        action = dialog('--menu', 'Control RGB y preferencias persistentes',
                        'color', 'Cambiar color (respeta apagados)', 'off', 'Elegir luces que mantener apagadas',
                        'inventory', 'Detectar componentes y ver inventario',
                        'defaults', 'Elegir qué hacer con componentes nuevos', 'apply', 'Reaplicar configuración')
        if action is None:
            return 0
    with (BASE / 'control.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Hay una aplicación en curso. Inténtalo de nuevo en unos segundos.')
        state = read_state(BASE)
        if args.enable_detector or args.disable_detector:
            state['enabled_detectors'] = sorted((set(state.get('enabled_detectors', [])) | set(args.enable_detector)) - set(args.disable_detector))
            state['disabled_detectors'] = sorted((set(state.get('disabled_detectors', [])) | set(args.disable_detector)) - set(args.enable_detector))
        if args.new_devices:
            state['new_devices_off'] = args.new_devices == 'off'
        snapshot = scan(state)
        if action == 'inventory' or args.scan:
            if interactive:
                show_inventory(state)
            else:
                print(json.dumps(state['devices'], indent=2, ensure_ascii=False))
            return 0
        if action == 'defaults':
            answer = dialog('--default', 'off' if state['new_devices_off'] else 'color', '--menu',
                            'Cuando aparezca un dispositivo compatible nuevo:',
                            'off', 'Mantener su RGB apagado', 'color', 'Aplicar el color guardado')
            if answer is None:
                return 0
            state['new_devices_off'] = answer == 'off'
        if action == 'off':
            updates = off_menu(state)
            if updates is None:
                return 0
            for key, value in updates.items():
                state['devices'][key]['off'] = value
        if args.off is not None:
            unknown = set(args.off) - set(state['devices'])
            if unknown:
                raise ValueError('IDs desconocidos: ' + ', '.join(sorted(unknown)))
            for key, entry in state['devices'].items():
                entry['off'] = key in args.off
        if action == 'color':
            value = dialog('--default', '#' + state['color'], '--getcolor')
            if value is None:
                return 0
            args.color = color_value(value)
        if args.color:
            state['color'] = args.color
        atomic_json(BASE / 'settings.json', state)
        apply(state, snapshot)
        if interactive:
            dialog('--passivepopup', 'Preferencias guardadas y aplicadas.', '5')
    return 0


def entrypoint():
    try:
        return main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        if len(sys.argv) == 1 or '--off-menu' in sys.argv:
            dialog('--error', str(exc))
        return 1
