/**
 * Genome Browser page (P2-16, P2-17).
 *
 * Full-page IGV.js browser with GRCh37 reference and default tracks:
 * RefSeq genes (built-in), ClinVar variants, user VCF, gnomAD AF,
 * ENCODE cCREs — all served from local API endpoints.
 *
 * Supports navigation via URL search params:
 *   ?locus=BRCA1  — jump to a gene/region
 *   ?sampleId=1   — load user variant track for the given sample
 */
import { useMemo } from "react"
import { useSearchParams } from "react-router-dom"
import { IgvBrowser } from "@/components/igv-browser"
import { buildDefaultTracks } from "@/components/igv-browser/tracks"

export default function GenomeBrowser() {
  const [searchParams] = useSearchParams()
  const locusParam = searchParams.get("locus") ?? "all"
  const sampleIdParam = searchParams.get("sampleId")
  const sampleId = sampleIdParam ? parseInt(sampleIdParam, 10) : undefined

  const tracks = useMemo(
    () => buildDefaultTracks(Number.isFinite(sampleId) ? sampleId : undefined),
    [sampleId],
  )

  return (
    <div className="flex flex-col h-[calc(100vh-40px)]">
      <div className="px-4 py-3 border-b border-border">
        <h1 className="text-xl font-semibold">Genome Browser</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Interactive genome visualization — GRCh37/hg19
        </p>
      </div>
      <div className="flex-1 overflow-auto p-4">
        <IgvBrowser
          locus={locusParam}
          tracks={tracks}
          className="rounded-md border border-border overflow-hidden"
          minHeight={600}
        />
      </div>
    </div>
  )
}
