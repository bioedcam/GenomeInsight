/** Variant table toolbar: search input + unannotated toggle (P1-15a). */

import { Search, Eye, EyeOff } from "lucide-react"

interface VariantToolbarProps {
  searchQuery: string
  onSearchChange: (query: string) => void
  showUnannotated: boolean
  onToggleUnannotated: () => void
  unannotatedCount: number | undefined
  totalCount: number | undefined
  totalCountLoading: boolean
  isLoading: boolean
}

export default function VariantToolbar({
  searchQuery,
  onSearchChange,
  showUnannotated,
  onToggleUnannotated,
  unannotatedCount,
  totalCount,
  totalCountLoading,
  isLoading,
}: VariantToolbarProps) {
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
