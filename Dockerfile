FROM python:3.12-slim

# ffmpeg: yt-dlp merges audio/video tracks. chromium: headless Instagram fallback. curl: healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl chromium \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY static/ ./static/

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
# Downloads go to /tmp (tempfile.mkdtemp), so no writable app dir / volume is needed.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://localhost:8000/ || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
