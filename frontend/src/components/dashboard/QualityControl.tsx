/** Collapsible QC summary card for the dashboard (P1-20).
 *
 * Shows basic sample quality metrics: call rate, heterozygosity ratio, Ti/Tv.
 * In Phase 1 only variant count is available. Plotly charts added in P1-21.
 */

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { ChevronDown, ChevronRight, FlaskConical } from 'lucide-react'

interface QualityControlProps {
  variantCount: number | null
}

function formatNumber(n: number): string {
  return n.toLocaleString()
}

export default function QualityControl({ variantCount }: QualityControlProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <section aria-label="Sample quality control">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className={cn(
          'flex w-full items-center justify-between rounded-lg border bg-card px-4 py-3',
          'text-sm font-medium text-foreground hover:bg-accent/50 transition-colors',
          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
          expanded && 'rounded-b-none border-b-0',
        )}
        aria-expanded={expanded}
        aria-controls="qc-content"
      >
        <span className="flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-muted-foreground" />
          Sample QC
        </span>
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {expanded && (
        <div
          id="qc-content"
          className="rounded-b-lg border border-t-0 bg-card px-4 py-4 space-y-3"
        >
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">Total Variants</p>
              <p className="text-sm font-medium text-foreground">
                {variantCount != null ? formatNumber(variantCount) : '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Call Rate</p>
              <p className="text-sm font-medium text-muted-foreground">
                —
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Ti/Tv Ratio</p>
              <p className="text-sm font-medium text-muted-foreground">
                —
              </p>
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            Detailed QC charts will be available after annotation.
          </p>
        </div>
      )}
    </section>
  )
}
