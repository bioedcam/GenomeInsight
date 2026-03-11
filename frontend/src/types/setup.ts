/** Setup wizard types. */

export interface SetupStatus {
  needs_setup: boolean
  disclaimer_accepted: boolean
  has_databases: boolean
  has_samples: boolean
  data_dir: string
}

export interface DisclaimerData {
  title: string
  text: string
  accept_label: string
}

export interface AcceptDisclaimerResult {
  accepted: boolean
  accepted_at: string
}

export interface DetectExistingResult {
  existing_found: boolean
  has_config: boolean
  has_samples: boolean
  has_databases: boolean
  data_dir: string
}

export interface ImportBackupResult {
  success: boolean
  samples_restored: number
  config_restored: boolean
  message: string
}

// ── P1-19c: Storage path + disk space ──────────────────────────

export interface StorageInfoResult {
  data_dir: string
  free_space_bytes: number
  free_space_gb: number
  total_space_bytes: number
  total_space_gb: number
  status: 'ok' | 'warning' | 'blocked'
  message: string
  path_exists: boolean
  path_writable: boolean
}

export interface SetStoragePathResult {
  success: boolean
  data_dir: string
  free_space_gb: number
  status: 'ok' | 'warning' | 'blocked'
  message: string
}

// ── P1-19e: External service credentials ────────────────────────

export interface CredentialsData {
  pubmed_email: string
  ncbi_api_key: string
  omim_api_key: string
}

export interface SaveCredentialsResult {
  success: boolean
  message: string
}

// ── P1-19f: Download databases ──────────────────────────────────

export interface DatabaseStatus {
  name: string
  display_name: string
  description: string
  filename: string
  expected_size_bytes: number
  required: boolean
  phase: number
  downloaded: boolean
  file_size_bytes: number | null
}

export interface DatabaseListResult {
  databases: DatabaseStatus[]
  total_size_bytes: number
  downloaded_count: number
  total_count: number
}

export interface DownloadJobInfo {
  db_name: string
  job_id: string
}

export interface TriggerDownloadResult {
  session_id: string
  downloads: DownloadJobInfo[]
}

export interface DatabaseProgressEvent {
  db_name: string
  job_id: string
  status: 'pending' | 'running' | 'complete' | 'failed' | 'unknown'
  progress_pct: number
  message: string
  error: string | null
}

export interface DownloadProgressData {
  session_id: string
  databases: DatabaseProgressEvent[]
}

// ── P1-19g: Upload sample file ──────────────────────────────────

export interface IngestResult {
  sample_id: number
  job_id: string
  variant_count: number
  nocall_count: number
  file_format: string
}
