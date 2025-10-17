"""Speech-to-text and text-to-speech endpoints."""

from __future__ import annotations

import os
from io import BytesIO
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from gtts import gTTS
from openai import OpenAI
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.dependencies import get_metrics_service, get_feature_flag_service
from app.api.deps import get_db_session, require_api_key
from app.db.models import PlanEnum, User
from app.settings import settings
from app.services.metrics_service import MetricsService
from app.services.feature_flags import FeatureFlagService

router = APIRouter(tags=["speech"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_AUDIO_SUFFIXES = {".m4a", ".mp3", ".wav", ".ogg"}


@router.post("/stt")
async def speech_to_text(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    api_key=Depends(require_api_key),
    session: Session = Depends(get_db_session),
    metrics: MetricsService = Depends(get_metrics_service),
    feature_flags: FeatureFlagService = Depends(get_feature_flag_service),
) -> dict:
    if not feature_flags.is_enabled("voice_mode", session=session):
        raise HTTPException(status_code=503, detail="Voice mode is disabled.")

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

    if len(contents) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file exceeds 10MB limit.")

    suffix = Path(file.filename or "audio.m4a").suffix or ".m4a"
    if suffix.lower() not in ALLOWED_AUDIO_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"Unsupported audio format: {suffix}")

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


class TextToSpeechRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    language: str = Field(default="en")


@router.post("/tts")
def text_to_speech(
    payload: TextToSpeechRequest,
    *,
    api_key=Depends(require_api_key),
    session: Session = Depends(get_db_session),
    metrics: MetricsService = Depends(get_metrics_service),
    feature_flags: FeatureFlagService = Depends(get_feature_flag_service),
) -> StreamingResponse:
    if not feature_flags.is_enabled("voice_mode", session=session):
        raise HTTPException(status_code=503, detail="Voice mode is disabled.")

    user = session.get(User, api_key.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.plan != PlanEnum.PRO:
        raise HTTPException(status_code=402, detail="Upgrade to Pro to use voice features.")

    try:
        tts = gTTS(text=payload.text, lang=payload.language)
        buffer = BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=502, detail=f"Failed to synthesize speech: {exc}") from exc

    metrics.track(
        "voice_tts",
        user_id=user.id,
        properties={
            "language": payload.language,
            "text_length": len(payload.text),
        },
    )

    headers = {"Content-Disposition": 'inline; filename="response.mp3"'}
    return StreamingResponse(buffer, media_type="audio/mpeg", headers=headers)
