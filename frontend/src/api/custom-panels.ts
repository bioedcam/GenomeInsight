/** React Query hooks for custom gene panel API (P4-11). */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import type {
  CustomPanelListResponse,
  CustomPanel,
  PanelUploadResponse,
  ParsePreviewResponse,
  PanelSearchRequest,
  PanelSearchResponse,
} from "@/types/custom-panels"

/** List all saved custom gene panels. Cached with 1-hour staleTime. */
export function useCustomPanels() {
  return useQuery({
    queryKey: ["custom-panels"],
    queryFn: async (): Promise<CustomPanelListResponse> => {
      const res = await fetch("/api/panels")
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Failed to load panels: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
    staleTime: 1000 * 60 * 60, // 1 hour
  })
}

/** Get a single custom panel by ID. */
export function useCustomPanel(panelId: number | null) {
  return useQuery({
    queryKey: ["custom-panel", panelId],
    queryFn: async (): Promise<CustomPanel> => {
      const res = await fetch(`/api/panels/${panelId}`)
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Failed to load panel: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
    enabled: panelId != null,
    staleTime: Infinity,
  })
}

/** Parse a panel file for preview (without saving). */
export function useParsePanelPreview() {
  return useMutation({
    mutationFn: async (file: File): Promise<ParsePreviewResponse> => {
      const formData = new FormData()
      formData.append("file", file)
      const res = await fetch("/api/panels/parse", {
        method: "POST",
        body: formData,
      })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Parse failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
  })
}

/** Upload and save a custom panel. */
export function useUploadPanel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      file,
      name,
      description,
    }: {
      file: File
      name: string
      description?: string
    }): Promise<PanelUploadResponse> => {
      const formData = new FormData()
      formData.append("file", file)
      const params = new URLSearchParams({ name })
      if (description) params.set("description", description)
      const res = await fetch(`/api/panels/upload?${params}`, {
        method: "POST",
        body: formData,
      })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Upload failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["custom-panels"] })
    },
  })
}

/** Delete a custom panel. */
export function useDeletePanel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (panelId: number): Promise<void> => {
      const res = await fetch(`/api/panels/${panelId}`, { method: "DELETE" })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Delete failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["custom-panels"] })
    },
  })
}

/** Run rare variant search using a saved panel. */
export function usePanelSearch(sampleId: number | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      panelId,
      filters,
    }: {
      panelId: number
      filters?: PanelSearchRequest
    }): Promise<PanelSearchResponse> => {
      if (sampleId == null) {
        throw new Error("Cannot search without a sample selected")
      }
      const params = new URLSearchParams({ sample_id: String(sampleId) })
      const res = await fetch(`/api/panels/${panelId}/search?${params}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters ?? {}),
      })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Panel search failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rare-variant-findings", sampleId] })
    },
  })
}
