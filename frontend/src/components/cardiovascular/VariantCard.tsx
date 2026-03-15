/** Cardiovascular monogenic variant card (P3-21).
 *
 * Displays a single P/LP variant with gene, ClinVar significance,
 * review stars, cardiovascular category, conditions, and evidence level.
 */

import { cn } from "@/lib/utils"
import type { CardiovascularVariant } from "@/types/cardiovascular"
import EvidenceStars from "@/components/ui/EvidenceStars"

interface VariantCardProps {
  variant: CardiovascularVariant
  onClick: () => void
  selected?: boolean
}

const SIGNIFICANCE_CONFIG: Record<
  string,
  { color: string; bg: string; border: string; badge: string }
> = {
  Pathogenic: {
    color: "text-red-700 dark:text-red-400",
    bg: "bg-red-50 dark:bg-red-950/30",
    border: "border-red-200 dark:border-red-800",
    badge: "bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300",
  },
  "Likely pathogenic": {
    color: "text-orange-700 dark:text-orange-400",
    bg: "bg-orange-50 dark:bg-orange-950/30",
    border: "border-orange-200 dark:border-orange-800",
    badge: "bg-orange-100 text-orange-800 dark:bg-orange-900/50 dark:text-orange-300",
  },
}

const DEFAULT_CONFIG = {
  color: "text-muted-foreground",
  bg: "bg-card",
  border: "border-border",
  badge: "bg-muted text-muted-foreground",
}

const INHERITANCE_LABELS: Record<string, string> = {
  AD: "Autosomal Dominant",
  AR: "Autosomal Recessive",
  XL: "X-linked",
  XLD: "X-linked Dominant",
  XLR: "X-linked Recessive",
  MT: "Mitochondrial",
}

const CATEGORY_CONFIG: Record<string, { label: string; badge: string }> = {
  FH: {
    label: "Familial Hypercholesterolemia",
    badge: "bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-300",
  },
  Lipid: {
    label: "Lipid Metabolism",
    badge: "bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300",
  },
  Channelopathy: {
    label: "Channelopathy",
    badge: "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300",
  },
  Cardiomyopathy: {
    label: "Cardiomyopathy",
    badge: "bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-300",
  },
}

const DEFAULT_CATEGORY = {
  label: "Cardiovascular",
  badge: "bg-muted text-muted-foreground",
}

export default function VariantCard({ variant, onClick, selected }: VariantCardProps) {
  const config = SIGNIFICANCE_CONFIG[variant.clinvar_significance] || DEFAULT_CONFIG
  const catConfig = CATEGORY_CONFIG[variant.cardiovascular_category] || DEFAULT_CATEGORY

  return (
    <article
      className={cn(
        "rounded-lg border p-4 cursor-pointer transition-all",
        "hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        config.bg,
        config.border,
        selected && "ring-2 ring-primary",
      )}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onClick()
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={`${variant.gene_symbol} ${variant.rsid} — ${variant.clinvar_significance}`}
      data-testid="cardiovascular-variant-card"
    >
      {/* Header: gene + significance badge */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <h3 className="font-semibold text-foreground">{variant.gene_symbol}</h3>
          <p className="text-xs font-mono text-muted-foreground">{variant.rsid}</p>
        </div>
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
            config.badge,
          )}
        >
          {variant.clinvar_significance}
        </span>
      </div>

      {/* Cardiovascular category badge */}
      {variant.cardiovascular_category && (
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium mb-2",
            catConfig.badge,
          )}
          data-testid="category-badge"
        >
          {catConfig.label}
        </span>
      )}

      {/* Genotype + zygosity */}
      {variant.genotype && (
        <p className="text-sm font-mono text-foreground mb-1">
          {variant.genotype}
          {variant.zygosity && (
            <span className="text-muted-foreground ml-2">({variant.zygosity})</span>
          )}
        </p>
      )}

      {/* ClinVar review stars */}
      {variant.clinvar_review_stars > 0 && (
        <p className="text-xs text-muted-foreground mb-1">
          ClinVar review: {"★".repeat(variant.clinvar_review_stars)}
          {"☆".repeat(Math.max(0, 4 - variant.clinvar_review_stars))}
        </p>
      )}

      {/* Conditions */}
      {variant.conditions.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {variant.conditions.map((c) => (
            <span
              key={c}
              className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
            >
              {c}
            </span>
          ))}
        </div>
      )}

      {/* ClinVar conditions */}
      {variant.clinvar_conditions && (
        <p className="text-xs text-muted-foreground mb-2 line-clamp-2">
          {variant.clinvar_conditions}
        </p>
      )}

      {/* Footer: evidence stars + inheritance */}
      <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/50">
        <EvidenceStars level={variant.evidence_level} />
        <span className="text-xs text-muted-foreground">
          {INHERITANCE_LABELS[variant.inheritance] ?? variant.inheritance}
        </span>
      </div>
    </article>
  )
}
