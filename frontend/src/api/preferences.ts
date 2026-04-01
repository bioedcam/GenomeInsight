/** API hooks for user preferences (P4-26a). */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

export type Theme = 'light' | 'dark' | 'system'

interface ThemeResponse {
  theme: Theme
}

/** Fetch current theme preference from backend. */
export function useThemePreference() {
  return useQuery<ThemeResponse>({
    queryKey: ['preferences', 'theme'],
    queryFn: async () => {
      const res = await fetch('/api/preferences/theme')
      if (!res.ok) throw new Error('Failed to fetch theme')
      return res.json()
    },
    staleTime: Infinity,
  })
}

/** Persist theme preference to backend config.toml. */
export function useSetThemePreference() {
  const qc = useQueryClient()
  return useMutation<ThemeResponse, Error, Theme>({
    mutationFn: async (theme) => {
      const res = await fetch('/api/preferences/theme', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ theme }),
      })
      if (!res.ok) throw new Error('Failed to set theme')
      return res.json()
    },
    onSuccess: (data) => {
      qc.setQueryData(['preferences', 'theme'], data)
    },
  })
}
