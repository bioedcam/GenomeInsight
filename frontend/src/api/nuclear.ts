/** React Query hook for Nuclear Delete (P4-21). */

import { useMutation, useQueryClient } from "@tanstack/react-query"

export interface NuclearDeleteResponse {
  deleted: boolean
  message: string
}

export function useNuclearDelete() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (): Promise<NuclearDeleteResponse> => {
      const res = await fetch("/api/data/nuclear", { method: "DELETE" })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(text || "Nuclear delete failed")
      }
      return await res.json()
    },
    onSuccess: () => {
      // Invalidate all queries since everything is gone
      queryClient.clear()
    },
  })
}
