/** Variant table toolbar: search + unannotated toggle + conflicts-only toggle + tag filter + preset selector + filter badge (P1-15a, P1-15c, P1-15e, P2-22, P4-12b). */

import { useEffect, useRef, useState } from "react"
import { Search, Eye, EyeOff, AlertTriangle, X, Tag } from "lucide-react"
import ColumnPresets from "./ColumnPresets"
import { filterLabel } from "./filterSuggestions"
import { useTags } from "@/api/tags"

interface VariantToolbarProps {
  searchQuery: string
  onSearchChange: (query: string) => void
  showUnannotated: boolean
  onToggleUnannotated: () => void
  showConflictsOnly: boolean
  onToggleConflictsOnly: () => void
  unannotatedCount: number | undefined
  totalCount: number | undefined
  totalCountLoading: boolean
  isLoading: boolean
  activePreset: string | null
  onPresetChange: (presetName: string | null, columns: string[] | null) => void
  activeFilter?: string
  onClearFilter?: () => void
  sampleId: number | null
  activeTag?: string | null
  onTagFilter?: (tagName: string | null) => void
}

export default function VariantToolbar({
  searchQuery,
  onSearchChange,
  showUnannotated,
  onToggleUnannotated,
  showConflictsOnly,
  onToggleConflictsOnly,
  unannotatedCount,
  totalCount,
  totalCountLoading,
  isLoading,
  activePreset,
  onPresetChange,
  activeFilter,
  onClearFilter,
  sampleId,
  activeTag,
  onTagFilter,
}: VariantToolbarProps) {
  const [tagDropdownOpen, setTagDropdownOpen] = useState(false)
  const tagDropdownRef = useRef<HTMLDivElement>(null)
  const { data: tags } = useTags(sampleId)

  // Close dropdown on outside click
  useEffect(() => {
    if (!tagDropdownOpen) return
    function handleClick(e: MouseEvent) {
      if (tagDropdownRef.current && !tagDropdownRef.current.contains(e.target as Node)) {
        setTagDropdownOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [tagDropdownOpen])

  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-card">
      {/* Search input */}
      <div className="relative flex-1 max-w-sm">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search rsid or gene..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full pl-9 pr-3 py-1.5 text-sm rounded-md border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          aria-label="Search variants by rsid or gene"
        />
      </div>

      {/* Unannotated toggle */}
      <button
        type="button"
        onClick={onToggleUnannotated}
        className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border transition-colors ${
          showUnannotated
            ? "border-primary bg-primary/10 text-primary"
            : "border-input bg-background text-muted-foreground hover:text-foreground"
        }`}
        aria-pressed={showUnannotated}
        aria-label={showUnannotated ? "Hide unannotated variants" : "Show unannotated variants"}
      >
        {showUnannotated ? (
          <Eye className="h-4 w-4" />
        ) : (
          <EyeOff className="h-4 w-4" />
        )}
        <span>
          {showUnannotated ? "Showing" : "Show"} unannotated
          {unannotatedCount != null && ` (${unannotatedCount.toLocaleString()})`}
        </span>
      </button>

      {/* Conflicts only toggle (P2-22) */}
      <button
        type="button"
        onClick={onToggleConflictsOnly}
        className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border transition-colors ${
          showConflictsOnly
            ? "border-amber-500 bg-amber-500/10 text-amber-600 dark:text-amber-400"
            : "border-input bg-background text-muted-foreground hover:text-foreground"
        }`}
        aria-pressed={showConflictsOnly}
        aria-label={showConflictsOnly ? "Show all variants" : "Show conflicts only"}
      >
        <AlertTriangle className="h-4 w-4" />
        <span>Conflicts only</span>
      </button>

      {/* Tag filter dropdown (P4-12b) */}
      <div className="relative" ref={tagDropdownRef}>
        <button
          type="button"
          onClick={() => setTagDropdownOpen((prev) => !prev)}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border transition-colors ${
            activeTag
              ? "border-teal-500 bg-teal-500/10 text-teal-600 dark:text-teal-400"
              : "border-input bg-background text-muted-foreground hover:text-foreground"
          }`}
          aria-expanded={tagDropdownOpen}
          aria-haspopup="listbox"
          aria-label={activeTag ? `Tag filter: ${activeTag}` : "Filter by tag"}
        >
          <Tag className="h-4 w-4" />
          <span>{activeTag ?? "Tags"}</span>
          {activeTag && onTagFilter && (
            <X
              className="h-3 w-3 ml-0.5"
              onClick={(e) => {
                e.stopPropagation()
                onTagFilter(null)
              }}
            />
          )}
        </button>

        {tagDropdownOpen && (
          <div
            className="absolute top-full left-0 mt-1 z-50 min-w-[180px] rounded-md border border-border bg-popover shadow-md py-1"
            role="listbox"
            aria-label="Available tags"
          >
            {!tags || tags.length === 0 ? (
              <div className="px-3 py-2 text-sm text-muted-foreground">No tags available</div>
            ) : (
              tags.map((tag) => (
                <button
                  key={tag.id}
                  type="button"
                  role="option"
                  aria-selected={activeTag === tag.name}
                  className={`w-full flex items-center gap-2 px-3 py-1.5 text-sm text-left hover:bg-accent transition-colors ${
                    activeTag === tag.name ? "bg-accent" : ""
                  }`}
                  onClick={() => {
                    onTagFilter?.(activeTag === tag.name ? null : tag.name)
                    setTagDropdownOpen(false)
                  }}
                >
                  <span
                    className="inline-block h-3 w-3 rounded-full shrink-0"
                    style={{ backgroundColor: tag.color }}
                  />
                  <span className="truncate">{tag.name}</span>
                  {tag.variant_count != null && (
                    <span className="ml-auto text-xs text-muted-foreground">
                      {tag.variant_count}
                    </span>
                  )}
                </button>
              ))
            )}
          </div>
        )}
      </div>

      {/* Active tag badge */}
      {activeTag && onTagFilter && (
        <button
          type="button"
          onClick={() => onTagFilter(null)}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-md border border-teal-500/30 bg-teal-500/10 text-teal-600 dark:text-teal-400 hover:bg-teal-500/20 transition-colors"
          aria-label={`Clear tag filter: ${activeTag}`}
        >
          Tag: {activeTag}
          <X className="h-3 w-3" />
        </button>
      )}

      {/* Active filter badge (P1-15e) */}
      {activeFilter && onClearFilter && (
        <button
          type="button"
          onClick={onClearFilter}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-md border border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
          aria-label={`Clear filter: ${filterLabel(activeFilter)}`}
        >
          {filterLabel(activeFilter)}
          <X className="h-3 w-3" />
        </button>
      )}

      {/* Column preset selector (P1-15c) */}
      <ColumnPresets activePreset={activePreset} onPresetChange={onPresetChange} />

      {/* Total count (async) */}
      <div className="ml-auto text-sm text-muted-foreground" aria-live="polite">
        {isLoading ? (
          "Loading..."
        ) : totalCountLoading ? (
          "Loading count\u2026"
        ) : totalCount != null ? (
          `${totalCount.toLocaleString()} variants`
        ) : null}
      </div>
    </div>
  )
}
