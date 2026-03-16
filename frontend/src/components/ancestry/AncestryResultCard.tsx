/** Ancestry inference summary card (P3-27).
 *
 * Shows the top inferred population, coverage stats, and
 * evidence level for the ancestry inference result.
 */

import { cn } from "@/lib/utils"
import { formatNumber } from "@/lib/format"
import EvidenceStars from "@/components/ui/EvidenceStars"
import type { AncestryFindingResponse } from "@/types/ancestry"
import { POPULATION_COLORS, POPULATION_LABELS } from "./constants"

interface AncestryResultCardProps {
  finding: AncestryFindingResponse
}

export default function AncestryResultCard({ finding }: AncestryResultCardProps) {
  const topLabel = POPULATION_LABELS[finding.top_population] ?? finding.top_population
  const coveragePct = Math.round(finding.coverage_fraction * 100)

  return (
    <div
      className="rounded-lg border bg-card p-5"
      data-testid="ancestry-result-card"
    >
      <div className="flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-lg font-semibold text-foreground">
              Inferred Ancestry
            </h3>
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                "bg-primary/10 text-primary",
              )}
              data-testid="top-population-badge"
            >
              {topLabel}
            </span>
          </div>

          <p className="text-sm text-muted-foreground mb-3">
            {finding.finding_text}
          </p>

          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span>
              {formatNumber(finding.snps_used)} / {formatNumber(finding.snps_total)} AIMs used ({coveragePct}%)
            </span>
            <span className="flex items-center gap-1">
              Evidence: <EvidenceStars level={finding.evidence_level} />
            </span>
            {!finding.is_sufficient && (
              <span className="text-amber-600 dark:text-amber-400 font-medium">
                Low coverage — results may be unreliable
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Population ranking */}
      {finding.population_ranking.length > 0 && (
        <div className="mt-4 pt-3 border-t">
          <p className="text-xs font-medium text-muted-foreground mb-2">Population Ranking</p>
          <div className="space-y-1">
            {finding.population_ranking.map((pr) => {
              const label = POPULATION_LABELS[pr.population] ?? pr.population
              const color = POPULATION_COLORS[pr.population] ?? "#94A3B8"
              return (
                <div
                  key={pr.population}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="flex items-center gap-2">
                    <span
                      className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: color }}
                    />
                    <span className="text-foreground">{label}</span>
                  </span>
                  <span className="text-muted-foreground font-mono">
                    {pr.distance.toFixed(4)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
