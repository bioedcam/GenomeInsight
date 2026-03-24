/** React Query hooks for variant tagging API (P4-12b). */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import type { Tag } from "@/types/variants"

/** List all tags for a sample */
export function useTags(sampleId: number | null) {
  return useQuery({
    queryKey: ["tags", sampleId],
    queryFn: async (): Promise<Tag[]> => {
      const res = await fetch(`/api/tags?sample_id=${sampleId}`)
      if (!res.ok) throw new Error("Failed to fetch tags")
      return res.json()
    },
    enabled: sampleId != null,
    staleTime: 0, // Tags change frequently
  })
}

/** Get tags for a specific variant */
export function useVariantTags(sampleId: number | null, rsid: string | null) {
  return useQuery({
    queryKey: ["variant-tags", sampleId, rsid],
    queryFn: async (): Promise<Tag[]> => {
      const res = await fetch(`/api/tags/variant/${encodeURIComponent(rsid!)}?sample_id=${sampleId}`)
      if (!res.ok) throw new Error("Failed to fetch variant tags")
      return res.json()
    },
    enabled: sampleId != null && rsid != null,
    staleTime: 0,
  })
}

/** Create a custom tag */
export function useCreateTag(sampleId: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { name: string; color?: string }) => {
      const res = await fetch("/api/tags", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sample_id: sampleId, ...data }),
      })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(text || "Failed to create tag")
      }
      return res.json()
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tags", sampleId] })
    },
  })
}

/** Update a custom tag */
export function useUpdateTag(sampleId: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { tagId: number; name?: string; color?: string }) => {
      const { tagId, ...body } = data
      const res = await fetch(`/api/tags/${tagId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sample_id: sampleId, ...body }),
      })
      if (!res.ok) throw new Error("Failed to update tag")
      return res.json()
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tags", sampleId] })
    },
  })
}

/** Delete a custom tag */
export function useDeleteTag(sampleId: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (tagId: number) => {
      const res = await fetch(`/api/tags/${tagId}?sample_id=${sampleId}`, {
        method: "DELETE",
      })
      if (!res.ok) throw new Error("Failed to delete tag")
      return res.json()
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tags", sampleId] })
      qc.invalidateQueries({ queryKey: ["variant-tags"] })
    },
  })
}

/** Add a tag to a variant */
export function useAddVariantTag(sampleId: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { rsid: string; tag_id: number }) => {
      const res = await fetch("/api/tags/variant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sample_id: sampleId, ...data }),
      })
      if (!res.ok) throw new Error("Failed to add tag")
      return res.json()
    },
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["variant-tags", sampleId, variables.rsid] })
      qc.invalidateQueries({ queryKey: ["tags", sampleId] })
      qc.invalidateQueries({ queryKey: ["variants"] })
    },
  })
}

/** Remove a tag from a variant */
export function useRemoveVariantTag(sampleId: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { rsid: string; tag_id: number }) => {
      const params = new URLSearchParams({
        sample_id: String(sampleId),
        rsid: data.rsid,
        tag_id: String(data.tag_id),
      })
      const res = await fetch(`/api/tags/variant?${params}`, { method: "DELETE" })
      if (!res.ok) throw new Error("Failed to remove tag")
      return res.json()
    },
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["variant-tags", sampleId, variables.rsid] })
      qc.invalidateQueries({ queryKey: ["tags", sampleId] })
      qc.invalidateQueries({ queryKey: ["variants"] })
    },
  })
}
