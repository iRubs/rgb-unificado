# Seguridad

El programa no necesita ejecutarse como root. Solo la instalación opcional de reglas udev requiere administración. Los permisos de acceso a HID/I2C deben limitarse a la sesión local de confianza; no concedas acceso remoto para controlar RGB.

No modifica BIOS, firmware, voltajes, velocidades de ventiladores ni calibración de teclas. No utiliza `i2cdetect` para barridos ni herramientas de escritura I2C genéricas. OpenRGB puede comunicarse con los dispositivos mediante los protocolos de sus controladores: úsalo únicamente con hardware soportado y una versión revisada.

El backend Redragon está restringido al modelo/firmware documentado. Los dispositivos ambiguos y los modos no compatibles no se modifican. No se interpreta texto de los nombres de dispositivos como comandos de shell.

La aplicación no inicia un servidor de red, descarga actualizaciones, envía telemetría ni publica el inventario. Los perfiles y logs locales de OpenRGB pueden contener series. Revísalos y anonimízalos antes de adjuntarlos a un issue.

Para informar un fallo, incluye versión, sistema, tipo de conexión, modelo y pasos de reproducción. Nunca adjuntes credenciales, datos personales o capturas completas de tráfico HID de teclados. Si crees que el fallo expone información sensible, evita publicarla en un issue abierto y contacta al mantenedor mediante los canales privados disponibles en su perfil de GitHub.
