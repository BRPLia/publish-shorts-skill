# Datos locales y distribución

Las API keys y los canales descubiertos se guardan en .local/config.json.
Los planes contienen rutas de videos, textos e identidades de destinos.
El historial contiene IDs y estados de publicaciones. Son datos del usuario:
permanecen fuera de Git y del paquete público.

## Compartir el proyecto

Usa scripts/prepare_release.py para generar una carpeta pública y un ZIP.
El exportador utiliza una lista explícita de archivos revisados y verifica
el contenido del ZIP. No recorre ni copia el estado de .local/.

Publica únicamente la carpeta generada buffer-shorts-github en un repositorio
dedicado. Contiene código, documentación, pruebas y ejemplos ficticios.
No uses como repositorio público el workspace que contiene tus otros proyectos.

El exportador comprueba patrones comunes de secretos y rutas absolutas. Esa
comprobación complementa la lista explícita; no identifica todos los secretos
posibles escritos manualmente en un archivo de código.

## Configuración y capturas

- Usa el prompt local oculto, un archivo privado o una variable de entorno
  para introducir tu key. No pegarla en issues, capturas o comandos públicos.
- La CLI no imprime las keys en accounts list, channels, planes ni historial.
- No compartir .local/, archivos .env, archivos de key, medios ni bitácoras.
- Si cambias --state-dir, mantén esa carpeta fuera del repositorio público.
- Si creas un ZIP manualmente, no comprimas la carpeta de desarrollo completa.

## Archivos previamente versionados

.gitignore no elimina archivos que Git ya tiene versionados. Antes de publicar,
comprueba que el repositorio público contiene solo los archivos del manifiesto
y que no existe una versión anterior con secretos en su historial.

Si una key fue compartida, revócala en Buffer y crea otra. Borrar el archivo
de la versión actual no revoca una key ni elimina por sí solo el historial.

## Publicación de videos

Al publicar, Buffer necesita acceder al MP4 mediante una URL pública.
La CLI puede subir únicamente el video elegido a un host temporal o usar la
URL propia indicada por el usuario. No envía keys de Buffer a esos hosts.
La key se utiliza exclusivamente para autenticarse ante la API de Buffer.

Este proyecto no incorpora telemetría, envío de configuración a un tercero,
sincronización de cuentas entre usuarios ni publicación automática en GitHub.
