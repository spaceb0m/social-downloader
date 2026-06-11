# Social Downloader

Aplicación web para descargar vídeos de **X (Twitter)** e **Instagram**: pega la URL de la publicación, elige la calidad y descarga el archivo MP4 a tu dispositivo.

Construida con [FastAPI](https://fastapi.tiangolo.com/) y [yt-dlp](https://github.com/yt-dlp/yt-dlp).

## Requisitos

- Python 3.11 o superior

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Abre <http://localhost:8000>, pega la URL de una publicación con vídeo (por ejemplo `https://x.com/usuario/status/123…` o `https://www.instagram.com/p/ABC…/`), pulsa **Obtener vídeo** y elige la calidad que quieras descargar.

### API

| Método | Ruta | Descripción |
| --- | --- | --- |
| `POST` | `/api/info` | Body `{"url": "..."}`. Devuelve título, miniatura, duración y formatos disponibles. |
| `GET` | `/api/download?url=...&format_id=...` | Descarga el vídeo y lo sirve como archivo adjunto. `format_id` es opcional (por defecto, la mejor calidad combinada). |

## Cómo funciona Instagram (sin configuración)

**Instagram rechaza las peticiones HTTP "limpias" de yt-dlp incluso para contenido público** («rate-limit / login required»). Un navegador real sí puede verlo, porque al renderizar la página establece una sesión anónima válida.

Por eso, cuando yt-dlp falla con un vídeo de Instagram, la app activa automáticamente un **fallback con Chrome/Chromium headless**: renderiza la página, extrae las URLs directas del vídeo del CDN y las descarga. No requiere cuenta, cookies ni configuración por parte del usuario — solo que el servidor tenga Chrome o Chromium instalado.

- El binario se autodetecta (Chrome en macOS, `google-chrome`/`chromium` en Linux). Puedes forzar uno con `CHROME_BIN=/ruta/al/binario`.
- En Docker o ejecutando como root, añade `CHROME_NO_SANDBOX=1`.
- La extracción añade ~5-10 s la primera vez que se consulta una URL.

## Contenido privado o restringido (cookies)

Para publicaciones **privadas** o con restricción de edad, el fallback no basta: necesitas cookies de una sesión con acceso. Hay dos formas:

### Opción A — Archivo `cookies.txt` (más fiable)

Exporta tus cookies de Instagram en formato Netscape (`cookies.txt`) con una extensión de navegador (p. ej. *«Get cookies.txt LOCALLY»*), **estando logueado en Instagram** (en una ventana normal, no de incógnito), y arranca con:

```bash
COOKIES_FILE=/ruta/a/cookies.txt uvicorn app.main:app --port 8000
```

### Opción B — Leer cookies directamente del navegador

yt-dlp puede leer las cookies de un navegador instalado:

```bash
COOKIES_FROM_BROWSER=firefox uvicorn app.main:app --port 8000
# también: chrome, chromium, edge, brave, opera, safari, vivaldi
# con perfil concreto:  COOKIES_FROM_BROWSER="chrome:Profile 1"
```

> **Nota en macOS:** Chrome cifra sus cookies con una clave del Keychain (cifrado *app-bound*) que yt-dlp **no** puede leer, y Safari requiere conceder *Acceso Total a Disco* al terminal. Firefox funciona sin trabas. Si la opción B no extrae cookies, usa la opción A.

Ambas variables pueden combinarse o usarse por separado. Si necesitas calidades por encima de las progresivas, instala `ffmpeg`.

## Limitaciones

- Solo se admiten URLs de `x.com`, `twitter.com` e `instagram.com`.
- X e Instagram cambian sus APIs con frecuencia; si una URL deja de funcionar, actualiza yt-dlp: `pip install -U yt-dlp`.
- Sin `ffmpeg` instalado solo se ofrecen formatos *progresivos* (vídeo y audio en un único archivo), que es lo habitual en X e Instagram. Si instalas `ffmpeg`, yt-dlp podrá combinar también pistas separadas.
- Descarga únicamente contenido del que tengas derechos o permiso. Respeta los términos de servicio de cada plataforma.
