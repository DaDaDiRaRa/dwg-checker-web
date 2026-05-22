import { getResultUrl } from "../api/client";

interface Props {
  jobId: string;
}

export default function DownloadButton({ jobId }: Props) {
  const url = getResultUrl(jobId);

  return (
    <a
      href={url}
      download="도면검토리포트_최종.xlsx"
      className="inline-flex items-center gap-2 rounded-md bg-kw-ok hover:bg-kw-ok px-5 py-2.5 text-sm font-semibold text-white transition-colors"
      style={{ filter: "brightness(1)", }}
      onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.88)")}
      onMouseLeave={(e) => (e.currentTarget.style.filter = "brightness(1)")}
    >
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
      Excel 리포트 다운로드
    </a>
  );
}
