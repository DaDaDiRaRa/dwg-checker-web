import axios from "axios";

const api = axios.create({ baseURL: "/" });

// ── 타입 정의 ─────────────────────────────────────────────────────────────────

export type JobStatus = "pending" | "running" | "done" | "cancelled" | "error";

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  current: number;
  total: number;
  current_file: string;
}

export interface ExtractorResponse {
  extractor: "ezdxf" | "vision";
}

// ── Jobs API ─────────────────────────────────────────────────────────────────

export async function createJob(
  xrefFile: File,
  listFile: File,
  dwgFiles: File[],
  blockName: string,
  slaveBlockName: string,
  roiConfig: object,
  onUploadProgress?: (percent: number) => void
): Promise<{ job_id: string }> {
  const fd = new FormData();
  fd.append("xref_file", xrefFile);
  fd.append("list_file", listFile);
  dwgFiles.forEach((f) => fd.append("dwg_files", f));
  fd.append("block_name", blockName);
  fd.append("slave_block_name", slaveBlockName);
  fd.append("roi_config_json", JSON.stringify(roiConfig));

  const res = await api.post<{ job_id: string }>("/api/jobs/create", fd, {
    onUploadProgress: (e) => {
      if (onUploadProgress && e.total) {
        onUploadProgress(Math.round((e.loaded / e.total) * 100));
      }
    },
  });
  return res.data;
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await api.get<JobStatusResponse>(`/api/jobs/${jobId}/status`);
  return res.data;
}

export function subscribeJobLog(
  jobId: string,
  onLog: (line: string) => void,
  onDone: (finalStatus: string) => void
): EventSource {
  const es = new EventSource(`/api/jobs/${jobId}/log`);
  es.onmessage = (e) => onLog(e.data as string);
  es.addEventListener("done", (e) => {
    onDone((e as MessageEvent).data as string);
    es.close();
  });
  return es;
}

export async function cancelJob(jobId: string): Promise<void> {
  await api.delete(`/api/jobs/${jobId}`);
}

export function getResultUrl(jobId: string): string {
  return `/api/jobs/${jobId}/result`;
}

// ── Settings API ─────────────────────────────────────────────────────────────

export async function getExtractor(): Promise<"ezdxf" | "vision"> {
  const res = await api.get<ExtractorResponse>("/api/settings/extractor");
  return res.data.extractor;
}

export async function setExtractor(
  extractor: "ezdxf" | "vision"
): Promise<"ezdxf" | "vision"> {
  const res = await api.patch<ExtractorResponse>("/api/settings/extractor", {
    extractor,
  });
  return res.data.extractor;
}
