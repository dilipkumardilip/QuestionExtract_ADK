"""
server.py
---------
FastAPI wrapper around the qextract multi-agent pipeline.

Endpoints
---------
  POST /extract          — Upload a PDF or image; returns extracted JSON.
  GET  /results/{job_id} — Fetch a previously extracted result by job ID.
  GET  /image/{filename} — Serve a cropped image from images_output/.
  GET  /                 — Serve the debug UI (ui.html).
  GET  /health           — Health check.

Run
---
    pip install -r requirements.txt
    uvicorn server:app --reload --port 8001
"""

import json
import shutil
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agents.pipeline import run_pipeline
from agents.config import OUTPUT_DIR

# ── App init ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="qextract — Exam Question Extractor (ADK Multi-Agent)",
    description="Upload a scanned exam paper (PDF/PNG/JPG) and receive a "
                "structured JSON of all questions with cropped visual elements. "
                "Powered by Google ADK multi-agent system.",
    version="2.0.0",
)

# ── Directories ───────────────────────────────────────────────────────────────
UPLOAD_DIR   = Path("uploads").resolve()
RESULTS_DIR  = Path("results_cache").resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Static file mounts ────────────────────────────────────────────────────────
app.mount("/images", StaticFiles(directory=str(OUTPUT_DIR)), name="images")


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_ui() -> HTMLResponse:
    """Serve the debug UI."""
    ui_path = Path(__file__).parent / "ui.html"
    if not ui_path.is_file():
        raise HTTPException(status_code=404, detail="ui.html not found")
    return HTMLResponse(content=ui_path.read_text(encoding="utf-8"))


@app.post("/extract", summary="Extract questions from an exam paper")
async def extract(file: UploadFile = File(...)) -> JSONResponse:
    """
    Upload a PDF, PNG, or JPG exam paper.

    Returns a JSON object with:
    - ``job_id``    : unique identifier for this extraction run
    - ``filename``  : original upload filename
    - ``page_count``: number of pages processed
    - ``questions`` : flat list of extracted question objects
    - ``metadata``  : extraction metadata (model, counts)
    - ``error``     : null on success, error detail string on failure
    """
    # ── Validate file type ────────────────────────────────────────────────────
    allowed = {".pdf", ".png", ".jpg", ".jpeg"}
    suffix  = Path(file.filename or "").suffix.lower()

    if suffix not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{suffix}'. "
                   f"Accepted: {', '.join(sorted(allowed))}",
        )

    # ── Save upload ───────────────────────────────────────────────────────────
    job_id    = uuid.uuid4().hex
    save_name = f"{job_id}{suffix}"
    save_path = UPLOAD_DIR / save_name

    with save_path.open("wb") as dest:
        shutil.copyfileobj(file.file, dest)

    # ── Run pipeline ──────────────────────────────────────────────────────────
    error_detail: str | None = None
    questions: list[dict]    = []
    metadata: dict           = {}

    try:
        questions, metadata = run_pipeline(str(save_path))
    except Exception:
        error_detail = traceback.format_exc()

    # ── Cache result ──────────────────────────────────────────────────────────
    result_payload = {
        "job_id":     job_id,
        "filename":   file.filename,
        "page_count": metadata.get("page_count"),
        "questions":  questions,
        "metadata":   metadata,
        "error":      error_detail,
    }
    (RESULTS_DIR / f"{job_id}.json").write_text(
        json.dumps(result_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    status_code = 200 if error_detail is None else 500
    return JSONResponse(content=result_payload, status_code=status_code)


@app.get("/results/{job_id}", summary="Fetch a cached extraction result")
async def get_result(job_id: str) -> JSONResponse:
    """Return a previously extracted result by its job ID."""
    result_file = RESULTS_DIR / f"{job_id}.json"
    if not result_file.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"No result found for job_id='{job_id}'",
        )
    return JSONResponse(
        content=json.loads(result_file.read_text(encoding="utf-8"))
    )


@app.get("/image/{filename}", summary="Serve a cropped question/option image")
async def serve_image(filename: str) -> FileResponse:
    """Return a cropped PNG from images_output/ by its filename."""
    image_path = OUTPUT_DIR / filename
    if not image_path.is_file():
        raise HTTPException(
            status_code=404, detail=f"Image '{filename}' not found"
        )
    return FileResponse(str(image_path), media_type="image/png")


@app.get("/health", summary="Health check")
async def health() -> dict:
    """Simple liveness probe."""
    from agents.config import MODEL_PROVIDER
    return {
        "status": "ok",
        "service": "qextract",
        "version": "2.0.0",
        "model_provider": MODEL_PROVIDER,
    }
