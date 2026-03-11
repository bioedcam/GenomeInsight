/** API hooks for the setup wizard. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { AcceptDisclaimerResult, DisclaimerData, SetupStatus } from '@/types/setup'

const SETUP_STATUS_KEY = ['setup', 'status'] as const
const DISCLAIMER_KEY = ['setup', 'disclaimer'] as const

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
