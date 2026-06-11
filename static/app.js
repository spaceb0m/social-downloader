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

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
  result.hidden = true;
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
    btn.addEventListener("click", () => download(url, f.format_id, btn));
    formatsBox.appendChild(btn);
  }

  result.hidden = false;
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
