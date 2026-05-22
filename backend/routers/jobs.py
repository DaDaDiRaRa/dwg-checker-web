"""
routers/jobs.py — 검토 Job 관리 엔드포인트
POST   /api/jobs/create          DWG 파일들 + ROI JSON + 블록명 → job_id 반환 후 백그라운드 분석 시작
GET    /api/jobs/{job_id}/status  진행률 + 현재 파일명
GET    /api/jobs/{job_id}/log     SSE 실시간 로그 스트리밍
GET    /api/jobs/{job_id}/result  Excel 파일 다운로드
DELETE /api/jobs/{job_id}         취소
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from backend import config
from backend.dependencies import get_job_store, get_store_lock
from backend.models.job import JobState, JobStatus
from backend.models.schemas import JobCreateResponse, JobStatusResponse
from backend.services.roi import parse_xref_original
from backend.services.list_parser import parse_list_dwg
from backend.services.dwg_processor import run_multiprocess
from backend.services.report_writer import build_report

logger = logging.getLogger("AutoDWG")
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ── 백그라운드 분석 스레드 ────────────────────────────────────────────────────

def _run_job(job: JobState, xref_path: str, list_path: str, dwg_paths: List[str], block_name: str, slave_block_name: str, roi_cfg: dict) -> None:
    """별도 스레드에서 실행되는 분석 파이프라인."""
    try:
        job.status = JobStatus.RUNNING

        base_w = roi_cfg.get('base_w', 594.0)
        base_h = roi_cfg.get('base_h', 420.0)

        # XREF 원본 텍스트 스캔
        xref_texts = []
        if xref_path:
            job.add_log(f"[XREF] 도곽 원본 스캔 중: {Path(xref_path).name}")
            xref_texts = parse_xref_original(xref_path)

        # 도면목록표 파싱
        job.add_log(f"[LIST] 도면목록표 분석 중: {Path(list_path).name}")
        list_df = parse_list_dwg(list_path, block_name, roi_cfg, base_w, base_h, xref_texts)
        job.add_log(f"[LIST] 도면목록표 추출 완료: {len(list_df)}건")

        if job.cancel_event.is_set():
            job.status = JobStatus.CANCELLED
            job.add_log("[취소] 사용자 요청으로 중단되었습니다.")
            return

        # 개별 도면 멀티프로세싱 분석
        def progress_cb(current: int, total: int, filename: str) -> None:
            job.current = current
            job.total   = total
            job.current_file = filename
            if filename:
                job.add_log(f"   [{current}/{total}] {filename}")

        job.add_log(f"[CAD ] 개별 도면 {len(dwg_paths)}개 분석 시작...")
        dwg_df, view_df = run_multiprocess(
            target_paths     = dwg_paths,
            slave_block_name = slave_block_name or block_name,
            roi_cfg          = roi_cfg,
            base_w           = base_w,
            base_h           = base_h,
            xref_texts       = xref_texts,
            progress_cb      = progress_cb,
            cancel_event     = job.cancel_event,
        )

        if job.cancel_event.is_set():
            job.status = JobStatus.CANCELLED
            job.add_log("[취소] 사용자 요청으로 중단되었습니다.")
            return

        # Excel 리포트 생성
        result_path = str(config.RESULT_DIR / f"{job.job_id}_리포트.xlsx")
        job.add_log("[XLSX] 리포트 생성 중...")
        build_report(list_df, dwg_df, result_path, view_df if not view_df.empty else None)

        job.result_path = result_path
        job.status = JobStatus.DONE
        job.add_log(f"[완료] 리포트 생성 완료! 목록표 {len(list_df)}건 / 개별도면 {len(dwg_df)}건")

    except Exception:
        logger.exception("[Job %s] 분석 중 예외 발생", job.job_id)
        job.add_log(f"[오류] 분석 중 예외가 발생했습니다. 서버 로그를 확인하세요.")
        job.status = JobStatus.ERROR


# ── 엔드포인트 ───────────────────────────────────────────────────────────────

_ROI_REQUIRED_KEYS = {"base_w", "base_h", "num_roi", "title_roi", "scale_roi"}


@router.post("/create", response_model=JobCreateResponse, status_code=202)
async def create_job(
    xref_file:        UploadFile = File(...),
    list_file:        UploadFile = File(...),
    dwg_files:        List[UploadFile] = File(...),
    block_name:       str = Form(...),
    slave_block_name: str = Form(""),
    roi_config_json:  str = Form(...),
    job_store = Depends(get_job_store),
    store_lock = Depends(get_store_lock),
):
    """파일들을 업로드하고 분석 Job을 생성한다.

    - xref_file:       도곽 원본 DWG (XREF 스캔용)
    - list_file:       도면목록표 DWG
    - dwg_files:       개별 도면 DWG 목록
    - block_name:      도곽 블록명
    - slave_block_name: 개별 도면 전용 도곽명 (목록표와 다를 경우)
    - roi_config_json: ROI 설정 JSON 문자열 (클라이언트에서 직접 전송)
    """
    # ROI JSON 파싱 및 검증
    try:
        roi_cfg: dict = json.loads(roi_config_json)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"roi_config_json 파싱 오류: {e}")

    missing = _ROI_REQUIRED_KEYS - set(roi_cfg.keys())
    if missing:
        raise HTTPException(status_code=400, detail=f"ROI 설정에 필수 키 누락: {missing}")

    job_id = str(uuid.uuid4())
    job_dir = config.UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # 파일 저장
    async def _save(upload: UploadFile, dest: Path) -> str:
        dest.write_bytes(await upload.read())
        return str(dest)

    xref_path = await _save(xref_file, job_dir / xref_file.filename)
    list_path  = await _save(list_file, job_dir / list_file.filename)
    dwg_paths  = [await _save(f, job_dir / f.filename) for f in dwg_files]

    # Job 생성 및 저장
    job = JobState(job_id=job_id, total=len(dwg_paths))
    with store_lock:
        job_store[job_id] = job

    # 백그라운드 스레드에서 분석 시작
    thread = threading.Thread(
        target=_run_job,
        args=(job, xref_path, list_path, dwg_paths, block_name, slave_block_name, roi_cfg),
        daemon=True,
    )
    thread.start()

    logger.info("[Job %s] 생성 완료. 파일 %d개 분석 시작.", job_id, len(dwg_paths))
    return JobCreateResponse(job_id=job_id)


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_status(job_id: str, job_store=Depends(get_job_store)):
    """Job의 현재 진행 상태를 반환한다."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    return JobStatusResponse(
        job_id       = job.job_id,
        status       = job.status,
        current      = job.current,
        total        = job.total,
        current_file = job.current_file,
    )


