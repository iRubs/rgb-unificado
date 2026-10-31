# RGB unificado

Un color estático para los dispositivos RGB compatibles de tu PC, con apagado selectivo persistente. Para **Linux**, con interfaz de escritorio mediante KDialog y controladores de hardware de **OpenRGB 1.1**.

## Qué hace

- Descubre los controladores que devuelve OpenRGB en cada escaneo; no depende de una plantilla fija de placa, RAM o mouse.
- Compara los USB y PCI conectados con un catálogo de registros exactos de OpenRGB 1.1. Solo habilita coincidencias revisadas y detectores optativos que hayas activado explícitamente.
- Añade automáticamente los dispositivos compatibles nuevos a la lista. Puedes elegir si deben recibir el color guardado o permanecer apagados.
- Conserva la orden individual de apagado al cambiar color, desconectar el dispositivo, reiniciar sesión o reanudar el equipo.
- Distingue módulos RAM por dirección y dispositivos con serie por identidad. Si dos dispositivos idénticos no ofrecen una identidad distinguible, los informa como ambiguos y no los modifica.
- Reaplica las preferencias tras cambios de USB/HID/PCI/I2C o al reanudar. No envía colores periódicamente mientras el hardware permanece estable.
- Incluye un adaptador de iluminación para el **Redragon K686RGB-M** con comprobación de identidad, formato, firmware y lectura posterior del estado.

**No puede garantizar compatibilidad con cualquier componente futuro.** Depende del soporte de OpenRGB o de un adaptador específico verificado, de los permisos y del cableado. Los ventiladores y tiras conectados a un mismo header se controlan como grupo. Un USB conectado no demuestra que tenga RGB ni que ese RGB acepte comandos.

## Requisitos

