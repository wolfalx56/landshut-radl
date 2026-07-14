from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import httpx
from datetime import datetime
from uuid import uuid4

from routing import generate_tour_options
from pois import get_pois
from weather import get_weather

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_recordings = {}

@app.get("/api/tours")
async def tours(lat: float, lon: float, duration_min: int = 60):
    """Generiert 3 Tour-Optionen basierend auf Standort und gewünschter Dauer."""
    try:
        options = await generate_tour_options(lat, lon, duration_min)
        return {"tours": options}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pois")
async def pois(lat: float, lon: float, radius_m: int = 5000):
    """Liefert POIs (Biergärten, Werkstätten, Wasser) im Radius."""
    try:
        result = await get_pois(lat, lon, radius_m)
        return {"pois": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/weather")
async def weather(lat: float, lon: float):
    """Liefert 3-Tage-Wettervorschau für den Startpunkt."""
    try:
        result = await get_weather(lat, lon)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.post("/api/tours/recording/start")
async def start_recording(body: dict = Body(...)):
    try:
        tour_id = body.get("tour_id")
        mode = body.get("mode", "bike")
        start_lat = body.get("start_lat")
        start_lon = body.get("start_lon")

        recording_id = str(uuid4())
        active_recordings[recording_id] = {
            "tour_id": tour_id,
            "mode": mode,
            "start_lat": start_lat,
            "start_lon": start_lon,
            "timestamp": datetime.utcnow().isoformat(),
            "points": []
        }

        return {
            "status": "recording",
            "recording_id": recording_id,
            "timestamp": datetime.utcnow().isoformat(),
            "tour_data": active_recordings[recording_id]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tours/recording/stop")
async def stop_recording(body: dict = Body(...)):
    try:
        recording_id = body.get("recording_id")

        if recording_id not in active_recordings:
            raise HTTPException(status_code=404, detail="Recording not found")

        recording = active_recordings[recording_id]
        points = recording.get("points", [])

        stats = {
            "distance_km": round(len(points) * 0.1, 2),
            "duration_min": 30,
            "avg_speed": 20.0,
            "points_collected": len(points)
        }

        recording["status"] = "completed"
        recording["stats"] = stats

        return {
            "status": "completed",
            "stats": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/assets", StaticFiles(directory=static_path / "assets"), name="assets")

    app.mount("/maps", StaticFiles(directory=static_path / "maps"), name="maps")
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        return FileResponse(static_path / "index.html")
