"""Extracción y descarga de vídeos de X/Twitter e Instagram mediante yt-dlp."""

import os
import re
import tempfile
from urllib.parse import urlparse

import yt_dlp

from app import instagram_fallback

ALLOWED_DOMAINS = {
    "x.com",
    "twitter.com",
    "instagram.com",
    "instagr.am",
}

COOKIES_FILE = os.environ.get("COOKIES_FILE")
# Navegador del que extraer cookies, p. ej. "firefox", "safari" o
# "chrome:Profile 3". yt-dlp espera la tupla (navegador, perfil, keyring,
# contenedor); aquí solo exponemos navegador y perfil.
COOKIES_FROM_BROWSER = os.environ.get("COOKIES_FROM_BROWSER")


def _cookies_from_browser_tuple(value: str | None) -> tuple | None:
    """Convierte "firefox" o "chrome:Perfil" en la tupla que espera yt-dlp."""
    value = (value or "").strip()
    if not value:
        return None
    browser, _, profile = value.partition(":")
    return (browser.lower().strip(), profile.strip() or None, None, None)


class DownloadError(Exception):
    """Error con mensaje apto para mostrar al usuario."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise DownloadError("Introduce una URL.")
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    try:
        parsed = urlparse(url)
    except ValueError:
        raise DownloadError("La URL no es válida.")
    host = (parsed.hostname or "").lower()
    domain = host[4:] if host.startswith("www.") else host
    # Acepta también subdominios como mobile.twitter.com
    if domain not in ALLOWED_DOMAINS and not any(
        domain.endswith("." + d) for d in ALLOWED_DOMAINS
    ):
        raise DownloadError(
            "Solo se admiten URLs de X/Twitter o Instagram "
            "(x.com, twitter.com, instagram.com)."
        )
    return url


def _is_instagram(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host.endswith("instagram.com") or host.endswith("instagr.am")


def _base_ydl_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
    }
    if COOKIES_FILE:
        opts["cookiefile"] = COOKIES_FILE
    browser = _cookies_from_browser_tuple(COOKIES_FROM_BROWSER)
    if browser:
        opts["cookiesfrombrowser"] = browser
    return opts


def _map_yt_dlp_error(exc: Exception) -> DownloadError:
    text = str(exc).lower()
    if "login" in text or "private" in text or "rate-limit" in text or "cookies" in text:
        return DownloadError(
            "Instagram exige una sesión para este contenido (incluso público). "
            "Arranca el servidor con COOKIES_FILE=/ruta/cookies.txt (cookies "
            "exportadas estando logueado) o con COOKIES_FROM_BROWSER=firefox.",
            status_code=403,
        )
    if "no video" in text or "unsupported url" in text:
        return DownloadError("Esta publicación no contiene ningún vídeo.", status_code=422)
    if "404" in text or "not found" in text or "unavailable" in text:
        return DownloadError(
            "No se ha encontrado la publicación. Comprueba que la URL es correcta.",
            status_code=404,
        )
    return DownloadError(
        "No se ha podido procesar la publicación. Comprueba la URL e inténtalo de nuevo.",
        status_code=422,
    )


def _progressive_formats(info: dict) -> list[dict]:
    """Filtra formatos con vídeo y audio combinados (no requieren ffmpeg).

    Los MP4 progresivos de X/Twitter no declaran códecs (None); solo se
    descarta el valor explícito 'none' (pista ausente) y los protocolos de
    streaming (HLS/DASH), que servirían pistas separadas sin ffmpeg.
    """
    formats = []
    for f in info.get("formats") or []:
        if f.get("vcodec") == "none" or f.get("acodec") == "none":
            continue
        if not (f.get("protocol") or "").startswith("http"):
            continue
        height = f.get("height")
        size = f.get("filesize") or f.get("filesize_approx")
        formats.append(
            {
                "format_id": f["format_id"],
                "ext": f.get("ext") or "mp4",
                "resolution": f"{height}p" if height else (f.get("format_note") or "desconocida"),
                "height": height or 0,
                "filesize": size,
            }
        )
    formats.sort(key=lambda f: f["height"], reverse=True)
    return formats


def get_video_info(url: str) -> dict:
    url = validate_url(url)
    try:
        with yt_dlp.YoutubeDL(_base_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        error = _map_yt_dlp_error(exc)
        # Instagram bloquea peticiones sin sesión incluso para contenido
        # público; un navegador headless sí puede extraerlo.
        if error.status_code == 403 and _is_instagram(url):
            fallback_info = instagram_fallback.extract_info(url)
            if fallback_info:
                for f in fallback_info["formats"]:
                    f.pop("direct_url", None)
                return fallback_info
        raise error

    # Publicaciones con varios vídeos: usamos el primero
    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        if not entries:
            raise DownloadError("Esta publicación no contiene ningún vídeo.", status_code=422)
        info = entries[0]

    formats = _progressive_formats(info)
    if not formats and not info.get("url"):
        raise DownloadError("Esta publicación no contiene ningún vídeo.", status_code=422)

    return {
        "title": info.get("title") or "Vídeo",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url") or url,
        "formats": formats,
    }


def download_video(url: str, format_id: str | None = None) -> tuple[str, str]:
    """Descarga el vídeo a un directorio temporal.

    Devuelve (ruta_del_archivo, nombre_para_el_usuario). El llamante es
    responsable de eliminar el directorio temporal tras servir el archivo.
    """
    url = validate_url(url)

    # Formatos "ig-N" provienen del fallback de navegador, no de yt-dlp
    if format_id and format_id.startswith("ig-") and _is_instagram(url):
        result = instagram_fallback.download(url, format_id)
        if not result:
            raise DownloadError("La descarga ha fallado. Inténtalo de nuevo.", status_code=500)
        return result

    tmpdir = tempfile.mkdtemp(prefix="socialdl-")
    opts = _base_ydl_opts()
    opts.update(
        {
            "outtmpl": os.path.join(tmpdir, "%(title).80B [%(id)s].%(ext)s"),
            # Sin ffmpeg solo podemos servir formatos ya combinados
            "format": format_id or "best[protocol^=http]/best",
            "restrictfilenames": True,
        }
    )
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        error = _map_yt_dlp_error(exc)
        if error.status_code == 403 and _is_instagram(url):
            result = instagram_fallback.download(url, format_id)
            if result:
                return result
        raise error

    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        if not entries:
            raise DownloadError("Esta publicación no contiene ningún vídeo.", status_code=422)
        info = entries[0]

    filepath = info.get("filepath") or (info.get("requested_downloads") or [{}])[0].get(
        "filepath"
    )
    if not filepath or not os.path.exists(filepath):
        raise DownloadError("La descarga ha fallado. Inténtalo de nuevo.", status_code=500)

    filename = os.path.basename(filepath)
    return filepath, filename
