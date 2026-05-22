# Design Audit — 하드코딩된 스타일 값 목록

분석 대상: `frontend/src/**/*.{tsx,ts,css}`
분석 기준: 토큰으로 교체 가능한 하드코딩 색상값·크기값·인라인 스타일

---

## 1. 교체 필요 항목

| 값 | 파일 | 줄 | 교체할 토큰 |
|---|---|---|---|
| `6px` (scrollbar width) | `src/index.css` | 11 | `var(--input-radius)` |
| `3px` (scrollbar thumb radius) | `src/index.css` | 18 | *(토큰 없음 — `--card-radius-sm: 6px`와 불일치, 3px 토큰 추가 권장)* |
| `text-[10px]` (배지 폰트) | `src/components/SettingsTab.tsx` | 75 | `var(--font-size-xs)` *(11px로 1px 차이)* |
| `filter: "brightness(1)"` | `src/components/DownloadButton.tsx` | 15 | `var(--transition-base)` 로 대체하거나 Tailwind `hover:brightness-90` 사용 |
| `filter: "brightness(0.88)"` | `src/components/DownloadButton.tsx` | 16–17 | 동일 — hover 효과를 CSS 클래스로 이동 권장 |

---

## 2. 동적 값 (토큰 교체 불필요)

| 값 | 파일 | 줄 | 이유 |
|---|---|---|---|
| `` style={{ width: `${uploadPct}%` }} `` | `src/App.tsx` | 213 | 런타임 계산값 |
| `` style={{ width: `${pct}%` }} `` | `src/components/JobProgress.tsx` | 90 | 런타임 계산값 |

---

## 3. 이미 토큰 사용 중 (정상)

| 값 | 파일 | 줄 | 비고 |
|---|---|---|---|
| `style={{ background: "var(--color-warning-bg)", color: "var(--color-warning)" }}` | `src/components/SettingsTab.tsx` | 76 | CSS 변수 직접 사용 — Tailwind arbitrary value 대신 인라인 스타일 사용한 것만 스타일 일관성 주의 |

---

## 4. 토큰 파일 내부 (정의값 — 변경 금지)

`src/kunwon-tokens.css` 내 모든 `#hex`, `px` 값은 토큰 정의 자체이므로 대상 아님.

---

## 5. 조치 우선순위

| 우선순위 | 항목 | 조치 |
|---------|------|------|
| 🔴 높음 | `DownloadButton.tsx` 인라인 `filter` | Tailwind `hover:brightness-90` 클래스로 교체 |
| 🟡 중간 | `SettingsTab.tsx` `text-[10px]` | `text-[length:var(--font-size-xs)]` 또는 토큰에 `10px` 추가 |
| 🟢 낮음 | `index.css` scrollbar `3px` | 토큰에 `--scrollbar-radius: 3px` 추가 후 교체 |
| 🟢 낮음 | `index.css` scrollbar `6px` | `var(--input-radius)` 로 교체 |