- Linux con sesión de escritorio; Python **3.10 o posterior**.
- OpenRGB **1.1**, instalado desde tu distribución o su [sitio oficial](https://openrgb.org/releases.html).
- `kdialog` para el menú gráfico. Los comandos de terminal no lo necesitan.
- Permisos udev para los dispositivos que se van a controlar.

El catálogo incluido corresponde a OpenRGB 1.1. Se rechaza otra versión antes de detectar hardware, para evitar habilitar detectores nuevos no revisados. Esto también significa que una actualización de OpenRGB requiere actualizar primero el catálogo y probar esta herramienta.

## Instalación

### Arch Linux / CachyOS

```bash
sudo pacman -S --needed python openrgb kdialog
git clone https://github.com/iRubs/rgb-unificado.git
cd rgb-unificado
python3 install.py --start
```

### Otras distribuciones Linux

Instala Python 3.10+, KDialog y **OpenRGB 1.1** con el gestor de tu distribución o una descarga oficial. Luego:

```bash
git clone https://github.com/iRubs/rgb-unificado.git
cd rgb-unificado
python3 install.py --start
```

El instalador se ejecuta **sin sudo**, no descarga ni ejecuta instaladores externos y no modifica servicios systemd. Copia el código a `~/.local/share/rgb-unificado`, crea un acceso **RGB unificado** y lo añade al inicio automático del escritorio. Si ya existía la versión anterior, respalda el código y las preferencias y migra los apagados.

Para un disco o carpeta diferente:

```bash
python3 install.py --data-dir /ruta/en/tu/disco/rgb-unificado --start
```

Si usas una versión portable de OpenRGB, define `OPENRGB_BIN` con la ruta de su ejecutable; esa variable debe estar disponible también en el entorno del escritorio. La actualización de una instalación anterior conserva su OpenRGB portable si existe dentro de `openrgb/usr/bin/openrgb`.

### Permisos USB y componentes nuevos

Si tu paquete OpenRGB ya instala reglas udev, úsalas. Si no, revisa e instala las reglas incluidas para los VID/PID exactos del catálogo:

```bash
python3 tools/install_permissions.py --print
sudo python3 tools/install_permissions.py
```

Esto permite que la sesión local activa acceda a las interfaces USB/HID RGB catalogadas, incluidas las que conectes más adelante. No ejecuta operaciones de firmware ni instala drivers y no accede a `/dev/port`. Antes de escribir su archivo respalda las reglas udev en `/var/lib/rgb-unificado/backup/`. No elimina las reglas anteriores.

### RAM y otros dispositivos SMBus/I2C

No se hace un barrido genérico de direcciones. Las coincidencias PCI exactas del catálogo pueden habilitar el controlador RGB de una GPU soportada. Los detectores de RAM requieren una elección explícita y soporte real del controlador.

Si necesitas acceso I2C y todavía no lo tienes:

```bash
sudo python3 tools/install_permissions.py --i2c
```

Esta opción concede acceso a los adaptadores I2C a la sesión activa. No habilita por sí sola ningún detector. **Úsala únicamente cuando hayas comprobado que el controlador de tu hardware está soportado.** No uses comandos I2C de escritura ni ajustes de BIOS para intentar forzar compatibilidad.

Ejemplo para una RAM Corsair compatible con el detector `Corsair DRAM`:

```bash
python3 ~/.local/share/rgb-unificado/rgb-control.py --enable-detector 'Corsair DRAM' --scan
```

Para desactivar un detector, incluso si coincide automáticamente:

```bash
python3 ~/.local/share/rgb-unificado/rgb-control.py --disable-detector 'Nombre exacto del detector' --scan
```

No todos los productos de una marca comparten protocolo. No habilites un detector de otro modelo solo por parecerse.

## Uso gráfico

Abre **RGB unificado** desde el menú de aplicaciones:

1. **Cambiar color:** aplica un color estático a los dispositivos habilitados y respeta los apagados.
2. **Elegir luces que mantener apagadas:** marca los dispositivos que deben permanecer apagados. Para reactivarlos, desmárcalos.
3. **Detectar componentes y ver inventario:** actualiza la lista y muestra los USB/PCI enumerados. Los dispositivos sin soporte, identidad o permisos no se presentan como controlados.
4. **Elegir qué hacer con componentes nuevos:** color guardado o apagado. Este ajuste solo afecta a los dispositivos que aparezcan por primera vez; no cambia tus preferencias anteriores.
5. **Reaplicar configuración:** aplica las preferencias guardadas a los dispositivos presentes.

Los dispositivos ausentes permanecen guardados. Si todos tus dispositivos estaban apagados al migrar, los nuevos se mantienen apagados por defecto; puedes cambiarlo en el menú. En una instalación nueva, el color inicial es azul `#0080FF` y los nuevos siguen ese color.

## Terminal

```bash
APP="$HOME/.local/share/rgb-unificado/rgb-control.py"
python3 "$APP" --scan                     # Descubrimiento e inventario
python3 "$APP" --status                   # Preferencias; no accede a hardware
python3 "$APP" --color FF0000             # Rojo; respeta apagados
python3 "$APP" --off-menu                 # Lista gráfica de apagados
python3 "$APP" --off ID1 ID2              # Reemplaza la lista completa de apagados
python3 "$APP" --off                      # Quita todos los apagados guardados
python3 "$APP" --new-devices off          # Componentes nuevos apagados
python3 "$APP" --new-devices color        # Componentes nuevos con el color común
python3 "$APP" --apply                    # Aplica preferencias guardadas
python3 "$APP" --watch                    # Monitor para inicio/reconexión/reanudación
```

Obtén los IDs reales mediante `--scan` o `--status`; `ID1`/`ID2` son marcadores de ejemplo. `--off` sustituye la lista completa. El apagado se guarda antes de escribir los colores. Si algo falla, se conserva la preferencia, se registra el error y los otros dispositivos se intentan controlar igualmente.

El monitor requiere una sesión iniciada. **No equivale a un ajuste de BIOS:** no garantiza oscuridad durante POST, antes de iniciar sesión ni con Linux apagado. Tampoco bloquea cambios de otro programa RGB. Usa una única herramienta propietaria de cada dispositivo.

## Actualizar y desinstalar

```bash
cd rgb-unificado
git pull --ff-only
python3 install.py --start
```

Cada actualización crea un respaldo en la carpeta de instalación bajo `backups/`. No publica ni elimina tus preferencias.

Para desinstalar, desactiva **RGB unificado** en el Inicio automático de tu escritorio, cierra su proceso `rgb-control.py --watch`, elimina el acceso de `~/.local/share/applications/rgb-unificado.desktop` y mueve la carpeta de instalación a la papelera. Si instalaste las reglas opcionales, puedes retirar únicamente `/etc/udev/rules.d/60-rgb-unificado.rules` y recargar udev. No borres reglas de otros programas. Eliminar archivos no garantiza que un dispositivo olvide el último color almacenado por su controlador.

## Diagnóstico y privacidad

Los archivos `settings.json`, `inventory.json`, `last-application.json`, `openrgb.log` y `watch.log` permanecen en la carpeta local de datos. El inventario detallado de OpenRGB puede contener números de serie: **no subas perfiles ni logs completos sin revisarlos**. Este repositorio incluye solo código, documentación, pruebas y metadatos públicos de OpenRGB, no el inventario de un usuario.

Consulta [Compatibilidad y límites](docs/COMPATIBILIDAD.md), [Desarrollo](docs/DESARROLLO.md) y [Seguridad](SECURITY.md).

## Pruebas

```bash
python3 -m unittest discover -s tests -v
```

Las pruebas simulan altas, cambios de enumeración, RAM reordenada, IDs ambiguos, dispositivos desconectados, migración y prioridad del apagado. No requieren hardware ni privilegios. Las pruebas físicas hechas en un equipo no demuestran compatibilidad universal.

## Licencia y fuentes

GPL-3.0-or-later. OpenRGB es un proyecto independiente y no se redistribuye su ejecutable. Catálogo derivado de sus registros públicos `release_1.1`, con atribución en [NOTICE](NOTICE). El formato de iluminación FF1B se basa en documentación de Omakboard; el adaptador solo admite el modelo y firmware comprobados. Ver [NOTICE](NOTICE) para fuentes y licencias.
