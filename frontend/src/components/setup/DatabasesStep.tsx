/** Setup wizard Step 5 — Download databases with parallel per-DB progress (P1-19f).
 *
 * Shows all reference databases, their status, and allows the user to trigger
 * parallel downloads. Progress is streamed via SSE from the backend.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { DATABASE_LIST_KEY, useDatabaseList, useTriggerDownload } from '@/api/setup'
import { useQueryClient } from '@tanstack/react-query'
import type { DatabaseProgressEvent, DownloadProgressData } from '@/types/setup'
import { cn } from '@/lib/utils'
import {
  AlertCircle,
  CheckCircle2,
  Database,
  Download,
  HardDrive,
  Loader2,
  RefreshCw,
} from 'lucide-react'

interface DatabasesStepProps {
  onNext: () => void
  onBack: () => void
}

/** Format bytes to a human-readable string (e.g. "1.5 GB"). */
function formatBytes(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`
  if (bytes >= 1_000) return `${(bytes / 1_000).toFixed(1)} KB`
  return `${bytes} B`
}

export default function DatabasesStep({ onNext, onBack }: DatabasesStepProps) {
  const queryClient = useQueryClient()
  const { data: dbList, isLoading, isError, error } = useDatabaseList()
  const triggerDownload = useTriggerDownload()

  // Per-DB progress from SSE
  const [dbProgress, setDbProgress] = useState<
    Record<string, DatabaseProgressEvent>
  >({})
  const [isDownloading, setIsDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close()
    }
  }, [])

  const handleStartDownload = useCallback(() => {
    if (!dbList) return

    // Get databases that need downloading
    const toDownload = dbList.databases
      .filter((db) => !db.downloaded)
      .map((db) => db.name)

    if (toDownload.length === 0) return

    setIsDownloading(true)
    setDownloadError(null)
    setDbProgress({})

    triggerDownload.mutate(toDownload, {
      onSuccess: (result) => {
        // Initialize progress for each database
        const initial: Record<string, DatabaseProgressEvent> = {}
        for (const dl of result.downloads) {
          initial[dl.db_name] = {
            db_name: dl.db_name,
            job_id: dl.job_id,
            status: 'pending',
            progress_pct: 0,
            message: 'Queued...',
            error: null,
          }
        }
        setDbProgress(initial)

        // Connect to SSE progress stream
        const es = new EventSource(
          `/api/databases/progress/${result.session_id}`,
        )
        eventSourceRef.current = es

        es.addEventListener('progress', (event: MessageEvent) => {
          const data: DownloadProgressData = JSON.parse(event.data)

          const updated: Record<string, DatabaseProgressEvent> = {}
          for (const db of data.databases) {
            updated[db.db_name] = db
          }
          setDbProgress(updated)

          // Check if all are terminal
          const allTerminal = data.databases.every(
            (db) =>
              db.status === 'complete' || db.status === 'failed',
          )
          if (allTerminal) {
            es.close()
            eventSourceRef.current = null
            setIsDownloading(false)

            // Refresh database list to get updated downloaded status
            queryClient.invalidateQueries({ queryKey: DATABASE_LIST_KEY })

            // Check if any failed
            const failed = data.databases.filter(
              (db) => db.status === 'failed',
            )
            if (failed.length > 0) {
              setDownloadError(
                `${failed.length} database(s) failed to download. You can retry.`,
              )
            }
          }
        })

        es.addEventListener('error', () => {
          es.close()
          eventSourceRef.current = null
          setIsDownloading(false)
          setDownloadError(
            'Lost connection to download progress stream. Check your downloads and retry if needed.',
          )
          queryClient.invalidateQueries({ queryKey: DATABASE_LIST_KEY })
        })
      },
      onError: (err) => {
        setIsDownloading(false)
        setDownloadError(
          err instanceof Error ? err.message : 'Failed to start downloads',
        )
      },
    })
  }, [dbList, triggerDownload, queryClient])

  const handleRetry = useCallback(() => {
    setDownloadError(null)
    handleStartDownload()
  }, [handleStartDownload])

  // Determine if we can proceed (all required DBs downloaded)
  const allRequiredDownloaded = dbList
    ? dbList.databases
        .filter((db) => db.required)
        .every((db) => {
          // Check live progress if available
          const progress = dbProgress[db.name]
          if (progress) return progress.status === 'complete'
          return db.downloaded
        })
    : false

  const needsDownload = dbList
    ? dbList.databases.some((db) => !db.downloaded)
    : false

  // ── Loading state ──────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex flex-col items-center gap-4 py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="text-sm text-muted-foreground">
          Loading database information...
        </p>
      </div>
    )
  }

  // ── Error state ────────────────────────────────────────────

  if (isError) {
    return (
      <div className="space-y-6">
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-center">
          <AlertCircle className="mx-auto h-8 w-8 text-destructive" />
          <p className="mt-3 text-sm font-medium text-destructive">
            Failed to load database information
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
        <div className="flex justify-center">
          <button
            type="button"
            onClick={onBack}
            className={cn(
              'rounded-lg border border-border px-5 py-2.5 text-sm font-medium',
              'text-foreground hover:bg-accent transition-colors',
              'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
            )}
          >
            Back
          </button>
        </div>
      </div>
    )
  }

  // ── Main content ───────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
          <Database className="h-6 w-6 text-primary" />
        </div>
        <h2 className="mt-3 text-xl font-semibold text-foreground">
          Reference Databases
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          GenomeInsight needs reference databases for variant annotation.
          {dbList && (
            <span className="block mt-1">
              Total size: {formatBytes(dbList.total_size_bytes)} &middot;{' '}
              {dbList.downloaded_count} of {dbList.total_count} downloaded
            </span>
          )}
        </p>
      </div>

      {/* Database list */}
      {dbList && (
        <div className="space-y-3">
          {dbList.databases.map((db) => {
            const progress = dbProgress[db.name]
            const isComplete = progress
              ? progress.status === 'complete'
              : db.downloaded
            const isFailed = progress?.status === 'failed'
            const isRunning = progress?.status === 'running'
            const isPending = progress?.status === 'pending'

            return (
              <div
                key={db.name}
                className={cn(
                  'rounded-lg border p-4 transition-colors',
                  isComplete && 'border-green-500/30 bg-green-500/5',
                  isFailed && 'border-destructive/30 bg-destructive/5',
                  !isComplete && !isFailed && 'border-border bg-card',
                )}
              >
                <div className="flex items-start gap-3">
                  {/* Status icon */}
                  <div className="mt-0.5 flex-shrink-0">
                    {isComplete && (
                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                    )}
                    {isFailed && (
                      <AlertCircle className="h-5 w-5 text-destructive" />
                    )}
                    {isRunning && (
                      <Loader2 className="h-5 w-5 animate-spin text-primary" />
                    )}
                    {isPending && (
                      <Download className="h-5 w-5 text-muted-foreground" />
                    )}
                    {!progress && !db.downloaded && (
                      <HardDrive className="h-5 w-5 text-muted-foreground" />
                    )}
                  </div>

                  {/* Info */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground">
                        {db.display_name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {formatBytes(db.expected_size_bytes)}
                      </span>
                      {db.required && (
                        <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                          Required
                        </span>
                      )}
                      {!db.required && (
                        <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                          Optional
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {db.description}
                    </p>

                    {/* Progress bar */}
                    {(isRunning || isPending) && (
                      <div className="mt-2">
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                          <div
                            className={cn(
                              'h-full rounded-full transition-all duration-300',
                              isRunning
                                ? 'bg-primary'
                                : 'bg-muted-foreground/30',
                            )}
                            style={{
                              width: `${Math.max(progress?.progress_pct ?? 0, isRunning ? 2 : 0)}%`,
                            }}
                            role="progressbar"
                            aria-valuenow={Math.round(
                              progress?.progress_pct ?? 0,
                            )}
                            aria-valuemin={0}
                            aria-valuemax={100}
                            aria-label={`${db.display_name} download progress`}
                          />
                        </div>
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          {progress?.message || 'Waiting...'}
                        </p>
                      </div>
                    )}

                    {/* Error message */}
                    {isFailed && progress?.error && (
                      <p className="mt-1 text-xs text-destructive">
                        {progress.error}
                      </p>
                    )}

                    {/* Downloaded status */}
                    {isComplete && (
                      <p className="mt-0.5 text-xs text-green-600 dark:text-green-400">
                        Downloaded
                        {db.file_size_bytes != null &&
                          ` (${formatBytes(db.file_size_bytes)})`}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Download error banner */}
      {downloadError && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-destructive" />
            <p className="text-sm text-destructive">{downloadError}</p>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          onClick={onBack}
          disabled={isDownloading}
          className={cn(
            'rounded-lg border border-border px-5 py-2.5 text-sm font-medium',
            'text-foreground hover:bg-accent transition-colors',
            'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
            'disabled:opacity-50 disabled:cursor-not-allowed',
          )}
        >
          Back
        </button>

        <div className="flex items-center gap-3">
          {/* Download / Retry button */}
          {needsDownload && !isDownloading && (
            <button
              type="button"
              onClick={downloadError ? handleRetry : handleStartDownload}
              className={cn(
                'inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium',
                'bg-primary text-primary-foreground hover:bg-primary/90 transition-colors',
                'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
              )}
            >
              {downloadError ? (
                <>
                  <RefreshCw className="h-4 w-4" />
                  Retry Download
                </>
              ) : (
                <>
                  <Download className="h-4 w-4" />
                  Download All
                </>
              )}
            </button>
          )}

          {/* Downloading indicator */}
          {isDownloading && (
            <div className="inline-flex items-center gap-2 rounded-lg bg-muted px-5 py-2.5 text-sm font-medium text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Downloading...
            </div>
          )}

          {/* Continue button */}
          <button
            type="button"
            onClick={onNext}
            disabled={!allRequiredDownloaded || isDownloading}
            className={cn(
              'rounded-lg px-5 py-2.5 text-sm font-medium transition-colors',
              'bg-primary text-primary-foreground hover:bg-primary/90',
              'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
              'disabled:opacity-50 disabled:cursor-not-allowed',
            )}
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  )
}
