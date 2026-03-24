/** API hooks for database update status and version stamps (P4-17). */

import { useQuery } from '@tanstack/react-query'

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

// ── Query keys ───────────────────────────────────────────────────────

export const DB_STATUS_KEY = ['updates', 'status'] as const
export const UPDATE_CHECK_KEY = ['updates', 'check'] as const

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
