/** Pathway card for Gene Health module (P3-66).
 *
 * Displays a single disease system pathway with its categorical level
 * (Elevated / Moderate / Standard), evidence stars, SNP coverage,
 * and contextual description. Click to expand detail view.
 */

import { cn } from "@/lib/utils"
import type { PathwaySummary, PathwayLevel } from "@/types/gene-health"
import EvidenceStars from "@/components/ui/EvidenceStars"
import { ChevronRight } from "lucide-react"

interface PathwayCardProps {
  pathway: PathwaySummary
  onClick: () => void
  selected?: boolean
}

const LEVEL_CONFIG: Record<
  PathwayLevel,
  { label: string; color: string; bg: string; border: string; badge: string }
> = {
  Elevated: {
    label: "Elevated",
    color: "text-amber-700 dark:text-amber-400",
    bg: "bg-amber-50 dark:bg-amber-950/30",
    border: "border-amber-200 dark:border-amber-800",
    badge: "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300",
  },
  Moderate: {
    label: "Moderate",
    color: "text-blue-700 dark:text-blue-400",
    bg: "bg-blue-50 dark:bg-blue-950/30",
    border: "border-blue-200 dark:border-blue-800",
    badge: "bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300",
  },
  Standard: {
    label: "Standard",
    color: "text-emerald-700 dark:text-emerald-400",
    bg: "bg-emerald-50 dark:bg-emerald-950/30",
    border: "border-emerald-200 dark:border-emerald-800",
    badge: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300",
  },
}

const PATHWAY_DESCRIPTIONS: Record<string, string> = {
  neurological:
    "Genetic associations with neurological conditions including Alzheimer's, Parkinson's, multiple sclerosis, ADHD, and migraine.",
  metabolic:
    "Genetic associations with metabolic conditions including type 2 diabetes, obesity, gout, and non-alcoholic fatty liver disease.",
  autoimmune:
    "Genetic associations with autoimmune conditions including rheumatoid arthritis, type 1 diabetes, IBD, celiac disease, and SLE.",
  sensory:
    "Genetic associations with sensory conditions including hearing loss, achromatopsia, and retinitis pigmentosa.",
}

export default function PathwayCard({ pathway, onClick, selected }: PathwayCardProps) {
  const config = LEVEL_CONFIG[pathway.level] || LEVEL_CONFIG.Standard
  const description = PATHWAY_DESCRIPTIONS[pathway.pathway_id] || ""

  return (
    <button
      type="button"
      className={cn(
        "w-full text-left rounded-lg border p-4 cursor-pointer transition-all",
        "hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        config.bg,
        config.border,
        selected && "ring-2 ring-primary",
      )}
      onClick={onClick}
      aria-label={`${pathway.pathway_name} — ${config.label}`}
      aria-pressed={!!selected}
      data-selected={selected || undefined}
    >
      {/* Header: pathway name + level badge */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="font-semibold text-foreground">{pathway.pathway_name}</h3>
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
            config.badge,
          )}
        >
          {config.label}
        </span>
      </div>

      {/* Description */}
      {description && (
        <p className="text-sm text-muted-foreground mb-3">{description}</p>
      )}

      {/* Footer: evidence stars + SNP coverage + expand hint */}
      <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/50">
        <div className="flex items-center gap-3">
          <EvidenceStars level={pathway.evidence_level} />
          <span className="text-xs text-muted-foreground">
            {pathway.called_snps}/{pathway.total_snps} SNPs called
          </span>
        </div>
        <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" aria-hidden="true" />
      </div>
    </button>
  )
}
