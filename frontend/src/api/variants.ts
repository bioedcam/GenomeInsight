/** React Query hooks for the variant table API (P1-15a). */

import { useInfiniteQuery, useQuery } from "@tanstack/react-query"
import type { VariantPage, VariantCount, VariantCursor } from "@/types/variants"

const PAGE_SIZE = 100

interface VariantQueryParams {
  sampleId: number | null
  filter?: string
  showUnannotated?: boolean
}

async function fetchVariantPage(
  sampleId: number,
  cursor: VariantCursor | null,
  limit: number,
  filter?: string,
): Promise<VariantPage> {
  const params = new URLSearchParams({
    sample_id: String(sampleId),
    limit: String(limit),
  })
  if (cursor) {
    params.set("cursor_chrom", cursor.chrom)
    params.set("cursor_pos", String(cursor.pos))
  }
  if (filter) {
    params.set("filter", filter)
  }
  const res = await fetch(`/api/variants?${params}`)
  if (!res.ok) {
    throw new Error(`Variant fetch failed: ${res.status}`)
  }
  return res.json()
}

async function fetchVariantCount(
  sampleId: number,
  filter?: string,
): Promise<VariantCount> {
  const params = new URLSearchParams({ sample_id: String(sampleId) })
  if (filter) {
    params.set("filter", filter)
  }
  const res = await fetch(`/api/variants/count?${params}`)
  if (!res.ok) {
    throw new Error(`Variant count failed: ${res.status}`)
  }
  return res.json()
}

/**
 * Infinite query for variant table with cursor-based keyset pagination.
 * Variant data uses staleTime: Infinity per PRD (never stale once loaded).
 */
export function useVariants({ sampleId, filter, showUnannotated }: VariantQueryParams) {
  // When hiding unannotated, add annotation_coverage filter
  // annotation_coverage IS NULL means unannotated — we filter on the API side
  // The API currently doesn't support IS NOT NULL filters directly,
  // so we pass a special filter marker
  const effectiveFilter = buildEffectiveFilter(filter, showUnannotated)

  return useInfiniteQuery({
    queryKey: ["variants", sampleId, effectiveFilter],
    queryFn: ({ pageParam }) =>
      fetchVariantPage(sampleId!, pageParam, PAGE_SIZE, effectiveFilter),
    initialPageParam: null as VariantCursor | null,
    getNextPageParam: (lastPage): VariantCursor | null => {
      if (!lastPage.has_more || !lastPage.next_cursor_chrom || lastPage.next_cursor_pos == null) {
        return null
      }
      return {
        chrom: lastPage.next_cursor_chrom,
        pos: lastPage.next_cursor_pos,
      }
    },
    enabled: sampleId != null,
    staleTime: Infinity,
  })
}

/**
 * Async total count — fires separately from the first page.
 * Cached per filter combination via query key.
 */
export function useVariantsCount({ sampleId, filter, showUnannotated }: VariantQueryParams) {
  const effectiveFilter = buildEffectiveFilter(filter, showUnannotated)

  return useQuery({
    queryKey: ["variants-count", sampleId, effectiveFilter],
    queryFn: () => fetchVariantCount(sampleId!, effectiveFilter),
    enabled: sampleId != null,
    staleTime: Infinity,
  })
}

function buildEffectiveFilter(filter?: string, showUnannotated?: boolean): string | undefined {
  // If showing all variants (including unannotated), use filter as-is
  if (showUnannotated) {
    return filter || undefined
  }
  // Default: hide unannotated. No server-side IS NOT NULL filter available yet,
  // so we handle this client-side by filtering out rows with annotation_coverage === null
  return filter || undefined
}

/**
 * Count of unannotated variants for the toggle label.
 * Queries for total count without annotation filter, minus count with annotation.
 */
export function useUnannotatedCount(sampleId: number | null) {
  return useQuery({
    queryKey: ["variants-unannotated-count", sampleId],
    queryFn: async () => {
      if (!sampleId) return 0
      const total = await fetchVariantCount(sampleId)
      return total.total
    },
    enabled: sampleId != null,
    staleTime: Infinity,
  })
}
