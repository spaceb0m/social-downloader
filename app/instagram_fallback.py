"""Fallback de extracción para Instagram mediante Chrome/Chromium headless.

Instagram rechaza las peticiones HTTP "limpias" de yt-dlp incluso para
contenido público (muro de "login required"). Un navegador real sí puede
verlo: al renderizar la página establece una sesión anónima válida y el
DOM resultante contiene las URLs directas del vídeo en el CDN
(`video_versions`), descargables después sin cookies.

Este módulo replica ese flujo: renderiza la página con Chrome headless,
extrae `video_versions` del DOM y descarga el MP4 directamente del CDN.
"""

import html
import json
import os
import re
import select
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.request
from urllib.parse import urlparse

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Etiquetas para los "type" conocidos de video_versions (101 es la mejor)
_TYPE_LABELS = {101: "calidad alta", 102: "calidad media", 103: "calidad baja"}

_CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
]


def find_chrome() -> str | None:
    """Localiza un binario de Chrome/Chromium (override con CHROME_BIN)."""
    env_bin = os.environ.get("CHROME_BIN")
    if env_bin:
        return env_bin if os.path.exists(env_bin) else shutil.which(env_bin)
    for candidate in _CHROME_CANDIDATES:
        if os.path.isabs(candidate):
            if os.path.exists(candidate):
                return candidate
        elif shutil.which(candidate):
            return shutil.which(candidate)
    return None


def _render_dom(url: str, chrome: str, timeout: int = 45) -> str:
    """Renderiza la página en headless y devuelve el DOM serializado.

    Chrome vuelca el DOM (--dump-dom) pero en páginas con streams activos
    el proceso no siempre termina: al agotar el plazo se mata el grupo de
    procesos entero y se conserva lo ya volcado, que es el DOM completo.
    """
    profile_dir = tempfile.mkdtemp(prefix="socialdl-chrome-")
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        f"--user-data-dir={profile_dir}",
        "--virtual-time-budget=15000",
        "--dump-dom",
        url,
    ]
    if os.environ.get("CHROME_NO_SANDBOX"):
        cmd.insert(1, "--no-sandbox")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    chunks: list[bytes] = []
    try:
        deadline = time.monotonic() + timeout
        fd = proc.stdout.fileno()
        while time.monotonic() < deadline:
            ready, _, _ = select.select([proc.stdout], [], [], 1.0)
            if ready:
                chunk = os.read(fd, 1 << 16)
                if not chunk:
                    break
                chunks.append(chunk)
                # El volcado del DOM acaba en </html>; no hay que esperar
                # a que Chrome salga (puede quedarse colgado con streams)
                if b"".join(chunks[-2:]).rstrip().endswith(b"</html>"):
                    break
            if proc.poll() is not None:
                break
    finally:
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
        proc.stdout.close()
        proc.wait()
        shutil.rmtree(profile_dir, ignore_errors=True)
    return b"".join(chunks).decode("utf-8", errors="replace")


def parse_video_versions(dom: str) -> list[dict]:
    """Extrae video_versions del DOM y deduplica por URL (conserva el mejor type)."""
    versions: list[dict] = []
    seen_urls: set[str] = set()
    for match in re.finditer(
        r'"video_versions"\s*:\s*(\[(?:[^\[\]]|\[[^\]]*\])*\])', dom
    ):
        try:
            entries = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        for entry in sorted(entries, key=lambda e: e.get("type") or 999):
            url = entry.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            versions.append({"type": entry.get("type") or 0, "url": url})
        if versions:
            break  # el primer bloque corresponde a la publicación principal
    return versions


def _parse_title(dom: str) -> str | None:
    m = re.search(r'property="og:title"\s+content="([^"]+)"', dom) or re.search(
        r'content="([^"]+)"\s+property="og:title"', dom
    )
    if m:
        return html.unescape(m.group(1))
    m = re.search(r'"username"\s*:\s*"([^"]{1,40})"', dom)
    return f"Vídeo de @{m.group(1)}" if m else None


def _parse_thumbnail(dom: str) -> str | None:
    m = re.search(r'property="og:image"\s+content="([^"]+)"', dom) or re.search(
        r'content="([^"]+)"\s+property="og:image"', dom
    )
    return html.unescape(m.group(1)) if m else None


def _shortcode(url: str) -> str:
    m = re.search(r"/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)", urlparse(url).path)
    return m.group(1) if m else "instagram"


def extract_info(url: str) -> dict | None:
    """Extrae info del vídeo vía navegador. None si no hay Chrome o no hay vídeo."""
    chrome = find_chrome()
    if not chrome:
        return None
    dom = _render_dom(url, chrome)
    versions = parse_video_versions(dom)
    if not versions:
        return None
    formats = [
        {
            "format_id": f"ig-{v['type']}",
            "ext": "mp4",
            "resolution": _TYPE_LABELS.get(v["type"], f"variante {v['type']}"),
            "height": 0,
            "filesize": None,
            "direct_url": v["url"],
        }
        for v in versions
    ]
    return {
        "title": _parse_title(dom) or "Vídeo de Instagram",
        "uploader": "",
        "thumbnail": _parse_thumbnail(dom),
        "duration": None,
        "webpage_url": url,
        "formats": formats,
    }


def download(url: str, format_id: str | None = None) -> tuple[str, str] | None:
    """Descarga el vídeo vía navegador. None si el fallback no puede extraer.

    Las URLs del CDN caducan, así que siempre se re-extraen en el momento
    de la descarga. Devuelve (ruta_del_archivo, nombre_para_el_usuario);
    el llamante elimina el directorio temporal tras servir el archivo.
    """
    info = extract_info(url)
    if not info:
        return None
    formats = info["formats"]
    chosen = next((f for f in formats if f["format_id"] == format_id), formats[0])

    safe_title = re.sub(r"[^\w\s.-]", "", info["title"])[:80].strip() or "video"
    filename = f"{safe_title} [{_shortcode(url)}].mp4"
    tmpdir = tempfile.mkdtemp(prefix="socialdl-")
    filepath = os.path.join(tmpdir, filename)

    request = urllib.request.Request(
        chosen["direct_url"], headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response, open(
            filepath, "wb"
        ) as out:
            shutil.copyfileobj(response, out)
    except OSError:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None

    if not os.path.getsize(filepath):
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None
    return filepath, filename
