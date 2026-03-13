/**
 * Shared placeholder component for modules not yet implemented.
 *
 * Renders a clear "Coming soon" card with the module name, target phase,
 * and optional description so users/testers don't mistake skeletons for bugs.
 */
import { Construction } from "lucide-react"

interface PlaceholderPageProps {
  moduleName: string
  phase: number
  description?: string
}

export default function PlaceholderPage({
  moduleName,
  phase,
  description,
}: PlaceholderPageProps) {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold">{moduleName}</h1>
      <div className="mt-6 max-w-lg rounded-lg border border-border bg-card p-6">
        <div className="flex items-start gap-3">
          <Construction className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Coming soon</span>
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                Phase {phase}
              </span>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              {description ??
                `This module is planned for Phase ${phase} of the GenomeInsight roadmap.`}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
