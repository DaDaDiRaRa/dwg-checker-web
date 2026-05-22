import { useEffect, useState } from "react";
import { getExtractor, setExtractor } from "../api/client";

export default function SettingsTab() {
  const [extractor, setExtractorState] = useState<"ezdxf" | "vision">("ezdxf");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getExtractor()
      .then(setExtractorState)
      .catch(() => setError("설정 로드 실패"))
      .finally(() => setLoading(false));
  }, []);

  const handleToggle = async (next: "ezdxf" | "vision") => {
    if (saving) return;
    setSaving(true);
    setError("");
    try {
      const saved = await setExtractor(next);
      setExtractorState(saved);
    } catch {
      setError("설정 저장 실패");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="text-sm text-gray-400">설정 로드 중…</div>;
  }

  return (
    <div className="space-y-6 max-w-md">
      <div>
        <h3 className="text-base font-semibold text-gray-200 mb-1">추출 엔진</h3>
        <p className="text-sm text-gray-400 mb-4">
          DWG 도면에서 텍스트를 추출하는 방식을 선택합니다.
        </p>

        <div className="flex gap-3">
          {/* ezdxf 옵션 */}
          <button
            type="button"
            disabled={saving}
            onClick={() => handleToggle("ezdxf")}
            className={`flex-1 rounded-lg border-2 p-4 text-left transition-colors
              ${extractor === "ezdxf"
                ? "border-blue-500 bg-blue-950/40"
                : "border-gray-600 hover:border-gray-400 bg-gray-800"}`}
          >
            <div className="font-semibold text-sm text-gray-100 mb-1">ezdxf</div>
            <div className="text-xs text-gray-400">
              Python 기반 DXF 파싱. 빠르고 안정적.
            </div>
            {extractor === "ezdxf" && (
              <div className="mt-2 text-xs text-blue-400 font-medium">현재 사용 중</div>
            )}
          </button>

          {/* Vision AI 옵션 */}
          <button
            type="button"
            disabled={saving}
            onClick={() => handleToggle("vision")}
            className={`flex-1 rounded-lg border-2 p-4 text-left transition-colors
              ${extractor === "vision"
                ? "border-purple-500 bg-purple-950/40"
                : "border-gray-600 hover:border-gray-400 bg-gray-800"}`}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="font-semibold text-sm text-gray-100">Vision AI</span>
              <span className="rounded-full bg-yellow-600/30 text-yellow-400 text-[10px] px-1.5 py-0.5 font-medium">
                준비 중
              </span>
            </div>
            <div className="text-xs text-gray-400">
              이미지 기반 AI 인식. 현재 개발 중입니다.
            </div>
            {extractor === "vision" && (
              <div className="mt-2 text-xs text-yellow-400 font-medium">
                ⚠ 분석 실행 시 오류가 발생합니다.
              </div>
            )}
          </button>
        </div>

        {error && <p className="text-xs text-red-400 mt-2">{error}</p>}
        {saving && <p className="text-xs text-gray-400 mt-2">저장 중…</p>}
      </div>
    </div>
  );
}
