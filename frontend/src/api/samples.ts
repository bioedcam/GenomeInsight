/** React Query hooks for sample management and file ingestion (P1-13, P1-16). */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import type { Sample, IngestResult } from "@/types/samples"

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
