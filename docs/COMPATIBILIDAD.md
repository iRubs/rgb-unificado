# Compatibilidad y ampliaciones

## Dos niveles de detección

1. **Inventario del sistema:** lectura de USB y PCI desde sysfs, sin sondear direcciones desconocidas. No todos estos dispositivos tienen RGB.
2. **Control RGB:** OpenRGB detecta con sus controladores habilitados y devuelve un perfil actual. Solo estos controladores y el adaptador Redragon comprobado se ofrecen como controlables, si tienen modos apropiados e identidad no ambigua.

El catálogo contiene coincidencias USB VID/PID y PCI vendor/device/subvendor/subdevice extraídas de registros de OpenRGB 1.1 habilitados por defecto. No incluye coincidencias comodín, registros deshabilitados por defecto ni expresiones que el generador no pueda resolver sin ambigüedad. Por tanto, **no es la lista completa de soporte de OpenRGB**. Un dispositivo soportado fuera de ese subconjunto puede requerir habilitar expresamente su detector con `--enable-detector`.

Los detectores de RAM no se activan automáticamente por tener una marca determinada. La migración conserva `Corsair DRAM` para la instalación anterior que ya lo utilizaba. En otras instalaciones hay que comprobar soporte, permisos y activar el detector correspondiente.

## Cómo identifica los componentes

- El ID local es un hash del proveedor, nombre, descripción, tipo, serie disponible y localización relevante.
- Las rutas `/dev/hidrawN` cambian al reconectar: no se usan como identidad persistente.
- En I2C se conserva la dirección del controlador, sin atar el dispositivo al número de adaptador del kernel.
- Dos dispositivos idénticos sin serie pueden ser indistinguibles. Se marcan como ambiguos y se omite su control individual, en vez de aplicar a uno la preferencia del otro.
- Sin una serie fiable, reemplazar una pieza por otra idéntica en la misma dirección puede conservar la preferencia anterior. No es posible demostrar su identidad física con datos que el controlador no proporciona.
- Un cambio de nombre/firmware/proveedor expuesto por OpenRGB puede crear un nuevo ID. La entrada anterior se conserva como ausente.

## Modos

Para un color uniforme se buscan modos `Static`, `Direct`, `Fixed` o `Solid`. Se usa `Off` cuando está disponible; en otros controladores se envía negro al modo estático/directo. Los dispositivos que solo exponen animaciones se omiten y se informa del motivo. No se cambia el tamaño de las zonas ni los límites de corriente.

El perfil leído después de aplicar sirve para confirmar lo que OpenRGB aceptó, **no es una medición óptica ni una lectura física de cada LED**. El adaptador Redragon sí consulta el estado de iluminación que responde el propio teclado. La detección OpenRGB puede intercambiar comandos de identificación/estado específicos del controlador, aunque `--scan` no aplique un perfil de color.

## Adaptador Redragon

USB `2e3c:c365`, nombre de producto `K686RGB-M`, interfaz HID FF1B/91. Antes de modificar iluminación comprueba exactamente la identidad:

```text
W669,34,KB,FR,7431UKHEXYXBJCARGB,V3.18.01
```

Solo consulta identidad, modos e iluminación y escribe la configuración de iluminación. Usa brillo cero y negro para apagar y lee de vuelta la configuración. Si la respuesta no coincide, intenta restaurar la configuración inmediatamente anterior. Otro modelo o firmware requiere revisar el protocolo y añadir pruebas; compartir VID/PID no basta.

## Dispositivos que no aparecen

Revisa permisos udev, conexión de datos, versión de OpenRGB, detector y compatibilidad exacta. Las luces alimentadas por USB sin interfaz de datos, los hubs con control remoto y el RGB fijo pueden carecer de control por software. Los headers de placa no enumeran los ventiladores o las tiras conectadas.

No hay soporte genérico para pantallas de refrigeración. La telemetría de una pantalla puede usar un programa separado que no compita por los dispositivos RGB. No se envían comandos de un modelo a otro para intentar hacerlo funcionar.

## Actualizaciones de hardware y software

Al conectar hardware USB compatible, el monitor reescanea y aplica la política de nuevos componentes. Una sustitución interna normalmente se detecta en el siguiente inicio de sesión. Los permisos USB opcionales cubren los IDs del catálogo instalado; un ID añadido en un catálogo posterior requiere regenerar también las reglas.

Actualizar OpenRGB exige revisar y regenerar el catálogo, actualizar su versión declarada y comprobar las diferencias de perfiles. No se descarga ni habilita código nuevo automáticamente desde GitHub. Los componentes no compatibles se informan; no existe una garantía de soporte de todo hardware futuro.
