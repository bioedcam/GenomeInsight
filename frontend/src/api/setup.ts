/** API hooks for the setup wizard. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  AcceptDisclaimerResult,
  DetectExistingResult,
  DisclaimerData,
  ImportBackupResult,
  SetupStatus,
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
