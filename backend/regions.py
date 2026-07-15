"""Region-Downloader: GPS -> pmtiles extract -> Region-PMTiles."""
import asyncio
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

MAPS_DIR = Path("/maps")
META_FILE = MAPS_DIR / "regions.json"
PLANET_URL = "https://data.source.coop/protomaps/openstreetmap/v4.pmtiles"
RADIUS_KM = 30
MAX_REGIONS = 4          # ohne Heimatregion

# job_id -> {"status": "running|done|error", "detail": str, "region": str}
jobs: dict[str, dict] = {}


def _load_meta() -> dict:
    if META_FILE.exists():
        return json.loads(META_FILE.read_text())
    return {"regions": []}


def _save_meta(meta: dict) -> None:
    META_FILE.write_text(json.dumps(meta, indent=2, ensure_ascii=False))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "region"


def _bbox(lat: float, lon: float, radius_km: float = RADIUS_KM) -> tuple:
    """Quadratischer bbox um lat/lon. Laengengrade werden Richtung Pol enger."""
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * math.cos(math.radians(lat)))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def list_regions() -> list[dict]:
    meta = _load_meta()
    out = []
    for r in meta["regions"]:
        f = MAPS_DIR / r["file"]
        out.append({**r, "exists": f.exists(),
                    "size_mb": round(f.stat().st_size / 1e6, 1) if f.exists() else 0})
    return out


def evict_candidate() -> dict | None:
    """Aelteste nicht-Heimat-Region (LRU). None, wenn noch Platz."""
    regions = [r for r in _load_meta()["regions"] if not r.get("is_home")]
    if len(regions) < MAX_REGIONS:
        return None
    return sorted(regions, key=lambda r: r.get("last_used") or "")[0]


def touch_region(name: str) -> bool:
    meta = _load_meta()
    for r in meta["regions"]:
        if r["name"] == name:
            r["last_used"] = _now()
            _save_meta(meta)
            return True
    return False


def delete_region(name: str) -> bool:
    meta = _load_meta()
    keep = []
    found = False
    for r in meta["regions"]:
        if r["name"] == name and not r.get("is_home"):
            (MAPS_DIR / r["file"]).unlink(missing_ok=True)
            found = True
        else:
            keep.append(r)
    meta["regions"] = keep
    _save_meta(meta)
    return found


async def _run_extract(job_id: str, name: str, lat: float, lon: float) -> None:
    file = f"region-{_slug(name)}.pmtiles"
    target = MAPS_DIR / file
    w, s, e, n = _bbox(lat, lon)
    try:
        cmd = ["/usr/local/bin/pmtiles", "extract", PLANET_URL, str(target),
               f"--bbox={w:.4f},{s:.4f},{e:.4f},{n:.4f}"]
        print(f"[regions] starte: {' '.join(cmd)}", flush=True)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        out = (stderr.decode() + stdout.decode()).strip()
        print(f"[regions] rc={proc.returncode} out={out[-800:]}", flush=True)
        if proc.returncode != 0:
            jobs[job_id] = {"status": "error",
                            "detail": out[-400:] or f"rc={proc.returncode}, keine Ausgabe",
                            "region": name}
            target.unlink(missing_ok=True)
            return
        if not target.exists() or target.stat().st_size < 100_000:
            jobs[job_id] = {"status": "error",
                            "detail": "Datei zu klein - Extract fehlgeschlagen",
                            "region": name}
            target.unlink(missing_ok=True)
            return

        meta = _load_meta()
        meta["regions"] = [r for r in meta["regions"] if r["name"] != name]
        meta["regions"].append({
            "name": name, "file": file, "bbox": [w, s, e, n],
            "lat": lat, "lon": lon, "radius_km": RADIUS_KM,
            "created": _now(), "last_used": _now(), "is_home": False,
        })
        _save_meta(meta)
        jobs[job_id] = {"status": "done", "detail": file, "region": name}
    except Exception as exc:
        import traceback; traceback.print_exc()
        jobs[job_id] = {"status": "error",
                        "detail": f"{type(exc).__name__}: {exc}", "region": name}
        target.unlink(missing_ok=True)


def start_extract(name: str, lat: float, lon: float) -> str:
    job_id = str(uuid4())
    jobs[job_id] = {"status": "running", "detail": "", "region": name}
    asyncio.create_task(_run_extract(job_id, name, lat, lon))
    return job_id


def job_status(job_id: str) -> dict | None:
    return jobs.get(job_id)
