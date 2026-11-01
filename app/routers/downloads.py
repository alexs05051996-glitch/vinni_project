"""Эндпоинты блока «Скачать»."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.config import BASE_DIR, IOS_CLIENTS
from app.templating import render

router = APIRouter(tags=["downloads"])

DOWNLOADS_DIR = BASE_DIR / "static" / "downloads"


@router.get("/download/android")
def download_android():
    path = DOWNLOADS_DIR / "v2rayNG.apk"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    # MIME-тип заставляет Android сразу предложить установку пакета
    return FileResponse(
        path,
        media_type="application/vnd.android.package-archive",
        filename="v2rayNG.apk",
    )


@router.get("/download/windows")
def download_windows():
    path = DOWNLOADS_DIR / "v2rayN-windows.zip"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(
        path,
        media_type="application/zip",
        filename="v2rayN-windows.zip",
    )


@router.get("/download/ios")
def download_ios(request: Request):
    # Страница-список iOS-клиентов (Streisand, V2Box, FoXray) — без принудительных редиректов
    return render(request, "download_ios.html", {"ios_clients": IOS_CLIENTS})
