/** Gene Fitness module page (P3-47).
 *
 * Displays four fitness pathway cards (Endurance, Power, Recovery & Injury,
 * Training Response) with categorical Elevated/Moderate/Standard scoring,
 * ACTN3/ACE highlight cards, and cross-pathway context findings.
 * Drill-down to individual SNPs and genotypes via slide-in panel.
 *
 * PRD E2E flow F19: Dashboard -> click Fitness card -> fitness page shows
 * 4 pathway cards -> ACTN3 highlight card visible.
 */

import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import { Dumbbell, Loader2, AlertCircle, ArrowRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { parseSampleId } from "@/lib/format"
import { useFitnessPathways } from "@/api/fitness"
import type { CrossContextItem } from "@/types/fitness"
import PathwayCard from "@/components/fitness/PathwayCard"
import PathwayDetailPanel from "@/components/fitness/PathwayDetailPanel"
import EvidenceStars from "@/components/ui/EvidenceStars"

export default function FitnessView() {
  const [searchParams] = useSearchParams()
  const sampleId = parseSampleId(searchParams.get("sample_id"))

  const [selectedPathway, setSelectedPathway] = useState<{
    id: string
    name: string
  } | null>(null)

  const pathwaysQuery = useFitnessPathways(sampleId)

  // No sample selected
  if (sampleId == null) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">Gene Fitness</h1>
        <div className="rounded-lg border bg-card p-8 text-center">
          <Dumbbell className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground">
            Select a sample to view fitness results.
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
          <Dumbbell className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Gene Fitness</h1>
          <p className="text-sm text-muted-foreground">
            Categorical pathway scoring for athletic and fitness traits based on your genotype
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
                Failed to load fitness data
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
          {/* Pathway cards */}
          {pathwaysQuery.data && pathwaysQuery.data.items.length > 0 && (
            <>
              <section aria-label="Fitness pathway results">
                <h2 className="text-lg font-semibold mb-3">Pathway Results</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                  {pathwaysQuery.data.items.map((pathway) => (
                    <PathwayCard
                      key={pathway.pathway_id}
                      pathway={pathway}
                      selected={selectedPathway?.id === pathway.pathway_id}
                      onClick={() =>
                        setSelectedPathway(
                          selectedPathway?.id === pathway.pathway_id
                            ? null
                            : { id: pathway.pathway_id, name: pathway.pathway_name },
                        )
                      }
                    />
                  ))}
                </div>
              </section>

              {/* Cross-pathway context */}
              {pathwaysQuery.data.cross_context.length > 0 && (
                <section className="mt-6" aria-label="Cross-pathway context">
                  <h2 className="text-lg font-semibold mb-3">Cross-Pathway Context</h2>
                  <div className="space-y-3">
                    {pathwaysQuery.data.cross_context.map((item: CrossContextItem) => (
                      <div
                        key={`${item.rsid}-${item.source_pathway}-${item.context_pathway}`}
                        className="rounded-lg border bg-card p-4"
                      >
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex items-center gap-2 text-sm">
                            <span className="font-mono font-medium">{item.gene}</span>
                            <span className="text-muted-foreground">({item.rsid})</span>
                            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                              {item.source_pathway}
                              <ArrowRight className="h-3 w-3" aria-hidden="true" />
                              {item.context_pathway}
                            </span>
                          </div>
                          <EvidenceStars level={item.evidence_level} />
                        </div>
                        <p className="text-sm text-muted-foreground">{item.finding_text}</p>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}

          {/* Empty state */}
          {pathwaysQuery.data && pathwaysQuery.data.items.length === 0 && (
            <div className="rounded-lg border bg-card p-8 text-center">
              <Dumbbell className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground">
                No fitness results yet. Run annotation to generate pathway scores.
              </p>
            </div>
          )}
        </>
      )}

      {/* Pathway detail slide-in panel */}
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
