"""Guarded lighting-only backend for the verified Redragon K686RGB-M firmware."""
import json
import os
from pathlib import Path
import select
import time
IDENTITY = b'W669,34,KB,FR,7431UKHEXYXBJCARGB,V3.18.01'

class Keyboard:
    def __init__(self, base):
        self.base = Path(base)
        self.fd = None
        for entry in Path('/sys/class/hidraw').glob('hidraw*'):
            dev = entry / 'device'
            info = (dev / 'uevent').read_text()
            if ('HID_ID=0003:00002E3C:0000C365' in info and
                    'HID_NAME=K686RGB-M\n' in info and
                    (dev / 'report_descriptor').read_bytes().startswith(bytes.fromhex('061bff0991'))):
                self.fd = os.open('/dev/' + entry.name, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
                break
        if self.fd is None:
            raise RuntimeError('K686RGB-M no disponible; revisa conexión y permisos USB.')

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def send(self, command, sub=0, body=b''):
        if (command, sub) not in {(13, 0), (10, 0), (7, 1), (7, 0)}:
            raise ValueError('Comando bloqueado')
        if command == 7 and sub == 0:
            if len(body) != 14:
                raise ValueError('Longitud de iluminación inválida')
        elif body:
            raise ValueError('Una consulta no puede contener ajustes')
        frame = bytes([1, command, sub, 0, 0, len(body)]) + body
        frame = frame.ljust(64, b'\0')
        if os.write(self.fd, frame) != 64:
            raise RuntimeError('Escritura USB incompleta')

    def query(self, command, sub=0):
        # This interface only contains vendor responses, never typing input.
        for _ in range(32):
            if not select.select([self.fd], [], [], 0)[0]:
                break
            os.read(self.fd, 4096)
        self.send(command, sub)
        end = time.monotonic() + 1.5
        while time.monotonic() < end:
            if select.select([self.fd], [], [], max(0, end - time.monotonic()))[0]:
                reply = os.read(self.fd, 4096)
                if len(reply) >= 6 and reply[0:2] == bytes([1, command]):
                    if reply[3:5] == b'\0\0':
                        return reply
        raise RuntimeError('El teclado no respondió a la consulta')

    def apply(self, color, off=False):
        ident = self.query(13)
        if ident[6:].split(b'\0', 1)[0] != IDENTITY:
            raise RuntimeError('Modelo o firmware distinto: iluminación bloqueada por seguridad')
        modes = self.query(10)
        mode_data = modes[6:6 + modes[5]]
        if b'\xa5\x5a' not in mode_data or 0 not in mode_data.split(b'\xa5\x5a')[0]:
            raise RuntimeError('El teclado no anuncia el modo estático esperado')
        current = self.query(7, 1)
        if current[5] != 12:
            raise RuntimeError('Formato de iluminación desconocido')
        old = current[6:18]
        if old[0] > 16 or old[1] > 4 or old[2] > 4 or old[9] > 7 or old[10] > 1 or old[11] > 1:
            raise RuntimeError('Ajustes fuera del protocolo documentado')
        backup = self.base / 'keyboard-before.json'
        if not backup.exists():
            backup.write_text(json.dumps({'identity': IDENTITY.decode(), 'lighting_hex': old.hex()}, indent=2))
        desired = bytearray(old)
        desired[0] = 0  # static
        brightness_file = self.base / 'keyboard-on-brightness.txt'
        if old[1] > 0:
            brightness_file.write_text(str(old[1]))
        brightness = int(brightness_file.read_text()) if brightness_file.exists() else 1
        if not 1 <= brightness <= 4:
            raise ValueError('Brillo guardado del teclado inválido')
        desired[1] = 0 if off else brightness
        desired[3:6] = bytes(3) if off else bytes.fromhex(color)
        desired[6:9] = bytes(3) if off else bytes.fromhex(color)
        desired[10] = 0  # rainbow disabled
        self.send(7, 0, bytes(desired) + b'\0\0')
        time.sleep(0.12)
        actual = self.query(7, 1)
        if actual[5] != 12 or actual[6:18] != bytes(desired):
            self.send(7, 0, old + b'\0\0')
            time.sleep(0.12)
            restored = self.query(7, 1)
            if restored[6:18] != old:
                raise RuntimeError('Falló la verificación y no se pudo verificar la restauración')
            raise RuntimeError('Falló la verificación; se restauró el ajuste anterior del teclado')
        (self.base / 'keyboard-last-verified.json').write_text(json.dumps({
            'identity': IDENTITY.decode(), 'lighting_hex': actual[6:18].hex(),
            'color': '000000' if off else color, 'off': off,
            'verified_at': time.strftime('%Y-%m-%d %H:%M:%S%z')}, indent=2))
