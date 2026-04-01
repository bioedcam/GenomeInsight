/** Ancestry module page (P3-27, P3-34).
 *
 * Layout:
 * - Ancestry result summary card (top population, coverage, evidence)
 * - Admixture bar chart (population fractions)
 * - PCA scatter plot (user projected onto reference panel)
 * - Haplogroup assignments with traversal path (P3-34)
 *
 * PRD P3-27: Ancestry UI — admixture bar, PCA scatter.
 * PRD P3-34: Ancestry UI haplogroup extension.
 */

import { useSearchParams } from "react-router-dom"
import { Globe, Loader2 } from "lucide-react"
import PageLoading from "@/components/ui/PageLoading"
import PageError from "@/components/ui/PageError"
import PageEmpty from "@/components/ui/PageEmpty"
import { cn } from "@/lib/utils"
import { parseSampleId } from "@/lib/format"
import { useAncestryFindings, useHaplogroups, usePCACoordinates } from "@/api/ancestry"
import AncestryResultCard from "@/components/ancestry/AncestryResultCard"
import AdmixtureBar from "@/components/ancestry/AdmixtureBar"
import PCAScatter from "@/components/ancestry/PCAScatter"
import HaplogroupCard from "@/components/ancestry/HaplogroupCard"

export default function AncestryView() {
  const [searchParams] = useSearchParams()
  const sampleId = parseSampleId(searchParams.get("sample_id"))

  const findingsQuery = useAncestryFindings(sampleId)
  const pcaQuery = usePCACoordinates(sampleId)
  const haplogroupQuery = useHaplogroups(sampleId)

  // No sample selected
  if (sampleId == null) {
    return (
      <div className="p-6">
        <PageEmpty icon={Globe} title="Select a sample to view ancestry results." />
      </div>
    )
  }

  const isLoading = findingsQuery.isLoading
  const hasError = findingsQuery.isError

  return (
    <div className="p-6">
      {/* Page header */}
      <div className="flex items-center gap-3 mb-6">
        <div
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-lg",
            "bg-primary/10 text-primary",
          )}
        >
          <Globe className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Ancestry</h1>
          <p className="text-sm text-muted-foreground">
            Ancestry inference via PCA projection and admixture estimation
          </p>
        </div>
      </div>

      {/* Loading state */}
      {isLoading && (
        <PageLoading message="Loading ancestry data..." />
      )}

      {/* Error state */}
      {hasError && !isLoading && (
        <PageError
          message={findingsQuery.error instanceof Error ? findingsQuery.error.message : "An unexpected error occurred."}
          onRetry={() => { findingsQuery.refetch(); }}
        />
      )}

      {/* No results yet */}
      {!isLoading && !hasError && !findingsQuery.data && (
        <PageEmpty
          icon={Globe}
          title="No ancestry results yet."
          description="Run the annotation pipeline to generate ancestry results."
        />
      )}

      {/* Main content */}
      {!isLoading && !hasError && findingsQuery.data && (
        <>
          {/* Ancestry Result Summary */}
          <section aria-label="Ancestry inference summary" className="mb-8">
            <AncestryResultCard finding={findingsQuery.data} />
          </section>

          {/* Admixture Bar Chart */}
          <section aria-label="Admixture proportions" className="mb-8">
            <div className="rounded-lg border bg-card p-5">
              <h2 className="text-lg font-semibold mb-3">Admixture Proportions</h2>
              <p className="text-sm text-muted-foreground mb-4">
                Estimated ancestry proportions based on PCA distance to reference populations
              </p>
              <AdmixtureBar admixture_fractions={findingsQuery.data.admixture_fractions} />
            </div>
          </section>

          {/* PCA Scatter Plot */}
          <section aria-label="PCA scatter plot">
            <div className="rounded-lg border bg-card p-5">
              <h2 className="text-lg font-semibold mb-3">PCA Projection</h2>
              <p className="text-sm text-muted-foreground mb-4">
                Your sample projected onto the reference panel PCA space (PC1 vs PC2)
              </p>
              {pcaQuery.isLoading && (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              )}
              {pcaQuery.isError && (
                <div className="text-sm text-destructive">
                  Failed to load PCA coordinates.
                </div>
              )}
              {pcaQuery.data && (
                <PCAScatter pcaData={pcaQuery.data} />
              )}
              {!pcaQuery.isLoading && !pcaQuery.isError && !pcaQuery.data && (
                <div className="text-sm text-muted-foreground text-center py-8">
                  PCA coordinates not available.
                </div>
              )}
            </div>
          </section>

          {/* Haplogroup Assignments (P3-34) */}
          <section aria-label="Haplogroup assignments" className="mt-8">
            {haplogroupQuery.isLoading && (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            )}
            {haplogroupQuery.isError && (
              <div className="text-sm text-destructive">
                Failed to load haplogroup data.
              </div>
            )}
            {haplogroupQuery.data && (
              <HaplogroupCard assignments={haplogroupQuery.data.assignments} />
            )}
          </section>
        </>
      )}
    </div>
  )
}
