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
