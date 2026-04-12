"""FastAPI application — ElephantVoices Denoiser API."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import batch, demo, pipeline_visualize, process, result, status, upload

app = FastAPI(title="ElephantVoices Denoiser API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # localhost only — hackathon demo
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

# Mount demo assets at /static/demo for the frontend
_DEMO_DIR = Path(__file__).resolve().parents[1] / "data" / "outputs" / "demo"
_DEMO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/demo", StaticFiles(directory=str(_DEMO_DIR)), name="demo_static")


@app.get("/")
async def root() -> dict:
    return {"status": "ok", "service": "ElephantVoices Denoiser API"}
