/** Variant table core: TanStack Table + infinite scroll + useInfiniteQuery (P1-15a). */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type VisibilityState,
} from "@tanstack/react-table"
import { Loader2 } from "lucide-react"

import { useVariants, useVariantsCount, useTotalVariantCount } from "@/api/variants"
import type { VariantRow } from "@/types/variants"
import { allColumns } from "./columns"
import VariantToolbar from "./VariantToolbar"

interface VariantTableProps {
  sampleId: number | null
}

export default function VariantTable({ sampleId }: VariantTableProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [showUnannotated, setShowUnannotated] = useState(false)
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})

  // Build filter string from search query.
  // The API doesn't support rsid/gene search directly in filters yet,
  // so we do client-side filtering and pass undefined to the API.
  const filter = undefined

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    status,
    error,
  } = useVariants({ sampleId, filter, showUnannotated })

  const { data: countData, isLoading: countLoading } = useVariantsCount({
    sampleId,
    filter,
    showUnannotated,
  })

  const { data: totalVariants } = useTotalVariantCount(sampleId)

  // Flatten pages into a single array
  const allRows = useMemo(() => {
    if (!data?.pages) return []
    const rows = data.pages.flatMap((page) => page.items)

    // Client-side filtering: hide unannotated by default
    const filtered = showUnannotated
      ? rows
      : rows.filter((row) => row.annotation_coverage != null)

    // Client-side search filtering (rsid / gene_symbol)
    if (!searchQuery.trim()) return filtered
    const q = searchQuery.trim().toLowerCase()
    return filtered.filter(
      (row) =>
        row.rsid.toLowerCase().includes(q) ||
        (row.gene_symbol && row.gene_symbol.toLowerCase().includes(q)),
    )
  }, [data?.pages, showUnannotated, searchQuery])

  const table = useReactTable<VariantRow>({
    data: allRows,
    columns: allColumns,
    state: { columnVisibility },
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    initialState: {
      columnPinning: { left: ["evidence_conflict"] },
    },
  })

  // Infinite scroll: observe sentinel element at bottom of table
  const sentinelRef = useRef<HTMLDivElement>(null)

  const handleIntersect = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      const entry = entries[0]
      if (entry?.isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage()
      }
    },
    [hasNextPage, isFetchingNextPage, fetchNextPage],
  )

  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(handleIntersect, {
      rootMargin: "200px",
    })
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [handleIntersect])

  // Empty states
  if (sampleId == null) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-lg text-muted-foreground">Upload a file to get started</p>
        <p className="text-sm text-muted-foreground mt-1">
          Go to the Dashboard to upload a 23andMe raw data file.
        </p>
      </div>
    )
  }

  if (status === "error") {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-lg text-destructive">Error loading variants</p>
        <p className="text-sm text-muted-foreground mt-1">
          {error?.message ?? "An unexpected error occurred."}
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <VariantToolbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        showUnannotated={showUnannotated}
        onToggleUnannotated={() => setShowUnannotated((prev) => !prev)}
        unannotatedCount={totalVariants}
        totalCount={countData?.total}
        totalCountLoading={countLoading}
        isLoading={status === "pending"}
      />

      <section className="flex-1 overflow-auto" aria-label="Variant table">
        <table className="w-full text-sm border-collapse">
          <thead className="sticky top-0 z-10 bg-card border-b border-border">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap"
                    style={{ width: header.getSize() }}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {status === "pending" ? (
              <tr>
                <td colSpan={table.getAllColumns().length} className="text-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto text-primary" />
                  <p className="text-sm text-muted-foreground mt-2">Loading variants...</p>
                </td>
              </tr>
            ) : allRows.length === 0 ? (
              <tr>
                <td colSpan={table.getAllColumns().length} className="text-center py-12">
                  <p className="text-muted-foreground">No variants match your filters</p>
                  <div className="flex gap-2 justify-center mt-3">
                    {searchQuery && (
                      <button
                        type="button"
                        onClick={() => setSearchQuery("")}
                        className="px-3 py-1 text-xs rounded-md border border-input bg-background hover:bg-accent text-foreground"
                      >
                        Clear search
                      </button>
                    )}
                    {!showUnannotated && (
                      <button
                        type="button"
                        onClick={() => setShowUnannotated(true)}
                        className="px-3 py-1 text-xs rounded-md border border-input bg-background hover:bg-accent text-foreground"
                      >
                        Show unannotated
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-border/50 hover:bg-accent/50 transition-colors"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="px-3 py-1.5 whitespace-nowrap"
                      style={{ width: cell.column.getSize() }}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Infinite scroll sentinel */}
        <div ref={sentinelRef} className="h-10 flex items-center justify-center">
          {isFetchingNextPage && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading more...
            </div>
          )}
          {!hasNextPage && allRows.length > 0 && !isFetching && (
            <p className="text-xs text-muted-foreground">All variants loaded</p>
          )}
        </div>
      </section>
    </div>
  )
}
