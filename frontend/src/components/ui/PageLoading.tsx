/** Consistent full-page loading spinner used across all pages (P4-26b). */

import { Loader2 } from "lucide-react"

interface PageLoadingProps {
  /** Message shown below the spinner. */
  message?: string
}

export default function PageLoading({ message = "Loading..." }: PageLoadingProps) {
  return (
    <div className="flex items-center justify-center py-16" role="status" aria-label={message}>
      <div className="text-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mx-auto" />
        <p className="text-sm text-muted-foreground mt-3">{message}</p>
      </div>
    </div>
  )
}
