/** React Query hooks for the variant table API (P1-15a, P1-15b, P1-15d). */

import { useInfiniteQuery, useQuery } from "@tanstack/react-query"
import type {
  VariantPage,
  VariantCount,
  VariantCursor,
  ChromosomeSummary,
} from "@/types/variants"

const PAGE_SIZE = 100

interface VariantQueryParams {
  sampleId: number | null
  filter?: string
  showUnannotated?: boolean
  /** When set, jump to the first variant on this chromosome (P1-15b). */
  startChrom?: string | null
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
    const text = await res.text().catch(() => "")
    throw new Error(`Variant fetch failed: ${res.status}${text ? ` - ${text}` : ""}`)
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
    const text = await res.text().catch(() => "")
    throw new Error(`Variant count failed: ${res.status}${text ? ` - ${text}` : ""}`)
  }
  return res.json()
}

/**
 * Infinite query for variant table with cursor-based keyset pagination.
 * Variant data uses staleTime: Infinity per PRD (never stale once loaded).
 *
 * When `startChrom` is set (P1-15b), the query starts from the first variant
 * on that chromosome by using cursor (chrom, pos=0). The chromosome is
 * included in the queryKey so changing it resets and refetches.
 */
export function useVariants({ sampleId, filter, showUnannotated, startChrom }: VariantQueryParams) {
  const effectiveFilter = buildEffectiveFilter(filter, showUnannotated)

  // Build initial cursor for chromosome jump (P1-15b).
  // cursor_pos=0 means "first variant on this chromosome" since all real positions are >= 1.
  const initialCursor: VariantCursor | null = startChrom
    ? { chrom: startChrom, pos: 0 }
    : null

  return useInfiniteQuery({
    queryKey: ["variants", sampleId, effectiveFilter, startChrom ?? null],
    queryFn: ({ pageParam }) =>
      fetchVariantPage(sampleId!, pageParam, PAGE_SIZE, effectiveFilter),
    initialPageParam: initialCursor,
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

/**
 * Per-chromosome variant counts for the chromosome nav bar (P1-15b).
 * Cached with staleTime: Infinity since variant data doesn't change.
 */
export function useChromosomeCounts(sampleId: number | null) {
  return useQuery({
    queryKey: ["variants-chromosomes", sampleId],
    queryFn: async (): Promise<ChromosomeSummary[]> => {
      const params = new URLSearchParams({ sample_id: String(sampleId!) })
      const res = await fetch(`/api/variants/chromosomes?${params}`)
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Chromosome counts failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
    enabled: sampleId != null,
    staleTime: Infinity,
  })
}

function buildEffectiveFilter(filter?: string, showUnannotated?: boolean): string | undefined {
  const parts: string[] = []
  if (filter) parts.push(filter)
  // When unannotated variants are hidden, ask the server to count only annotated rows.
  if (!showUnannotated) {
    parts.push("annotation_coverage:notnull")
  }
  return parts.length > 0 ? parts.join(",") : undefined
}

/**
 * Total variant count for the sample (unfiltered).
 * Used to display count in the unannotated toggle label.
 */
export function useTotalVariantCount(sampleId: number | null) {
  return useQuery({
    queryKey: ["variants-total-count", sampleId],
    queryFn: async () => {
      if (!sampleId) return 0
      const total = await fetchVariantCount(sampleId)
      return total.total
    },
    enabled: sampleId != null,
    staleTime: Infinity,
  })
}
