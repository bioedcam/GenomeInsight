/** React Query hooks for the query builder API (P4-02). */

import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from "@tanstack/react-query"
import type {
  QueryMetaResponse,
  QueryResultPage,
  RuleGroupModel,
  SavedQuery,
  SavedQueryListResponse,
} from "@/types/query-builder"

// ── Field metadata ──────────────────────────────────────────────────

export function useQueryFields() {
  return useQuery({
    queryKey: ["query-fields"],
    queryFn: async (): Promise<QueryMetaResponse> => {
      const res = await fetch("/api/query/fields")
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Failed to fetch query fields: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
    staleTime: Infinity,
  })
}

// ── Execute query ───────────────────────────────────────────────────

interface ExecuteQueryParams {
  sampleId: number
  filter: RuleGroupModel
}

const QUERY_PAGE_SIZE = 50

export function useExecuteQuery(sampleId: number | null, filter: RuleGroupModel | null) {
  return useInfiniteQuery({
    queryKey: ["query-results", sampleId, filter],
    queryFn: async ({ pageParam }): Promise<QueryResultPage> => {
      const body: Record<string, unknown> = {
        sample_id: sampleId!,
        filter: filter!,
        limit: QUERY_PAGE_SIZE,
      }
      if (pageParam) {
        body.cursor_chrom = pageParam.chrom
        body.cursor_pos = pageParam.pos
      }
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Query execution failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
    initialPageParam: null as { chrom: string; pos: number } | null,
    getNextPageParam: (lastPage): { chrom: string; pos: number } | null => {
      if (!lastPage.has_more || !lastPage.next_cursor_chrom || lastPage.next_cursor_pos == null) {
        return null
      }
      return { chrom: lastPage.next_cursor_chrom, pos: lastPage.next_cursor_pos }
    },
    enabled: sampleId != null && filter != null,
    staleTime: Infinity,
  })
}

/** One-shot mutation for executing a query (used for the Run button). */
export function useRunQuery() {
  return useMutation({
    mutationFn: async ({ sampleId, filter }: ExecuteQueryParams): Promise<QueryResultPage> => {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sample_id: sampleId,
          filter,
          limit: QUERY_PAGE_SIZE,
        }),
      })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Query execution failed: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      return res.json()
    },
  })
}

// ── Saved queries ───────────────────────────────────────────────────

export function useSavedQueries() {
  return useQuery({
    queryKey: ["saved-queries"],
    queryFn: async (): Promise<SavedQuery[]> => {
      const res = await fetch("/api/saved-queries")
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(`Failed to fetch saved queries: ${res.status}${text ? ` - ${text}` : ""}`)
      }
      const data: SavedQueryListResponse = await res.json()
      return data.queries
    },
    staleTime: 1000 * 60 * 5, // 5 min
  })
}

export function useSaveQuery() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; filter: RuleGroupModel }): Promise<SavedQuery> => {
      const res = await fetch("/api/saved-queries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(text || "Failed to save query")
      }
      return res.json()
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["saved-queries"] }),
  })
}

export function useUpdateSavedQuery() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      name,
      ...body
    }: {
      name: string
      new_name?: string
      filter?: RuleGroupModel
    }): Promise<SavedQuery> => {
      const res = await fetch(`/api/saved-queries/${encodeURIComponent(name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(text || "Failed to update saved query")
      }
      return res.json()
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["saved-queries"] }),
  })
}

export function useDeleteSavedQuery() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (name: string) => {
      const res = await fetch(`/api/saved-queries/${encodeURIComponent(name)}`, {
        method: "DELETE",
      })
      if (!res.ok) {
        const text = await res.text().catch(() => "")
        throw new Error(text || "Failed to delete saved query")
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["saved-queries"] }),
  })
}
