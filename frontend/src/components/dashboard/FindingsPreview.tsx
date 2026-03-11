/** High-confidence findings preview for the dashboard (P1-20).
 *
 * Shows top findings (★★★★ and ★★★) across all analysis modules.
 * In Phase 1 this is a placeholder — real findings are wired in P3-43a.
 */

import { cn } from '@/lib/utils'
import { Star } from 'lucide-react'

export default function FindingsPreview() {
  return (
    <section aria-label="High-confidence findings">
      <h2 className="text-sm font-semibold text-foreground mb-3">
        High-Confidence Findings
      </h2>

      <div
        className={cn(
          'rounded-lg border bg-card p-6 text-center',
        )}
      >
        <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-muted">
          <Star className="h-5 w-5 text-muted-foreground" />
        </div>
        <p className="mt-3 text-sm text-muted-foreground">
          No findings yet
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Run annotation to see high-confidence findings across all analysis modules.
        </p>
      </div>
    </section>
  )
}
