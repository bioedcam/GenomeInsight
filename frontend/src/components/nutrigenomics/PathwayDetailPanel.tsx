/** Pathway detail slide-in panel for nutrigenomics (P3-11).
 *
 * Shows the per-SNP breakdown for a selected pathway with genotypes,
 * effect summaries, recommendations, and PubMed literature links.
 */

import { cn } from "@/lib/utils"
import { useNutrigenomicsPathwayDetail } from "@/api/nutrigenomics"
import type { SNPDetail, PathwayLevel } from "@/types/nutrigenomics"
import { X, Loader2, ExternalLink, AlertCircle, Dna } from "lucide-react"

interface PathwayDetailPanelProps {
  pathwayId: string
  pathwayName: string
  sampleId: number
  onClose: () => void
}

const CATEGORY_COLORS: Record<PathwayLevel, string> = {
  Elevated: "text-amber-700 dark:text-amber-400",
  Moderate: "text-blue-700 dark:text-blue-400",
  Standard: "text-emerald-700 dark:text-emerald-400",
}

const CATEGORY_DOT: Record<PathwayLevel, string> = {
  Elevated: "bg-amber-500",
  Moderate: "bg-blue-500",
  Standard: "bg-emerald-500",
}

function EvidenceStars({ level }: { level: number }) {
  const stars = Math.max(0, Math.min(4, level))
  return (
    <span
      className="text-xs text-muted-foreground"
      role="img"
      aria-label={`${stars} of 4 stars evidence`}
    >
      {"★".repeat(stars)}
      {"☆".repeat(4 - stars)}
    </span>
  )
}

function SNPRow({ snp }: { snp: SNPDetail }) {
  const categoryColor = CATEGORY_COLORS[snp.category] || CATEGORY_COLORS.Standard
  const dotColor = CATEGORY_DOT[snp.category] || CATEGORY_DOT.Standard

  return (
    <div className="rounded-lg border bg-card p-4">
      {/* SNP header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <span className={cn("h-2 w-2 rounded-full shrink-0", dotColor)} />
          <div>
            <span className="font-mono text-sm font-medium text-foreground">
              {snp.rsid}
            </span>
            <span className="text-sm text-muted-foreground ml-2">
              {snp.gene} — {snp.variant_name}
            </span>
          </div>
        </div>
        <span className={cn("text-xs font-medium whitespace-nowrap", categoryColor)}>
          {snp.category}
        </span>
      </div>

      {/* Genotype */}
      {snp.genotype && (
        <p className="text-sm mb-1">
          <span className="text-muted-foreground">Genotype: </span>
          <span className="font-mono font-medium">{snp.genotype}</span>
        </p>
      )}

      {/* Effect summary */}
      <p className="text-sm text-muted-foreground mb-2">{snp.effect_summary}</p>

      {/* Recommendation */}
      {snp.recommendation && (
        <p className="text-sm text-foreground bg-muted/50 rounded px-3 py-2 mb-2">
          {snp.recommendation}
        </p>
      )}

      {/* Footer: evidence + PubMed links */}
      <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/50">
        <EvidenceStars level={snp.evidence_level} />
        {snp.pmids.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            {snp.pmids.map((pmid) => (
              <a
                key={pmid}
                href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}/`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                aria-label={`PubMed article ${pmid}`}
              >
                PMID:{pmid}
                <ExternalLink className="h-3 w-3" aria-hidden="true" />
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function PathwayDetailPanel({
  pathwayId,
  pathwayName,
  sampleId,
  onClose,
}: PathwayDetailPanelProps) {
  const detailQuery = useNutrigenomicsPathwayDetail(pathwayId, sampleId)

  return (
    <aside
      className={cn(
        "fixed right-0 top-0 z-40 h-full w-full max-w-lg",
        "bg-background border-l shadow-xl",
        "flex flex-col",
        "animate-in slide-in-from-right duration-200",
      )}
      role="dialog"
      aria-label={`${pathwayName} pathway details`}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b px-6 py-4">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold truncate">{pathwayName}</h2>
          {detailQuery.data && (
            <p className="text-sm text-muted-foreground">
              {detailQuery.data.called_snps}/{detailQuery.data.total_snps} SNPs called
              {detailQuery.data.missing_snps.length > 0 && (
                <span className="ml-1">
                  ({detailQuery.data.missing_snps.length} not on array)
                </span>
              )}
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1.5 hover:bg-muted transition-colors"
          aria-label="Close pathway details"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {/* Loading */}
        {detailQuery.isLoading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Error */}
        {detailQuery.isError && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-5 w-5 text-destructive mt-0.5 shrink-0" />
              <p className="text-sm text-destructive">
                {detailQuery.error instanceof Error
                  ? detailQuery.error.message
                  : "Failed to load pathway details."}
              </p>
            </div>
          </div>
        )}

        {/* Data */}
        {detailQuery.data && (
          <>
            {/* Pathway-level PubMed references */}
            {detailQuery.data.pmids.length > 0 && (
              <section className="mb-6" aria-label="Pathway literature references">
                <h3 className="text-sm font-semibold mb-2">Literature References</h3>
                <div className="flex flex-wrap gap-2">
                  {detailQuery.data.pmids.map((pmid) => (
                    <a
                      key={pmid}
                      href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}/`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs hover:bg-muted transition-colors"
                      aria-label={`PubMed article ${pmid}`}
                    >
                      PMID:{pmid}
                      <ExternalLink className="h-3 w-3" aria-hidden="true" />
                    </a>
                  ))}
                </div>
              </section>
            )}

            {/* SNP details */}
            <section aria-label="Individual SNP results">
              <h3 className="text-sm font-semibold mb-3">
                Individual Variants ({detailQuery.data.snp_details.length})
              </h3>
              {detailQuery.data.snp_details.length > 0 ? (
                <div className="space-y-3">
                  {detailQuery.data.snp_details.map((snp) => (
                    <SNPRow key={snp.rsid} snp={snp} />
                  ))}
                </div>
              ) : (
                <div className="rounded-lg border bg-card p-6 text-center">
                  <Dna className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">
                    No variant data available for this pathway.
                  </p>
                </div>
              )}
            </section>

            {/* Missing SNPs note */}
            {detailQuery.data.missing_snps.length > 0 && (
              <section className="mt-4" aria-label="Missing SNPs">
                <p className="text-xs text-muted-foreground italic">
                  Not on array: {detailQuery.data.missing_snps.join(", ")}
                </p>
              </section>
            )}
          </>
        )}
      </div>
    </aside>
  )
}
