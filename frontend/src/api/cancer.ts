/** React Query hooks for cancer module API (P3-18). */

import { useQuery } from "@tanstack/react-query"
import type {
  CancerVariantsListResponse,
  CancerPRSListResponse,
  CancerDisclaimerResponse,
} from "@/types/cancer"

/**
 * Cancer P/LP variant findings for a sample.
 * Monogenic pathogenic variants from the 28-gene cancer panel.
 * Cached with staleTime: Infinity since annotation data doesn't change.
 */
export function useCancerVariants(sampleId: number | null) {
  return useQuery({
    queryKey: ["cancer-variants", sampleId],
    queryFn: async (): Promise<CancerVariantsListResponse> => {
      const params = new URLSearchParams({ sample_id: String(sampleId!) })
      const res = await fetch(`/api/analysis/cancer/variants?${params}`)
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Cancer variants failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
    enabled: sampleId != null,
    staleTime: Infinity,
  })
}

/**
 * Cancer PRS results (breast, prostate, colorectal, melanoma).
 * Secondary "Research Use Only" tier with bootstrap CI gauges.
 * Cached with staleTime: Infinity since PRS data doesn't change until re-annotation.
 */
export function useCancerPRS(sampleId: number | null) {
  return useQuery({
    queryKey: ["cancer-prs", sampleId],
    queryFn: async (): Promise<CancerPRSListResponse> => {
      const params = new URLSearchParams({ sample_id: String(sampleId!) })
      const res = await fetch(`/api/analysis/cancer/prs?${params}`)
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Cancer PRS failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
    enabled: sampleId != null,
    staleTime: Infinity,
  })
}

/**
 * Cancer module disclaimer text (P3-17).
 * Not sample-specific — shared reference data.
 * Cached with staleTime: Infinity since disclaimer text doesn't change.
 */
export function useCancerDisclaimer() {
  return useQuery({
    queryKey: ["cancer-disclaimer"],
    queryFn: async (): Promise<CancerDisclaimerResponse> => {
      const res = await fetch("/api/analysis/cancer/disclaimer")
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Cancer disclaimer failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
    staleTime: Infinity,
  })
}
