/** Sample types matching backend Pydantic models (P1-13, P1-16). */

export interface Sample {
  id: number
  name: string
  db_path: string
  file_format: string | null
  file_hash: string | null
  created_at: string | null
  updated_at: string | null
}

export interface IngestResult {
  sample_id: number
  job_id: string
  variant_count: number
  nocall_count: number
  file_format: string
}

export interface IngestProgress {
  job_id: string
  status: "pending" | "running" | "complete" | "failed" | "cancelled"
  progress_pct: number
  message: string
  error: string | null
}
