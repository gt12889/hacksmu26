"""FastAPI application — ElephantVoices Denoiser API."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import batch, process, result, status, upload

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


@app.get("/")
async def root() -> dict:
    return {"status": "ok", "service": "ElephantVoices Denoiser API"}
