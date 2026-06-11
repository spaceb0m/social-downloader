const form = document.getElementById("url-form");
const input = document.getElementById("url-input");
const fetchBtn = document.getElementById("fetch-btn");
const btnLabel = fetchBtn.querySelector(".btn-label");
const spinner = fetchBtn.querySelector(".spinner");
const errorBox = document.getElementById("error");
const result = document.getElementById("result");
const thumbnail = document.getElementById("thumbnail");
const videoTitle = document.getElementById("video-title");
const videoDetails = document.getElementById("video-details");
const formatsBox = document.getElementById("formats");
const downloadNote = document.getElementById("download-note");

function setLoading(loading) {
  fetchBtn.disabled = loading;
  spinner.hidden = !loading;
  btnLabel.textContent = loading ? "Buscando…" : "Obtener vídeo";
}

function showError(message, keepResult = false) {
  errorBox.textContent = message;
  errorBox.hidden = false;
  if (!keepResult) result.hidden = true;
}

function isInstagramUrl(url) {
  return url.includes("instagram.com") || url.includes("instagr.am");
}

function formatDuration(seconds) {
  if (!seconds) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")} min`;
}

function formatSize(bytes) {
  if (!bytes) return "";
  const mb = bytes / (1024 * 1024);
  return mb >= 1 ? `~${mb.toFixed(1)} MB` : `~${(bytes / 1024).toFixed(0)} KB`;
}

function renderResult(info, url) {
  errorBox.hidden = true;

  if (info.thumbnail) {
    thumbnail.src = info.thumbnail;
    thumbnail.hidden = false;
  } else {
    thumbnail.hidden = true;
  }

  videoTitle.textContent = info.title;
  const details = [info.uploader, formatDuration(info.duration)]
    .filter(Boolean)
    .join(" · ");
  videoDetails.textContent = details;

  formatsBox.innerHTML = "";
  const formats = info.formats.length
    ? info.formats
    : [{ format_id: "", resolution: "Mejor calidad", ext: "mp4", filesize: null }];

  for (const f of formats) {
    const btn = document.createElement("button");
    const label = [f.resolution, f.ext.toUpperCase(), formatSize(f.filesize)]
      .filter(Boolean)
      .join(" · ");
    btn.innerHTML = `<span>${label}</span><span class="dl-icon">⬇ Descargar</span>`;
    btn.addEventListener("click", () => {
      if (f.direct_url) {
        downloadDirect(f.direct_url, safeFilename(info.title, f.resolution, f.ext));
      } else if (!isInstagramUrl(url)) {
        // Sin direct_url el servidor tendría que hacer de proxy, y la CDN de X
        // se lo bloquea (403): mejor un error claro que una página JSON
        showError(
          "Este vídeo de X solo está disponible en streaming y no se puede " +
            "descargar directamente desde el navegador.",
          true
        );
      } else {
        download(url, f.format_id, btn);
      }
    });
    formatsBox.appendChild(btn);
  }

  result.hidden = false;
}

function safeFilename(title, resolution, ext) {
  const cleaned = (title || "video")
    .replace(/[\\/:*?"<>|]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
  // Spread por code-points: slice() de string partiría emojis por la mitad
  const base = [...cleaned].slice(0, 80).join("").trim() || "video";
  const res = resolution ? ` [${resolution}]` : "";
  return `${base}${res}.${ext || "mp4"}`;
}

const DOWNLOAD_NOTE_DEFAULT = downloadNote.textContent;

function setFormatsDisabled(disabled) {
  for (const b of formatsBox.querySelectorAll("button")) b.disabled = disabled;
}

// La CDN de X devuelve 403 a las IPs de datacenter, así que el servidor no
// puede hacer de proxy: el navegador descarga el archivo directamente
// (la CDN envía access-control-allow-origin: *, que permite el fetch).
async function downloadDirect(directUrl, filename) {
  setFormatsDisabled(true);
  downloadNote.hidden = false;
  errorBox.hidden = true;

  try {
    // Sin no-referrer la CDN de X devuelve 403 (protección anti-hotlink)
    const res = await fetch(directUrl, { referrerPolicy: "no-referrer" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    let blob;
    if (res.body && res.body.getReader) {
      const total = Number(res.headers.get("Content-Length")) || 0;
      const reader = res.body.getReader();
      const chunks = [];
      let received = 0;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        received += value.length;
        const mb = (received / 1048576).toFixed(1);
        downloadNote.textContent = total
          ? `Descargando… ${mb} MB de ${(total / 1048576).toFixed(1)} MB`
          : `Descargando… ${mb} MB`;
      }
      blob = new Blob(chunks, { type: "video/mp4" });
    } else {
      blob = await res.blob();
    }

    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    // Safari puede abortar el guardado si se revoca en la misma tarea
    setTimeout(() => URL.revokeObjectURL(blobUrl), 30000);
  } catch {
    showError(
      "No se ha podido descargar el vídeo directamente desde X. " +
        "Vuelve a obtener el vídeo e inténtalo de nuevo.",
      true
    );
  } finally {
    setFormatsDisabled(false);
    downloadNote.hidden = true;
    downloadNote.textContent = DOWNLOAD_NOTE_DEFAULT;
  }
}

function download(url, formatId, btn) {
  const params = new URLSearchParams({ url });
  if (formatId) params.set("format_id", formatId);

  btn.disabled = true;
  downloadNote.hidden = false;

  // Navegar al endpoint hace que el navegador gestione la descarga
  window.location.href = `/api/download?${params.toString()}`;

  setTimeout(() => {
    btn.disabled = false;
    downloadNote.hidden = true;
  }, 8000);
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = input.value.trim();
  if (!url) return;

  setLoading(true);
  errorBox.hidden = true;
  result.hidden = true;

  try {
    const res = await fetch("/api/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (!res.ok) {
      showError(data.detail || "Se ha producido un error inesperado.");
      return;
    }
    renderResult(data, url);
  } catch {
    showError("No se ha podido conectar con el servidor. Inténtalo de nuevo.");
  } finally {
    setLoading(false);
  }
});
