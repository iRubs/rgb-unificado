import copy
import json
from pathlib import Path
import tempfile
import unittest

from rgb_unificado.core import (atomic_json, build_profile, controller_ids, identity,
                               matched_detectors, migrate, read_state)


def device(name='Example mouse', location='HID: /dev/hidraw1', serial=''):
    return {'name': name, 'vendor': 'Example', 'description': 'RGB', 'type': 1,
            'location': location, 'serial': serial, 'active_mode': 1, 'colors': [9, 9],
            'modes': [{'name': 'Off'}, {'name': 'Static', 'colors': [9]}, {'name': 'Breathing'}]}


def state(off=False):
    return {'version': 2, 'color': '0080FF', 'devices': {}, 'new_devices_off': off}


class CoreTests(unittest.TestCase):
    def test_new_device_uses_saved_default(self):
        d = device()
        on, _ = build_profile({'controllers': [d]}, state())
        off, _ = build_profile({'controllers': [d]}, state(True))
        self.assertEqual(on['controllers'][0]['colors'], [0xFF8000] * 2)
        self.assertEqual(off['controllers'][0]['active_mode'], 0)
        self.assertEqual(off['controllers'][0]['colors'], [0, 0])

    def test_off_wins_when_color_changes_and_usb_path_changes(self):
        d = device()
        s = state()
        s['devices'][identity(d)] = {'off': True}
        s['color'] = 'ABCDEF'
        replugged = device(location='HID: /dev/hidraw9')
        result, _ = build_profile({'controllers': [replugged]}, s)
        self.assertEqual(identity(d), identity(replugged))
        self.assertEqual(result['controllers'][0]['colors'], [0, 0])

    def test_ram_identified_by_address_not_bus_number_or_order(self):
        a = device('RAM', 'I2C: bus 2, address 0x18')
        b = device('RAM', 'I2C: bus 2, address 0x1A')
        replugged = device('RAM', 'I2C: bus 6, address 0x18')
        self.assertEqual(identity(a), identity(replugged))
        self.assertNotEqual(identity(a), identity(b))
        s = state()
        s['devices'][identity(a)] = {'off': True}
        output, _ = build_profile({'controllers': [b, replugged]}, s)
        self.assertNotEqual(output['controllers'][0]['colors'], [0, 0])
        self.assertEqual(output['controllers'][1]['colors'], [0, 0])

    def test_indistinguishable_duplicates_are_never_written(self):
        devices = [device(), device(location='HID: /dev/hidraw9')]
        output, warnings = build_profile({'controllers': devices}, state(True))
        self.assertEqual(output['controllers'], [])
        self.assertEqual(len(warnings), 2)

    def test_serial_distinguishes_identical_models(self):
        ids = controller_ids([device(serial='a'), device(serial='b')])
        self.assertNotEqual(ids[0][0], ids[1][0])
        self.assertFalse(any(ambiguous for _, ambiguous in ids))

    def test_animation_only_device_is_reported_and_not_written(self):
        d = device()
        d['modes'] = [{'name': 'Breathing'}]
        output, warnings = build_profile({'controllers': [d]}, state())
        self.assertEqual(output['controllers'], [])
        self.assertTrue(warnings)

    def test_direct_black_fallback_without_off_mode(self):
        d = device()
        d['modes'] = [{'name': 'Direct'}]
        profile, _ = build_profile({'controllers': [d]}, state(True))
        self.assertEqual(profile['controllers'][0]['colors'], [0, 0])

    def test_legacy_migration_preserves_all_off_and_future_policy(self):
        a = device('Corsair Vengeance RGB DDR5', 'I2C: bus 2, address 0x18')
        b = device('Corsair Vengeance RGB DDR5', 'I2C: bus 2, address 0x1A')
        migrated = migrate({'color': '0080FF', 'off': ['ram18', 'keyboard']}, {'controllers': [a, b]})
        self.assertTrue(migrated['devices'][identity(a)]['off'])
        self.assertFalse(migrated['devices'][identity(b)]['off'])
        self.assertTrue(migrated['devices']['redragon-k686rgb-m']['off'])
        self.assertTrue(migrated['new_devices_off'])

    def test_absent_preference_survives_load_and_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            s = state()
            s['devices']['absent'] = {'off': True, 'present': False}
            atomic_json(base / 'settings.json', s)
            loaded = read_state(base)
            build_profile({'controllers': []}, loaded)
            atomic_json(base / 'settings.json', loaded)
            self.assertTrue(read_state(base)['devices']['absent']['off'])

    def test_exact_usb_and_pci_matching_only(self):
        catalog = {'matches': [{'kind': 'usb', 'ids': ['1111', '2222'], 'detector': 'USB'},
                               {'kind': 'pci', 'ids': ['1111', '2222', '3333', '4444'], 'detector': 'GPU'}]}
        inv = [{'kind': 'usb', 'ids': ['1111', '2222']},
               {'kind': 'pci', 'ids': ['1111', '2222', '3333', '9999']}]
        self.assertEqual(matched_detectors(catalog, inv), {'USB'})

    def test_profile_generation_does_not_mutate_inventory(self):
        snapshot = {'controllers': [device()]}
        old = copy.deepcopy(snapshot)
        build_profile(snapshot, state(True))
        self.assertEqual(snapshot, old)

    def test_invalid_state_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / 'settings.json').write_text('{broken')
            with self.assertRaises(json.JSONDecodeError):
                read_state(base)
            self.assertEqual((base / 'settings.json').read_text(), '{broken')


if __name__ == '__main__':
    unittest.main()
