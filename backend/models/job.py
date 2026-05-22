"""
models/job.py — Job 상태 모델
in-memory job_store의 단일 항목 구조.
"""
from __future__ import annotations
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class JobStatus(str, Enum):
    PENDING   = "pending"    # 생성 직후, 아직 시작 안 됨
    RUNNING   = "running"    # 분석 진행 중
    DONE      = "done"       # 완료 (Excel 다운로드 가능)
    CANCELLED = "cancelled"  # 사용자가 취소
    ERROR     = "error"      # 예외 발생


@dataclass
class JobState:
    job_id: str
    status: JobStatus = JobStatus.PENDING

    # 진행률
    current: int = 0      # 처리 완료 파일 수
    total: int = 0        # 전체 파일 수
    current_file: str = ""

    # 실시간 로그 버퍼 (SSE 스트리밍용)
    logs: List[str] = field(default_factory=list)

    # 완성된 Excel 파일 경로 (DONE 상태일 때만 유효)
    result_path: Optional[str] = None

    # 취소 요청 플래그 (dwg_processor가 폴링)
    cancel_event: threading.Event = field(default_factory=threading.Event)

    # SSE 구독자들에게 새 로그가 생겼음을 알리는 이벤트
    log_event: threading.Event = field(default_factory=threading.Event)

    def add_log(self, message: str) -> None:
        """로그 메시지 추가 후 SSE 구독자에게 알림."""
        self.logs.append(message)
        self.log_event.set()
        self.log_event.clear()
