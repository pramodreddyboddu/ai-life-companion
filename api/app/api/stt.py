"""Speech-to-text endpoint using OpenAI Whisper."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from openai import OpenAI
from sqlalchemy.orm import Session

from app.api.dependencies import get_metrics_service
from app.api.deps import get_db_session, require_api_key
from app.db.models import PlanEnum, User
from app.settings import settings
from app.services.metrics_service import MetricsService

router = APIRouter(tags=["speech"])


@router.post("/stt")
async def speech_to_text(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    api_key=Depends(require_api_key),
    session: Session = Depends(get_db_session),
    metrics: MetricsService = Depends(get_metrics_service),
) -> dict:
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="Speech-to-text is not configured.")

    user = session.get(User, api_key.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.plan != PlanEnum.PRO:
        raise HTTPException(status_code=402, detail="Upgrade to Pro to use voice features.")

    client = OpenAI(api_key=settings.openai_api_key)

    try:
        contents = await file.read()
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=400, detail=f"Failed to read audio file: {exc}") from exc

    suffix = Path(file.filename or "audio.m4a").suffix or ".m4a"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(contents)
        tmp_path = Path(tmp_file.name)

    try:
        with tmp_path.open("rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language,
            )
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=502, detail=f"Failed to transcribe audio: {exc}") from exc
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    metrics.track(
        "voice_used",
        user_id=user.id,
        properties={
            "language": language,
            "filename": file.filename,
        },
    )
    return {"text": transcription.text}
