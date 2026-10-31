# Desarrollo y ampliación

El código usa únicamente la biblioteca estándar de Python. KDialog se ejecuta como proceso para la interfaz; OpenRGB es el controlador de hardware externo. No requiere un SDK expuesto por red.

- `rgb_unificado/core.py`: identidad, migración, política de nuevos componentes y generación de perfiles.
- `rgb_unificado/app.py`: detección actual, CLI, diálogos, aplicación y monitor.
- `rgb_unificado/keyboard.py`: adaptador restringido del K686RGB-M.
- `data/openrgb-1.1.json`: metadatos de registros exactos y nombres de detectores; no contiene perfiles de usuario.
- `install.py`: instalación por usuario, respaldos y acceso de escritorio.
- `tools/install_permissions.py`: reglas udev opcionales, sin drivers ni servicios.
- `tools/build_catalog.py`: extracción conservadora de registros C++, sin ejecutarlos.

## Regenerar el catálogo revisado

```bash
git clone --depth 1 --branch release_1.1 https://github.com/CalcProgrammer1/OpenRGB.git /ruta/OpenRGB
python3 tools/build_catalog.py /ruta/OpenRGB /tmp/catalogo.json
```

Revisa el diff antes de reemplazar `data/openrgb-1.1.json`. El generador omite macros, registros y expresiones que no puede resolver con seguridad. Para incluir nombres registrados dinámicamente puedes proporcionar `--registered-settings /ruta/OpenRGB.json`: solo importa las claves de nombres de detectores, nunca sus valores ni otras preferencias. No debe usarse para publicar ese archivo de configuración.

El catálogo publicado se complementó con los nombres registrados por OpenRGB 1.1 para que todos quedaran explícitamente habilitados o deshabilitados. Al revisar otra versión, compara esos nombres con los del binario. La aplicación rechaza versiones distintas a la declarada en el catálogo antes de detectar dispositivos.

## Añadir un backend

Añade una implementación explícita y pruebas para el modelo y firmware. Evita cargar plugins arbitrarios desde la carpeta actual o descargar código durante el control. Los backends deben identificar el dispositivo, limitar los comandos a iluminación y verificar el resultado cuando el protocolo lo permita. Nunca incluyas comandos de firmware/calibración o direcciones inventadas como alternativa a un fallo de soporte.

## Validación

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q rgb_unificado install.py tools rgb-control.py
python3 tools/install_permissions.py --print > /tmp/rgb-unificado.rules
```

Las pruebas no abren hardware. Para probar en un equipo, usa primero un directorio de datos separado con `RGB_UNIFICADO_HOME`, copia solo las preferencias necesarias, ejecuta `--scan`, revisa el inventario y después `--apply`. No publiques perfiles, logs ni IDs privados.
