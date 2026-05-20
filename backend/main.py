from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import httpx

from routing import generate_tour_options
from pois import get_pois
from weather import get_weather

app = FastAPI()

@app.get("/api/tours")
async def tours(lat: float, lon: float, duration_min: int = 60):
    try:
        options = await generate_tour_options(lat, lon, duration_min)
        return {"tours": options}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pois")
async def pois(lat: float, lon: float, radius_m: int = 5000):
    try:
        result = await get_pois(lat, lon, radius_m)
        return {"pois": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/weather")
async def weather(lat: float, lon: float):
    try:
        result = await get_weather(lat, lon)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health():
    return {"status": "ok"}

static_path = Path(__file__).parent / "static"
if static_path.exists():
    # Root-Level statische Dateien direkt servieren
    for static_file in ["sw.js", "registerSW.js", "manifest.webmanifest",
                        "icon-192.png", "icon-512.png"]:
        _path = static_path / static_file
        _headers = {"Cache-Control": "no-store"} if static_file == "sw.js" else {}
        app.add_api_route(
            f"/{static_file}",
            (lambda p=_path, h=_headers: lambda: FileResponse(p, headers=h))(),
            methods=["GET"]
        )

    app.mount("/assets", StaticFiles(directory=static_path / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        return FileResponse(static_path / "index.html")
