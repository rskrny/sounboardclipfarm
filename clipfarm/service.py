"""FastAPI service layer — wraps the pipeline with async job tracking.

Endpoints:
  POST /extract          Start an extraction job, returns job_id immediately.
  GET  /jobs/{job_id}    Full job record with live stage/progress (poll this).
  GET  /config           Supported providers, constraints, defaults.
  GET  /jobs/{job_id}/download  Stream the output WAV file when succeeded.

Job record shape (per codex contract):
  job_id, status, stage, progress_message, result, error, diagnostics,
  rights_status, provenance, source_detail
"""

from __future__ import annotations

import os
import threading
import uuid
from dataclasses import asdict
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .pipeline import run as pipeline_run

app = FastAPI(title="soundboardclipfarm", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store — sufficient for local single-user deployment
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


# ── Request / response models ─────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    movie: str
    quote: str
    output_path: str
    local_file: Optional[str] = None
    local_srt: Optional[str] = None
    sample_rate: int = 44100
    channels: Literal[1, 2] = 1
    padding_before_ms: int = 200
    padding_after_ms: int = 200
    language: str = "en"


# ── Job helpers ───────────────────────────────────────────────────────────────

def _new_job(job_id: str, req: ExtractRequest) -> dict:
    return {
        "job_id": job_id,
        "status": "queued",           # queued | running | succeeded | failed
        "stage": None,                # sourcing | transcript | matching | extraction
        "progress_message": "Job queued.",
        "result": None,               # ClipResult as dict when succeeded
        "error": None,                # error message string when failed
        "diagnostics": [],            # list of (stage, message) tuples as dicts
        "rights_status": None,        # policy from RightsInfo
        "provenance": None,
        "source_detail": None,
        "request": req.model_dump(),
    }


def _update_job(job_id: str, **kwargs) -> None:
    with _jobs_lock:
        _jobs[job_id].update(kwargs)


def _append_diagnostic(job_id: str, stage: str, message: str) -> None:
    with _jobs_lock:
        _jobs[job_id]["diagnostics"].append({"stage": stage, "message": message})


def _run_job(job_id: str, req: ExtractRequest) -> None:
    _update_job(job_id, status="running")

    def on_progress(stage: str, message: str) -> None:
        _update_job(job_id, stage=stage, progress_message=message)
        _append_diagnostic(job_id, stage, message)

    try:
        result = pipeline_run(
            title=req.movie,
            quote=req.quote,
            output_path=req.output_path,
            local_file=req.local_file,
            local_srt=req.local_srt,
            sample_rate=req.sample_rate,
            channels=req.channels,
            padding_before_ms=req.padding_before_ms,
            padding_after_ms=req.padding_after_ms,
            language=req.language,
            on_progress=on_progress,
        )
        result_dict = asdict(result)
        rights = result_dict.pop("rights", None)
        _update_job(
            job_id,
            status="succeeded",
            stage="done",
            progress_message="Clip extracted successfully.",
            result=result_dict,
            rights_status=rights["policy"] if rights else None,
            provenance=rights["provenance"] if rights else None,
            source_detail=rights["source_detail"] if rights else None,
        )
    except Exception as exc:
        _update_job(
            job_id,
            status="failed",
            error=str(exc),
            progress_message=f"Failed: {exc}",
        )
        _append_diagnostic(job_id, _jobs[job_id].get("stage") or "unknown", f"ERROR: {exc}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/extract", status_code=202)
def extract(req: ExtractRequest) -> dict:
    """Start an extraction job. Returns job_id for polling."""
    job_id = str(uuid.uuid4())
    job = _new_job(job_id, req)
    with _jobs_lock:
        _jobs[job_id] = job
    thread = threading.Thread(target=_run_job, args=(job_id, req), daemon=True)
    thread.start()
    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    """Full job record. Poll this endpoint to track live stage progress.

    Returns the complete record including diagnostics, rights provenance,
    and full ClipResult JSON on success — never a summary.
    """
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


@app.get("/jobs/{job_id}/download")
def download_clip(job_id: str) -> FileResponse:
    """Stream the output WAV file for a succeeded job."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job["status"] != "succeeded":
        raise HTTPException(status_code=409, detail=f"Job status is '{job['status']}', not succeeded.")
    output_path = job["result"]["output_path"]
    if not os.path.isfile(output_path):
        raise HTTPException(status_code=410, detail="Output file no longer exists on disk.")
    return FileResponse(
        path=output_path,
        media_type="audio/wav",
        filename=os.path.basename(output_path),
    )


@app.get("/config")
def get_config() -> dict:
    """Returns supported providers, subtitle sources, and technical constraints."""
    return {
        "providers": {
            "local_file": "User-provided local media file. Most reliable.",
            "internet_archive": "Public domain catalog. Only pre-1928 era titles.",
            "youtube": "yt-dlp YouTube search. CC-licensed content preferred.",
        },
        "subtitle_sources": {
            "local_srt": "User-provided .srt file.",
            "opensubtitles": "OpenSubtitles.com REST API (requires env vars).",
            "whisper": "Local faster-whisper transcription (optional install).",
        },
        "constraints": {
            "max_clip_duration_seconds": 14.9,
            "output_format": "WAV",
            "bit_depth": 16,
            "default_sample_rate": 44100,
            "supported_sample_rates": [8000, 16000, 22050, 44100, 48000],
        },
        "env_vars_required": {
            "OPENSUBTITLES_API_KEY": "For OpenSubtitles subtitle source",
            "OPENSUBTITLES_USER": "For OpenSubtitles subtitle source",
            "OPENSUBTITLES_PASS": "For OpenSubtitles subtitle source",
        },
    }


# ── Dev server entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("clipfarm.service:app", host="127.0.0.1", port=8000, reload=True)
