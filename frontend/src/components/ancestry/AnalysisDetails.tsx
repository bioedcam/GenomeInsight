/** Analysis details collapsible section (AMv2 Step 5.3).
 *
 * Shows technical details: AIMs used, PCs, method, reference panel info,
 * missing AIM rate. Collapsed by default to keep the page clean.
 */

import { useState } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import { formatNumber } from "@/lib/format"
import type { AncestryFindingResponse } from "@/types/ancestry"

interface AnalysisDetailsProps {
  finding: AncestryFindingResponse
}

const METHOD_DESCRIPTIONS: Record<string, string> = {
  nnls: "Non-negative least squares (NNLS) against population centroids, validated with k-nearest neighbors (kNN, k=15).",
  idw: "Inverse distance weighting based on PCA centroid distances.",
}

export default function AnalysisDetails({ finding }: AnalysisDetailsProps) {
  const [isOpen, setIsOpen] = useState(false)

  const missingPct = Math.round(finding.missing_aim_rate * 100)
  const coveragePct = Math.round(finding.coverage_fraction * 100)
  const methodDesc = METHOD_DESCRIPTIONS[finding.admixture_method] ?? finding.admixture_method

  return (
    <div className="rounded-lg border bg-card" data-testid="analysis-details">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between p-4 text-left hover:bg-muted/50 transition-colors rounded-lg"
        aria-expanded={isOpen}
        data-testid="analysis-details-toggle"
      >
        <h3 className="text-sm font-semibold text-foreground">Analysis Details</h3>
        {isOpen ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {isOpen && (
        <div className="px-4 pb-4 space-y-3" data-testid="analysis-details-content">
          <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-xs">
            <div>
              <span className="text-muted-foreground">AIMs used</span>
              <p className="font-medium text-foreground">
                {formatNumber(finding.snps_used)} / {formatNumber(finding.snps_total)} ({coveragePct}%)
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Principal components</span>
              <p className="font-medium text-foreground">
                {finding.n_pcs_used > 0 ? finding.n_pcs_used : finding.pc_scores.length}
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Missing AIM rate</span>
              <p className="font-medium text-foreground">{missingPct}%</p>
            </div>
            <div>
              <span className="text-muted-foreground">Projection time</span>
              <p className="font-medium text-foreground">{finding.projection_time_ms.toFixed(0)} ms</p>
            </div>
          </div>

          <div className="pt-2 border-t">
            <span className="text-xs text-muted-foreground">Method</span>
            <p className="text-xs text-foreground mt-1">{methodDesc}</p>
          </div>

          <div className="pt-2 border-t">
            <span className="text-xs text-muted-foreground">Reference panel</span>
            <p className="text-xs text-foreground mt-1">
              3,419 single-ancestry samples from gnomAD HGDP+1KG across 7 superpopulations.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
