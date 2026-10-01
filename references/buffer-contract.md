# Contrato Buffer consultado · 30/09/2026

Los nombres de inputs y estados se contrastaron con documentación oficial.
La implementación conserva el descubrimiento/GraphQL y puente de medios de
Content Publisher, pero no su servidor ni sus archivos de configuración.

## Descubrimiento

- account.organizations devuelve id/name de todas las organizaciones accesibles.
- channels(input: ChannelsInput!) recibe organizationId y devuelve
  id/name/displayName/service.
- No limitar el número de organizaciones o canales por cuenta en el código.
- Guardar la relación account_id → organization → channelId.

## Creación

createPost(input: CreatePostInput!) recibe channelId, text, mode=shareNow,
schedulingType=automatic, needsApproval=false y assets con video.url.
Usar variables GraphQL; no interpolar títulos/descripciones en la consulta.

Metadata:

- YouTube: title y categoryId. text es descripción.
- Instagram: type=reel y shouldShareToFeed=true.
- Facebook: type=reel.
- TikTok: text es caption del video. metadata.title aplica a fotos, no videos.
- LinkedIn y los adaptadores básicos no requieren metadata de video adicional.
- La ausencia de campos obligatorios no garantiza que cualquier MP4 cumpla
  los límites de una red.

## Verificación

post(input: PostInput!) recibe id y devuelve status/sentAt/externalLink/error.
Estados: draft, error, needs_approval, scheduled, sending, sent.
Solo sent confirma publicación.

Buffer no ofrece un endpoint de upload de archivo local: requiere una URL
pública directa que permanezca accesible hasta publicar. Los hosts temporales
se usan solamente para envío inmediato y pueden fallar.

## Fuentes oficiales

- https://developers.buffer.com/types/CreatePostInput.html
- https://developers.buffer.com/types/YoutubePostMetadataInput.html
- https://developers.buffer.com/types/InstagramPostMetadataInput.html
- https://developers.buffer.com/types/FacebookPostMetadataInput.html
- https://developers.buffer.com/types/TikTokPostMetadataInput.html
- https://developers.buffer.com/types/PostInput.html
- https://developers.buffer.com/types/PostStatus.html
- https://developers.buffer.com/examples/get-organizations.html
- https://developers.buffer.com/examples/get-channels.html
- https://developers.buffer.com/guides/hosting-media.html
- https://buffer.com/pricing
