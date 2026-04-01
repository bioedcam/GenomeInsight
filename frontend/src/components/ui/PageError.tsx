/** Consistent error state with retry button used across all pages (P4-26b). */

import { AlertCircle, RefreshCw } from "lucide-react"

interface PageErrorProps {
  /** Error message to display. */
  message?: string
  /** Callback to retry the failed operation. */
  onRetry?: () => void
}

export default function PageError({
  message = "An unexpected error occurred.",
  onRetry,
}: PageErrorProps) {
  return (
    <div
      className="rounded-lg border border-destructive/50 bg-destructive/5 p-6"
      role="alert"
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 text-destructive mt-0.5 shrink-0" />
        <div className="flex-1">
          <p className="font-medium text-destructive">Failed to load data</p>
          <p className="text-sm text-muted-foreground mt-1">{message}</p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent transition-colors"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Retry
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
