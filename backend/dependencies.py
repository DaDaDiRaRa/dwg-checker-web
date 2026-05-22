"""
dependencies.py — FastAPI 공통 의존성
job_store: 단일 서버용 in-memory Job 저장소 (싱글톤)
"""
from __future__ import annotations
import threading
from typing import Dict
from backend.models.job import JobState

# ── In-memory Job 저장소 ─────────────────────────────────────────────────────
# { job_id: JobState }
# 멀티스레드 접근 시 lock으로 보호한다.
_job_store: Dict[str, JobState] = {}
_store_lock = threading.Lock()


def get_job_store() -> Dict[str, JobState]:
    """라우터에서 Depends()로 주입받는 저장소 접근자."""
    return _job_store


def get_store_lock() -> threading.Lock:
    return _store_lock
