---
name: buffer-shorts
description: Configura cuentas de Buffer y publica videos cortos terminados desde el equipo usando una CLI portable. Usa esta skill cuando el usuario quiera conectar su API key, añadir otra cuenta de Buffer, publicar un MP4 en YouTube Shorts, TikTok, Instagram Reels, Facebook o LinkedIn, preparar títulos y captions por red o consultar el resultado. Permite varias cuentas y grupos de canales entre ellas. No genera ni edita videos.
---

# Buffer Shorts

Convierte un pedido como "publica este video en mis redes" en un plan concreto y
una publicación comprobable. Opera scripts/buffer_shorts.py desde esta carpeta.
La CLI usa Python 3.9+ estándar, devuelve JSON y no necesita Content Publisher,
servidor, navegador ni dependencias Python externas.

## Primer contacto

1. Localiza esta carpeta sin asumir una ruta absoluta ni un nombre del usuario.
2. Lee README.md para instalación y límites solo si lo necesitas.
3. Ejecuta channels para ver cuentas ya configuradas. Respeta las reglas de
   permisos y terminal del workspace. Mostrar ayuda no publica nada.
4. Si no hay cuentas, guía el onboarding siguiente. Si ya existen, reutilízalas.

## Onboarding conversacional

Pregunta únicamente lo que falta: nombre de la cuenta y cómo entregar la key.
Explica: "Conecta tus redes en Buffer y crea tu API key en Ajustes → API.
Yo detecto los canales y guardo la configuración; no tienes que buscar IDs".
URL: https://publish.buffer.com/settings/api
Si cambia la ruta, entra a Buffer → Settings → API.

Ejemplo de conversación:

- Usuario: "Configúrame Buffer, esta cuenta es Mi marca".
- Agente: "Conecta las redes en Buffer. Puedes introducir la key en el prompt
  local oculto, dejarla en un archivo local o compartirla aquí si aceptas que
  quede en el historial del chat".
- Usuario entrega la key mediante el método elegido.
- Agente configura, detecta canales y responde sus nombres; no repite la key.
- Agente: "Encontré YouTube Mi Canal, TikTok Mi Canal e Instagram Mi Canal.
  ¿Los guardo en el grupo Mi marca?" Si el usuario ya indicó el grupo/destinos,
  créalo directamente.

Para entrada local oculta:

    python scripts/buffer_shorts.py accounts add --label "Mi marca"

Esto requiere una terminal interactiva donde el usuario escriba con getpass.
No lo ejecutes en una herramienta sin entrada interactiva esperando que el
usuario pueda escribir allí.

Para un archivo local preparado por el usuario:

    python scripts/buffer_shorts.py accounts add --label "Mi marca" --key-file ".local/key-input.txt"

Si la key fue entregada en el chat, crea primero .local/ y escribe únicamente la
key en .local/key-input.txt con la herramienta de archivos del agente. Ejecuta
el comando anterior, verifica éxito y elimina ese archivo temporal con la
herramienta de archivos. La key queda en .local/config.json. No interpolar la
key en comandos de shell, argumentos, documentos, ejemplos ni mensajes.

También se admite --key-env NOMBRE_VARIABLE o --key-stdin. No inventes keys ni
copies las de otros proyectos. No muestres config.json; accounts list y
channels están diseñados para mostrar resultados sin secretos.

## Varias cuentas

Si pide "añade otra cuenta", repite accounts add con otro nombre y su key.
Se agregan sus canales sin reemplazar los anteriores. Si añadió conexiones en
Buffer, ejecuta accounts refresh, opcionalmente --account ID.

El plan Free de cada cuenta ofrece hasta tres canales según los límites de
Buffer vigentes. Varias keys de la misma cuenta no multiplican ese límite.
Esta skill gestiona cuentas independientes, descubre sus conexiones reales y
no fuerza un máximo de tres: también sirve para planes con más canales.
No prometas conexiones ilimitadas ni que Buffer autorice una estrategia de
cuentas múltiples; documenta las condiciones vigentes como las del proveedor.

Cada canal tiene una ref: ID_CUENTA:ID_CANAL. Conserva estas identidades aunque
dos redes tengan el mismo nombre. Si "youtube" coincide con dos canales,
pregunta cuál y usa su ref; no publiques en todos ni escojas el primero.
Un grupo puede combinar destinos de varias cuentas:

    python scripts/buffer_shorts.py group "Mi marca" --targets "REF_1,REF_2,REF_3"

## Preparar un video

1. Obtén ruta del MP4 y destino(s), por grupo o ref. Usa channels; no inventes.
2. Usa transcripción/contexto del usuario o inspección del video para comprender
   su contenido. Si no puedes inspeccionarlo, pide una explicación breve. No
   deduzcas hechos, resultados, millones de vistas o marcas del nombre del archivo.
