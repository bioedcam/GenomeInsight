/** React Query hooks for sample management and file ingestion (P1-13, P1-16). */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import type {
  IngestResult,
  MergedChild,
  Sample,
  SampleUpdate,
} from "@/types/samples"

export function useSamples() {
  return useQuery({
    queryKey: ["samples"],
    queryFn: async (): Promise<Sample[]> => {
      const res = await fetch("/api/samples")
      if (!res.ok) throw new Error("Failed to fetch samples")
      return await res.json()
    },
    staleTime: 0,
  })
}

export function useSample(sampleId: number | null) {
  return useQuery({
    queryKey: ["samples", sampleId],
    queryFn: async (): Promise<Sample> => {
      const res = await fetch(`/api/samples/${sampleId}`)
      if (!res.ok) throw new Error("Failed to fetch sample")
      return await res.json()
    },
    enabled: sampleId != null,
  })
}

export function useIngestFile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file: File): Promise<IngestResult> => {
      const formData = new FormData()
      formData.append("file", file)
      const res = await fetch("/api/ingest", {
        method: "POST",
        body: formData,
      })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(text || `Upload failed: ${res.status}`)
      }
      return await res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["samples"] })
    },
  })
}

export function useUpdateSample() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      sampleId,
      data,
    }: {
      sampleId: number
      data: SampleUpdate
    }): Promise<Sample> => {
      const res = await fetch(`/api/samples/${sampleId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(text || "Failed to update sample")
      }
      return await res.json()
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["samples"] })
      queryClient.invalidateQueries({
        queryKey: ["samples", variables.sampleId],
      })
    },
  })
}

export function useDeleteSample() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (sampleId: number): Promise<void> => {
      const res = await fetch(`/api/samples/${sampleId}`, {
        method: "DELETE",
      })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(text || "Failed to delete sample")
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["samples"] })
    },
  })
}

/** Merged samples that reference this sample as a source (Plan §10.8 / Step 66).
 *
 * Returns ``[]`` when the sample has never been merged. The delete
 * confirmation hook uses this to surface the cascade count + names before
 * the user commits.
 */
export function useSampleMergedChildren(sampleId: number | null) {
  return useQuery({
    queryKey: ["samples", sampleId, "merged-children"],
    queryFn: async (): Promise<MergedChild[]> => {
      const res = await fetch(`/api/samples/${sampleId}/merged-children`)
      if (!res.ok) throw new Error("Failed to fetch merged children")
      return (await res.json()) as MergedChild[]
    },
    enabled: sampleId != null,
    staleTime: 0,
  })
}
