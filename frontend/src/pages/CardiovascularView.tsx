/** Cardiovascular module page (P3-21).
 *
 * Single-tier layout:
 * - FH status card (prominent, from fh-status API)
 * - Monogenic variant cards (ClinVar P/LP from 16-gene panel)
 *   grouped by cardiovascular category (FH, Lipid, Channelopathy, Cardiomyopathy)
 *
 * Module-specific disclaimer shown at the top.
 *
 * PRD P3-21: Cardiovascular UI — FH status, cardiomyopathy/channelopathy variant list.
 */

import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { HeartPulse, Loader2, AlertCircle, ChevronDown, ChevronUp } from "lucide-react"
import { cn } from "@/lib/utils"
import { parseSampleId } from "@/lib/format"
import {
  useCardiovascularVariants,
  useFHStatus,
  useCardiovascularDisclaimer,
} from "@/api/cardiovascular"
import type { CardiovascularVariant } from "@/types/cardiovascular"
import VariantCard from "@/components/cardiovascular/VariantCard"
import FHStatusCard from "@/components/cardiovascular/FHStatusCard"
import VariantDetailPanel from "@/components/cardiovascular/VariantDetailPanel"

export default function CardiovascularView() {
  const [searchParams] = useSearchParams()
  const sampleId = parseSampleId(searchParams.get("sample_id"))

  const [selectedVariant, setSelectedVariant] = useState<CardiovascularVariant | null>(null)
  const [disclaimerExpanded, setDisclaimerExpanded] = useState(false)

  // Close detail panel on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && selectedVariant) {
        setSelectedVariant(null)
      }
    }
    document.addEventListener("keydown", handleEscape)
    return () => document.removeEventListener("keydown", handleEscape)
  }, [selectedVariant])

  const variantsQuery = useCardiovascularVariants(sampleId)
  const fhStatusQuery = useFHStatus(sampleId)
  const disclaimerQuery = useCardiovascularDisclaimer()

  // No sample selected
  if (sampleId == null) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">Cardiovascular</h1>
        <div className="rounded-lg border bg-card p-8 text-center">
          <HeartPulse className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground">
            Select a sample to view cardiovascular results.
          </p>
        </div>
      </div>
    )
  }

  const isLoading = variantsQuery.isLoading || fhStatusQuery.isLoading
  const hasError = variantsQuery.isError || fhStatusQuery.isError

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
          <HeartPulse className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Cardiovascular</h1>
          <p className="text-sm text-muted-foreground">
            Monogenic cardiac variants and familial hypercholesterolemia status
          </p>
        </div>
      </div>

      {/* Module disclaimer */}
      {disclaimerQuery.data && (
        <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-4 mb-6" data-testid="cardiovascular-disclaimer">
          <button
            type="button"
            className="flex items-center justify-between w-full text-left"
            onClick={() => setDisclaimerExpanded(!disclaimerExpanded)}
            aria-expanded={disclaimerExpanded}
          >
            <h2 className="text-sm font-semibold text-amber-800 dark:text-amber-300">
              {disclaimerQuery.data.title}
            </h2>
            {disclaimerExpanded ? (
              <ChevronUp className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
            ) : (
              <ChevronDown className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
            )}
          </button>
          {disclaimerExpanded && (
            <p className="text-sm text-amber-700 dark:text-amber-400 mt-3 whitespace-pre-line">
              {disclaimerQuery.data.text}
            </p>
          )}
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Error state */}
      {hasError && !isLoading && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-destructive mt-0.5 shrink-0" />
            <div>
              <p className="font-medium text-destructive">Failed to load cardiovascular data</p>
              <p className="text-sm text-muted-foreground mt-1">
                {variantsQuery.error instanceof Error
                  ? variantsQuery.error.message
                  : fhStatusQuery.error instanceof Error
                    ? fhStatusQuery.error.message
                    : "An unexpected error occurred."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Main content */}
      {!isLoading && !hasError && (
        <>
          {/* ── FH Status Card ── */}
          {fhStatusQuery.data && (
            <section aria-label="Familial hypercholesterolemia status" className="mb-8">
              <FHStatusCard fhStatus={fhStatusQuery.data} />
            </section>
          )}

          {/* ── Monogenic Variants ── */}
          <section aria-label="Cardiovascular monogenic variants">
            <h2 className="text-lg font-semibold mb-3">Monogenic Findings</h2>
            <p className="text-sm text-muted-foreground mb-4">
              Pathogenic and likely pathogenic variants in the 16-gene cardiovascular panel
            </p>

            {variantsQuery.data && variantsQuery.data.items.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {variantsQuery.data.items.map((variant) => (
                  <VariantCard
                    key={`${variant.gene_symbol}-${variant.rsid}`}
                    variant={variant}
                    onClick={() =>
                      setSelectedVariant(
                        selectedVariant?.rsid === variant.rsid &&
                          selectedVariant?.gene_symbol === variant.gene_symbol
                          ? null
                          : variant,
                      )
                    }
                    selected={
                      selectedVariant?.rsid === variant.rsid &&
                      selectedVariant?.gene_symbol === variant.gene_symbol
                    }
                  />
                ))}
              </div>
            ) : (
              <div className="rounded-lg border bg-card p-8 text-center">
                <HeartPulse className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
                <p className="text-muted-foreground">
                  No pathogenic or likely pathogenic variants found in the cardiovascular gene panel.
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  This does not eliminate cardiovascular risk. Consult a healthcare provider for comprehensive assessment.
                </p>
              </div>
            )}
          </section>
        </>
      )}

      {/* Variant detail slide-in panel */}
      {selectedVariant && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-30 bg-black/20"
            onClick={() => setSelectedVariant(null)}
            aria-hidden="true"
          />
          <VariantDetailPanel
            variant={selectedVariant}
            onClose={() => setSelectedVariant(null)}
          />
        </>
      )}
    </div>
  )
}
