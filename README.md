# Buffer Shorts

Publica un video corto desde tu agente mediante Buffer. El agente redacta los
textos, detecta tus canales y ejecuta una CLI independiente. Puedes reunir
canales de varias cuentas en un grupo.

## Instalar desde GitHub con tu agente

Copia el enlace de este repositorio y dile a tu agente:

> Instala la skill Buffer Shorts desde este enlace: [ENLACE DEL REPOSITORIO].
> Descarga el repositorio en una carpeta local estable, lee SKILL.md completo
> antes de ejecutar sus scripts y registra la skill en la ubicación admitida
> por este agente. Si no tiene registro de skills, utiliza esa carpeta y lee
> SKILL.md cuando te pida publicar. Comprueba Python y ayúdame a conectar
> Buffer. No publiques ningún video durante la instalación.

El enlace lo obtienes de la barra de direcciones de GitHub. Cada persona
configura su propia cuenta y API key; el repositorio no incluye credenciales
ni cuentas preconfiguradas. No hace falta instalar Content Publisher.

Si prefieres descargarlo, usa Code → Download ZIP en GitHub, extrae la carpeta
y entrégasela al agente con el pedido anterior. Para instalar con Git, el
agente puede clonar la URL HTTPS del repositorio en su carpeta de skills,
sin sobrescribir una instalación previa ni borrar su .local/.

## Empieza chateando

Entrega la carpeta a Claude Code, Codex, OpenCode o Antigravity y escribe:

> Lee SKILL.md de esta carpeta. Configura Buffer para mi marca, detecta mis
> canales y ayúdame a publicar un Short.

El agente debe disponer de herramientas para leer/escribir archivos y ejecutar
Python. No requiere integración específica con un modelo. Su compatibilidad
se basa en el formato SKILL.md y la CLI; no se ha probado en cada aplicación.

Necesitas Python 3.9+, cuenta de Buffer, redes conectadas y una API key de
Buffer → Settings → API. No necesitas instalar paquetes Python ni ejecutar
Content Publisher. ffprobe es opcional para comprobar formato y duración.

### Configuración inicial

Desde esta carpeta:

    python scripts/buffer_shorts.py accounts add --label "Mi marca"

La entrada de la key es oculta en una terminal interactiva. Si prefieres
configurar con el agente, entrega la key mediante un archivo local o el
mecanismo de secretos de tu agente. Si la pegas en un chat, puede permanecer
en su historial. La CLI acepta --key-file, --key-env o --key-stdin; no acepta
la key como argumento literal.

    python scripts/buffer_shorts.py channels
    python scripts/buffer_shorts.py group "Mi marca" --targets "REF_1,REF_2,REF_3"

Las refs las devuelve channels; no debes inventar ni buscar IDs manualmente.
Si solo tienes un canal de cada red, --targets "youtube,tiktok,instagram"
también funciona. Si hay coincidencias múltiples, se pide elegir una ref.

### Añadir otra cuenta

    python scripts/buffer_shorts.py accounts add --label "Mi segunda cuenta"
    python scripts/buffer_shorts.py channels

Repite con la API key de la otra cuenta. Se conservan las cuentas anteriores.
Puedes guardar un grupo que combine seis destinos de dos cuentas.

El plan Free de Buffer permite hasta tres canales por cuenta. Otra key de
la misma cuenta no añade otros tres. La herramienta admite varias cuentas
independientes y planes de pago; no modifica los límites ni valida las
condiciones comerciales de una estrategia de cuentas múltiples.

Si conectas nuevas redes en Buffer:

    python scripts/buffer_shorts.py accounts refresh

## Publicar

> Publica este MP4 en el grupo Mi marca. Trata sobre [contexto].
> Prepara un título de YouTube y captions adecuados para cada red.

El agente prepara un plan:

    python scripts/buffer_shorts.py prepare "video.mp4" --group "Mi marca" --title "Mi título" --description "Mi descripción"

Con ajustes por red:

    python scripts/buffer_shorts.py prepare "video.mp4" --group "Mi marca" --title "Mi título" --description "Mi descripción" --copy-file "examples/copy.json"

Después de revisar los destinos/textos y autorizar la publicación:

    python scripts/buffer_shorts.py publish "RUTA_DEL_PLAN" --yes
    python scripts/buffer_shorts.py status "RUTA_DEL_PLAN"

prepare no realiza llamadas a Buffer ni sube medios. publish sí aloja el video
y crea publicaciones reales. El archivo queda accesible públicamente para que
Buffer pueda descargarlo. Usa el puente temporal solo para publicación
inmediata, sin garantías de permanencia ni servicio. Para usar tu propio
alojamiento: publish PLAN --yes --media-url "https://tu-host/video.mp4".
La URL propia debe servir exactamente los mismos bytes del MP4 del plan;
se compara su huella antes de publicar.