@router.get("/{job_id}/log")
async def stream_log(job_id: str, job_store=Depends(get_job_store)):
    """SSE(Server-Sent Events)로 실시간 로그를 스트리밍한다.

    클라이언트는 EventSource API로 구독하며,
    Job이 완료/취소/오류 상태가 되면 스트림을 종료한다.
    """
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")

    async def event_generator():
        sent_index = 0  # 이미 전송한 로그 인덱스
        terminal_statuses = {JobStatus.DONE, JobStatus.CANCELLED, JobStatus.ERROR}

        while True:
            # 새로 추가된 로그 전송
            current_logs = job.logs
            while sent_index < len(current_logs):
                line = current_logs[sent_index].replace("\n", " ")
                yield f"data: {line}\n\n"
                sent_index += 1

            # Job 종료 상태이면 스트림 닫기
            if job.status in terminal_statuses and sent_index >= len(job.logs):
                yield f"event: done\ndata: {job.status.value}\n\n"
                break

            await asyncio.sleep(0.3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{job_id}/result")
def download_result(job_id: str, job_store=Depends(get_job_store)):
    """완성된 Excel 리포트를 다운로드한다."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if job.status != JobStatus.DONE:
        raise HTTPException(status_code=409, detail=f"Job이 아직 완료되지 않았습니다. (현재 상태: {job.status.value})")
    if not job.result_path or not os.path.exists(job.result_path):
        raise HTTPException(status_code=404, detail="결과 파일을 찾을 수 없습니다.")

    return FileResponse(
        path=job.result_path,
        filename="도면검토리포트_최종.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.delete("/{job_id}", status_code=204)
def cancel_job(job_id: str, job_store=Depends(get_job_store), store_lock=Depends(get_store_lock)):
    """실행 중인 Job을 취소한다."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job을 찾을 수 없습니다.")
    if job.status not in {JobStatus.PENDING, JobStatus.RUNNING}:
        raise HTTPException(status_code=409, detail=f"취소할 수 없는 상태입니다. (현재 상태: {job.status.value})")

    job.cancel_event.set()
    job.add_log("[취소] 취소 신호 전송됨. 현재 파일 처리 완료 후 중단됩니다.")
    return
