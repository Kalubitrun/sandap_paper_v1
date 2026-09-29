"""FastAPI server exposing the document engine to the web UI (Phase 6).

Run from the project root:
    uvicorn app.api.server:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api.service import (
    ApiError,
    analyze_document_bytes,
    generate_document_bytes,
)
from app.renderer import PaperSettings

log = logging.getLogger("vps.api")

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

app = FastAPI(title="Question Paper Formatter API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


def _friendly(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code,
                        content={"error": {"message": message, "code": code}})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    try:
        data = await file.read()
        return analyze_document_bytes(data, file.filename or "upload.docx")
    except ApiError as exc:
        return _friendly(exc.status_code, exc.message, exc.code)
    except Exception:
        log.exception("Unexpected /api/analyze failure")
        return _friendly(500, "Unable to read the question paper. "
                              "Please check that the DOCX file is valid.",
                         "internal_error")


@app.post("/api/generate")
async def generate(
    file: UploadFile = File(...),
    examination: str = Form(...),
    session: str = Form(...),
    class_name: str = Form(...),
    subject: str = Form(...),
    subject_code: str = Form(...),
    max_marks: str = Form(...),
    time: str = Form(...),
):
    try:
        try:
            settings = PaperSettings(
                examination=examination, session=session.strip(),
                class_name=class_name.strip(), subject=subject.strip(),
                subject_code=subject_code.strip(), max_marks=max_marks,
                time=time.strip(),
            )
        except ValueError:
            return _friendly(400, "Some required paper information is missing "
                                  "or invalid.", "invalid_settings")
        missing = [k for k, v in {
            "session": settings.session, "class": settings.class_name,
            "subject": settings.subject, "subject code": settings.subject_code,
            "time": settings.time}.items() if not str(v).strip()]
        if missing:
            return _friendly(400, "Some required paper information is missing: "
                                  + ", ".join(missing) + ".", "missing_settings")
        data = await file.read()
        blob, download_name = generate_document_bytes(
            data, file.filename or "upload.docx", settings)
        return Response(
            content=blob, media_type=DOCX_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{download_name}"',
                     "X-File-Name": download_name},
        )
    except ApiError as exc:
        return _friendly(exc.status_code, exc.message, exc.code)
    except Exception:
        log.exception("Unexpected /api/generate failure")
        return _friendly(500, "Question paper generation failed. "
                              "Please try again.", "internal_error")
