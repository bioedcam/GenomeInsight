/**
 * Genome Browser page (P2-16).
 *
 * Full-page IGV.js browser with GRCh37 reference.
 * Supports navigation via URL search params (?locus=BRCA1).
 */
import { useSearchParams } from "react-router-dom"
import { IgvBrowser } from "@/components/igv-browser"

export default function GenomeBrowser() {
  const [searchParams] = useSearchParams()
  const locusParam = searchParams.get("locus") ?? "all"

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
          className="rounded-md border border-border overflow-hidden"
          minHeight={600}
        />
      </div>
    </div>
  )
}
