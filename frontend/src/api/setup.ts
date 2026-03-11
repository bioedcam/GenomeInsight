/** API hooks for the setup wizard. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  AcceptDisclaimerResult,
  CredentialsData,
  DatabaseListResult,
  DetectExistingResult,
  DisclaimerData,
  ImportBackupResult,
  SaveCredentialsResult,
  SetStoragePathResult,
  SetupStatus,
  StorageInfoResult,
  TriggerDownloadResult,
} from '@/types/setup'

const SETUP_STATUS_KEY = ['setup', 'status'] as const
const DISCLAIMER_KEY = ['setup', 'disclaimer'] as const
const DETECT_EXISTING_KEY = ['setup', 'detect-existing'] as const

async function fetchSetupStatus(): Promise<SetupStatus> {
  const res = await fetch('/api/setup/status')
  if (!res.ok) throw new Error(`Setup status failed: ${res.status}`)
  return res.json()
}

async function fetchDisclaimer(): Promise<DisclaimerData> {
  const res = await fetch('/api/setup/disclaimer')
  if (!res.ok) throw new Error(`Disclaimer fetch failed: ${res.status}`)
  return res.json()
}

async function postAcceptDisclaimer(): Promise<AcceptDisclaimerResult> {
  const res = await fetch('/api/setup/accept-disclaimer', { method: 'POST' })
  if (!res.ok) throw new Error(`Accept disclaimer failed: ${res.status}`)
  return res.json()
}

export function useSetupStatus() {
  return useQuery({
    queryKey: SETUP_STATUS_KEY,
    queryFn: fetchSetupStatus,
    staleTime: 0,
  })
}

export function useDisclaimer() {
  return useQuery({
    queryKey: DISCLAIMER_KEY,
    queryFn: fetchDisclaimer,
    staleTime: Infinity,
  })
}

export function useAcceptDisclaimer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: postAcceptDisclaimer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SETUP_STATUS_KEY })
    },
  })
}

// ── P1-19b: Import from backup ──────────────────────────────────

async function fetchDetectExisting(): Promise<DetectExistingResult> {
  const res = await fetch('/api/setup/detect-existing')
  if (!res.ok) throw new Error(`Detect existing failed: ${res.status}`)
  return res.json()
}

async function postImportBackup(file: File): Promise<ImportBackupResult> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch('/api/setup/import-backup', {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail || `Import failed: ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

export function useDetectExisting() {
  return useQuery({
    queryKey: DETECT_EXISTING_KEY,
    queryFn: fetchDetectExisting,
    staleTime: 0,
  })
}

export function useImportBackup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: postImportBackup,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SETUP_STATUS_KEY })
      queryClient.invalidateQueries({ queryKey: DETECT_EXISTING_KEY })
    },
  })
}

// ── P1-19c: Storage path + disk space ──────────────────────────

const STORAGE_INFO_KEY = ['setup', 'storage-info'] as const

async function fetchStorageInfo(): Promise<StorageInfoResult> {
  const res = await fetch('/api/setup/storage-info')
  if (!res.ok) throw new Error(`Storage info failed: ${res.status}`)
  return res.json()
}

async function postSetStoragePath(path: string): Promise<SetStoragePathResult> {
  const res = await fetch('/api/setup/set-storage-path', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail || `Set storage path failed: ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

export function useStorageInfo() {
  return useQuery({
    queryKey: STORAGE_INFO_KEY,
    queryFn: fetchStorageInfo,
    staleTime: 0,
  })
}

export function useSetStoragePath() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: postSetStoragePath,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: STORAGE_INFO_KEY })
      queryClient.invalidateQueries({ queryKey: SETUP_STATUS_KEY })
    },
  })
}

// ── P1-19e: External service credentials ────────────────────────

const CREDENTIALS_KEY = ['setup', 'credentials'] as const

async function fetchCredentials(): Promise<CredentialsData> {
  const res = await fetch('/api/setup/credentials')
  if (!res.ok) throw new Error(`Credentials fetch failed: ${res.status}`)
  return res.json()
}

async function postSaveCredentials(data: CredentialsData): Promise<SaveCredentialsResult> {
  const res = await fetch('/api/setup/credentials', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail || `Save credentials failed: ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

export function useCredentials() {
  return useQuery({
    queryKey: CREDENTIALS_KEY,
    queryFn: fetchCredentials,
    staleTime: 0,
  })
}

export function useSaveCredentials() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: postSaveCredentials,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CREDENTIALS_KEY })
    },
  })
}

// ── P1-19f: Download databases ──────────────────────────────────

export const DATABASE_LIST_KEY = ['setup', 'databases'] as const

async function fetchDatabaseList(): Promise<DatabaseListResult> {
  const res = await fetch('/api/databases')
  if (!res.ok) throw new Error(`Database list failed: ${res.status}`)
  return res.json()
}

async function postTriggerDownload(
  databases?: string[],
): Promise<TriggerDownloadResult> {
  const res = await fetch('/api/databases/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ databases: databases ?? null }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail || `Download trigger failed: ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

export function useDatabaseList() {
  return useQuery({
    queryKey: DATABASE_LIST_KEY,
    queryFn: fetchDatabaseList,
    staleTime: 0,
  })
}

// Note: Query invalidation is handled by DatabasesStep after SSE progress
// completes, rather than on mutation success, to reflect actual download state.
export function useTriggerDownload() {
  return useMutation({
    mutationFn: postTriggerDownload,
  })
}
