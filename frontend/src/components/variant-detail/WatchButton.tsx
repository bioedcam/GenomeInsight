/** Watch/Unwatch toggle button for variant detail (P4-21j).
 *
 * Used in both the side panel and the full detail page.
 * Toggles between "Watch this variant" and "Unwatch" states. */

import { Eye, EyeOff, Loader2 } from "lucide-react"

import { useWatchedVariants, useWatchVariant, useUnwatchVariant } from "@/api/watches"
import { cn } from "@/lib/utils"

interface WatchButtonProps {
  rsid: string
  sampleId: number
  /** Compact mode for use in the page header. */
  compact?: boolean
  className?: string
}

export default function WatchButton({
  rsid,
  sampleId,
  compact = false,
  className,
}: WatchButtonProps) {
  const { data: watchedVariants } = useWatchedVariants(sampleId)
  const watchMutation = useWatchVariant(sampleId)
  const unwatchMutation = useUnwatchVariant(sampleId)

  const isWatched = Array.isArray(watchedVariants) && watchedVariants.some((w) => w.rsid === rsid)
  const isPending = watchMutation.isPending || unwatchMutation.isPending

  const handleClick = () => {
    if (isPending) return
    if (isWatched) {
      unwatchMutation.mutate(rsid)
    } else {
      watchMutation.mutate(rsid)
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={isPending}
      aria-label={isWatched ? "Unwatch this variant" : "Watch this variant"}
      className={cn(
        "inline-flex items-center gap-1.5 font-medium rounded-md transition-colors",
        compact
          ? "px-3 py-1.5 text-xs"
          : "px-4 py-2 text-sm w-full justify-center",
        isWatched
          ? "border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-950/50"
          : "border border-input bg-background text-foreground hover:bg-accent",
        isPending && "opacity-60 cursor-not-allowed",
        className,
      )}
    >
      {isPending ? (
        <Loader2 className={cn("animate-spin", compact ? "h-3 w-3" : "h-3.5 w-3.5")} />
      ) : isWatched ? (
        <EyeOff className={cn(compact ? "h-3 w-3" : "h-3.5 w-3.5")} />
      ) : (
        <Eye className={cn(compact ? "h-3 w-3" : "h-3.5 w-3.5")} />
      )}
      {isWatched ? "Unwatch" : "Watch this variant"}
    </button>
  )
}
