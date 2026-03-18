/** Reusable analysis module card for the dashboard grid (P1-20, wired P3-43a).
 *
 * Clickable card that navigates to the module page. Shows module name,
 * icon, finding count badge, top finding preview, and evidence stars.
 */

import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import EvidenceStars from '@/components/ui/EvidenceStars'
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
  /** Number of findings for this module. */
  findingCount?: number
  /** Highest evidence level among this module's findings (1-4). */
  maxEvidenceLevel?: number | null
  /** Text of the top finding (highest evidence). */
  topFindingText?: string | null
}

export default function ModuleCard({
  to,
  label,
  icon: Icon,
  description,
  gated,
  gateText,
  findingCount,
  maxEvidenceLevel,
  topFindingText,
}: ModuleCardProps) {
  const hasFindings = findingCount != null && findingCount > 0

  return (
    <Link
      to={to}
      className={cn(
        'group flex flex-col rounded-lg border bg-card p-4 transition-all',
        'hover:border-primary/50 hover:shadow-sm',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
      )}
      aria-label={`${label} module${hasFindings ? `, ${findingCount} findings` : ''}`}
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
        {hasFindings && (
          <span className="ml-auto rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            {findingCount}
          </span>
        )}
      </div>

      {gated ? (
        <p className="text-xs text-muted-foreground italic">
          {gateText ?? 'Tap to learn more'}
        </p>
      ) : hasFindings && topFindingText ? (
        <div className="space-y-1">
          {maxEvidenceLevel != null && (
            <EvidenceStars level={maxEvidenceLevel} />
          )}
          <p className="text-xs text-muted-foreground line-clamp-2">
            {topFindingText}
          </p>
        </div>
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
