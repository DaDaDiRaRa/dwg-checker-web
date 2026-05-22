"""
main.py — FastAPI 앱 진입점
uvicorn backend.main:app --reload 로 실행
"""
import logging
import logging.handlers
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import config
from backend.routers import jobs, settings

# 빌드된 React 정적 파일 경로 (프로덕션)
_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


# ── 로깅 설정 ────────────────────────────────────────────────────────────────
def _setup_logging() -> None:
    """콘솔 + 파일 로그 핸들러 설정."""
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger("AutoDWG")
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    # 콘솔
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # 파일 (10MB × 3 개 순환)
    fh = logging.handlers.RotatingFileHandler(
        config.LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    logging.getLogger("AutoDWG").info("AutoDWG 서버 시작 (EXTRACTOR=%s)", config.EXTRACTOR)
    yield
    logging.getLogger("AutoDWG").info("AutoDWG 서버 종료")


# ── FastAPI 앱 ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="AutoDWG Cross-Checker API",
    description="도면목록표 ↔ 개별 캐드 도면 자동 교차 검토",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: 로컬 개발(Vite dev 서버)에서만 필요. 프로덕션은 동일 origin이므로 무효.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://kw-ai-hub.pages.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록 (StaticFiles보다 먼저 등록해야 /api 경로가 우선함)
app.include_router(jobs.router)
app.include_router(settings.router)


@app.get("/health")
def health():
    return {"status": "ok", "extractor": config.EXTRACTOR}


# 프로덕션: 빌드된 React 앱을 서빙 (개발 중에는 dist 폴더가 없으므로 건너뜀)
if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
