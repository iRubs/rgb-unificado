import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('build_catalog', ROOT / 'tools/build_catalog.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class CatalogTests(unittest.TestCase):
    def test_disabled_wildcards_and_comments_are_not_auto_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            (source / 'detector.cpp').write_text('''
                #define VENDOR 0x1111
                #define PRODUCT 0x2222
                // REGISTER_HID_DETECTOR("Commented", fn, VENDOR, PRODUCT);
                REGISTER_HID_DETECTOR("Supported", fn, VENDOR, PRODUCT);
                REGISTER_HID_DETECTOR_DISABLED("Experimental", fn, VENDOR, PRODUCT);
                REGISTER_HID_DETECTOR("Wildcard", fn, VENDOR, 0);
                REGISTER_HID_DETECTOR("Unknown", fn, VENDOR, UNRESOLVED);
            ''')
            with patch.object(builder.subprocess, 'check_output', return_value='testcommit\n'):
                result = builder.build(source)
            self.assertEqual([r['detector'] for r in result['matches']], ['Supported'])
            self.assertNotIn('Commented', result['all_detectors'])
            self.assertIn('Experimental', result['all_detectors'])

    def test_published_catalog_contains_no_wildcards(self):
        catalog = json.loads((ROOT / 'data/openrgb-1.1.json').read_text())
        for row in catalog['matches']:
            self.assertEqual(len(row['ids']), 2 if row['kind'] == 'usb' else 4)
            self.assertTrue(all(int(value, 16) > 0 for value in row['ids']))
            self.assertIn(row['detector'], catalog['all_detectors'])


if __name__ == '__main__':
    unittest.main()
