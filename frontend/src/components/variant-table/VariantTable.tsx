/** Variant table core: TanStack Table + infinite scroll + useInfiniteQuery (P1-15a).
 *  Chromosome anchors: jump-to-chromosome navigation bar (P1-15b).
 *  Column preset profiles (P1-15c).
 *  Contextual empty states (P1-15e).
 *  Variant detail side panel on row click (P2-21).
 *  Annotation columns per presets + evidence conflict indicator + "Conflicts only" toggle (P2-22). */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type VisibilityState,
} from "@tanstack/react-table"
import { Loader2 } from "lucide-react"

import { useVariants, useVariantsCount, useTotalVariantCount, useChromosomeCounts } from "@/api/variants"
import { useColumnPresets } from "@/api/columnPresets"
import type { VariantRow } from "@/types/variants"
import { allColumns } from "./columns"
import VariantToolbar from "./VariantToolbar"
import ChromosomeNav from "./ChromosomeNav"
import { ALWAYS_VISIBLE } from "./ColumnPresets"
import {
  PreUploadEmpty,
  PreAnnotationEmpty,
  NoMatchEmpty,
  ErrorEmpty,
} from "./EmptyStates"
import VariantDetailSidePanel from "@/components/variant-detail/VariantDetailSidePanel"

interface VariantTableProps {
  sampleId: number | null
}

/** GRCh38 liftover column IDs (P4-20). */
const GRCH38_COLUMNS = ["chrom_grch38", "pos_grch38"]

/** Convert a preset's column list to TanStack Table VisibilityState.
 *  GRCh38 columns are controlled separately via the liftover toggle (P4-20). */
function presetToVisibility(
  presetColumns: string[] | null,
  allColumnIds: string[],
  showGRCh38: boolean,
): VisibilityState {
  if (!presetColumns) {
    // All visible — but still respect GRCh38 toggle
    return {
      chrom_grch38: showGRCh38,
      pos_grch38: showGRCh38,
    }
  }
  const visibility: VisibilityState = {}
  for (const colId of allColumnIds) {
    if (ALWAYS_VISIBLE.has(colId)) continue
    if (GRCH38_COLUMNS.includes(colId)) {
      visibility[colId] = showGRCh38
    } else {
      visibility[colId] = presetColumns.includes(colId)
    }
  }
  return visibility
}

