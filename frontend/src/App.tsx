import { useCallback, useEffect, useRef, useState } from "react";
import DropZone from "./components/DropZone";
import BlockSelector from "./components/BlockSelector";
import JobProgress from "./components/JobProgress";
import DownloadButton from "./components/DownloadButton";
import SettingsTab from "./components/SettingsTab";
import { createJob, getJobStatus, JobStatus, JobStatusResponse } from "./api/client";

type AppTab = "checker" | "settings";

interface JobInfo extends JobStatusResponse {
  done: boolean;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<AppTab>("checker");

  // ── 입력 상태 ──────────────────────────────────────────────────────────────
  const [xrefFiles, setXrefFiles]   = useState<File[]>([]);
  const [listFiles, setListFiles]   = useState<File[]>([]);
  const [dwgFiles,  setDwgFiles]    = useState<File[]>([]);
  const [blockName, setBlockName]   = useState("");
  const [slaveBlock, setSlaveBlock] = useState("");
  const [roiConfig, setRoiConfig]   = useState<object | null>(null);

  // ── Job 상태 ───────────────────────────────────────────────────────────────
  const [uploading, setUploading]     = useState(false);
  const [uploadPct, setUploadPct]     = useState(0);
  const [submitError, setSubmitError] = useState("");
  const [job, setJob]                 = useState<JobInfo | null>(null);
  const pollRef                       = useRef<number | null>(null);

  // Job 상태 주기적 폴링 (0.5초)
  useEffect(() => {
    if (!job || job.done) return;

    const poll = async () => {
      try {
        const s = await getJobStatus(job.job_id);
        setJob((prev) => prev ? { ...prev, ...s } : prev);
        if (["done", "cancelled", "error"].includes(s.status)) {
          setJob((prev) => prev ? { ...prev, done: true } : prev);
        }
      } catch {
        // 일시적 네트워크 오류는 무시
      }
    };

    pollRef.current = window.setInterval(poll, 500);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [job?.job_id, job?.done]);

  const handleFinished = useCallback(() => {
    setJob((prev) => prev ? { ...prev, done: true } : prev);
  }, []);

  // ── 폼 제출 ────────────────────────────────────────────────────────────────
  const canSubmit =
    xrefFiles.length > 0 &&
    listFiles.length > 0 &&
    dwgFiles.length > 0 &&
    blockName !== "" &&
    roiConfig !== null &&
    !uploading;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitError("");
    setUploading(true);
    setUploadPct(0);
    try {
      const { job_id } = await createJob(
        xrefFiles[0], listFiles[0], dwgFiles, blockName, slaveBlock,
        roiConfig!,
        (pct) => setUploadPct(pct)
      );
      const initialStatus = await getJobStatus(job_id);
      setJob({ ...initialStatus, done: false });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "알 수 없는 오류";
      setSubmitError(`업로드 실패: ${msg}`);
    } finally {
      setUploading(false);
    }
  };

  const handleReset = () => {
    setJob(null);
    setXrefFiles([]);
    setListFiles([]);
    setDwgFiles([]);
    setSubmitError("");
  };

