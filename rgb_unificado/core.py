"""Device discovery, stable preferences and conservative profile generation."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(filename, path)
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def color_value(value):
    value = value.removeprefix('#').upper()
    if not re.fullmatch('[A-F0-9]{6}', value):
        raise ValueError('El color necesita seis dígitos RGB: por ejemplo 0080FF')
    return value


def identity(controller):
    """Same matching principles as OpenRGB: HID path is volatile; I2C address is not."""
    serial = controller.get('serial', '').strip()
    if serial.lower() in ('', 'unknown', 'n/a', 'none', '0'):
        serial = ''
    location = controller.get('location', '')
    address = re.search(r'address (0x[0-9a-f]+)', location, re.I)
    if address:
        location = address[1].lower()
    elif location.startswith('HID:'):
        location = ''
    basis = [controller.get(k, '') for k in ('vendor', 'name', 'description', 'type')]
    basis += [serial, location]
    return 'orgb-' + hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()[:20]


def controller_ids(controllers):
    ids = [identity(c) for c in controllers]
    duplicates = {key for key in ids if ids.count(key) > 1}
    # Identical devices without a serial cannot be safely remembered individually.
    return [(key, key in duplicates) for key in ids]


def mode_index(controller, names):
    for name in names:
        for index, mode in enumerate(controller.get('modes', [])):
            if mode.get('name', '').casefold() == name.casefold():
                return index
    return None


def capabilities(controller):
    on = mode_index(controller, ('Static', 'Direct', 'Fixed', 'Solid'))
    off = mode_index(controller, ('Off',))
    return {'color': on is not None and bool(controller.get('colors')),
            'off': off is not None or (on is not None and bool(controller.get('colors'))),
            'mode_on': on, 'mode_off': off}


def build_profile(snapshot, state):
    profile = copy.deepcopy(snapshot)
    profile['profile_name'] = 'Unificado'
    profile['controllers'] = []
    warnings = []
    value = int.from_bytes(bytes.fromhex(color_value(state['color'])), 'little')
    for controller, (key, ambiguous) in zip(snapshot['controllers'], controller_ids(snapshot['controllers'])):
        capability = capabilities(controller)
        entry = state['devices'].get(key, {})
        off = entry.get('off', state['new_devices_off'])
        if ambiguous:
            warnings.append(controller['name'] + ': identidad duplicada sin serie; no se modificó')
            continue
        index = capability['mode_off'] if off and capability['mode_off'] is not None else capability['mode_on']
        if index is None or (not off and not capability['color']):
            warnings.append(controller['name'] + ': sin modo estático/apagado compatible')
            continue
        item = copy.deepcopy(controller)
        item['active_mode'] = index
        item['colors'] = [0 if off else value] * len(item.get('colors', []))
        mode = item['modes'][index]
        if 'colors' in mode:
            mode['colors'] = [0 if off else value] * len(mode['colors'])
        # Enable brightness when reactivating only if this mode exposes brightness.
        if mode.get('brightness_max', 0) > mode.get('brightness_min', 0):
            mode['brightness'] = mode['brightness_min'] if off else mode['brightness_max']
        profile['controllers'].append(item)
    return profile, warnings


def migrate(old, legacy_profile):
    state = {'version': 2, 'color': color_value(old.get('color', '0080FF')), 'devices': {},
             'new_devices_off': bool(old.get('off')),
             'enabled_detectors': ['Corsair DRAM'] if legacy_profile else []}
    for controller in (legacy_profile or {}).get('controllers', []):
        name, location = controller['name'], controller.get('location', '')
        alias = {'ASRock B860M-H2': 'motherboard', 'G502 HERO Gaming Mouse': 'mouse'}.get(name)
        if name == 'Corsair Vengeance RGB DDR5':
            address = re.search(r'address 0x(18|1a)', location, re.I)
            alias = 'ram' + address[1].lower() if address else None
        state['devices'][identity(controller)] = {'label': name, 'off': alias in old.get('off', []), 'present': False}
    if legacy_profile:
        state['devices']['redragon-k686rgb-m'] = {'label': 'Redragon K686RGB-M', 'off': 'keyboard' in old.get('off', []), 'present': False}
    return state


def read_state(base):
    path = base / 'settings.json'
    old = json.loads(path.read_text()) if path.exists() else {}
    if old.get('version', 1) == 1:
        template = base / 'profile-template.json'
        state = migrate(old, json.loads(template.read_text()) if template.exists() else None)
    elif old.get('version') == 2:
        state = old
    else:
        raise ValueError('Versión de configuración desconocida; no se sobrescribió')
    state['color'] = color_value(state['color'])
    if not isinstance(state['devices'], dict) or not isinstance(state['new_devices_off'], bool):
        raise ValueError('Configuración inválida')
    for entry in state['devices'].values():
        if not isinstance(entry.get('off'), bool):
            raise ValueError('Preferencia de apagado inválida')
    return state


def sysfs_inventory(root=Path('/sys')):
    rows = []
    for dev in sorted((root / 'bus/usb/devices').glob('*')):
        try:
            vid, pid = (dev / 'idVendor').read_text().strip(), (dev / 'idProduct').read_text().strip()
            product = (dev / 'product').read_text().strip() if (dev / 'product').exists() else 'USB ' + vid + ':' + pid
            rows.append({'kind': 'usb', 'ids': [vid, pid], 'name': product, 'port': dev.name})
        except OSError:
            pass
    for dev in sorted((root / 'bus/pci/devices').glob('*')):
        try:
            ids = [(dev / field).read_text().strip().removeprefix('0x') for field in ('vendor', 'device', 'subsystem_vendor', 'subsystem_device')]
            rows.append({'kind': 'pci', 'ids': ids, 'name': 'PCI ' + ':'.join(ids[:2]), 'port': dev.name})
        except OSError:
            pass
    return rows


def matched_detectors(catalog, inventory):
    attached = {(d['kind'], tuple(d['ids'])) for d in inventory}
    return {r['detector'] for r in catalog['matches'] if (r['kind'], tuple(r['ids'])) in attached}
