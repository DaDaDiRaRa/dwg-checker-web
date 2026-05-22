# AutoDWG Cross-Checker — 프로젝트 컨텍스트

## 프로젝트 개요

도면목록표(DWG) ↔ 개별 CAD 도면(DWG) 자동 교차 검토 도구.
도면번호·명칭·축척 불일치 항목을 Excel 리포트로 출력한다.

**배포 URL:** `https://autodwg-checker-30350777436.asia-northeast3.run.app`
**허브 등록:** `https://kw-ai-hub.pages.dev` (APPS 배열에 카드 추가 완료)

---

## 스택

| 레이어 | 기술 |
|--------|------|
| 백엔드 | FastAPI (Python 3.11), uvicorn, ezdxf, openpyxl, pandas |
| 프론트엔드 | React + TypeScript, Vite, TailwindCSS |
| 배포 | Docker 멀티스테이지 빌드 → GCP Cloud Run (asia-northeast3) |
| CI/CD | GitHub Actions (main 브랜치 push → 자동 배포) |
| GCP 프로젝트 | `arch-diagnose` (번호: 30350777436) |

---

## 파일 구조

```
dwg-checker-web/
├── Dockerfile                  # 멀티스테이지: Node(React 빌드) → Python 런타임
├── .dockerignore
├── .gitignore                  # key.json, env.yaml 포함
├── docker-compose.yml          # 로컬 개발용
├── .env.example
├── deploy.sh                   # 수동 배포 스크립트 (참고용)
├── .github/workflows/deploy.yml  # GitHub Actions 자동 배포
├── backend/
│   ├── main.py                 # FastAPI 앱 진입점, StaticFiles 마운트
│   ├── config.py               # 환경변수 기반 설정
│   ├── dependencies.py
│   ├── routers/
│   │   ├── jobs.py             # POST /api/jobs/create 등
│   │   └── settings.py        # GET/PATCH /api/settings/extractor
│   └── services/
│       ├── dwg_processor.py
│       ├── roi.py
│       ├── list_parser.py
│       ├── report_writer.py
│       └── extractors/
│           ├── ezdxf_extractor.py
│           └── vision_extractor.py  # stub — 미구현
└── frontend/
    ├── src/
    │   ├── kunwon-tokens.css   # 건원 디자인 토큰 (색상·폰트·레이아웃)
    │   ├── index.css           # Tailwind base + 스크롤바 스타일
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── api/client.ts
    │   └── components/
    │       ├── DropZone.tsx
    │       ├── BlockSelector.tsx
    │       ├── JobProgress.tsx
    │       └── DownloadButton.tsx
    │       └── SettingsTab.tsx
    ├── tailwind.config.ts      # kw-* 색상 팔레트 (CSS 변수 매핑)
    └── DESIGN_SYSTEM.md
```

---

## 핵심 설계 결정

### ROI JSON 처리 방식
서버에 저장하지 않는다. 클라이언트(localStorage)에 캐시하고, Job 생성 시 `roi_config_json` Form 필드로 인라인 전송한다.

- 이유: Cloud Run은 재시작 시 파일시스템이 초기화되고, 다중 사용자가 같은 파일명을 올리면 덮어쓰기 충돌이 발생하기 때문.
- `POST /api/configs/upload` 엔드포인트는 제거됨.
- `BlockSelector.tsx`가 로컬 파일 선택 → localStorage 저장 → 다음 방문 시 자동 복원.

### Job 아키텍처
DWG 처리는 오래 걸리므로 비동기 Job 방식. 프론트엔드가 0.5초마다 상태 폴링 + SSE로 실시간 로그 수신.

```
POST /api/jobs/create  →  job_id 반환 (202)
GET  /api/jobs/{id}/status
GET  /api/jobs/{id}/log     ← SSE 스트리밍
GET  /api/jobs/{id}/result  ← Excel 다운로드
DELETE /api/jobs/{id}       ← 취소
```

### DWG 처리 흐름
1. 도곽 원본 DWG → XREF 텍스트 스캔 (`ezdxf`)
2. 도면목록표 DWG → 도면번호/제목 파싱
3. 개별 도면 DWG → ROI 블록에서 속성 추출 (멀티프로세싱)
4. 교차 비교 → Excel 리포트 생성

### CORS
`main.py`에 허용 origin 명시:
- `http://localhost:5173` (Vite 개발)
- `http://localhost:3000`
- `https://kw-ai-hub.pages.dev`

---

## 디자인 시스템

**토큰 파일:** `frontend/src/kunwon-tokens.css` (건원 CI 기반, 라이트 테마)

Tailwind에서 토큰을 사용하는 방식:
- `tailwind.config.ts`에 `kw-*` 색상 팔레트 등록 → CSS 변수 참조
- 컴포넌트에서 `bg-kw-accent`, `text-kw-muted` 등으로 사용
- 폰트: `font-kw` (Pretendard), `font-kw-mono` (JetBrains Mono)

주요 토큰:
| 토큰 | 값 | 용도 |
|------|----|------|
| `--color-accent` | `#e60012` | 건원 RED, 포인트 색 |
| `--color-bg-page` | `#f5f5f5` | 페이지 배경 |
| `--color-bg-surface` | `#ffffff` | 카드·패널 배경 |
| `--color-text-primary` | `#001623` | 기본 텍스트 |
| `--font-size-2xs` | `10px` | 배지 등 초소형 텍스트 |
| `--scrollbar-width` | `6px` | 스크롤바 너비 |
| `--scrollbar-radius` | `3px` | 스크롤바 라운드 |

---

## 미해결 사항

1. **ODA File Converter 미설치** — `Dockerfile` TODO 섹션 완성 필요. Linux `.deb` 패키지 확보 후 주석 해제. 미설치 시 DWG→DXF 변환 불가 (ezdxf는 DXF 직접 읽기 가능).
2. **Vision AI 추출 엔진** — `vision_extractor.py` stub 상태. 미구현.

---

## 배포

### 자동 배포 (일반)
```
git push origin main
# → GitHub Actions가 gcloud run deploy --source . 실행
```

### 수동 배포
```
gcloud run deploy autodwg-checker --source . --region asia-northeast3 --allow-unauthenticated --project arch-diagnose
```

### 환경변수 (Cloud Run)
| 변수 | 기본값 | 설명 |
|------|--------|------|
| `EXTRACTOR` | `ezdxf` | 추출 엔진 선택 |
| `ODA_EXEC_PATH` | `""` | ODA 실행 파일 경로 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `PORT` | `8080` | Cloud Run 주입값 |

---

## 로컬 개발

```
# 백엔드
cd dwg-checker-web
uvicorn backend.main:app --reload

# 프론트엔드 (별도 터미널)
cd frontend
npm install
npm run dev
# → http://localhost:5173 (Vite가 /api → :8000 프록시)
```
