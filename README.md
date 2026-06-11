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

## Contenido privado o restringido (cookies)

Instagram (y a veces X) exige sesión iniciada para publicaciones privadas o con restricción de edad. Exporta tus cookies en formato Netscape (`cookies.txt`) con una extensión de navegador y arranca el servidor con:

```bash
COOKIES_FILE=/ruta/a/cookies.txt uvicorn app.main:app --port 8000
```

## Limitaciones

- Solo se admiten URLs de `x.com`, `twitter.com` e `instagram.com`.
- X e Instagram cambian sus APIs con frecuencia; si una URL deja de funcionar, actualiza yt-dlp: `pip install -U yt-dlp`.
- Sin `ffmpeg` instalado solo se ofrecen formatos *progresivos* (vídeo y audio en un único archivo), que es lo habitual en X e Instagram. Si instalas `ffmpeg`, yt-dlp podrá combinar también pistas separadas.
- Descarga únicamente contenido del que tengas derechos o permiso. Respeta los términos de servicio de cada plataforma.
