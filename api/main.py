"""FastAPI application — ElephantVoices Denoiser API."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import batch, demo, pipeline_visualize, process, result, status, upload

app = FastAPI(title="ElephantVoices Denoiser API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(process.router)
app.include_router(status.router)
app.include_router(result.router)
app.include_router(batch.router)
app.include_router(demo.router)
app.include_router(pipeline_visualize.router)

_REPO_ROOT = Path(__file__).resolve().parents[1]

_DEMO_DIR = _REPO_ROOT / "data" / "outputs" / "demo"
_DEMO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/demo", StaticFiles(directory=str(_DEMO_DIR)), name="demo_static")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "ElephantVoices Denoiser API"}


_FRONTEND_DIST = _REPO_ROOT / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
        name="spa_assets",
    )

    @app.get("/")
    async def spa_root() -> FileResponse:
        return FileResponse(_FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    async def spa_catchall(full_path: str) -> FileResponse:
        if full_path.startswith(("api/", "static/", "assets/")):
            raise HTTPException(status_code=404)
        candidate = _FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    async def root_no_spa() -> dict:
        return {"status": "ok", "service": "ElephantVoices Denoiser API", "spa": "not built"}
