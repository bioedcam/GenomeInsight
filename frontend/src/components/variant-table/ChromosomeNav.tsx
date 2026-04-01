/** Chromosome anchor navigation bar (P1-15b).
 *
 * Horizontal bar with buttons for chr1–22, X, Y, MT. Clicking an anchor
 * jumps to the first variant on that chromosome via the cursor API.
 * Shows a visual indicator of the current chromosome and variant counts.
 */

import { useMemo } from "react"
import { CHROMOSOMES, type ChromosomeSummary } from "@/types/variants"
import { cn } from "@/lib/utils"

interface ChromosomeNavProps {
  /** Per-chromosome variant counts from the API. */
  chromosomeCounts: ChromosomeSummary[] | undefined
  /** Whether chromosome count data is loading. */
  isLoading: boolean
  /** Currently active/visible chromosome (derived from loaded data). */
  activeChrom: string | null
  /** Callback when a chromosome button is clicked. */
  onJumpToChrom: (chrom: string) => void
}

export default function ChromosomeNav({
  chromosomeCounts,
  isLoading,
  activeChrom,
  onJumpToChrom,
}: ChromosomeNavProps) {
  // Build a lookup map: chrom -> count
  const countMap = useMemo(() => {
    const map = new Map<string, number>()
    if (chromosomeCounts) {
      for (const { chrom, count } of chromosomeCounts) {
        map.set(chrom, count)
      }
    }
    return map
  }, [chromosomeCounts])

  // Find max count for relative sizing of count indicators
  const maxCount = useMemo(() => {
    if (!chromosomeCounts?.length) return 0
    return Math.max(...chromosomeCounts.map((c) => c.count))
  }, [chromosomeCounts])

  if (isLoading) {
    return (
      <div
        className="flex items-center gap-1 px-4 py-1.5 border-b border-border bg-card overflow-x-auto"
        aria-label="Chromosome navigation"
        role="toolbar"
      >
        <span className="text-xs text-muted-foreground mr-2 shrink-0">Chr</span>
        {CHROMOSOMES.map((chrom) => (
          <span
            key={chrom}
            className="h-7 w-7 rounded bg-muted animate-pulse shrink-0 inline-block"
          />
        ))}
      </div>
    )
  }

  return (
    <div
      className="flex items-center gap-1 px-4 py-1.5 border-b border-border bg-card overflow-x-auto"
      aria-label="Chromosome navigation"
      role="toolbar"
    >
      <span className="text-xs text-muted-foreground mr-2 shrink-0 font-medium">Chr</span>
      {CHROMOSOMES.map((chrom) => {
        const count = countMap.get(chrom) ?? 0
        const hasData = count > 0
        const isActive = activeChrom === chrom
        // Relative intensity: opacity scales with count proportion
        const intensity = hasData && maxCount > 0 ? Math.max(0.15, count / maxCount) : 0

        return (
          <button
            key={chrom}
            type="button"
            onClick={() => hasData && onJumpToChrom(chrom)}
            disabled={!hasData}
            title={
              hasData
                ? `Chromosome ${chrom}: ${count.toLocaleString()} variants`
                : `Chromosome ${chrom}: no variants`
            }
            aria-label={`Jump to chromosome ${chrom}${hasData ? `, ${count.toLocaleString()} variants` : ""}`}
            aria-current={isActive ? "location" : undefined}
            className={cn(
              "relative flex flex-col items-center justify-center shrink-0",
              "min-w-[28px] h-8 px-1 rounded text-xs font-mono transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
              isActive && hasData
                ? "bg-primary text-primary-foreground font-semibold shadow-sm"
                : hasData
                  ? "bg-background border border-input text-foreground hover:bg-accent hover:text-accent-foreground"
                  : "bg-muted/50 text-muted-foreground/40 cursor-not-allowed border border-transparent",
            )}
          >
            <span>{chrom}</span>
            {/* Variant density indicator bar */}
            {hasData && !isActive && (
              <span
                className="absolute bottom-0.5 left-1/2 -translate-x-1/2 h-[2px] rounded-full bg-primary"
                style={{ width: `${Math.max(20, intensity * 100)}%` }}
                aria-hidden="true"
              />
            )}
          </button>
        )
      })}
    </div>
  )
}
