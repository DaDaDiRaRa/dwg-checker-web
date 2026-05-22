import { useEffect, useRef, useState } from "react";
import { subscribeJobLog, cancelJob, JobStatus } from "../api/client";

interface Props {
  jobId: string;
  status: JobStatus;
  current: number;
  total: number;
  currentFile: string;
  onFinished: () => void;
}

export default function JobProgress({
  jobId, status, current, total, currentFile, onFinished,
}: Props) {
  const [logs, setLogs] = useState<string[]>([]);
  const [cancelling, setCancelling] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  // SSE 로그 구독
  useEffect(() => {
    const es = subscribeJobLog(
      jobId,
      (line) => setLogs((prev) => [...prev, line]),
      (_finalStatus) => onFinished()
    );
    return () => es.close();
  }, [jobId, onFinished]);

  // 새 로그 추가 시 자동 스크롤
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await cancelJob(jobId);
    } finally {
      setCancelling(false);
    }
  };

  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  const isRunning = status === "running" || status === "pending";

  const statusColor: Record<JobStatus, string> = {
    pending:   "text-kw-warn",
    running:   "text-kw-accent",
    done:      "text-kw-ok",
    cancelled: "text-kw-muted",
    error:     "text-kw-err",
  };

  const statusLabel: Record<JobStatus, string> = {
    pending:   "대기 중",
    running:   "분석 중",
    done:      "완료",
    cancelled: "취소됨",
    error:     "오류",
  };

  return (
    <div className="space-y-4">
      {/* 상태 헤더 */}
      <div className="flex items-center justify-between">
        <span className={`text-sm font-semibold ${statusColor[status]}`}>
          {statusLabel[status]}
        </span>
        {isRunning && (
          <button
            onClick={handleCancel}
            disabled={cancelling}
            className="text-xs text-kw-err hover:text-kw-err disabled:opacity-50"
          >
            {cancelling ? "취소 중…" : "분석 취소"}
          </button>
        )}
      </div>

      {/* 진행률 바 */}
      <div>
        <div className="flex justify-between text-xs text-kw-muted mb-1">
          <span>{currentFile || "준비 중…"}</span>
          <span>{current}/{total} ({pct}%)</span>
        </div>
        <div className="h-2 rounded-full bg-kw-surface-alt border border-kw-border overflow-hidden">
          <div
            className="h-full rounded-full bg-kw-accent transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* SSE 실시간 로그 */}
      <div className="log-panel h-56 overflow-y-auto rounded-md bg-kw-surface-alt border border-kw-border p-3 font-kw-mono text-xs text-kw-body space-y-0.5">
        {logs.map((line, i) => {
          const isError = line.includes("[오류]");
          const isDone  = line.includes("[완료]");
          const isWarn  = line.includes("[취소]");
          return (
            <div
              key={i}
              className={
                isError ? "text-kw-err" :
                isDone  ? "text-kw-ok" :
                isWarn  ? "text-kw-warn" : ""
              }
            >
              {line}
            </div>
          );
        })}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}