Solo sent confirma publicación. La consulta status devuelve estado, enlace
externo si existe y error de publicación. No confundir sending con publicado.
La CLI no añade IA generativa: los textos los escribe el agente.

### Textos con consulta actual

Antes de redactar, la skill pide al agente una revisión web breve de consejos
para las redes elegidas. Prioriza fuentes oficiales y aplica hasta tres
mejoras útiles; el presupuesto orientativo es un minuto, no una garantía.
Reutiliza la revisión del mismo día dentro de un lote para evitar esperas.

Las fuentes y la fecha quedan en .local/, fuera del repositorio público.
El agente necesita búsqueda web para realizar esa consulta. Si no la tiene,
lo indica y usa criterios básicos; la CLI sigue funcionando.

## Redes y límites

- Principales: YouTube Shorts, TikTok, Instagram Reels, Facebook Reels,
  LinkedIn video.
- Adaptador básico: X/Twitter, Threads, Bluesky y Mastodon.
- Pinterest, Google Business y demás servicios sin adaptador se muestran,
  pero no se publican en esta versión.
- Entrada: .mp4, vertical/cuadrado, hasta 180 s y 150 MB.
- Cada plataforma impone sus propios límites y condiciones de publicación.
- Se publica inmediatamente; esta versión no programa publicaciones ni
  añade música, edita el video o asegura crecimiento.
- Puede haber conexión por notificación o revisión pendiente en Buffer:
  la skill debe informar el estado y no afirmar que publicó automáticamente.

## Archivos locales y recuperación

Todo el estado está en .local/, ignorado por Git:

- config.json: keys, cuentas descubiertas y grupos. Contiene secretos en texto
  plano; no compartir ni incluir en paquetes.
- plans/: planes y rutas de videos.
- history.json: recibos de envío y estados.
- publish.lock: evita publicar a la vez desde dos agentes.

Para otra ubicación, --state-dir debe colocarse antes del comando.

Las cuentas no se eligen por posición ni nombre de red cuando hay ambigüedad.
Los duplicados se identifican por huella del MP4 y canal. Un envío recibido
no se repite por defecto. --republish permite republicación expresa.

Si hay unknown/submitting, revisa Buffer antes de reintentar. Si el proceso
se cerró inesperadamente y quedó publish.lock, comprueba que no esté activo,
revisa history y elimina solo ese lock para volver a consultar status.
No borres recibos para forzar un reintento de una publicación incierta.

Si encontraste el post en Buffer, verifica que corresponde al video y recupera
su ID con recover PLAN --target REF --post-id ID --yes. La CLI comprueba el
canal. Si comprobaste que no se creó, recover PLAN --target REF --not-sent
--yes habilita otro intento. Un timeout por sí solo no demuestra que no se creó.

## Distribución

Desde esta carpeta:

    python scripts/prepare_release.py

Genera una carpeta hermana buffer-shorts-github con solo los archivos públicos
y un ZIP buffer-shorts-skill.zip. Incluye un manifiesto con las huellas de
los archivos. Publica esa carpeta limpia como repositorio independiente.
Para elegir otras ubicaciones, usa --output-dir y --zip.

No incluyas .local/, tus videos, archivos de key, bitácoras ni notas internas.
No se copiaron keys, contenido ni configuraciones de Content Publisher.
Los nombres de cuenta, IDs y claves de pruebas son ficticios.
Consulta [SECURITY.md](SECURITY.md) para el alcance de las exclusiones.

## Pruebas de desarrollo

Desde la raíz de esta carpeta:

    python -m unittest discover -s tests -v

Las pruebas usan cuentas y llamadas simuladas; no publican ni contactan Buffer.
No reemplazan una prueba real autorizada.

## Procedencia y documentación

El flujo GraphQL y la cadena uguu → filebin → tmpfiles se adaptaron de
Content Publisher, con independencia del servidor y textos separados
para YouTube. Los adaptadores se contrastaron con la documentación oficial.

- [API y planes](https://buffer.com/api)
- [Planes y tres canales Free](https://buffer.com/pricing)
- [Descubrir cuentas](https://developers.buffer.com/examples/get-organizations.html)
- [Descubrir canales](https://developers.buffer.com/examples/get-channels.html)
- [Crear video](https://developers.buffer.com/examples/create-video-post.html)
- [Alojamiento de medios](https://developers.buffer.com/guides/hosting-media.html)
- [Estados](https://developers.buffer.com/types/PostStatus.html)

Revisado: 30 de septiembre de 2026. El servicio y sus límites pueden cambiar.
