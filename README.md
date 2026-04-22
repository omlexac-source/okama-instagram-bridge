# Okama Instagram Bridge - Despliegue en Render.com

## Que es esto
Servidor webhook que recibe mensajes de WhatsApp, filtra por tu numero autorizado,
y ejecuta comandos para publicar en Instagram de Okama.

## Requisitos previos
- Cuenta gratis en [render.com](https://render.com)
- App configurada en [Meta for Developers](https://developers.facebook.com)

## Archivos incluidos
- `app.py` - Servidor Flask con webhook
- `requirements.txt` - Dependencias Python
- `render.yaml` - Configuracion de Render (blueprint)

## Pasos de despliegue

### 1. Crear cuenta en Render
- Ve a [render.com](https://render.com) y crea una cuenta gratis
- Puedes usar "Sign up with GitHub" para mas facilidad

### 2. Crear nuevo servicio Web
- En el dashboard de Render, click "New +" > "Web Service"
- Conecta tu repositorio de GitHub (sube estos archivos primero)
- O usa "Deploy from Blueprint" con el archivo render.yaml

### 3. Configurar variables de entorno
En el dashboard de tu servicio, ve a "Environment" y configura:

| Variable | Valor | Estado |
|----------|-------|--------|
| `WHATSAPP_PHONE_NUMBER_ID` | 068769399658514 | Ya configurado |
| `WHATSAPP_ACCESS_TOKEN` | EAAYJCs8FM18... | Ya configurado |
| `WHATSAPP_APP_SECRET` | 9a4dae607d62... | Ya configurado |
| `WHATSAPP_VERIFY_TOKEN` | Generado automaticamente | Ya configurado |
| `AUTHORIZED_PHONE_NUMBER` | +52XXXXXXXXXX | **PENDIENTE - tu numero personal** |
| `INSTAGRAM_USER_ID` | 17841400000000000 | **PENDIENTE** |
| `INSTAGRAM_ACCESS_TOKEN` | EAA... | **PENDIENTE** |
| `AUTO_REPLY` | true | Ya configurado |

### 4. Desplegar
- Click "Deploy" (o "Create Web Service")
- Espera a que termine (1-2 minutos)
- Copia la URL generada (ej: `https://okama-instagram-bridge.onrender.com`)

### 5. Configurar webhook en Meta
1. Ve a [developers.facebook.com](https://developers.facebook.com) > tu app > WhatsApp > Configuration
2. En "Webhook", click "Edit"
3. Callback URL: `https://tu-url-de-render.onrender.com/webhook`
4. Verify Token: el valor que se genero en WHATSAPP_VERIFY_TOKEN
5. Click "Verify and Save"
6. En "Webhook Fields", suscribete a "messages"

### 6. Probar
- Manda un WhatsApp al numero +524446080703
- Si todo esta bien, recibiras respuesta del bot

## Comandos disponibles
Manda estos mensajes por WhatsApp al numero business:

- `help` o `ayuda` - Ver comandos
- `status` o `estado` - Ver estado
- `post image <URL> caption <texto>` - Publicar foto en Instagram
- `post reel <URL> caption <texto>` - Publicar reel
- `post carousel <URL1>, <URL2> caption <texto>` - Publicar carrusel

## Obtener datos pendientes de Instagram

Para completar la configuracion necesitas:

### Instagram User ID
1. Ve a [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Selecciona tu app, genera token con `instagram_basic`
3. Consulta: `GET /{facebook_page_id}?fields=instagram_business_account`
4. El campo `id` dentro de `instagram_business_account` es tu IG User ID

### Instagram Access Token
1. En el Graph API Explorer, genera token con permisos:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
2. Extiende a long-lived: usa el endpoint de exchange token
3. O usa el token de pagina permanente

Una vez tengas estos valores, agregalos como variables de entorno en Render.
