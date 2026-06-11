"""Aplicación FastAPI: API de descarga + frontend estático."""

import mimetypes
import os
import shutil

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.background import BackgroundTask

from app.downloader import DownloadError, download_video, get_video_info

app = FastAPI(title="Social Downloader")

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


class InfoRequest(BaseModel):
    url: str


@app.exception_handler(DownloadError)
async def download_error_handler(_request, exc: DownloadError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.post("/api/info")
def api_info(body: InfoRequest):
    return get_video_info(body.url)


@app.get("/api/download")
def api_download(url: str = Query(...), format_id: str | None = Query(None)):
    filepath, filename = download_video(url, format_id)
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    cleanup = BackgroundTask(shutil.rmtree, os.path.dirname(filepath), ignore_errors=True)
    return FileResponse(
        filepath,
        media_type=media_type,
        filename=filename,
        background=cleanup,
    )


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
