/** Dashboard status bar — sample info + database version indicators (P1-20).
 *
 * Shows current sample name, variant count, and database statuses.
 * Database dots: filled = downloaded, hollow = not downloaded / update available.
 */

import { useNavigate } from 'react-router-dom'
import { useDatabaseList } from '@/api/setup'
import { cn } from '@/lib/utils'
import { formatNumber } from '@/lib/format'
import { Database, User } from 'lucide-react'
import type { Sample } from '@/types/samples'

interface StatusBarProps {
  sample: Sample
  variantCount: number | null
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60_000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays === 1) return 'yesterday'
  return `${diffDays}d ago`
}

export default function StatusBar({ sample, variantCount }: StatusBarProps) {
  const navigate = useNavigate()
  const { data: dbList } = useDatabaseList()

  const downloadedCount = dbList?.downloaded_count ?? 0
  const totalCount = dbList?.total_count ?? 0

  return (
    <div
      className={cn(
        'flex items-center justify-between gap-4 rounded-lg border bg-card px-4',
        'h-10 text-sm',
      )}
      role="status"
      aria-label="Sample and database status"
    >
      {/* Left: Sample info */}
      <div className="flex items-center gap-2 min-w-0">
        <User className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="font-medium text-foreground truncate">
          {sample.name}
        </span>
        {variantCount != null && (
          <span className="text-muted-foreground">
            · {formatNumber(variantCount)} SNPs
          </span>
        )}
        {sample.created_at && (
          <span className="text-muted-foreground hidden sm:inline">
            · Uploaded {formatRelativeTime(sample.created_at)}
          </span>
        )}
      </div>

      {/* Right: Database status */}
      <button
        type="button"
        onClick={() => navigate('/settings')}
        className={cn(
          'flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors',
          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary rounded',
        )}
        aria-label={`Databases: ${downloadedCount} of ${totalCount} downloaded`}
        title="View database status in Settings"
      >
        <Database className="h-3.5 w-3.5 shrink-0" />
        <span className="hidden sm:inline text-xs">Databases</span>
        <span className="flex items-center gap-0.5" aria-hidden="true">
          {totalCount > 0
            ? Array.from({ length: totalCount }, (_, i) => (
                <span
                  key={i}
                  className={cn(
                    'inline-block h-2 w-2 rounded-full',
                    i < downloadedCount
                      ? 'bg-primary'
                      : 'border border-muted-foreground',
                  )}
                />
              ))
            : <span className="text-xs">—</span>
          }
        </span>
      </button>
    </div>
  )
}
