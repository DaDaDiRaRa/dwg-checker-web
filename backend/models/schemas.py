"""
models/schemas.py — FastAPI 요청/응답 Pydantic 스키마
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel
from backend.models.job import JobStatus


# ── Job 생성 응답 ────────────────────────────────────────────────────────────
class JobCreateResponse(BaseModel):
    job_id: str


# ── Job 상태 응답 ────────────────────────────────────────────────────────────
class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    current: int
    total: int
    current_file: str


# ── ROI 설정 목록 응답 ───────────────────────────────────────────────────────
class ConfigListResponse(BaseModel):
    block_names: List[str]


# ── 추출 방식 조회/변경 ──────────────────────────────────────────────────────
class ExtractorResponse(BaseModel):
    extractor: str   # "ezdxf" | "vision"


class ExtractorPatchRequest(BaseModel):
    extractor: str   # "ezdxf" | "vision"
