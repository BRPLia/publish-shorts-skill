# Onboarding para grabar el tutorial

## Conversación 1: primera cuenta

Usuario:

> Lee esta skill y configura mi cuenta de Buffer para Mi marca.

Agente:

> Conecta tus redes en Buffer y crea la API key en Settings → API. Dime cómo
> prefieres introducirla: prompt local oculto o archivo local.

Después de recibir la key por el método elegido, el agente configura y devuelve
los nombres reales de los canales detectados. El usuario no busca IDs.
Si entrega la key en el chat por elección propia, no mostrarla durante la
grabación; usar la herramienta de archivos para preparar la entrada local.

## Conversación 2: otra cuenta

Usuario:

> Añade mi segunda cuenta de Buffer y junta sus canales con los anteriores
> en el grupo Mi marca.

El agente agrega otra cuenta, conserva la primera y muestra los destinos.
Si hay varios canales YouTube u otras coincidencias, pide escoger sus nombres.
Cada ref mantiene cuenta + channelId. No identifica marcas solo por el nombre
de la red ni deduce que los nombres distintos pertenecen a marcas distintas.

Cada cuenta Free tiene su propio límite de hasta tres canales, según Buffer.
Las API keys no crean capacidad adicional en una misma cuenta. Dos cuentas
independientes con tres canales cada una pueden gestionarse conjuntamente;
la skill no cambia las condiciones del proveedor.

## Conversación 3: publicación

Usuario:

> Publica demo.mp4 en el grupo Mi marca. Es un tutorial sobre automatización
> con IA. Escribe los textos adecuados para cada red.

El agente obtiene contexto, prepara los textos, muestra destinos y ejecuta
el envío autorizado. Explica que se utilizará un alojamiento público temporal.
Al terminar, consulta el estado en Buffer y reporta cada canal:

- Publicado: enlace si Buffer lo proporciona.
- Pendiente: recibió el envío y sigue procesando.
- Falló: mensaje concreto y siguiente corrección.
- No enviado: ese destino todavía no alcanzó el envío.

No mostrar "publicado" solo porque Buffer devuelve un ID.

## Qué grabar

1. Resultado real en las redes al inicio.
2. Pedido al agente en lenguaje natural.
3. Instalación: leer SKILL.md, comprobar Python y conectar Buffer una vez.
4. Configuración de una cuenta; añadir otra como opción.
5. Preparación de textos y publicación de un MP4 vertical.
6. Estado final y enlaces por destino.

Solo afirmar compatibilidad con las redes efectivamente probadas durante el
ensayo. No anunciar "redes ilimitadas", "anti-ban" ni publicación sin servicios
externos.
