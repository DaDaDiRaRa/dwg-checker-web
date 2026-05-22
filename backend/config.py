"""
config.py — 전역 설정값
환경변수 또는 기본값으로 동작. 운영 환경에서는 .env 파일로 재정의한다.
"""
import os
from pathlib import Path

# ── 기본 경로 ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

# ROI JSON 파일 저장 폴더 (POST /api/configs/upload 업로드 목적지)
# Cloud Run 주의: 인스턴스가 재시작되면 이 폴더 내용이 초기화됩니다.
# 영속성이 필요하면 Cloud Storage FUSE 마운트 또는 GCS_CONFIG_BUCKET 환경변수를 추가하세요.
CONFIG_DIR = Path(os.getenv("CONFIG_DIR", str(BASE_DIR / "data" / "configs")))

# 업로드된 DWG 임시 파일 폴더
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads")))

# 완성된 Excel 리포트 저장 폴더
RESULT_DIR = Path(os.getenv("RESULT_DIR", str(BASE_DIR / "data" / "results")))

# 폴더가 없으면 자동 생성
for _dir in (CONFIG_DIR, UPLOAD_DIR, RESULT_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ── 추출 엔진 선택 ──────────────────────────────────────────────────────────
# "ezdxf"  → services/extractors/ezdxf_extractor.py (기본값, 현재 동작)
# "vision" → services/extractors/vision_extractor.py (준비 중 stub)
EXTRACTOR: str = os.getenv("EXTRACTOR", "ezdxf")

# ── 로그 설정 ───────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = os.getenv("LOG_FILE", str(BASE_DIR / "data" / "autodwg.log"))

# ── ODA File Converter 경로 (Linux/Windows 자동 탐색용) ─────────────────────
# Dockerfile에서 ODA 설치 후 경로를 이 변수로 주입하면 된다.
ODA_EXEC_PATH: str = os.getenv("ODA_EXEC_PATH", "")