export default function VariantTable({ sampleId }: VariantTableProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [showUnannotated, setShowUnannotated] = useState(false)
  const [showConflictsOnly, setShowConflictsOnly] = useState(false)
  const [showGRCh38, setShowGRCh38] = useState(false)
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({
    chrom_grch38: false,
    pos_grch38: false,
  })
  const [startChrom, setStartChrom] = useState<string | null>(null)
  const [activeFilter, setActiveFilter] = useState<string | undefined>(undefined)
  const [activeTag, setActiveTag] = useState<string | null>(null)

  // Variant detail side panel state (P2-21)
  const [selectedRsid, setSelectedRsid] = useState<string | null>(null)

  // Column preset state from URL param (P1-15c)
  const [activePreset, setActivePreset] = useState<string | null>(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get("profile") || null
  })

  // Fetch presets to resolve initial URL param
  const { data: presets } = useColumnPresets()
  // TanStack Table accessor columns store their ID in `accessorKey` rather than `id`.
  // The union type doesn't expose accessorKey directly, so we cast through `any`.
  const allColumnIds = useMemo(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    () => allColumns.map((c) => c.id ?? ((c as any).accessorKey as string)).filter(Boolean),
    [],
  )

  // Apply preset from URL param on initial load
  const initialPresetApplied = useRef(false)
  useEffect(() => {
    if (initialPresetApplied.current || !presets || !activePreset) return
    const match = presets.find((p) => p.name.toLowerCase() === activePreset.toLowerCase())
    if (match) {
      setActivePreset(match.name)
      setColumnVisibility(presetToVisibility(match.columns, allColumnIds, showGRCh38))
    } else {
      // Invalid preset in URL — reset
      setActivePreset(null)
    }
    initialPresetApplied.current = true
  }, [presets, activePreset, allColumnIds, showGRCh38])

  const handlePresetChange = useCallback(
    (presetName: string | null, columns: string[] | null) => {
      setActivePreset(presetName)
      setColumnVisibility(presetToVisibility(columns, allColumnIds, showGRCh38))

      // Update URL param
      const url = new URL(window.location.href)
      if (presetName) {
        url.searchParams.set("profile", presetName.toLowerCase())
      } else {
        url.searchParams.delete("profile")
      }
      window.history.replaceState({}, "", url.toString())
    },
    [allColumnIds, showGRCh38],
  )

  // GRCh38 liftover toggle (P4-20): show/hide GRCh38 columns independently of presets
  const handleToggleGRCh38 = useCallback(() => {
    setShowGRCh38((prev) => {
      const next = !prev
      setColumnVisibility((vis) => ({
        ...vis,
        chrom_grch38: next,
        pos_grch38: next,
      }))
      return next
    })
  }, [])

  // Server-side filter string (set by quick-apply suggestions in P1-15e, P2-22 conflicts toggle).
  const filter = useMemo(() => {
    const parts: string[] = []
    if (activeFilter) parts.push(activeFilter)
    if (showConflictsOnly) parts.push("evidence_conflict:1")
    return parts.length > 0 ? parts.join(",") : undefined
  }, [activeFilter, showConflictsOnly])

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    status,
    error,
  } = useVariants({ sampleId, filter, showUnannotated, startChrom, tag: activeTag })

  // Chromosome counts for the nav bar (P1-15b)
  const { data: chromCounts, isLoading: chromCountsLoading } =
    useChromosomeCounts(sampleId)

  const { data: countData, isLoading: countLoading } = useVariantsCount({
    sampleId,
    filter,
    showUnannotated,
    tag: activeTag,
  })

  const { data: totalVariants } = useTotalVariantCount(sampleId)

  // Derive current chromosome from the first visible row (P1-15b)
  const activeChrom = useMemo(() => {
    if (!data?.pages?.length) return null
    const firstPage = data.pages[0]
    if (!firstPage?.items?.length) return null
    return firstPage.items[0].chrom
  }, [data?.pages])

  // Jump to a chromosome: reset infinite query by changing startChrom
  const tableContainerRef = useRef<HTMLElement>(null)

  const handleJumpToChrom = useCallback(
    (chrom: string) => {
      setStartChrom(chrom)
      tableContainerRef.current?.scrollTo({ top: 0, behavior: "instant" })
    },
    [],
  )

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

  // Detect pre-annotation state (P1-15e): sample has raw variants but none annotated.
  // When showUnannotated is off (default), annotated count = 0 but total > 0.
  const isPreAnnotation = useMemo(() => {
    if (showUnannotated || searchQuery || activeFilter || showConflictsOnly) return false
    if (totalVariants == null || totalVariants === 0) return false
    // countData is filtered by annotation_coverage:notnull — if 0, no annotated variants
    if (countData && countData.total === 0) return true
    return false
  }, [showUnannotated, searchQuery, activeFilter, showConflictsOnly, totalVariants, countData])

  // Empty states (P1-15e)
  if (sampleId == null) {
    return <PreUploadEmpty />
  }

  if (status === "error") {
    return <ErrorEmpty message={error?.message ?? "An unexpected error occurred."} />
  }

  return (
    <div className="flex flex-col h-full">
      <ChromosomeNav
        chromosomeCounts={chromCounts}
        isLoading={chromCountsLoading}
        activeChrom={activeChrom}
        onJumpToChrom={handleJumpToChrom}
      />

      <VariantToolbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        showUnannotated={showUnannotated}
        onToggleUnannotated={() => setShowUnannotated((prev) => !prev)}
        showConflictsOnly={showConflictsOnly}
        onToggleConflictsOnly={() => setShowConflictsOnly((prev) => !prev)}
        unannotatedCount={totalVariants}
        totalCount={countData?.total}
        totalCountLoading={countLoading}
        isLoading={status === "pending"}
        activePreset={activePreset}
        onPresetChange={handlePresetChange}
        activeFilter={activeFilter}
        onClearFilter={() => setActiveFilter(undefined)}
        sampleId={sampleId}
        activeTag={activeTag}
        onTagFilter={setActiveTag}
        showGRCh38={showGRCh38}
        onToggleGRCh38={handleToggleGRCh38}
      />

      <section ref={tableContainerRef} className="flex-1 overflow-auto" aria-label="Variant table">
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
                <td colSpan={table.getAllColumns().length}>
                  {isPreAnnotation ? (
                    <PreAnnotationEmpty
                      totalVariants={totalVariants ?? 0}
                      onShowUnannotated={() => setShowUnannotated(true)}
                    />
                  ) : (
                    <NoMatchEmpty
                      searchQuery={searchQuery}
                      hasActiveFilter={!!activeFilter}
                      onClearSearch={() => setSearchQuery("")}
                      onClearFilters={() => setActiveFilter(undefined)}
                      onApplyFilter={(f) => {
                        setActiveFilter(f)
                        setShowUnannotated(true)
                      }}
                    />
                  )}
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className={`border-b border-border/50 hover:bg-accent/50 transition-colors cursor-pointer ${
                    row.original.rsid === selectedRsid ? "bg-accent" : ""
                  }`}
                  onClick={() => setSelectedRsid(row.original.rsid)}
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

      {/* Variant detail side panel (P2-21) */}
      <VariantDetailSidePanel
        rsid={selectedRsid}
        sampleId={sampleId}
        onClose={() => setSelectedRsid(null)}
      />
    </div>
  )
}
