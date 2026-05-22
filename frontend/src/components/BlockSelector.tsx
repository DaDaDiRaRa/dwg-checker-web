import React, { useEffect, useRef, useState } from "react";

const CACHE_KEY = "autodwg_roi_config";

interface CachedConfig {
  fileName: string;
  blockName: string;
  config: object;
}

interface Props {
  blockName: string;
  slaveBlockName: string;
  onBlockChange: (name: string) => void;
  onSlaveChange: (name: string) => void;
  onConfigLoad: (config: object) => void;
}

const REQUIRED_KEYS = ["base_w", "base_h", "num_roi", "title_roi", "scale_roi"];

export default function BlockSelector({
  blockName,
  slaveBlockName,
  onBlockChange,
  onSlaveChange,
  onConfigLoad,
}: Props) {
  const [cached, setCached] = useState<CachedConfig | null>(null);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  // 마운트 시 localStorage에서 저장된 config 복원
  useEffect(() => {
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return;
      const saved: CachedConfig = JSON.parse(raw);
      setCached(saved);
      onBlockChange(saved.blockName);
      onConfigLoad(saved.config);
    } catch {
      localStorage.removeItem(CACHE_KEY);
    }
  }, []);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");

    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const parsed = JSON.parse(ev.target?.result as string);
        const missing = REQUIRED_KEYS.filter((k) => !(k in parsed));
        if (missing.length > 0) {
          setError(`필수 키 누락: ${missing.join(", ")}`);
          return;
        }
        const name = file.name.replace(/\.json$/i, "");
        const saved: CachedConfig = { fileName: file.name, blockName: name, config: parsed };
        localStorage.setItem(CACHE_KEY, JSON.stringify(saved));
        setCached(saved);
        onBlockChange(name);
        onConfigLoad(parsed);
      } catch {
        setError("JSON 파싱 오류");
      }
    };
    reader.readAsText(file);
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="space-y-4">
      {/* ROI 파일 선택 */}
      <div>
        <label className="block text-sm font-medium text-kw-body mb-1">
          ROI 설정 파일 <span className="text-xs text-kw-faint">(SET_ROI.lsp 생성 .json)</span>
        </label>

        {cached ? (
          <div className="flex items-center gap-2 rounded-md bg-kw-surface border border-kw-border px-3 py-2">
            <span className="text-xs text-kw-ok font-medium shrink-0">저장됨</span>
            <span className="flex-1 text-sm text-kw-text truncate">{cached.fileName}</span>
            <span className="text-xs text-kw-faint shrink-0">블록: {cached.blockName}</span>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="shrink-0 text-xs text-kw-muted hover:text-kw-text underline"
            >
              변경
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="w-full rounded-md border border-dashed border-kw-border bg-kw-surface-alt hover:border-kw-accent
              text-kw-muted hover:text-kw-text text-sm py-2 px-3 text-center transition-colors"
          >
            파일 선택
          </button>
        )}

        <input
          ref={fileRef}
          type="file"
          accept=".json"
          onChange={handleFile}
          className="hidden"
        />
        {error && <p className="text-xs text-kw-err mt-1">{error}</p>}
        <p className="text-xs text-kw-faint mt-1">
          한 번 선택하면 브라우저에 저장되어 다음 방문 시 자동으로 불러옵니다.
        </p>
      </div>

      {/* 개별 도면 전용 블록명 (선택 사항) */}
      <div>
        <label className="block text-sm font-medium text-kw-body mb-1">
          도곽 블록명 — 개별 도면
          <span className="ml-1 text-xs text-kw-faint">목록표와 다를 때만 입력</span>
        </label>
        <input
          type="text"
          value={slaveBlockName}
          onChange={(e) => onSlaveChange(e.target.value)}
          placeholder={blockName || "목록표와 동일"}
          className="w-full rounded-md bg-kw-input border border-kw-border text-kw-text
            placeholder:text-kw-subtle px-3 py-2 text-sm focus:outline-none focus:border-kw-accent"
        />
      </div>
    </div>
  );
}
