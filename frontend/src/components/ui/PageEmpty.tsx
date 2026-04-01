/** Contextual empty state with icon, message, and optional action (P4-26b). */

import type { LucideIcon } from "lucide-react"

interface PageEmptyProps {
  /** Icon displayed above the message. */
  icon: LucideIcon
  /** Primary empty state message. */
  title: string
  /** Secondary descriptive text. */
  description?: string
  /** Optional action button. */
  action?: {
    label: string
    onClick: () => void
  }
}

export default function PageEmpty({
  icon: Icon,
  title,
  description,
  action,
}: PageEmptyProps) {
  return (
    <div
      className="rounded-lg border bg-card p-8 text-center"
      role="region"
      aria-label={title}
    >
      <Icon className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
      <p className="text-muted-foreground">{title}</p>
      {description && (
        <p className="text-sm text-muted-foreground/80 mt-1">{description}</p>
      )}
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium text-primary hover:bg-accent transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  )
}