  // ── 렌더 ───────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-kw-bg text-kw-text font-kw">
      {/* 헤더 */}
      <header className="border-b border-kw-border bg-kw-surface px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div>
            <h1 className="text-lg font-bold tracking-tight text-kw-text">AutoDWG Cross-Checker</h1>
            <p className="text-xs text-kw-muted">도면목록표 ↔ 개별 캐드 도면 자동 교차 검토</p>
          </div>
          <nav className="flex gap-1">
            {(["checker", "settings"] as AppTab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`rounded-md px-4 py-1.5 text-sm transition-colors
                  ${activeTab === tab
                    ? "bg-kw-accent text-kw-bg"
                    : "text-kw-muted hover:text-kw-text hover:bg-kw-surface-alt"}`}
              >
                {tab === "checker" ? "도면 검토" : "설정"}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        {activeTab === "settings" ? (
          <SettingsTab />
        ) : job ? (
          /* ── Job 실행 뷰 ─────────────────────────────────────────── */
          <div className="space-y-6">
            <JobProgress
              jobId={job.job_id}
              status={job.status as JobStatus}
              current={job.current}
              total={job.total}
              currentFile={job.current_file}
              onFinished={handleFinished}
            />

            {job.done && job.status === "done" && (
              <div className="flex items-center gap-4 rounded-lg bg-kw-ok-bg border border-kw-ok-bd p-4">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-kw-ok">분석 완료!</p>
                  <p className="text-xs text-kw-muted mt-0.5">Excel 리포트가 준비되었습니다.</p>
                </div>
                <DownloadButton jobId={job.job_id} />
              </div>
            )}

            {job.done && job.status === "error" && (
              <div className="rounded-lg bg-kw-err-bg border border-kw-err-bd p-4">
                <p className="text-sm font-semibold text-kw-err">분석 중 오류가 발생했습니다.</p>
                <p className="text-xs text-kw-muted mt-0.5">로그 패널에서 상세 내용을 확인하세요.</p>
              </div>
            )}

            {job.done && (
              <button
                onClick={handleReset}
                className="text-sm text-kw-muted hover:text-kw-text underline"
              >
                새 검토 시작
              </button>
            )}
          </div>
        ) : (
          /* ── 업로드 폼 ────────────────────────────────────────────── */
          <div className="space-y-8">
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              {/* 왼쪽 열: 파일 업로드 */}
              <div className="space-y-5">
                <h2 className="text-sm font-semibold text-kw-muted uppercase tracking-wider">
                  파일 선택
                </h2>
                <DropZone
                  label="도곽 원본 DWG (XREF 스캔용)"
                  files={xrefFiles}
                  onChange={setXrefFiles}
                />
                <DropZone
                  label="도면목록표 DWG"
                  files={listFiles}
                  onChange={setListFiles}
                />
                <DropZone
                  label="개별 도면 DWG (복수 선택 가능)"
                  multiple
                  files={dwgFiles}
                  onChange={setDwgFiles}
                />
              </div>

              {/* 오른쪽 열: 블록 선택 + 제출 */}
              <div className="space-y-5">
                <h2 className="text-sm font-semibold text-kw-muted uppercase tracking-wider">
                  블록 설정
                </h2>
                <BlockSelector
                  blockName={blockName}
                  slaveBlockName={slaveBlock}
                  onBlockChange={setBlockName}
                  onSlaveChange={setSlaveBlock}
                  onConfigLoad={setRoiConfig}
                />

                {/* 업로드 진행률 */}
                {uploading && (
                  <div>
                    <div className="flex justify-between text-xs text-kw-muted mb-1">
                      <span>파일 업로드 중…</span>
                      <span>{uploadPct}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-kw-surface-alt overflow-hidden border border-kw-border">
                      <div
                        className="h-full bg-kw-accent transition-all duration-200"
                        style={{ width: `${uploadPct}%` }}
                      />
                    </div>
                  </div>
                )}

                {submitError && (
                  <p className="text-sm text-kw-err">{submitError}</p>
                )}

                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={!canSubmit}
                  className="w-full rounded-lg bg-kw-accent hover:bg-kw-accent-h disabled:bg-kw-input-dis disabled:text-kw-subtle
                    px-4 py-3 text-sm font-semibold text-kw-bg transition-colors disabled:cursor-not-allowed"
                >
                  {uploading ? "업로드 중…" : "검토 시작"}
                </button>

                {/* 요건 체크리스트 */}
                <ul className="space-y-1 text-xs text-kw-faint">
                  {[
                    ["도곽 원본 DWG", xrefFiles.length > 0],
                    ["도면목록표 DWG", listFiles.length > 0],
                    [`개별 도면 DWG (${dwgFiles.length}개)`, dwgFiles.length > 0],
                    ["ROI 설정 파일", roiConfig !== null],
                  ].map(([label, ok]) => (
                    <li key={label as string} className={ok ? "text-kw-ok" : ""}>
                      {ok ? "✔" : "○"} {label as string}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
