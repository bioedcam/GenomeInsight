/** Reusable analysis module card for the dashboard grid (P1-20).
 *
 * Clickable card that navigates to the module page. Shows module name,
 * icon, and placeholder for finding count / top finding. In Phase 1,
 * all cards show placeholder content — real data wired in P3-43a.
 */

import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'

export interface ModuleCardProps {
  /** Route path (e.g. "/pharmacogenomics"). */
  to: string
  /** Module display name. */
  label: string
  /** Lucide icon component. */
  icon: LucideIcon
  /** Short description shown below the label. */
  description: string
  /** Whether this module requires a gate/acknowledgment (e.g. APOE). */
  gated?: boolean
  /** Gate prompt text when gated. */
  gateText?: string
}

export default function ModuleCard({
  to,
  label,
  icon: Icon,
  description,
  gated,
  gateText,
}: ModuleCardProps) {
  return (
    <Link
      to={to}
      className={cn(
        'group flex flex-col rounded-lg border bg-card p-4 transition-all',
        'hover:border-primary/50 hover:shadow-sm',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
      )}
      aria-label={`${label} module`}
    >
      <div className="flex items-center gap-2.5 mb-2">
        <div
          className={cn(
            'flex h-8 w-8 items-center justify-center rounded-md',
            'bg-primary/10 text-primary',
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
        <h3 className="font-medium text-foreground text-sm">{label}</h3>
      </div>

      {gated ? (
        <p className="text-xs text-muted-foreground italic">
          {gateText ?? 'Tap to learn more'}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground line-clamp-2">
          {description}
        </p>
      )}

      <div className="mt-auto pt-3">
        <span
          className={cn(
            'text-xs text-muted-foreground',
            'group-hover:text-primary transition-colors',
          )}
        >
          View details →
        </span>
      </div>
    </Link>
  )
}
