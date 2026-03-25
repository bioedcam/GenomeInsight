/** API hooks for database update status, history, and triggers (P4-17, P4-18). */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

// ── Types ────────────────────────────────────────────────────────────

export interface DatabaseStatus {
  db_name: string
  display_name: string
  current_version: string | null
  version_display: string | null
  downloaded_at: string | null
  auto_update: boolean
  update_available: boolean
}

export interface UpdateAvailable {
  db_name: string
  latest_version: string
  download_size_bytes: number
  release_date: string | null
}

export interface UpdateCheckResult {
  available: UpdateAvailable[]
  up_to_date: string[]
  errors: string[]
  checked_at: string
}

export interface UpdateHistoryEntry {
  id: number
  db_name: string
  previous_version: string | null
  new_version: string
  updated_at: string | null
  variants_added: number | null
  variants_reclassified: number | null
  download_size_bytes: number | null
  duration_seconds: number | null
}

export interface ReannotationPrompt {
  id: number
  sample_id: number
  db_name: string
  db_version: string
  candidate_count: number
  created_at: string | null
}

export interface TriggerUpdateResponse {
  job_id: string
  db_name: string
  message: string
}

// ── Query keys ───────────────────────────────────────────────────────

export const DB_STATUS_KEY = ['updates', 'status'] as const
export const UPDATE_CHECK_KEY = ['updates', 'check'] as const
export const UPDATE_HISTORY_KEY = ['updates', 'history'] as const
export const REANNOTATION_PROMPTS_KEY = ['updates', 'prompts'] as const

// ── Fetchers ─────────────────────────────────────────────────────────

async function fetchDatabaseStatuses(): Promise<DatabaseStatus[]> {
  const res = await fetch('/api/updates/status')
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Database status fetch failed: ${res.status} ${text}`.trim())
  }
  return res.json()
}

async function fetchUpdateCheck(): Promise<UpdateCheckResult> {
  const res = await fetch('/api/updates/check')
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Update check failed: ${res.status} ${text}`.trim())
  }
  return res.json()
}

async function fetchUpdateHistory(dbName?: string, limit = 50): Promise<UpdateHistoryEntry[]> {
  const params = new URLSearchParams()
  if (dbName) params.set('db_name', dbName)
  params.set('limit', String(limit))
  const res = await fetch(`/api/updates/history?${params}`)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Update history fetch failed: ${res.status} ${text}`.trim())
  }
  return res.json()
}

async function fetchReannotationPrompts(sampleId?: number): Promise<ReannotationPrompt[]> {
  const params = new URLSearchParams()
  if (sampleId != null) params.set('sample_id', String(sampleId))
  const res = await fetch(`/api/updates/prompts?${params}`)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Prompts fetch failed: ${res.status} ${text}`.trim())
  }
  return res.json()
}

async function triggerUpdate(dbName: string): Promise<TriggerUpdateResponse> {
  const res = await fetch('/api/updates/trigger', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ db_name: dbName }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Trigger update failed: ${res.status} ${text}`.trim())
  }
  return res.json()
}

async function dismissPrompt(promptId: number): Promise<void> {
  const res = await fetch(`/api/updates/prompts/${promptId}/dismiss`, { method: 'POST' })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Dismiss prompt failed: ${res.status} ${text}`.trim())
  }
}

async function toggleAutoUpdate(dbName: string, enabled: boolean): Promise<void> {
  const res = await fetch('/api/updates/auto-update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ db_name: dbName, enabled }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Toggle auto-update failed: ${res.status} ${text}`.trim())
  }
}

// ── Hooks ────────────────────────────────────────────────────────────

/** Fetch per-DB version stamps and auto-update status. staleTime=1h. */
export function useDatabaseStatuses() {
  return useQuery({
    queryKey: DB_STATUS_KEY,
    queryFn: fetchDatabaseStatuses,
    staleTime: 60 * 60 * 1000, // 1 hour
  })
}

/** Check for available updates (hits remote). staleTime=1h. */
export function useUpdateCheck(enabled = false) {
  return useQuery({
    queryKey: UPDATE_CHECK_KEY,
    queryFn: fetchUpdateCheck,
    staleTime: 60 * 60 * 1000,
    enabled,
  })
}

/** Fetch update history, optionally filtered by db_name. */
export function useUpdateHistory(dbName?: string) {
  return useQuery({
    queryKey: [...UPDATE_HISTORY_KEY, dbName ?? 'all'],
    queryFn: () => fetchUpdateHistory(dbName),
    staleTime: 60 * 60 * 1000,
  })
}

/** Fetch active re-annotation prompts. */
export function useReannotationPrompts(sampleId?: number) {
  return useQuery({
    queryKey: [...REANNOTATION_PROMPTS_KEY, sampleId ?? 'all'],
    queryFn: () => fetchReannotationPrompts(sampleId),
    staleTime: 5 * 60 * 1000, // 5 min
  })
}

/** Trigger a database update. Invalidates status + check caches on success. */
export function useTriggerUpdate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (dbName: string) => triggerUpdate(dbName),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: DB_STATUS_KEY })
      qc.invalidateQueries({ queryKey: UPDATE_CHECK_KEY })
      qc.invalidateQueries({ queryKey: UPDATE_HISTORY_KEY })
    },
  })
}

/** Dismiss a re-annotation prompt. Invalidates prompts cache on success. */
export function useDismissPrompt() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (promptId: number) => dismissPrompt(promptId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: REANNOTATION_PROMPTS_KEY })
    },
  })
}

/** Toggle auto-update for a database. Invalidates status cache on success. */
export function useToggleAutoUpdate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ dbName, enabled }: { dbName: string; enabled: boolean }) =>
      toggleAutoUpdate(dbName, enabled),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: DB_STATUS_KEY })
    },
  })
}
