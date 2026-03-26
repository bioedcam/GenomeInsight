/** API hooks for authentication (P4-21a). */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

// ── Types ────────────────────────────────────────────────────────────

export interface AuthStatus {
  auth_enabled: boolean
  has_password: boolean
  authenticated: boolean
}

export interface LoginResponse {
  success: boolean
  message: string
}

export interface SetPasswordResponse {
  success: boolean
  message: string
}

export interface RemovePasswordResponse {
  success: boolean
  message: string
}

// ── Query keys ───────────────────────────────────────────────────────

export const AUTH_STATUS_KEY = ['auth', 'status'] as const

// ── Fetch functions ──────────────────────────────────────────────────

async function fetchAuthStatus(): Promise<AuthStatus> {
  const res = await fetch('/api/auth/status', { credentials: 'include' })
  if (!res.ok) throw new Error(`Auth status failed: ${res.status}`)
  return res.json()
}

async function postLogin(password: string): Promise<LoginResponse> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `Login failed: ${res.status}`)
  }
  return res.json()
}

async function postLogout(): Promise<LoginResponse> {
  const res = await fetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`Logout failed: ${res.status}`)
  return res.json()
}

async function postSetPassword(data: {
  password: string
  current_password?: string
}): Promise<SetPasswordResponse> {
  const res = await fetch('/api/auth/set-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `Set password failed: ${res.status}`)
  }
  return res.json()
}

async function postRemovePassword(password: string): Promise<RemovePasswordResponse> {
  const res = await fetch('/api/auth/remove-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `Remove password failed: ${res.status}`)
  }
  return res.json()
}

// ── Hooks ────────────────────────────────────────────────────────────

export function useAuthStatus() {
  return useQuery({
    queryKey: AUTH_STATUS_KEY,
    queryFn: fetchAuthStatus,
    staleTime: 0,
    retry: false,
  })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: postLogin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AUTH_STATUS_KEY })
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: postLogout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AUTH_STATUS_KEY })
    },
  })
}

export function useSetPassword() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: postSetPassword,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AUTH_STATUS_KEY })
    },
  })
}

export function useRemovePassword() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: postRemovePassword,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AUTH_STATUS_KEY })
    },
  })
}
