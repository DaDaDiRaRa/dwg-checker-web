# ══════════════════════════════════════════════════════════════════════════════
# Stage 1 — React 빌드
# ══════════════════════════════════════════════════════════════════════════════
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build          # → /app/frontend/dist


# ══════════════════════════════════════════════════════════════════════════════
# Stage 2 — Python 런타임 + 정적 파일 통합
# ══════════════════════════════════════════════════════════════════════════════
FROM python:3.11-slim AS runtime

WORKDIR /app

# 시스템 패키지
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# TODO: ODA File Converter (Linux) 설치
# ODA 공식 사이트(https://www.opendesign.com/guestfiles/oda_file_converter)에서
# Linux 패키지를 받아 아래 주석을 해제하고 경로를 맞추세요.
#
#   COPY ODAFileConverter_QA_lnxX64_8.3dll_23.9.deb /tmp/
#   RUN dpkg -i /tmp/ODAFileConverter_QA_lnxX64_8.3dll_23.9.deb
#   ENV ODA_EXEC_PATH=/usr/bin/ODAFileConverter
#
# 설치하지 않으면 DWG → DXF 변환 단계에서 오류가 발생합니다.

# Python 패키지
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 백엔드 소스
COPY backend/ /app/backend/

# Stage 1에서 빌드된 React 앱 복사 (FastAPI StaticFiles가 서빙)
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# 데이터 디렉토리
RUN mkdir -p /app/backend/data/configs \
             /app/backend/data/uploads \
             /app/backend/data/results \
             /app/logs

# ── 환경변수 기본값 ────────────────────────────────────────────────────────────
ENV CONFIG_DIR=/app/backend/data/configs \
    UPLOAD_DIR=/app/backend/data/uploads \
    RESULT_DIR=/app/backend/data/results \
    LOG_FILE=/app/logs/autodwg.log \
    LOG_LEVEL=INFO \
    EXTRACTOR=ezdxf \
    ODA_EXEC_PATH="" \
    PORT=8080

EXPOSE 8080

# Cloud Run은 PORT 환경변수를 주입함
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
