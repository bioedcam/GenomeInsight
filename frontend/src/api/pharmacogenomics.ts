/** React Query hooks for pharmacogenomics API (P3-06). */

import { useQuery } from "@tanstack/react-query"
import type {
  GeneSummaryResponse,
  DrugListResponse,
  DrugLookupResponse,
} from "@/types/pharmacogenomics"

/**
 * Gene summaries for metabolizer cards.
 * Returns per-gene star-allele calls, phenotypes, and associated drugs.
 * Cached with staleTime: Infinity since annotation data doesn't change.
 */
export function usePharmaGenes(sampleId: number | null) {
  return useQuery({
    queryKey: ["pharma-genes", sampleId],
    queryFn: async (): Promise<GeneSummaryResponse> => {
      const params = new URLSearchParams({ sample_id: String(sampleId!) })
      const res = await fetch(`/api/analysis/pharma/genes?${params}`)
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Pharma genes failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
    enabled: sampleId != null,
    staleTime: Infinity,
  })
}

/**
 * All CPIC drugs with associated genes and classifications.
 * Not sample-specific — shared reference data.
 * Cached with staleTime: Infinity since CPIC data doesn't change between updates.
 */
export function usePharmaDrugs() {
  return useQuery({
    queryKey: ["pharma-drugs"],
    queryFn: async (): Promise<DrugListResponse> => {
      const res = await fetch("/api/analysis/pharma/drugs")
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Pharma drugs failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
    staleTime: Infinity,
  })
}

/**
 * Drug detail with per-gene genotype effects for a specific sample.
 * Returns recommendations, classifications, and guideline URLs.
 * Cached with staleTime: Infinity since annotation data doesn't change.
 */
export function usePharmaDrugLookup(drugName: string | null, sampleId: number | null) {
  return useQuery({
    queryKey: ["pharma-drug", drugName, sampleId],
    queryFn: async (): Promise<DrugLookupResponse> => {
      const params = new URLSearchParams({ sample_id: String(sampleId!) })
      const res = await fetch(
        `/api/analysis/pharma/drug/${encodeURIComponent(drugName!)}?${params}`,
      )
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Pharma drug lookup failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
    enabled: drugName != null && sampleId != null,
    staleTime: Infinity,
  })
}
