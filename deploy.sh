#!/usr/bin/env bash
# deploy.sh — Google Cloud Run 배포 스크립트
#
# 사전 준비:
#   1. gcloud CLI 설치 및 로그인: gcloud auth login
#   2. 프로젝트 설정:             gcloud config set project <PROJECT_ID>
#   3. API 활성화:
#        gcloud services enable run.googleapis.com artifactregistry.googleapis.com
#
# 사용법:
#   chmod +x deploy.sh
#   ./deploy.sh

set -euo pipefail

# ── 변수 설정 (필요 시 수정) ─────────────────────────────────────────────────
PROJECT_ID=$(gcloud config get-value project)
REGION="asia-northeast3"           # 서울 리전
REPO="autodwg"                     # Artifact Registry 레포지토리 이름
SERVICE="autodwg-checker"          # Cloud Run 서비스 이름
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/app"

echo "=== AutoDWG Cloud Run 배포 ==="
echo "프로젝트: ${PROJECT_ID}"
echo "리전:     ${REGION}"
echo "이미지:   ${IMAGE}"
echo ""

# ── 1. Artifact Registry 레포지토리 생성 (최초 1회) ─────────────────────────
if ! gcloud artifacts repositories describe "${REPO}" \
    --location="${REGION}" &>/dev/null; then
  echo "[1/4] Artifact Registry 레포지토리 생성..."
  gcloud artifacts repositories create "${REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="AutoDWG Cross-Checker"
else
  echo "[1/4] Artifact Registry 레포지토리 이미 존재, 건너뜀."
fi

# ── 2. Docker 빌드 ──────────────────────────────────────────────────────────
echo "[2/4] Docker 이미지 빌드 중..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker build --platform linux/amd64 -t "${IMAGE}:latest" .

# ── 3. 이미지 푸시 ──────────────────────────────────────────────────────────
echo "[3/4] 이미지 푸시 중..."
docker push "${IMAGE}:latest"

# ── 4. Cloud Run 배포 ────────────────────────────────────────────────────────
echo "[4/4] Cloud Run 배포 중..."
gcloud run deploy "${SERVICE}" \
  --image="${IMAGE}:latest" \
  --region="${REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2 \
  --timeout=600 \
  --concurrency=10 \
  --set-env-vars="EXTRACTOR=ezdxf,LOG_LEVEL=INFO" \
  --port=8080

echo ""
echo "=== 배포 완료 ==="
SERVICE_URL=$(gcloud run services describe "${SERVICE}" \
  --region="${REGION}" --format="value(status.url)")
echo "서비스 URL: ${SERVICE_URL}"
echo ""
echo "주의: ODA File Converter가 설치되지 않은 이미지는 DWG→DXF 변환이 불가합니다."
echo "      Dockerfile의 TODO 섹션을 참고하여 ODA를 포함시키거나,"
echo "      DXF 파일로 변환한 뒤 업로드하세요."
