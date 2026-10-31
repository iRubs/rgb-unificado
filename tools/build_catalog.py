#!/usr/bin/env python3
"""Extract exact, default-enabled USB/PCI registrations; never execute C++ code."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def build(source, registered=None):
    texts = {}
    definitions = {}
    for path in sorted(source.rglob('*')):
        if path.suffix not in ('.cpp', '.h'):
            continue
        text = re.sub(r'/\*.*?\*/|//[^\n]*', '', path.read_text(errors='replace'), flags=re.S)
        texts[path] = text
        for key, value in re.findall(r'^\s*#define\s+(\w+)\s+([^\n]+)', text, re.M):
            definitions.setdefault(key, set()).add(value.strip())

    def resolve(value, local, visited=()):
        value = value.strip()
        if re.fullmatch(r'0[xX][0-9a-fA-F]+|[0-9]+', value):
            return int(value, 0)
        if value.startswith('"') and value.endswith('"'):
            return json.loads(value)
        if value in visited:
            return None
        candidates = {local[value]} if value in local else definitions.get(value, set())
        if len(candidates) != 1:
            return None
        return resolve(next(iter(candidates)), local, (*visited, value))

    records, names = [], set()
    for path, text in texts.items():
        local = dict(re.findall(r'^\s*#define\s+(\w+)\s+([^\n]+)', text, re.M))
        for macro, body in re.findall(r'\b(REGISTER_(?:HID|I2C|USB|DETECTOR)[A-Z_]*?)\s*\(([^;]*?)\)\s*;', text, re.S):
            fields = [s.strip() for s in re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', body)]
            if len(fields) < 2:
                continue
            name = resolve(fields[0], local)
            if not isinstance(name, str):
                continue
            names.add(name)
            if 'DISABLED' in macro:
                continue
            kind, ids = None, []
            if macro.startswith('REGISTER_HID_DETECTOR') and len(fields) >= 4 and not any(t in macro for t in ('_ONLY', '_B')):
                kind, ids = 'usb', fields[2:4]
            elif macro == 'REGISTER_I2C_PCI_DETECTOR' and len(fields) == 7:
                kind, ids = 'pci', fields[2:6]
            if kind is None:
                continue
            values = [resolve(s, local) for s in ids]
            if any(not isinstance(v, int) or v <= 0 or v > 65535 for v in values):
                continue
            records.append({'kind': kind, 'ids': [f'{n:04x}' for n in values], 'detector': name})
    if registered:
        names.update(json.loads(registered.read_text())['Detectors']['detectors'])
    commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    return {'openrgb_version': '1.1', 'source_commit': commit,
            'source_url': 'https://github.com/CalcProgrammer1/OpenRGB/tree/release_1.1',
            'all_detectors': sorted(names), 'matches': sorted(records, key=lambda r: (r['kind'], r['ids'], r['detector']))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--registered-settings', type=Path)
    args = parser.parse_args()
    catalog = build(args.source, args.registered_settings)
    args.output.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n')
    print(len(catalog['matches']), 'exact registrations;', len(catalog['all_detectors']), 'detector names')
