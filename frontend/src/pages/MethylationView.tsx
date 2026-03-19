/** MTHFR & Methylation module page (P3-53).
 *
 * Displays a pathway flow diagram showing biochemical relationships,
 * per-pathway score bars with Elevated/Moderate/Standard levels, MTHFR
 * compound heterozygosity banner, and expandable Advanced View for
 * per-SNP details. No gauge charts — categorical display only.
 *
 * PRD E2E flow F22: Methylation page shows pathway flow diagram,
 * 5 pathway score bars, expandable Advanced View.
 */

import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import { FlaskConical, Loader2, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import { parseSampleId } from "@/lib/format"
import { useMethylationPathways } from "@/api/methylation"
import PathwayFlowDiagram from "@/components/methylation/PathwayFlowDiagram"
import PathwayScoreBar from "@/components/methylation/PathwayScoreBar"
import CompoundHetBanner from "@/components/methylation/CompoundHetBanner"
import PathwayDetailPanel from "@/components/methylation/PathwayDetailPanel"

export default function MethylationView() {
  const [searchParams] = useSearchParams()
  const sampleId = parseSampleId(searchParams.get("sample_id"))

  const [selectedPathway, setSelectedPathway] = useState<{
    id: string
    name: string
  } | null>(null)

  const pathwaysQuery = useMethylationPathways(sampleId)

  const handleSelectPathway = (pathwayId: string) => {
    if (selectedPathway?.id === pathwayId) {
      setSelectedPathway(null)
    } else {
      const pathway = pathwaysQuery.data?.items.find((p) => p.pathway_id === pathwayId)
      if (pathway) {
        setSelectedPathway({ id: pathway.pathway_id, name: pathway.pathway_name })
      }
    }
  }

  // No sample selected
  if (sampleId == null) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">MTHFR & Methylation</h1>
        <div className="rounded-lg border bg-card p-8 text-center">
          <FlaskConical className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground">
            Select a sample to view methylation pathway results.
          </p>
        </div>
      </div>
    )
  }

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
          <FlaskConical className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">MTHFR & Methylation</h1>
          <p className="text-sm text-muted-foreground">
            Five-pathway methylation analysis with additive scoring and MTHFR
            compound heterozygosity assessment
          </p>
        </div>
      </div>

      {/* Loading state */}
      {pathwaysQuery.isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Error state */}
      {pathwaysQuery.isError && !pathwaysQuery.isLoading && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-destructive mt-0.5 shrink-0" />
            <div>
              <p className="font-medium text-destructive">
                Failed to load methylation data
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {pathwaysQuery.error instanceof Error
                  ? pathwaysQuery.error.message
                  : "An unexpected error occurred."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Main content */}
      {!pathwaysQuery.isLoading && !pathwaysQuery.isError && (
        <>
          {pathwaysQuery.data && pathwaysQuery.data.items.length > 0 && (
            <>
              {/* Compound heterozygosity banner */}
              {pathwaysQuery.data.compound_het && (
                <div className="mb-6">
                  <CompoundHetBanner compoundHet={pathwaysQuery.data.compound_het} />
                </div>
              )}

              {/* Pathway flow diagram */}
              <section aria-label="Methylation pathway flow diagram" className="mb-8">
                <h2 className="text-lg font-semibold mb-3">Pathway Relationships</h2>
                <div className="rounded-lg border bg-card p-4">
                  <PathwayFlowDiagram
                    pathways={pathwaysQuery.data.items}
                    selectedPathwayId={selectedPathway?.id ?? null}
                    onSelectPathway={handleSelectPathway}
                  />
                </div>
              </section>

              {/* Per-pathway score bars */}
              <section aria-label="Methylation pathway results">
                <h2 className="text-lg font-semibold mb-3">Pathway Scores</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {pathwaysQuery.data.items.map((pathway) => (
                    <PathwayScoreBar
                      key={pathway.pathway_id}
                      pathway={pathway}
                      selected={selectedPathway?.id === pathway.pathway_id}
                      onClick={() => handleSelectPathway(pathway.pathway_id)}
                    />
                  ))}
                </div>
              </section>
            </>
          )}

          {/* Empty state */}
          {pathwaysQuery.data && pathwaysQuery.data.items.length === 0 && (
            <div className="rounded-lg border bg-card p-8 text-center">
              <FlaskConical className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground">
                No methylation results yet. Run annotation to generate pathway scores.
              </p>
            </div>
          )}
        </>
      )}

      {/* Pathway detail slide-in panel (Advanced View) */}
      {selectedPathway && sampleId && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-30 bg-black/20"
            onClick={() => setSelectedPathway(null)}
            aria-hidden="true"
          />
          <PathwayDetailPanel
            pathwayId={selectedPathway.id}
            pathwayName={selectedPathway.name}
            sampleId={sampleId}
            onClose={() => setSelectedPathway(null)}
          />
        </>
      )}
    </div>
  )
}