3. Antes de redactar, haz una consulta web breve sobre títulos/captions para
   las redes elegidas: hasta 3 búsquedas agrupadas y 3 páginas, unos 60 segundos
   como presupuesto orientativo. Prioriza fuentes oficiales; aplica como máximo
   3 mejoras útiles. Lee references/copy-refresh.md para el procedimiento.
   Reutiliza lo revisado el mismo día para el mismo lote de publicaciones.
   Guarda fecha, fuentes y reglas en .local/copy-research.json; nunca en archivos
   públicos. No busques keys, IDs de cuentas ni textos privados del usuario.
   Si no puedes navegar, usa principios básicos e informa que no hubo consulta
   actual; no inventes novedades del algoritmo ni frenes la publicación.
4. Redacta textos fieles, breves y adecuados a cada red. YouTube separa título
   y descripción; TikTok usa caption, no un título de video independiente.
5. Prepara un JSON local de ajustes por service o ref, si hacen falta:

    {
      "youtube": {"title": "Título concreto", "description": "Descripción útil", "category_id": "27"},
      "tiktok": {"caption": "Gancho y contexto #Tema"},
      "instagram": {"caption": "Contexto y llamada a la acción"},
      "facebook": {"caption": "Texto para el Reel"},
      "linkedin": {"title": "Aprendizaje", "caption": "Contexto profesional"}
    }

Una entrada por ref tiene prioridad sobre la entrada por service. El título
base y descripción base son obligatorios. No añadas automáticamente un emoji
ni #youtube/#tiktok. Marca ai_generated solo cuando tengas información para
hacerlo; omitir no significa afirmar que el video no usa IA. Si el usuario
quiere ajustar privacidad o contenido para niños, esta versión requiere
revisar esas opciones en Buffer antes de enviar; no prometas que la CLI las
configura.

    python scripts/buffer_shorts.py prepare "video.mp4" --group "Mi marca" --title "Título" --description "Descripción" --copy-file ".local/copy.json"

Alternativa a --group: --targets "REF_1,REF_2". prepare es local: no sube el
video ni publica. Devuelve la ruta de un plan con cuentas, textos y huella
del video. Muestra al usuario los destinos y el texto final en lenguaje simple.

## Publicar y verificar

Si el usuario ya pidió publicar ese video en esos destinos, la instrucción
autoriza la publicación. Si solo pidió preparar, proponer textos o configurar,
espera su autorización para publicar. Respeta los permisos locales adicionales.
No pidas confirmar de nuevo una acción que ya está claramente autorizada.

    python scripts/buffer_shorts.py publish "RUTA_PLAN" --yes
    python scripts/buffer_shorts.py status "RUTA_PLAN"

Explica antes del primer envío que el video se alojará en un host público
temporal para que Buffer pueda descargarlo. Usa esa opción para publicación
inmediata; no usarla para programar. --media-url URL permite un MP4 público
propio. No se anuncian beneficios "anti-ban", de alcance ni de viralidad.

La CLI registra cada envío antes de solicitarlo a Buffer. No ejecuta reintentos
ciegos. Si se interrumpe una petición, el estado unknown/submitting bloquea
el reenvío: consulta Buffer y el historial antes de decidir. --republish solo
con una petición expresa de republicar; no lo uses para resolver errores.

Para recuperar un envío incierto después de comprobarlo, usa recover PLAN
--target REF --post-id ID --yes si encontraste el post en Buffer. Verifica que
el contenido coincide; la CLI comprueba que el ID pertenece al canal elegido.
Si el usuario comprobó que no se creó, recover PLAN --target REF --not-sent
--yes permite un nuevo intento. No afirmar ausencia de un post por un timeout.
Un lock tras una interrupción exige comprobar que el proceso terminó y revisar
history antes de eliminar solo .local/publish.lock.

- sent: publicado; devuelve external_link si está disponible.
- sending/scheduled/accepted: Buffer lo recibió, aún no confirmado como publicado.
- error: informa del fallo; permite reintentar después de corregirlo.
- needs_approval/draft: requiere completar el paso pendiente en Buffer.
- skipped: ya enviado; comprueba el plan original indicado en el resultado.
- unknown/blocked: revisión necesaria, no volver a enviar automáticamente.
- not_submitted: ese destino todavía no fue enviado.

Si está pendiente, vuelve a consultar status de forma espaciada. Un
PostActionSuccess o un ID no prueba la publicación. Reporta por destino:
nombre de cuenta/red, estado, post_id, enlace y error si existe.

## Alcance

Adaptadores principales: YouTube, TikTok, Instagram, Facebook y LinkedIn.
También hay un adaptador básico de video para X (service=twitter), Threads,
Bluesky y Mastodon; sujeto a sus límites. channels marca supported=false
para servicios detectados sin adaptador. No afirmar "todas las redes".

Usa un MP4 vertical o cuadrado de hasta 180 segundos y máximo 150 MB. ffprobe
opcional verifica dimensiones/duración; sin él, la CLI lo indica como no
verificado y hay que comprobarlo antes de publicar. Los límites específicos
de cada red pueden ser más restrictivos. No convertir videos ni instalar
ffmpeg automáticamente.

No instales esta skill globalmente salvo que el usuario lo pida. Para usarla
en cualquier agente, basta leer este SKILL.md y disponer de ejecución Python.
